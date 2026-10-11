#!/usr/bin/env python3
"""
AceStream Launcher - Navegación por Categorías/Carpetas y Canales
Compatible con Linux y Windows.
"""
import curses
import subprocess
import time
import os
import sys
import urllib.request
import urllib.error
import json

# ── Ruta base del proyecto (compatible con PyInstaller y ejecución normal) ───
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ROOT_DIR = os.path.dirname(BASE_DIR)

IS_WINDOWS = os.name == 'nt'

CAT_META = {
    'la_liga': ('LA LIGA', 10),
    'hypermotion': ('LA LIGA HYPERMOTION', 20),
    'liga_de_campeones': ('LIGA DE CAMPEONES', 30),
    '1rfef': ('1a RFEF', 40),
    'formula_1': ('FORMULA 1', 50),
    'motor': ('MOTOR', 60),
    'futbol_int': ('FUTBOL INTERNACIONAL', 70),
    'deportes': ('DEPORTES', 80),
    'cadenas/dazn': ('CADENAS: DAZN', 90),
    'cadenas/movistar': ('CADENAS: MOVISTAR+', 100),
    'cadenas/movistar_deportes': ('CADENAS: M+ DEPORTES', 110),
    'cadenas/eurosport': ('CADENAS: EUROSPORT', 120),
    'cadenas/sport_tv': ('CADENAS: SPORT TV', 130),
}

# ── Carga canales organizados por categorías/carpetas ─────────────────────────
def load_categories():
    categories = []
    
    # 1. Escanear carpetas de canales/
    canales_dirs = [
        os.path.join(ROOT_DIR, "canales"),
        os.path.join(BASE_DIR, "canales")
    ]
    
    seen_keys = set()
    for c_dir in canales_dirs:
        if os.path.exists(c_dir) and os.path.isdir(c_dir):
            for root, _, files in os.walk(c_dir):
                for f in sorted(files):
                    if f.endswith(".txt"):
                        rel = os.path.relpath(root, c_dir).replace('\\', '/')
                        if rel in seen_keys:
                            continue
                        seen_keys.add(rel)
                        
                        fpath = os.path.join(root, f)
                        chs = []
                        with open(fpath, "r", encoding="utf-8") as fl:
                            for line in fl:
                                line = line.strip()
                                if line and not line.startswith("#"):
                                    parts = [p.strip() for p in line.split(",")]
                                    if len(parts) >= 3:
                                        cid = parts[2].replace("acestream://", "")
                                        chs.append({
                                            "name": parts[0],
                                            "lang": parts[1],
                                            "url": f"http://127.0.0.1:6878/ace/getstream?id={cid}",
                                            "category": rel
                                        })
                        if chs:
                            cat_name, order = CAT_META.get(rel, (rel.upper().replace("_", " "), 900))
                            categories.append({
                                "name": cat_name,
                                "key": rel,
                                "order": order,
                                "channels": chs
                            })

    # 2. Canales manuales sueltos en raíz
    manual_chs = []
    manual_files = [
        os.path.join(ROOT_DIR, "canales_manuales.txt"),
        os.path.join(BASE_DIR, "canales_manuales.txt"),
    ]
    for mf in manual_files:
        if os.path.exists(mf):
            with open(mf, "r", encoding="utf-8") as fl:
                for line in fl:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        parts = [p.strip() for p in line.split(",")]
                        if len(parts) >= 3:
                            cid = parts[2].replace("acestream://", "")
                            manual_chs.append({
                                "name": parts[0],
                                "lang": parts[1],
                                "url": f"http://127.0.0.1:6878/ace/getstream?id={cid}",
                                "category": "manuales"
                            })
            break
    if manual_chs:
        categories.append({
            "name": "CANALES MANUALES",
            "key": "manuales",
            "order": 5,
            "channels": manual_chs
        })

    categories.sort(key=lambda x: x["order"])
    return categories

# ── Colores por idioma ───────────────────────────────────────────────────────
LANG_COLORS = {"ES": 1, "EN": 2, "DE": 3, "PL": 4, "PT": 5, "RU": 6}

# ── Escritura segura (evita crash en esquina inferior derecha) ───────────────
def safe_addstr(stdscr, y, x, text, attr=0):
    h, w = stdscr.getmaxyx()
    if y < 0 or y >= h or x < 0 or x >= w:
        return
    max_len = w - x
    if max_len <= 0:
        return
    text = text[:max_len]
    try:
        if attr:
            stdscr.addstr(y, x, text, attr)
        else:
            stdscr.addstr(y, x, text)
    except curses.error:
        pass

