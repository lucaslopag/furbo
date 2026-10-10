#!/usr/bin/env python3
"""
AceStream Launcher - Selecciona canal con flechas y lo abre en VLC
"""
import curses
import subprocess
import time
import os
import urllib.request
import urllib.error
import json
import threading

# ── Carga canales desde el .ods ──────────────────────────────────────────────
def load_channels():
    try:
        import odf.opendocument as od
        import odf.table as ot
        import odf.text as otext

        def cell_text(cell):
            parts = []
            for p in cell.getElementsByType(otext.P):
                s = ""
                for node in p.childNodes:
                    if hasattr(node, 'data'):
                        s += node.data
                parts.append(s)
        import sys
        
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            
        ods_path = os.path.join(base_dir, "Acestream_Links.ods")
        
        if not os.path.exists(ods_path):
            return []
            
        doc = od.load(ods_path)
        channels = []
        for sheet in doc.spreadsheet.getElementsByType(ot.Table):
            for i, row in enumerate(sheet.getElementsByType(ot.TableRow)):
                if i == 0:
                    continue
                cols = [cell_text(c) for c in row.getElementsByType(ot.TableCell)]
                while len(cols) < 6:
                    cols.append("")
                name = cols[0]
                lang = cols[1]
                url = ""
                for c in cols:
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
    except Exception as e:
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
    # En la última celda de la pantalla curses falla, usamos insch
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

# ── Docker ───────────────────────────────────────────────────────────────────
ACE_API = "http://127.0.0.1:6878"

def ace_api(path):
    """Llama a la API del motor AceStream y devuelve el JSON o None."""
    try:
        with urllib.request.urlopen(f"{ACE_API}{path}", timeout=5) as r:
            return json.loads(r.read())
    except Exception:
        return None

def ensure_docker(stdscr, h, w, msg_y):
    safe_addstr(stdscr, msg_y, 2, "⏳ Verificando Proxy Tor y Docker AceStream...".ljust(w-4), curses.color_pair(7) | curses.A_BOLD)
    stdscr.refresh()
    
    # 1. Tor Proxy
    res_tor = subprocess.run(["sudo", "-S", "docker", "inspect", "-f", "{{.State.Running}}", "tor-proxy"], input="s\n", capture_output=True, text=True)
    if res_tor.stdout.strip() != "true":
        safe_addstr(stdscr, msg_y, 2, "🚀 Arrancando Proxy antibloqueo (Tor)...".ljust(w-4), curses.color_pair(7) | curses.A_BOLD)
        stdscr.refresh()
        subprocess.run(["sudo", "-S", "docker", "run", "-d", "--name", "tor-proxy", "--network", "host", "--restart", "unless-stopped", "dockage/tor-privoxy:latest"], input="s\n", capture_output=True, text=True)
        time.sleep(3) # Darle unos segundos a Tor para conectar a los nodos

    # 2. AceStream
    res_ace = subprocess.run(["sudo", "-S", "docker", "inspect", "-f", "{{.State.Running}}", "acestream"], input="s\n", capture_output=True, text=True)
    if res_ace.stdout.strip() != "true":
        safe_addstr(stdscr, msg_y, 2, "🚀 Arrancando motor AceStream...".ljust(w-4), curses.color_pair(7) | curses.A_BOLD)
        stdscr.refresh()
        subprocess.run(
            ["sudo", "-S", "docker", "run", "-d",
             "--name", "acestream", "--network", "host", "--restart", "unless-stopped",
             "-e", "HTTP_PROXY=http://127.0.0.1:8118", "-e", "HTTPS_PROXY=http://127.0.0.1:8118",
             "-e", "NO_PROXY=127.0.0.1,localhost,192.168.0.0/16,10.0.0.0/8,172.16.0.0/12",
             "jopsis/acestream:latest"],
            input="s\n", capture_output=True, text=True
        )
        # Esperar a que el motor esté listo
        for _ in range(15):
            if ace_api("/webui/api/service?method=get_version"):
                break
            safe_addstr(stdscr, msg_y, 2, f"⏳ Esperando motor{'.'*(_ % 4)}  ".ljust(w-4), curses.color_pair(7) | curses.A_BOLD)
            stdscr.refresh()
            time.sleep(1)
            
    safe_addstr(stdscr, msg_y, 2, "✅ Motor AceStream + Red Antibloqueo listos".ljust(w-4), curses.color_pair(2) | curses.A_BOLD)
    stdscr.refresh()
    time.sleep(0.5)

