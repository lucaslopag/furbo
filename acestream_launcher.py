#!/usr/bin/env python3
"""
AceStream Launcher - Selecciona canal con flechas y lo abre en el reproductor
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

IS_WINDOWS = os.name == 'nt'

# ── Carga canales desde el .ods ──────────────────────────────────────────────
def load_channels():
    try:
        import odf.opendocument as od
        import odf.table as ot
        import odf.text as otext

        def cell_text(cell):
            """Extrae todo el texto de una celda ODS, incluyendo hyperlinks."""
            parts = []
            for p in cell.getElementsByType(otext.P):
                fragments = []
                def extract(node):
                    if hasattr(node, 'data'):
                        fragments.append(node.data)
                    for child in node.childNodes:
                        extract(child)
                for node in p.childNodes:
                    extract(node)
                parts.append("".join(fragments))
            return " ".join(parts).strip()

        ods_path = os.path.join(BASE_DIR, "Acestream_Links.ods")
        txt_path = os.path.join(BASE_DIR, "mis_canales.txt")

        channels = []

        # Cargar de mis_canales.txt si existe
        if os.path.exists(txt_path):
            with open(txt_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip() or line.startswith("#"):
                        continue
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 3:
                        name = parts[0]
                        lang = parts[1]
                        raw_url = parts[2]
                        
                        cid = raw_url.replace("acestream://", "")
                        url = f"http://127.0.0.1:6878/ace/getstream?id={cid}"
                        channels.append({"name": name, "lang": lang, "url": url})

        if not os.path.exists(ods_path):
            return channels

        doc = od.load(ods_path)
        for sheet in doc.spreadsheet.getElementsByType(ot.Table):
            for i, row in enumerate(sheet.getElementsByType(ot.TableRow)):
                if i == 0:
                    continue
                cols = [cell_text(c) for c in row.getElementsByType(ot.TableCell)]
                while len(cols) < 6:
                    cols.append("")
                name = cols[0].strip()
                lang = cols[1].strip()
                url = ""
                for c in cols:
                    c = c.strip()
                    if c.startswith("http://127.0.0.1:6878"):
                        url = c
                        break
                    elif c.startswith("acestream://"):
                        cid = c.replace("acestream://", "")
                        url = f"http://127.0.0.1:6878/ace/getstream?id={cid}"
                        break
                if url and name:
                    channels.append({"name": name, "lang": lang, "url": url})
        return channels
    except Exception:
        # Escribir error a un log para poder depurar
        import traceback
        log_path = os.path.join(BASE_DIR, "acestream_error.log")
        try:
            with open(log_path, "w") as f:
                traceback.print_exc(file=f)
        except Exception:
            pass
        return []

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
        # En Windows, AceStream corre como app nativa (bandeja del sistema)
        safe_addstr(stdscr, msg_y, 2,
                    "Modo Windows: comprobando AceStream Engine...".ljust(w - 4),
                    curses.color_pair(2) | curses.A_BOLD)
        stdscr.refresh()
        for attempt in range(10):
            if ace_api("/webui/api/service?method=get_version"):
                safe_addstr(stdscr, msg_y, 2,
                            "Motor AceStream detectado".ljust(w - 4),
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
    # 1. Tor Proxy (antibloqueo de ISP)
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

    # 2. Motor AceStream
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
    """
    1) Lanza un hilo en segundo plano que pide el stream para despertar al motor
    2) Espera a que haya peers sondendo /ace/stat/
    3) Lanza el reproductor
    """
    import threading

    spinner = ['|', '/', '-', '\\']
    spin_i = 0

    safe_addstr(stdscr, status_y, 2,
                f"{spinner[0]} Despertando motor: {ch_name[:w - 30]}...".ljust(w - 4),
                curses.color_pair(7) | curses.A_BOLD)
    stdscr.refresh()

    play_url = f"{ACE_API}/ace/getstream?id={content_id}"

    engine_ready = False

    # Hilo para forzar a AceStream a empezar a buscar
    def trigger_engine():
        nonlocal engine_ready
        try:
            req = urllib.request.Request(play_url, headers={'User-Agent': 'VLC/3.0.0'})
            # urlopen se bloquea hasta que AceStream termina el pre-buffering
            with urllib.request.urlopen(req, timeout=30) as r:
                engine_ready = True
        except Exception:
            pass

    threading.Thread(target=trigger_engine, daemon=True).start()
    time.sleep(1) # Darle un segundito al motor para reaccionar

    # Sondear peers
    peers = 0
    MAX_WAIT = 30  # Esperar hasta 30 segs

    for i in range(MAX_WAIT * 2):
        spin_i = (spin_i + 1) % len(spinner)
        stat = ace_api(f"/ace/stat/{content_id}")
        if stat and stat.get("response"):
            peers = stat["response"].get("peers", 0)
            status = stat["response"].get("status", "")
            if peers > 0 and status in ("dl", "prebuf", "buf"):
                break
                
        # Si el hilo de urllib consiguio respuesta, el stream ya esta listo
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
                    "! Sin peers - abriendo reproductor igualmente (puede fallar)".ljust(w - 4),
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
             "--cache=yes", "--demuxer-max-bytes=1000M",
             "--demuxer-max-back-bytes=200M",
             "--hwdec=auto", "--vo=gpu", "--profile=gpu-hq",
             "--deinterlace=auto",
             "--title=" + ch_name, play_url],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    return peers

# ── UI ───────────────────────────────────────────────────────────────────────
def draw_ui(stdscr, channels, selected, scroll, search, search_mode, status):
    h, w = stdscr.getmaxyx()
    if h < 8 or w < 40:
        stdscr.erase()
        safe_addstr(stdscr, 0, 0, "Terminal demasiado pequena")
        stdscr.refresh()
        return
    stdscr.erase()

    # ── Cabecera ──
    title = " ACESTREAM LAUNCHER "
    safe_addstr(stdscr, 0, 0, title.center(w - 1), curses.color_pair(8) | curses.A_BOLD)
    controls = " Flechas: Mover | ENTER: Reproducir | /: Buscar | q: Salir "
    safe_addstr(stdscr, 1, 0, controls.center(w - 1), curses.color_pair(9))

    # ── Separador ──
    safe_hline(stdscr, 2, 0, curses.ACS_HLINE, w - 1)
    if search_mode:
        hint = f" >> {search}_ "
        safe_addstr(stdscr, 2, 2, hint, curses.color_pair(3) | curses.A_BOLD)
    elif search:
        hint = f" >> '{search}' - {len(channels)} resultado(s) "
        safe_addstr(stdscr, 2, 2, hint, curses.color_pair(4))

    # ── Lista de canales ──
    list_top = 3
    list_bot = h - 3
    list_h = list_bot - list_top
    if list_h <= 0:
        return

    for i in range(list_h):
        idx = scroll + i
        y = list_top + i
        if idx >= len(channels):
            break
        ch = channels[idx]
        is_sel = (idx == selected)
        lang = ch["lang"]
        col = LANG_COLORS.get(lang, 7)
        lang_tag = f"[{lang}]"
        name_w = w - len(lang_tag) - 5
        if name_w < 1:
            name_w = 1
        name = ch["name"][:name_w].ljust(name_w)

        if is_sel:
            line = f" > {name} {lang_tag} "
            safe_addstr(stdscr, y, 0, line[:w - 1].ljust(w - 1),
                        curses.color_pair(10) | curses.A_BOLD)
        else:
            safe_addstr(stdscr, y, 0, f"   {name} ", curses.color_pair(0))
            safe_addstr(stdscr, y, 4 + len(name), lang_tag, curses.color_pair(col))

    # ── Scrollbar visual ──
    if len(channels) > list_h and list_h > 0:
        bar_h = max(1, list_h * list_h // len(channels))
        bar_pos = int(scroll / max(1, len(channels) - list_h) * (list_h - bar_h))
        for r in range(list_h):
            ch_char = curses.ACS_CKBOARD if bar_pos <= r < bar_pos + bar_h else ord(' ')
            try:
                stdscr.addch(list_top + r, w - 1, ch_char, curses.color_pair(9))
            except curses.error:
                pass

    # ── Separador inferior ──
    safe_hline(stdscr, h - 3, 0, curses.ACS_HLINE, w - 1)

    # ── Barra de estado ──
    safe_addstr(stdscr, h - 2, 0, f" {status}"[:w - 1].ljust(w - 1),
                curses.color_pair(9))

    # ── Controles ──
    controls_bot = "  ESC: Limpiar busqueda | PgUp/PgDn: Pagina"
    safe_addstr(stdscr, h - 1, 0, controls_bot[:w - 1], curses.color_pair(9) | curses.A_DIM)

    stdscr.refresh()

# ── Main ─────────────────────────────────────────────────────────────────────
def main(stdscr):
    curses.start_color()
    try:
        curses.use_default_colors()
        default_bg = -1
    except curses.error:
        # Windows curses no soporta use_default_colors; usar negro como fondo
        default_bg = curses.COLOR_BLACK

    curses.curs_set(0)
    stdscr.keypad(True)
    stdscr.timeout(100)

    curses.init_pair(1,  curses.COLOR_RED,     default_bg)   # ES
    curses.init_pair(2,  curses.COLOR_GREEN,   default_bg)   # EN / OK
    curses.init_pair(3,  curses.COLOR_YELLOW,  default_bg)   # DE / search
    curses.init_pair(4,  curses.COLOR_CYAN,    default_bg)   # PL / search result
    curses.init_pair(5,  curses.COLOR_MAGENTA, default_bg)   # PT
    curses.init_pair(6,  curses.COLOR_RED,     default_bg)   # RU
    curses.init_pair(7,  curses.COLOR_YELLOW,  default_bg)   # Info/warning
    curses.init_pair(8,  curses.COLOR_BLACK,   curses.COLOR_CYAN)   # Header
    curses.init_pair(9,  curses.COLOR_WHITE,   curses.COLOR_BLUE)   # Footer/bar
    curses.init_pair(10, curses.COLOR_BLACK,   curses.COLOR_GREEN)  # Selected

    all_channels = load_channels()
    if not all_channels:
        stdscr.erase()
        safe_addstr(stdscr, 2, 2, "ERROR: No se cargaron canales desde Acestream_Links.ods")
        safe_addstr(stdscr, 3, 2, f"Directorio: {BASE_DIR}")
        safe_addstr(stdscr, 5, 2, "Pulsa una tecla para salir...")
        stdscr.refresh()
        stdscr.timeout(-1)
        stdscr.getch()
        return

    channels = all_channels[:]
    selected = 0
    scroll = 0
    search = ""
    search_mode = False
    status = f"{len(channels)} canales  -  ENTER para reproducir"

    h, w = stdscr.getmaxyx()
    ensure_engine(stdscr, h, w, h // 2)

    while True:
        h, w = stdscr.getmaxyx()
        list_h = h - 6
        if list_h < 1:
            list_h = 1

        draw_ui(stdscr, channels, selected, scroll, search, search_mode, status)

        key = stdscr.getch()
        if key == -1:
            continue

        # ── Modo busqueda ──
        if search_mode:
            if key == 27:
                search_mode = False
                search = ""
                channels = all_channels[:]
                selected = 0
                scroll = 0
                status = f"{len(all_channels)} canales"
            elif key in (curses.KEY_BACKSPACE, 127, 8):
                search = search[:-1]
                if search:
                    channels = [c for c in all_channels
                                if search.lower() in c["name"].lower()]
                else:
                    channels = all_channels[:]
                selected = 0
                scroll = 0
            elif key in (10, 13):   # ENTER (10 en Linux, 13 en Windows)
                search_mode = False
                status = f"'{search}' - {len(channels)} resultado(s)"
            elif 32 <= key <= 126:
                search += chr(key)
                channels = [c for c in all_channels
                            if search.lower() in c["name"].lower()]
                selected = 0
                scroll = 0
            continue

        # ── Modo normal ──
        if key in (ord('q'), ord('Q')):
            break
        elif key in (ord('n'), ord('N'), ord('+')):
            curses.flushinp()
            stdscr.timeout(-1)  # Desactivar timeout temporalmente para getstr
            curses.echo()
            curses.curs_set(1)
            stdscr.erase()
            safe_addstr(stdscr, 2, 2, "=== AÑADIR NUEVO CANAL ===", curses.color_pair(8) | curses.A_BOLD)
            
            safe_addstr(stdscr, 4, 2, "Nombre del canal: ")
            stdscr.refresh()
            new_name = stdscr.getstr(4, 20, 50).decode('utf-8', errors='ignore').strip()
            
            safe_addstr(stdscr, 5, 2, "Idioma (ej. ES, EN): ")
            stdscr.refresh()
            new_lang = stdscr.getstr(5, 23, 10).decode('utf-8', errors='ignore').strip().upper()
            if not new_lang: new_lang = "ES"

            safe_addstr(stdscr, 6, 2, "ID de AceStream: ")
            stdscr.refresh()
            new_url = stdscr.getstr(6, 19, 100).decode('utf-8', errors='ignore').strip()

            curses.noecho()
            curses.curs_set(0)

            if new_name and new_url:
                txt_path = os.path.join(BASE_DIR, "mis_canales.txt")
                with open(txt_path, "a", encoding="utf-8") as f:
                    f.write(f"{new_name},{new_lang},{new_url}\n")
                safe_addstr(stdscr, 8, 2, "[OK] Canal añadido correctamente a mis_canales.txt!", curses.color_pair(2) | curses.A_BOLD)
                # Recargar canales
                all_channels = load_channels()
                channels = all_channels[:]
                status = f"{len(all_channels)} canales actualizados"
            else:
                safe_addstr(stdscr, 8, 2, "[!] Cancelado: Faltan datos.", curses.color_pair(1) | curses.A_BOLD)
            
            stdscr.refresh()
            time.sleep(2)
            stdscr.timeout(100)  # Restaurar timeout
            
        elif key == 27:   # ESC limpia busqueda o sale
            if search:
                search = ""
                channels = all_channels[:]
                selected = 0
                scroll = 0
                status = f"{len(all_channels)} canales"
            else:
                break
        elif key == ord('/'):
            search_mode = True
            search = ""
        elif key == curses.KEY_UP:
            if selected > 0:
                selected -= 1
                if selected < scroll:
                    scroll = selected
        elif key == curses.KEY_DOWN:
            if channels and selected < len(channels) - 1:
                selected += 1
                if selected >= scroll + list_h:
                    scroll = selected - list_h + 1
        elif key == curses.KEY_PPAGE:
            selected = max(0, selected - list_h)
            scroll = max(0, scroll - list_h)
        elif key == curses.KEY_NPAGE:
            if channels:
                selected = min(len(channels) - 1, selected + list_h)
                if selected >= scroll + list_h:
                    scroll = selected - list_h + 1
        elif key == curses.KEY_HOME:
            selected = 0
            scroll = 0
        elif key == curses.KEY_END:
            if channels:
                selected = len(channels) - 1
                scroll = max(0, selected - list_h + 1)
        elif key in (10, 13) and channels:   # ENTER
            ch = channels[selected]
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