def safe_hline(stdscr, y, x, ch, n):
    try:
        stdscr.hline(y, x, ch, n)
    except curses.error:
        pass

# ── API del motor AceStream ─────────────────────────────────────────────────
ACE_API = "http://127.0.0.1:6878"

def ace_api(path):
    """Llama a la API del motor AceStream y devuelve el JSON o None."""
    try:
        with urllib.request.urlopen(f"{ACE_API}{path}", timeout=5) as r:
            return json.loads(r.read())
    except Exception:
        return None

# ── Arranque del motor ───────────────────────────────────────────────────────
def ensure_engine(stdscr, h, w, msg_y):
    """Arranca el motor de AceStream (Docker en Linux, app nativa en Windows)."""
    safe_addstr(stdscr, msg_y, 2, "⏳ Verificando motor AceStream...".ljust(w - 4),
                curses.color_pair(7) | curses.A_BOLD)
    stdscr.refresh()

    if IS_WINDOWS:
        safe_addstr(stdscr, msg_y, 2,
                    "Modo Windows: comprobando AceStream Engine...".ljust(w - 4),
                    curses.color_pair(2) | curses.A_BOLD)
        stdscr.refresh()
        for attempt in range(10):
            if ace_api("/webui/api/service?method=get_version"):
                safe_addstr(stdscr, msg_y, 2,
                            "AceStream Engine conectado correctamente".ljust(w - 4),
                            curses.color_pair(2) | curses.A_BOLD)
                stdscr.refresh()
                time.sleep(0.5)
                return
            dots = "." * (attempt % 4 + 1)
            safe_addstr(stdscr, msg_y, 2,
                        f"Buscando AceStream Engine{dots}".ljust(w - 4),
                        curses.color_pair(7) | curses.A_BOLD)
            stdscr.refresh()
            time.sleep(1)
        safe_addstr(stdscr, msg_y, 2,
                    "! No se encontro AceStream. Abrelo manualmente.".ljust(w - 4),
                    curses.color_pair(7) | curses.A_BOLD)
        stdscr.refresh()
        time.sleep(2)
        return

    # ── Linux: gestionar contenedores Docker ──
    res_tor = subprocess.run(
        ["sudo", "-S", "docker", "inspect", "-f", "{{.State.Running}}", "tor-proxy"],
        input="s\n", capture_output=True, text=True
    )
    if res_tor.stdout.strip() != "true":
        safe_addstr(stdscr, msg_y, 2,
                    "Arrancando Proxy antibloqueo (Tor)...".ljust(w - 4),
                    curses.color_pair(7) | curses.A_BOLD)
        stdscr.refresh()
        subprocess.run(
            ["sudo", "-S", "docker", "run", "-d",
             "--name", "tor-proxy", "--network", "host",
             "--restart", "unless-stopped",
             "dockage/tor-privoxy:latest"],
            input="s\n", capture_output=True, text=True
        )
        time.sleep(3)

    res_ace = subprocess.run(
        ["sudo", "-S", "docker", "inspect", "-f", "{{.State.Running}}", "acestream"],
        input="s\n", capture_output=True, text=True
    )
    if res_ace.stdout.strip() != "true":
        safe_addstr(stdscr, msg_y, 2,
                    "Arrancando motor AceStream (Docker)...".ljust(w - 4),
                    curses.color_pair(7) | curses.A_BOLD)
        stdscr.refresh()
        subprocess.run(
            ["sudo", "-S", "docker", "run", "-d",
             "--name", "acestream", "--network", "host",
             "--restart", "unless-stopped",
             "-e", "HTTP_PROXY=http://127.0.0.1:8118",
             "-e", "HTTPS_PROXY=http://127.0.0.1:8118",
             "-e", "NO_PROXY=127.0.0.1,localhost,192.168.0.0/16,10.0.0.0/8,172.16.0.0/12",
             "jopsis/acestream:latest"],
            input="s\n", capture_output=True, text=True
        )
        for attempt in range(15):
            if ace_api("/webui/api/service?method=get_version"):
                break
            dots = "." * (attempt % 4 + 1)
            safe_addstr(stdscr, msg_y, 2,
                        f"Esperando motor{dots}".ljust(w - 4),
                        curses.color_pair(7) | curses.A_BOLD)
            stdscr.refresh()
            time.sleep(1)

    safe_addstr(stdscr, msg_y, 2,
                "Motor AceStream + Red Antibloqueo listos".ljust(w - 4),
                curses.color_pair(2) | curses.A_BOLD)
    stdscr.refresh()
    time.sleep(0.5)