def start_stream_and_open_vlc(content_id, ch_name, stdscr, status_y, w):
    """
    1) Llama a la API para iniciar el stream
    2) Espera a que haya peers (hasta 30s)
    3) Lanza VLC con la URL de reproducción
    """
    spinner = ['⠋','⠙','⠹','⠸','⠼','⠴','⠦','⠧','⠇','⠏']
    spin_i  = 0

    # Iniciar stream via API
    api_start = f"/ace/getstream?id={content_id}&format=json"
    safe_addstr(stdscr, status_y, 2, f"{spinner[0]} Iniciando stream: {ch_name[:w-20]}...".ljust(w-4), curses.color_pair(7) | curses.A_BOLD)
    stdscr.refresh()

    play_url = f"{ACE_API}/ace/getstream?id={content_id}"

    # Sondear la API de estadísticas para detectar peers
    stat_url = f"/ace/stat/{content_id}"
    peers     = 0
    elapsed   = 0
    MAX_WAIT  = 20  # segundos máximo esperando peers

    for i in range(MAX_WAIT * 2):
        spin_i = (spin_i + 1) % len(spinner)
        stat   = ace_api(stat_url)
        if stat and stat.get("result"):
            peers = stat["result"].get("peers", 0)
        elapsed = i * 0.5
        msg = f"{spinner[spin_i]} Buscando peers... {peers} peers | {elapsed:.0f}s"
        safe_addstr(stdscr, status_y, 2, msg.ljust(w-4), curses.color_pair(3) | curses.A_BOLD)
        stdscr.refresh()
        if peers > 0:
            break
        time.sleep(0.5)

    if peers == 0:
        safe_addstr(stdscr, status_y, 2, f"⚠  Sin peers — abriendo VLC igualmente (puede tardar)".ljust(w-4), curses.color_pair(7))
    else:
        safe_addstr(stdscr, status_y, 2, f"✅ {peers} peers — abriendo VLC".ljust(w-4), curses.color_pair(2) | curses.A_BOLD)
    stdscr.refresh()
    time.sleep(0.5)

    subprocess.Popen(
        ["mpv", "--quiet", "--no-terminal", "--force-window=immediate", 
         "--cache=yes", "--demuxer-max-bytes=1000M", "--demuxer-max-back-bytes=200M",
         "--hwdec=auto", "--vo=gpu", "--profile=gpu-hq", "--deinterlace=auto", 
         "--title=" + ch_name, play_url],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    return peers

# ── UI ───────────────────────────────────────────────────────────────────────
def draw_ui(stdscr, channels, selected, scroll, search, search_mode, status):
    h, w = stdscr.getmaxyx()
    stdscr.erase()

    # ── Cabecera ──
    title = " 🎬  ACESTREAM LAUNCHER "
    safe_addstr(stdscr, 0, 0, title.center(w - 1), curses.color_pair(8) | curses.A_BOLD)
    controls = " ↑↓ Mover   ENTER Reproducir   / Buscar   q Salir "
    safe_addstr(stdscr, 1, 0, controls.center(w - 1), curses.color_pair(9))

    # ── Separador ──
    safe_hline(stdscr, 2, 0, curses.ACS_HLINE, w - 1)
    if search_mode:
        hint = f" 🔍 {search}▌ "
        safe_addstr(stdscr, 2, 2, hint, curses.color_pair(3) | curses.A_BOLD)
    elif search:
        hint = f" 🔍 '{search}' — {len(channels)} resultado(s) "
        safe_addstr(stdscr, 2, 2, hint, curses.color_pair(4))

    # ── Lista de canales ──
    list_top = 3
    list_bot = h - 3   # dejar 2 líneas para status y controles
    list_h   = list_bot - list_top

    for i in range(list_h):
        idx = scroll + i
        y   = list_top + i
        if idx >= len(channels):
            break
        ch      = channels[idx]
        is_sel  = (idx == selected)
        lang    = ch["lang"]
        col     = LANG_COLORS.get(lang, 7)
        lang_tag = f"[{lang}]"
        name_w   = w - len(lang_tag) - 5
        name     = ch["name"][:name_w].ljust(name_w)

        if is_sel:
            line = f" ▶ {name} {lang_tag} "
            safe_addstr(stdscr, y, 0, line[:w - 1].ljust(w - 1), curses.color_pair(10) | curses.A_BOLD)
        else:
            safe_addstr(stdscr, y, 0, f"   {name} ", curses.color_pair(0))
            safe_addstr(stdscr, y, 4 + len(name), lang_tag, curses.color_pair(col))

    # ── Scrollbar visual ──
    if len(channels) > list_h:
        bar_h   = max(1, list_h * list_h // len(channels))
        bar_pos = int(scroll / max(1, len(channels) - list_h) * (list_h - bar_h))
        for r in range(list_h):
            c = curses.ACS_CKBOARD if bar_pos <= r < bar_pos + bar_h else ord(' ')
            try:
                stdscr.addch(list_top + r, w - 1, c, curses.color_pair(9))
            except curses.error:
                pass

    # ── Separador inferior ──
    safe_hline(stdscr, h - 3, 0, curses.ACS_HLINE, w - 1)

    # ── Barra de estado ──
    safe_addstr(stdscr, h - 2, 0, f" {status}"[:w - 1].ljust(w - 1), curses.color_pair(9))

    # ── Controles ──
    controls_bot = "  ESC Limpiar búsqueda   PgUp/PgDn Página"
    safe_addstr(stdscr, h - 1, 0, controls_bot[:w - 1], curses.color_pair(9) | curses.A_DIM)

    stdscr.refresh()

# ── Main ─────────────────────────────────────────────────────────────────────
def main(stdscr):
    curses.start_color()
    curses.use_default_colors()
    curses.curs_set(0)
    stdscr.keypad(True)
    stdscr.timeout(50)   # ms, para resize reactivo

    curses.init_pair(1,  curses.COLOR_RED,     -1)   # ES
    curses.init_pair(2,  curses.COLOR_GREEN,   -1)   # EN / OK
    curses.init_pair(3,  curses.COLOR_YELLOW,  -1)   # DE / search
    curses.init_pair(4,  curses.COLOR_CYAN,    -1)   # PL / search result
    curses.init_pair(5,  curses.COLOR_MAGENTA, -1)   # PT
    curses.init_pair(6,  curses.COLOR_RED,     -1)   # RU
    curses.init_pair(7,  curses.COLOR_YELLOW,  -1)   # Info/warning
    curses.init_pair(8,  curses.COLOR_BLACK,   curses.COLOR_CYAN)   # Header
    curses.init_pair(9,  curses.COLOR_WHITE,   curses.COLOR_BLUE)   # Footer/bar
    curses.init_pair(10, curses.COLOR_BLACK,   curses.COLOR_GREEN)  # Selected

    all_channels = load_channels()
    if not all_channels:
        stdscr.erase()
        safe_addstr(stdscr, 2, 2, "ERROR: No se cargaron canales desde Acestream_Links.ods")
        stdscr.refresh()
        stdscr.getch()
        return

    channels    = all_channels[:]
    selected    = 0
    scroll      = 0
    search      = ""
    search_mode = False
    status      = f"📺 {len(channels)} canales  —  ENTER para reproducir"

    h, w = stdscr.getmaxyx()
    ensure_docker(stdscr, h, w, h // 2)

    while True:
        h, w   = stdscr.getmaxyx()
        list_h = (h - 3) - 3  # list_bot - list_top

        draw_ui(stdscr, channels, selected, scroll, search, search_mode, status)

        key = stdscr.getch()
        if key == -1:  # timeout, no key
            continue

        # ── Modo búsqueda ──
        if search_mode:
            if key == 27:
                search_mode = False
                search      = ""
                channels    = all_channels[:]
                selected    = 0; scroll = 0
                status      = f"📺 {len(all_channels)} canales"
            elif key in (curses.KEY_BACKSPACE, 127, 8):
                search   = search[:-1]
                channels = [c for c in all_channels if search.lower() in c["name"].lower()] if search else all_channels[:]
                selected = 0; scroll = 0
            elif key == 10:
                search_mode = False
                status = f"🔍 '{search}' — {len(channels)} resultado(s)"
            elif 32 <= key <= 126:
                search  += chr(key)
                channels = [c for c in all_channels if search.lower() in c["name"].lower()]
                selected = 0; scroll = 0
            continue

        # ── Modo normal ──
        if key in (ord('q'), 27):
            break
        elif key == ord('/'):
            search_mode = True
            search      = ""
        elif key == curses.KEY_UP:
            if selected > 0:
                selected -= 1
                if selected < scroll:
                    scroll = selected
        elif key == curses.KEY_DOWN:
            if selected < len(channels) - 1:
                selected += 1
                if selected >= scroll + list_h:
                    scroll = selected - list_h + 1
        elif key == curses.KEY_PPAGE:
            selected = max(0, selected - list_h)
            scroll   = max(0, scroll - list_h)
        elif key == curses.KEY_NPAGE:
            selected = min(len(channels) - 1, selected + list_h)
            if selected >= scroll + list_h:
                scroll = selected - list_h + 1
        elif key == curses.KEY_HOME:
            selected = 0; scroll = 0
        elif key == curses.KEY_END:
            selected = len(channels) - 1
            scroll   = max(0, selected - list_h + 1)
        elif key == 10 and channels:   # ENTER
            ch = channels[selected]
            ensure_docker(stdscr, h, w, h // 2)
            # Extraer content_id de la URL
            url    = ch["url"]
            cid    = url.split("id=")[-1].split("&")[0] if "id=" in url else ""
            peers  = start_stream_and_open_vlc(cid, ch["name"], stdscr, h - 4, w)
            p_str  = f"{peers} peers" if peers else "sin peers"
            status = f"▶  {ch['name']} [{ch['lang']}] — {p_str}"
        elif key == curses.KEY_RESIZE:
            curses.resizeterm(*stdscr.getmaxyx())

curses.wrapper(main)