# ── Iniciar stream y abrir reproductor ───────────────────────────────────────
def start_stream(content_id, ch_name, stdscr, status_y, w):
    import threading

    spinner = ['|', '/', '-', '\\']
    spin_i = 0

    safe_addstr(stdscr, status_y, 2,
                f"{spinner[0]} Despertando motor: {ch_name[:w - 30]}...".ljust(w - 4),
                curses.color_pair(7) | curses.A_BOLD)
    stdscr.refresh()

    play_url = f"{ACE_API}/ace/getstream?id={content_id}"
    engine_ready = False

    def trigger_engine():
        nonlocal engine_ready
        try:
            req = urllib.request.Request(play_url, headers={'User-Agent': 'VLC/3.0.0'})
            with urllib.request.urlopen(req, timeout=30) as r:
                engine_ready = True
        except Exception:
            pass

    threading.Thread(target=trigger_engine, daemon=True).start()
    time.sleep(1)

    peers = 0
    MAX_WAIT = 25

    for i in range(MAX_WAIT * 2):
        spin_i = (spin_i + 1) % len(spinner)
        stat = ace_api(f"/ace/stat/{content_id}")
        if stat and stat.get("response"):
            peers = stat["response"].get("peers", 0)
            status = stat["response"].get("status", "")
            if peers > 0 and status in ("dl", "prebuf", "buf"):
                break
                
        if engine_ready:
            break
            
        elapsed = i * 0.5
        msg = f"{spinner[spin_i]} Conectando a la red... {peers} peers | {elapsed:.0f}s"
        safe_addstr(stdscr, status_y, 2, msg.ljust(w - 4),
                    curses.color_pair(3) | curses.A_BOLD)
        stdscr.refresh()
        time.sleep(0.5)

    if peers == 0:
        safe_addstr(stdscr, status_y, 2,
                    "! Sin peers - abriendo reproductor igualmente...".ljust(w - 4),
                    curses.color_pair(7))
    else:
        player_name = "VLC" if IS_WINDOWS else "mpv"
        safe_addstr(stdscr, status_y, 2,
                    f"{peers} peers - abriendo {player_name}".ljust(w - 4),
                    curses.color_pair(2) | curses.A_BOLD)
    stdscr.refresh()
    time.sleep(0.5)

    # ── Lanzar el reproductor ──
    if IS_WINDOWS:
        vlc_paths = [
            r"C:\Program Files\VideoLAN\VLC\vlc.exe",
            r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
        ]
        vlc_exe = "vlc"
        for p in vlc_paths:
            if os.path.exists(p):
                vlc_exe = p
                break
        try:
            subprocess.Popen(
                [vlc_exe, "--qt-minimal-view", "--meta-title", ch_name, "--network-caching=5000", play_url],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except FileNotFoundError:
            safe_addstr(stdscr, status_y, 2,
                        "ERROR: VLC no encontrado. Instalalo desde videolan.org".ljust(w - 4),
                        curses.color_pair(1) | curses.A_BOLD)
            stdscr.refresh()
            time.sleep(3)
    else:
        subprocess.Popen(
            ["mpv", "--quiet", "--no-terminal", "--force-window=immediate",
             "--cache=yes", "--cache-secs=30",
             "--demuxer-readahead-secs=20",
             "--demuxer-max-bytes=500M",
             "--demuxer-max-back-bytes=100M",
             "--demuxer-lavf-o=reconnect=1,reconnect_streamed=1,reconnect_delay_max=5",
             "--hwdec=auto", "--vo=gpu",
             "--deinterlace=auto",
             "--title=" + ch_name, play_url],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    return peers

# ── Interfaz Curses ──────────────────────────────────────────────────────────
def draw_ui(stdscr, current_cat, items, selected, scroll, search, search_mode, status):
    h, w = stdscr.getmaxyx()
    if h < 8 or w < 40:
        stdscr.erase()
        safe_addstr(stdscr, 0, 0, "Terminal demasiado pequena")
        stdscr.refresh()
        return
    stdscr.erase()

    # ── Cabecera ──
    title = f" FURBO - ACESTREAM TV "
    safe_addstr(stdscr, 0, 0, title.center(w - 1), curses.color_pair(8) | curses.A_BOLD)
    
    if current_cat is None:
        nav = " Selecciona una CARPETA/COMPETICION (ENTER: Entrar | /: Buscar canal | q: Salir) "
    else:
        nav = f" [CARPETA: {current_cat['name']}]  (BACKSPACE/ESC: Volver a carpetas | ENTER: Reproducir) "
    safe_addstr(stdscr, 1, 0, nav.center(w - 1), curses.color_pair(9))

    # ── Separador ──
    safe_hline(stdscr, 2, 0, curses.ACS_HLINE, w - 1)
    if search_mode:
        hint = f" >> Buscar canal: {search}_ "
        safe_addstr(stdscr, 2, 2, hint, curses.color_pair(3) | curses.A_BOLD)
    elif search:
        hint = f" >> Filtrado: '{search}' ({len(items)} resultados) "
        safe_addstr(stdscr, 2, 2, hint, curses.color_pair(4))

    # ── Lista principal ──
    list_top = 3
    list_bot = h - 3
    list_h = list_bot - list_top
    if list_h <= 0:
        return

    for i in range(list_h):
        idx = scroll + i
        y = list_top + i
        if idx >= len(items):
            break
        item = items[idx]
        is_sel = (idx == selected)

        if current_cat is None and not search:
            # Vista de CARPETAS
            cat_name = item["name"]
            count = f"({len(item['channels'])} canales)"
            name_w = w - len(count) - 8
            if name_w < 1: name_w = 1
            line_name = cat_name[:name_w].ljust(name_w)

            if is_sel:
                line = f" > [DIR]  {line_name} {count} "
                safe_addstr(stdscr, y, 0, line[:w - 1].ljust(w - 1), curses.color_pair(10) | curses.A_BOLD)
            else:
                safe_addstr(stdscr, y, 0, f"   [DIR]  {line_name} ", curses.color_pair(0) | curses.A_BOLD)
                safe_addstr(stdscr, y, 10 + len(line_name), count, curses.color_pair(4))
        else:
            # Vista de CANALES
            ch = item
            lang = ch.get("lang", "ES")
            col = LANG_COLORS.get(lang, 7)
            lang_tag = f"[{lang}]"
            name_w = w - len(lang_tag) - 6
            if name_w < 1: name_w = 1
            name = ch["name"][:name_w].ljust(name_w)

            if is_sel:
                line = f" > {name} {lang_tag} "
                safe_addstr(stdscr, y, 0, line[:w - 1].ljust(w - 1), curses.color_pair(10) | curses.A_BOLD)
            else:
                safe_addstr(stdscr, y, 0, f"   {name} ", curses.color_pair(0))
                safe_addstr(stdscr, y, 4 + len(name), lang_tag, curses.color_pair(col))

    # ── Scrollbar ──
    if len(items) > list_h and list_h > 0:
        bar_h = max(1, list_h * list_h // len(items))
        bar_pos = int(scroll / max(1, len(items) - list_h) * (list_h - bar_h))
        for r in range(list_h):
            ch_char = curses.ACS_CKBOARD if bar_pos <= r < bar_pos + bar_h else ord(' ')
            try:
                stdscr.addch(list_top + r, w - 1, ch_char, curses.color_pair(9))
            except curses.error:
                pass

    # ── Separador inferior y status ──
    safe_hline(stdscr, h - 3, 0, curses.ACS_HLINE, w - 1)
    safe_addstr(stdscr, h - 2, 0, f" {status}"[:w - 1].ljust(w - 1), curses.color_pair(9))
    controls_bot = "  ENTER: Seleccionar | ESC/Retroceso: Volver | /: Buscar canal | PgUp/PgDn: Pagina"
    safe_addstr(stdscr, h - 1, 0, controls_bot[:w - 1], curses.color_pair(9) | curses.A_DIM)
    stdscr.refresh()

# ── Main ─────────────────────────────────────────────────────────────────────
def main(stdscr):
    curses.start_color()
    try:
        curses.use_default_colors()
        default_bg = -1
    except curses.error:
        default_bg = curses.COLOR_BLACK

    curses.curs_set(0)
    stdscr.keypad(True)
    stdscr.timeout(100)

    curses.init_pair(1,  curses.COLOR_RED,     default_bg)   # ES
    curses.init_pair(2,  curses.COLOR_GREEN,   default_bg)   # EN / OK
    curses.init_pair(3,  curses.COLOR_YELLOW,  default_bg)   # DE / search
    curses.init_pair(4,  curses.COLOR_CYAN,    default_bg)   # PL / count
    curses.init_pair(5,  curses.COLOR_MAGENTA, default_bg)   # PT
    curses.init_pair(6,  curses.COLOR_RED,     default_bg)   # RU
    curses.init_pair(7,  curses.COLOR_YELLOW,  default_bg)   # Info/warning
    curses.init_pair(8,  curses.COLOR_BLACK,   curses.COLOR_CYAN)   # Header
    curses.init_pair(9,  curses.COLOR_WHITE,   curses.COLOR_BLUE)   # Footer/bar
    curses.init_pair(10, curses.COLOR_BLACK,   curses.COLOR_GREEN)  # Selected

    categories = load_categories()
    if not categories:
        stdscr.erase()
        safe_addstr(stdscr, 2, 2, "ERROR: No se encontraron canales en la carpeta canales/")
        safe_addstr(stdscr, 4, 2, "Pulsa una tecla para salir...")
        stdscr.refresh()
        stdscr.timeout(-1)
        stdscr.getch()
        return

    # Aplanar todos los canales para búsqueda global
    all_channels_flat = []
    for cat in categories:
        all_channels_flat.extend(cat["channels"])

    current_cat = None
    items = categories[:]
    selected = 0
    scroll = 0
    search = ""
    search_mode = False
    
    total_chs = len(all_channels_flat)
    status = f"{len(categories)} carpetas ({total_chs} canales)  -  ENTER para abrir carpeta"

    h, w = stdscr.getmaxyx()
    ensure_engine(stdscr, h, w, h // 2)

    while True:
        h, w = stdscr.getmaxyx()
        list_h = h - 6
        if list_h < 1:
            list_h = 1

        draw_ui(stdscr, current_cat, items, selected, scroll, search, search_mode, status)

        key = stdscr.getch()
        if key == -1:
            continue

        # ── Modo búsqueda global ──
        if search_mode:
            if key == 27: # ESC cancelar
                search_mode = False
                search = ""
                if current_cat is None:
                    items = categories[:]
                    status = f"{len(categories)} carpetas ({total_chs} canales)"
                else:
                    items = current_cat["channels"][:]
                    status = f"{current_cat['name']} - {len(items)} canales"
                selected = 0
                scroll = 0
            elif key in (curses.KEY_BACKSPACE, 127, 8):
                search = search[:-1]
                if search:
                    items = [c for c in all_channels_flat if search.lower() in c["name"].lower()]
                else:
                    items = categories[:] if current_cat is None else current_cat["channels"][:]
                selected = 0
                scroll = 0
            elif key in (10, 13): # ENTER fija búsqueda
                search_mode = False
                status = f"'{search}' - {len(items)} resultado(s)"
            elif 32 <= key <= 126:
                search += chr(key)
                items = [c for c in all_channels_flat if search.lower() in c["name"].lower()]
                selected = 0
                scroll = 0
            continue

        # ── Modo normal ──
        if key in (ord('q'), ord('Q')):
            break

        elif key == ord('/'):
            search_mode = True
            search = ""
            current_cat = None # Buscar sobre todos los canales

        elif key in (27, curses.KEY_BACKSPACE, 127, 8):
            # Salir de carpeta o limpiar búsqueda
            if search:
                search = ""
                items = categories[:] if current_cat is None else current_cat["channels"][:]
                selected = 0
                scroll = 0
                status = f"{len(items)} elementos"
            elif current_cat is not None:
                current_cat = None
                items = categories[:]
                selected = 0
                scroll = 0
                status = f"{len(categories)} carpetas  -  ENTER para abrir"

        elif key == curses.KEY_UP:
            if selected > 0:
                selected -= 1
                if selected < scroll:
                    scroll = selected

        elif key == curses.KEY_DOWN:
            if items and selected < len(items) - 1:
                selected += 1
                if selected >= scroll + list_h:
                    scroll = selected - list_h + 1

        elif key == curses.KEY_PPAGE:
            selected = max(0, selected - list_h)
            scroll = max(0, scroll - list_h)

        elif key == curses.KEY_NPAGE:
            if items:
                selected = min(len(items) - 1, selected + list_h)
                if selected >= scroll + list_h:
                    scroll = selected - list_h + 1

        elif key in (10, 13) and items: # ENTER
            if current_cat is None and not search:
                # Entrar a la carpeta seleccionada
                current_cat = items[selected]
                items = current_cat["channels"][:]
                selected = 0
                scroll = 0
                status = f"Carpeta: {current_cat['name']} ({len(items)} canales)  -  ENTER para reproducir"
            else:
                # Reproducir canal
                ch = items[selected]
                ensure_engine(stdscr, h, w, h // 2)
                url = ch["url"]
                cid = url.split("id=")[-1].split("&")[0] if "id=" in url else ""
                peers = start_stream(cid, ch["name"], stdscr, h - 4, w)
                p_str = f"{peers} peers" if peers else "sin peers"
                status = f">  {ch['name']} [{ch['lang']}] - {p_str}"

        elif key == curses.KEY_RESIZE:
            try:
                curses.resizeterm(*stdscr.getmaxyx())
            except Exception:
                pass

if __name__ == "__main__":
    curses.wrapper(main)
