#!/usr/bin/env python3
"""
AceStream Launcher - Furbo (AceStream TV)
Compatible con Windows y Linux.
Navegación por Categorías, Búsqueda, Favoritos (Fondo Dorado),
Historial de Reproducción, Borrado/Añadido local de canales,
Comprobación de Peers y Detección Automática de AceStream Engine.
"""
import curses
import subprocess
import time
import os
import sys
import urllib.request
import urllib.error
import json

# ── Configurar codificación UTF-8 en Windows ────────────────────────────────
if sys.platform.startswith('win'):
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8')
        if hasattr(sys.stdin, 'reconfigure'):
            sys.stdin.reconfigure(encoding='utf-8')
    except Exception:
        pass

# ── Ruta base del proyecto (compatible con PyInstaller y ejecución normal) ───
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ROOT_DIR = os.path.dirname(BASE_DIR)
IS_WINDOWS = os.name == 'nt'

FAV_FILE = os.path.join(ROOT_DIR, "favoritos.json")
HIST_FILE = os.path.join(ROOT_DIR, "historial.json")

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

# ── Gestión de Favoritos Persistentes ───────────────────────────────────────
def load_favorites():
    if os.path.exists(FAV_FILE):
        try:
            with open(FAV_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return set(data)
        except Exception:
            pass
    return set()

def save_favorites(fav_set):
    try:
        with open(FAV_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(list(fav_set)), f, indent=2, ensure_ascii=False)
    except Exception:
        pass

# ── Gestión de Historial Persistente (Últimos Reproducidos) ───────────────────
def load_history():
    if os.path.exists(HIST_FILE):
        try:
            with open(HIST_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            pass
    return []

def save_history(hist_list):
    try:
        with open(HIST_FILE, "w", encoding="utf-8") as f:
            json.dump(hist_list[:25], f, indent=2, ensure_ascii=False)
    except Exception:
        pass

def record_channel_played(ch):
    hist = load_history()
    entry = {
        "name": ch["name"],
        "lang": ch.get("lang", "ES"),
        "cid": ch.get("cid", ""),
        "fpath": ch.get("fpath", ""),
        "category": ch.get("category", "")
    }
    hist = [h for h in hist if h.get("cid") != entry["cid"] and h.get("name") != entry["name"]]
    hist.insert(0, entry)
    save_history(hist)

# ── Carga canales organizados por categorías/carpetas ─────────────────────────
def load_categories(fav_set=None):
    if fav_set is None:
        fav_set = load_favorites()

    categories = []

    # 1. Historial de reproducción
    hist_entries = load_history()
    if hist_entries:
        hist_chs = []
        for h in hist_entries:
            cid = h.get("cid", "")
            is_fav = (cid in fav_set)
            hist_chs.append({
                "name": h.get("name", "Canal"),
                "lang": h.get("lang", "ES"),
                "cid": cid,
                "url": f"http://127.0.0.1:6878/ace/getstream?id={cid}",
                "category": "historial",
                "fpath": h.get("fpath", ""),
                "is_fav": is_fav
            })
        if hist_chs:
            categories.append({
                "name": "HISTORIAL (ÚLTIMOS REPRODUCIDOS)",
                "key": "historial",
                "order": 9200,
                "channels": hist_chs
            })
    
    # 2. Escanear carpetas de canales/
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
                                        cid = parts[2].replace("acestream://", "").strip()
                                        is_fav = (cid in fav_set)
                                        chs.append({
                                            "name": parts[0],
                                            "lang": parts[1],
                                            "cid": cid,
                                            "url": f"http://127.0.0.1:6878/ace/getstream?id={cid}",
                                            "category": rel,
                                            "fpath": fpath,
                                            "is_fav": is_fav
                                        })
                        if chs:
                            name_counts = {}
                            for ch in chs:
                                name_counts[ch["name"]] = name_counts.get(ch["name"], 0) + 1
                            if any(c > 1 for c in name_counts.values()):
                                seen_occ = {}
                                for ch in chs:
                                    bn = ch["name"]
                                    if name_counts[bn] > 1:
                                        seen_occ[bn] = seen_occ.get(bn, 0) + 1
                                        ch["name"] = f"{bn} ({seen_occ[bn]})"

                            chs.sort(key=lambda x: (0 if x.get("is_fav") else 1))

                            cat_name, order = CAT_META.get(rel, (rel.upper().replace("_", " "), 900))
                            categories.append({
                                "name": cat_name,
                                "key": rel,
                                "order": order,
                                "channels": chs
                            })

    # 3. Canales manuales sueltos en raíz
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
                            cid = parts[2].replace("acestream://", "").strip()
                            is_fav = (cid in fav_set)
                            manual_chs.append({
                                "name": parts[0],
                                "lang": parts[1],
                                "cid": cid,
                                "url": f"http://127.0.0.1:6878/ace/getstream?id={cid}",
                                "category": "manuales",
                                "fpath": mf,
                                "is_fav": is_fav
                            })
            break
    if manual_chs:
        manual_chs.sort(key=lambda x: (0 if x.get("is_fav") else 1))
        categories.append({
            "name": "CANALES MANUALES",
            "key": "manuales",
            "order": 9100,
            "channels": manual_chs
        })

    # 4. Carpeta al final del todo con TODOS LOS CANALES (orden 9999)
    all_unique_chs = []
    seen_all_cids = set()
    for cat in categories:
        if cat.get("key") in ("historial", "todos"):
            continue
        for ch in cat["channels"]:
            cid = ch.get("cid")
            if cid and cid not in seen_all_cids:
                seen_all_cids.add(cid)
                ch_copy = ch.copy()
                all_unique_chs.append(ch_copy)

    if all_unique_chs:
        all_unique_chs.sort(key=lambda x: (0 if x.get("is_fav") else 1, x["name"].lower()))
        categories.append({
            "name": "TODOS LOS CANALES",
            "key": "todos",
            "order": 9999,
            "channels": all_unique_chs
        })

    categories.sort(key=lambda x: x["order"])
    return categories

def get_root_items(categories, fav_set, all_channels_flat):
    """Devuelve los canales favoritos arriba del todo y luego la lista de carpetas."""
    fav_chs = []
    seen = set()
    for ch in all_channels_flat:
        cid = ch.get("cid")
        if cid and cid in fav_set and cid not in seen:
            seen.add(cid)
            ch_copy = ch.copy()
            ch_copy["is_fav"] = True
            fav_chs.append(ch_copy)
    return fav_chs + categories

# ── Borrado local de canal en archivo de disco ───────────────────────────────
def delete_channel_file(ch):
    fpath = ch.get("fpath")
    cid = ch.get("cid")
    name = ch.get("name")
    if not fpath or not os.path.exists(fpath):
        return False
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        new_lines = []
        deleted = False
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                parts = [p.strip() for p in stripped.split(",")]
                if len(parts) >= 3:
                    l_cid = parts[2].replace("acestream://", "").strip()
                    if (cid and l_cid == cid) or (name and parts[0] == name):
                        deleted = True
                        continue
            new_lines.append(line)

        if deleted:
            with open(fpath, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            return True
    except Exception:
        pass
    return False

# ── Colores por idioma ───────────────────────────────────────────────────────
LANG_COLORS = {"ES": 1, "EN": 2, "DE": 3, "PL": 4, "PT": 5, "RU": 6}

# ── Escritura segura (evita crash en bordes de terminal) ─────────────────────
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

# ── Dibujar fila de canal con soporte para [E] en verde brillante ───────────
def draw_channel_row(stdscr, y, w, mid_col, ch, is_sel):
    is_fav = ch.get("is_fav", False)
    lang = ch.get("lang", "ES")
    col = LANG_COLORS.get(lang, 7)
    lang_tag = f"[{lang}]"
    
    full_name = ch["name"]
    has_excel_tag = full_name.endswith("[E]")
    if has_excel_tag:
        base_name = full_name[:-3].rstrip()
    else:
        base_name = full_name

    fav_icon = "★ " if is_fav else "  "
    avail_name_w = max(10, mid_col - 5)
    
    if is_sel:
        prefix = " > "
        if is_fav:
            row_attr = curses.color_pair(11) | curses.A_BOLD | curses.A_STANDOUT
            tag_attr = curses.color_pair(13) | curses.A_BOLD | curses.A_STANDOUT
        else:
            row_attr = curses.color_pair(10) | curses.A_BOLD
            tag_attr = curses.color_pair(10) | curses.A_BOLD
    else:
        prefix = "   "
        if is_fav:
            row_attr = curses.color_pair(11) | curses.A_BOLD
            tag_attr = curses.color_pair(13) | curses.A_BOLD
        else:
            row_attr = curses.color_pair(0)
            tag_attr = curses.color_pair(2) | curses.A_BOLD

    safe_addstr(stdscr, y, 0, f"{prefix}{fav_icon}", row_attr)
    curr_x = len(prefix) + len(fav_icon)
    
    if has_excel_tag:
        disp_base = base_name[:max(1, avail_name_w - 4)]
        safe_addstr(stdscr, y, curr_x, disp_base, row_attr)
        curr_x += len(disp_base)
        safe_addstr(stdscr, y, curr_x, " [E]", tag_attr)
        curr_x += 4
    else:
        disp_name = base_name[:avail_name_w]
        safe_addstr(stdscr, y, curr_x, disp_name, row_attr)
        curr_x += len(disp_name)

    if curr_x < mid_col:
        safe_addstr(stdscr, y, curr_x, " " * (mid_col - curr_x), row_attr)

    if is_sel or is_fav:
        safe_addstr(stdscr, y, mid_col, f" {lang_tag} ", row_attr)
    else:
        safe_addstr(stdscr, y, mid_col, lang_tag, curses.color_pair(col))

    if is_fav:
        badge = " ★ FAVORITO "
        safe_addstr(stdscr, y, mid_col + 7, badge, row_attr)
        fill_start = mid_col + 7 + len(badge)
    else:
        fill_start = mid_col + len(lang_tag) + 2

    if (is_sel or is_fav) and fill_start < (w - 1):
        safe_addstr(stdscr, y, fill_start, " " * (w - 1 - fill_start), row_attr)

# ── Cuadro de Diálogo Modal para Entrada de Texto ───────────────────────────
def prompt_input(stdscr, title, prompt_text, default_val=""):
    h, w = stdscr.getmaxyx()
    box_w = min(74, max(42, w - 4))
    box_h = 7
    box_y = max(1, (h - box_h) // 2)
    box_x = max(1, (w - box_w) // 2)

    val = default_val
    curses.curs_set(1)
    stdscr.timeout(-1)

    while True:
        for dy in range(box_h):
            safe_addstr(stdscr, box_y + dy, box_x, " " * box_w, curses.color_pair(8))
        safe_addstr(stdscr, box_y + 1, box_x + 2, f"=== {title} ==="[:box_w - 4], curses.color_pair(8) | curses.A_BOLD)
        safe_addstr(stdscr, box_y + 3, box_x + 2, prompt_text[:box_w - 4], curses.color_pair(8))

        disp_len = box_w - 6
        inp_disp = val[-disp_len:] if len(val) > disp_len else val
        safe_addstr(stdscr, box_y + 4, box_x + 2, f"> {inp_disp}_"[:box_w - 4], curses.color_pair(10) | curses.A_BOLD)
        safe_addstr(stdscr, box_y + 5, box_x + 2, "[ENTER: Guardar | ESC: Cancelar]"[:box_w - 4], curses.color_pair(8) | curses.A_DIM)
        stdscr.refresh()

        ch = stdscr.getch()
        if ch == 27:
            curses.curs_set(0)
            stdscr.timeout(100)
            return None
        elif ch in (10, 13):
            curses.curs_set(0)
            stdscr.timeout(100)
            return val.strip()
        elif ch in (curses.KEY_BACKSPACE, 127, 8):
            val = val[:-1]
        elif 32 <= ch <= 126:
            val += chr(ch)

# ── API del motor AceStream ─────────────────────────────────────────────────
ACE_API = "http://127.0.0.1:6878"

def ace_api(path):
    """Llama a la API del motor AceStream y devuelve el JSON o None."""
    try:
        req = urllib.request.Request(f"{ACE_API}{path}", headers={'User-Agent': 'Furbo/2.0'})
        with urllib.request.urlopen(req, timeout=1.5) as r:
            return json.loads(r.read())
    except Exception:
        return None

# ── Búsqueda activa y arranque automático del motor ─────────────────────────
def find_and_start_engine(stdscr=None, h=0, w=0, msg_y=0):
    """Busca activamente la ruta de instalación de AceStream y lo inicia si está cerrado."""
    if ace_api("/webui/api/service?method=get_version"):
        return True

    if IS_WINDOWS:
        if stdscr:
            safe_addstr(stdscr, msg_y, 2, "Buscando instalacion de AceStream en el ordenador...".ljust(w - 4),
                        curses.color_pair(7) | curses.A_BOLD)
            stdscr.refresh()

        candidate_paths = [
            os.path.expandvars(r"%APPDATA%\AceStream\engine\ace_engine.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\AceStream\engine\ace_engine.exe"),
            os.path.expandvars(r"%PROGRAMFILES%\AceStream\engine\ace_engine.exe"),
            os.path.expandvars(r"%PROGRAMFILES(X86)%\AceStream\engine\ace_engine.exe"),
            os.path.expandvars(r"%PROGRAMFILES%\AceStream\ace_engine.exe"),
            os.path.expandvars(r"C:\Users\%USERNAME%\AppData\Roaming\AceStream\engine\ace_engine.exe"),
            os.path.expandvars(r"C:\Users\%USERNAME%\AppData\Local\AceStream\engine\ace_engine.exe"),
        ]

        try:
            import winreg
            for root_hkey in [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]:
                for subkey_path in [
                    r"Software\AceStream",
                    r"Software\WOW6432Node\AceStream",
                    r"Software\Microsoft\Windows\CurrentVersion\Uninstall\AceStream"
                ]:
                    try:
                        with winreg.OpenKey(root_hkey, subkey_path) as k:
                            for val_name in ["InstallDir", "EnginePath", "Path", "InstallLocation"]:
                                try:
                                    val, _ = winreg.QueryValueEx(k, val_name)
                                    if val:
                                        if val.lower().endswith("ace_engine.exe") and os.path.isfile(val):
                                            candidate_paths.insert(0, val)
                                        else:
                                            cand = os.path.join(val, "engine", "ace_engine.exe")
                                            if os.path.isfile(cand):
                                                candidate_paths.insert(0, cand)
                                            cand2 = os.path.join(val, "ace_engine.exe")
                                            if os.path.isfile(cand2):
                                                candidate_paths.insert(0, cand2)
                                except Exception:
                                    pass
                    except Exception:
                        pass
        except Exception:
            pass

        found_exe = None
        for cp in candidate_paths:
            if cp and os.path.isfile(cp):
                found_exe = cp
                break

        if not found_exe:
            appdata = os.path.expandvars(r"%APPDATA%")
            if os.path.isdir(appdata):
                for root_dir, dirs, files in os.walk(appdata):
                    if "ace_engine.exe" in files:
                        found_exe = os.path.join(root_dir, "ace_engine.exe")
                        break
                    if root_dir.count(os.sep) - appdata.count(os.sep) > 3:
                        dirs.clear()

        if found_exe:
            if stdscr:
                safe_addstr(stdscr, msg_y, 2, f"Iniciando AceStream: {os.path.basename(found_exe)}...".ljust(w - 4),
                            curses.color_pair(2) | curses.A_BOLD)
                stdscr.refresh()
            try:
                DETACHED = 0x00000008 | 0x00000200
                subprocess.Popen(
                    [found_exe],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=DETACHED
                )
            except Exception:
                pass
    else:
        linux_bins = [
            "/snap/bin/acestream-player.engine",
            "/usr/bin/acestreamengine",
            os.path.expanduser("~/.ACEStream/engine/app.py"),
            "/opt/acestream/acestreamengine"
        ]
        found_bin = None
        for lb in linux_bins:
            if os.path.isfile(lb) and os.access(lb, os.X_OK):
                found_bin = lb
                break
        if found_bin:
            try:
                subprocess.Popen([found_bin, "--client-console"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
        else:
            try:
                subprocess.run(["docker", "start", "tor-proxy"], capture_output=True)
                subprocess.run(["docker", "start", "acestream"], capture_output=True)
            except Exception:
                pass

    for attempt in range(16):
        if ace_api("/webui/api/service?method=get_version"):
            return True
        if stdscr:
            dots = "." * (attempt % 4 + 1)
            safe_addstr(stdscr, msg_y, 2, f"Esperando que AceStream responda{dots}".ljust(w - 4),
                        curses.color_pair(7) | curses.A_BOLD)
            stdscr.refresh()
        time.sleep(0.4)

    return ace_api("/webui/api/service?method=get_version") is not None

def ensure_engine(stdscr, h, w, msg_y):
    """Garantiza que AceStream Engine esté activo de forma rápida si ya responde."""
    if ace_api("/webui/api/service?method=get_version"):
        return True

    safe_addstr(stdscr, msg_y, 2, "⏳ Comprobando motor AceStream...".ljust(w - 4),
                curses.color_pair(7) | curses.A_BOLD)
    stdscr.refresh()

    ok = find_and_start_engine(stdscr, h, w, msg_y)
    if ok:
        safe_addstr(stdscr, msg_y, 2,
                    "AceStream Engine conectado correctamente".ljust(w - 4),
                    curses.color_pair(2) | curses.A_BOLD)
        stdscr.refresh()
        time.sleep(0.3)
    else:
        safe_addstr(stdscr, msg_y, 2,
                    "! No se pudo conectar a AceStream. Asegurate de que este abierto.".ljust(w - 4),
                    curses.color_pair(7) | curses.A_BOLD)
        stdscr.refresh()
        time.sleep(1.2)
    return ok

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
    time.sleep(0.8)

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
                    "! Sin peers detectados aun - abriendo reproductor igualmente...".ljust(w - 4),
                    curses.color_pair(7))
    else:
        player_name = "VLC" if IS_WINDOWS else "mpv"
        safe_addstr(stdscr, status_y, 2,
                    f"✓ {peers} peers activos - abriendo {player_name}".ljust(w - 4),
                    curses.color_pair(2) | curses.A_BOLD)
    stdscr.refresh()
    time.sleep(0.4)

    # ── Lanzar reproductor de vídeo ──
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
            time.sleep(2.5)
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
def draw_ui(stdscr, current_cat, items, selected, scroll, search, search_mode, status, engine_online):
    h, w = stdscr.getmaxyx()
    if h < 8 or w < 40:
        stdscr.erase()
        safe_addstr(stdscr, 0, 0, "Terminal demasiado pequeña")
        stdscr.refresh()
        return
    stdscr.erase()

    # ── Cabecera ──
    title = " ★ TEBAS CABRON TOMA SOLUCION ★ "
    safe_addstr(stdscr, 0, 0, title.center(w - 1), curses.color_pair(8) | curses.A_BOLD)

    # Widget de estado de AceStream Engine en tiempo real (Item 11)
    if engine_online:
        engine_str = " [ACE: ● ON] "
        eng_x = max(0, w - len(engine_str) - 1)
        safe_addstr(stdscr, 0, eng_x, engine_str, curses.color_pair(12) | curses.A_BOLD)
    else:
        engine_str = " [ACE: ○ OFF] "
        eng_x = max(0, w - len(engine_str) - 1)
        safe_addstr(stdscr, 0, eng_x, engine_str, curses.color_pair(1) | curses.A_BOLD)
    
    if current_cat is None and not search:
        nav = " Favoritos arriba | CARPETAS abajo (ENTER: Abrir | /: Buscar | +: Añadir | q: Salir) "
    elif current_cat is None and search:
        nav = f" Búsqueda Global: '{search}' (ENTER: Fijar | ESC: Volver) "
    else:
        nav = f" [CARPETA: {current_cat['name']}]  (BACKSPACE/ESC: Volver | ENTER: Reproducir | f: Favorito | p: Peers) "
    safe_addstr(stdscr, 1, 0, nav.center(w - 1), curses.color_pair(9))

    # ── Separador ──
    safe_hline(stdscr, 2, 0, curses.ACS_HLINE, w - 1)
    if search_mode:
        hint = f" >> Buscar canal: {search}_ "
        safe_addstr(stdscr, 2, 2, hint, curses.color_pair(3) | curses.A_BOLD)
    elif search:
        hint = f" >> Filtrado: '{search}' ({len(items)} resultados, favoritos arriba) "
        safe_addstr(stdscr, 2, 2, hint, curses.color_pair(4))

    # ── Lista principal ──
    list_top = 3
    list_bot = h - 3
    list_h = list_bot - list_top
    if list_h <= 0:
        return

    # Posición central para el idioma [ES] (cerca del centro de la pantalla)
    mid_col = max(26, min(38, w // 2 - 2))

    for i in range(list_h):
        idx = scroll + i
        y = list_top + i
        if idx >= len(items):
            break
        item = items[idx]
        is_sel = (idx == selected)

        if current_cat is None and not search:
            # En la vista principal: puede haber CANALES FAVORITOS arriba o DIRECTORIOS debajo
            if "channels" in item:
                # Es un DIRECTORIO / CARPETA
                cat_name = item["name"]
                count = f"({len(item['channels'])} canales)"
                name_w = max(1, w - len(count) - 10)
                line_name = cat_name[:name_w].ljust(name_w)

                if is_sel:
                    line = f" > [DIR]  {line_name} {count} "
                    safe_addstr(stdscr, y, 0, line[:w - 1].ljust(w - 1), curses.color_pair(10) | curses.A_BOLD)
                else:
                    safe_addstr(stdscr, y, 0, f"   [DIR]  {line_name} ", curses.color_pair(0) | curses.A_BOLD)
                    safe_addstr(stdscr, y, 10 + len(line_name), count, curses.color_pair(4))
            else:
                # Es un CANAL FAVORITO en la parte superior
                draw_channel_row(stdscr, y, w, mid_col, item, is_sel)
        else:
            # Vista dentro de carpeta o búsqueda: todos son canales
            draw_channel_row(stdscr, y, w, mid_col, item, is_sel)

    # ── Barra de Scroll Protegida (Sin división por cero) ──
    if len(items) > list_h and list_h > 0:
        bar_h = max(1, list_h * list_h // max(1, len(items)))
        max_scroll = max(1, len(items) - list_h)
        avail_space = max(1, list_h - bar_h)
        bar_pos = min(avail_space, max(0, int((scroll / max_scroll) * avail_space)))
        for r in range(list_h):
            ch_char = curses.ACS_CKBOARD if bar_pos <= r < bar_pos + bar_h else ord(' ')
            try:
                stdscr.addch(list_top + r, w - 1, ch_char, curses.color_pair(9))
            except curses.error:
                pass

    # ── Barra inferior y Controles ──
    safe_hline(stdscr, h - 3, 0, curses.ACS_HLINE, w - 1)
    safe_addstr(stdscr, h - 2, 0, f" {status}"[:w - 1].ljust(w - 1), curses.color_pair(9))
    controls_bot = " ENTER: Reproducir/Entrar | f: Fav (★) | +: Añadir | p: Peers | d: Borrar | ESC: Volver | /: Buscar | q: Salir"
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

    # Pares de color estándar
    curses.init_pair(1,  curses.COLOR_RED,     default_bg)   # ES / Error
    curses.init_pair(2,  curses.COLOR_GREEN,   default_bg)   # EN / OK / [E] tag
    curses.init_pair(3,  curses.COLOR_YELLOW,  default_bg)   # DE / search
    curses.init_pair(4,  curses.COLOR_CYAN,    default_bg)   # PL / count
    curses.init_pair(5,  curses.COLOR_MAGENTA, default_bg)   # PT
    curses.init_pair(6,  curses.COLOR_RED,     default_bg)   # RU
    curses.init_pair(7,  curses.COLOR_YELLOW,  default_bg)   # Info/warning
    curses.init_pair(8,  curses.COLOR_BLACK,   curses.COLOR_CYAN)   # Header
    curses.init_pair(9,  curses.COLOR_WHITE,   curses.COLOR_BLUE)   # Footer/bar
    curses.init_pair(10, curses.COLOR_BLACK,   curses.COLOR_GREEN)  # Selected normal
    curses.init_pair(11, curses.COLOR_BLACK,   curses.COLOR_YELLOW) # Favorito (Fondo Dorado)
    curses.init_pair(12, curses.COLOR_BLACK,   curses.COLOR_GREEN)  # Online Tag
    curses.init_pair(13, curses.COLOR_GREEN,   curses.COLOR_YELLOW) # [E] tag en Fondo Dorado

    fav_set = load_favorites()
    categories = load_categories(fav_set)
    if not categories:
        stdscr.erase()
        safe_addstr(stdscr, 2, 2, "ERROR: No se encontraron canales en la carpeta canales/")
        safe_addstr(stdscr, 4, 2, "Pulsa una tecla para salir...")
        stdscr.refresh()
        stdscr.timeout(-1)
        stdscr.getch()
        return

    # Aplanar canales para búsqueda global y favoritos de inicio
    all_channels_flat = []
    for cat in categories:
        if cat.get("key") not in ("historial", "todos"):
            all_channels_flat.extend(cat["channels"])

    current_cat = None
    items = get_root_items(categories, fav_set, all_channels_flat)
    selected = 0
    scroll = 0
    search = ""
    search_mode = False
    
    total_chs = len(all_channels_flat)
    status = f"{len(categories)} carpetas ({total_chs} canales)  -  ENTER para abrir | f: Favorito | +: Añadir canal"

    h, w = stdscr.getmaxyx()
    ensure_engine(stdscr, h, w, h // 2)

    last_engine_check = 0
    engine_online = False

    while True:
        h, w = stdscr.getmaxyx()
        list_h = h - 6
        if list_h < 1:
            list_h = 1

        now = time.time()
        if now - last_engine_check > 3.0:
            engine_online = (ace_api("/webui/api/service?method=get_version") is not None)
            last_engine_check = now

        draw_ui(stdscr, current_cat, items, selected, scroll, search, search_mode, status, engine_online)

        key = stdscr.getch()
        if key == -1:
            continue

        # ── Modo búsqueda global ──
        if search_mode:
            if key == 27: # ESC cancelar
                search_mode = False
                search = ""
                if current_cat is None:
                    items = get_root_items(categories, fav_set, all_channels_flat)
                    status = f"{len(categories)} carpetas ({total_chs} canales)"
                else:
                    items = current_cat["channels"][:]
                    status = f"{current_cat['name']} - {len(items)} canales"
                selected = 0
                scroll = 0
            elif key in (curses.KEY_BACKSPACE, 127, 8):
                search = search[:-1]
                if search:
                    matches = [c for c in all_channels_flat if search.lower() in c["name"].lower()]
                    matches.sort(key=lambda x: (0 if x.get("is_fav") else 1))
                    items = matches
                else:
                    items = get_root_items(categories, fav_set, all_channels_flat) if current_cat is None else current_cat["channels"][:]
                selected = 0
                scroll = 0
            elif key in (10, 13): # ENTER fija búsqueda
                search_mode = False
                status = f"'{search}' - {len(items)} resultado(s)"
            elif 32 <= key <= 126:
                search += chr(key)
                matches = [c for c in all_channels_flat if search.lower() in c["name"].lower()]
                matches.sort(key=lambda x: (0 if x.get("is_fav") else 1))
                items = matches
                selected = 0
                scroll = 0
            continue

        # ── Modo normal ──
        if key in (ord('q'), ord('Q')):
            break

        elif key == ord('/'):
            search_mode = True
            search = ""
            current_cat = None

        # ── Añadir nuevo canal interactivo (Tecla '+') ──
        elif key == ord('+'):
            ch_name_in = prompt_input(stdscr, "AÑADIR CANAL (1/3)", "Nombre del canal:")
            if not ch_name_in:
                status = "Añadir canal cancelado."
                continue

            lang_in = prompt_input(stdscr, "AÑADIR CANAL (2/3)", "Idioma (ES, EN, DE, FR...):", default_val="ES")
            if not lang_in:
                status = "Añadir canal cancelado."
                continue
            lang_in = lang_in.upper().strip()

            cid_in = prompt_input(stdscr, "AÑADIR CANAL (3/3)", "Enlace acestream:// o Content ID:")
            if not cid_in:
                status = "Añadir canal cancelado."
                continue
            cid_clean = cid_in.replace("acestream://", "").strip()
            if not cid_clean:
                status = "Error: El ID de AceStream no puede estar vacío."
                continue

            dest_file = os.path.join(ROOT_DIR, "canales_manuales.txt")
            if current_cat and current_cat.get("channels") and current_cat["channels"][0].get("fpath"):
                dest_file = current_cat["channels"][0]["fpath"]

            try:
                with open(dest_file, "a", encoding="utf-8") as f:
                    f.write(f"\n{ch_name_in}, {lang_in}, acestream://{cid_clean}\n")
                status = f"[OK] ¡Canal '{ch_name_in}' añadido correctamente a {os.path.basename(dest_file)}!"
                
                # Recargar categorías
                categories = load_categories(fav_set)
                all_channels_flat = []
                for cat in categories:
                    if cat.get("key") not in ("historial", "todos"):
                        all_channels_flat.extend(cat["channels"])
                total_chs = len(all_channels_flat)

                if current_cat:
                    for c in categories:
                        if c["key"] == current_cat["key"]:
                            current_cat = c
                            items = current_cat["channels"][:]
                            selected = len(items) - 1
                            break
                else:
                    items = get_root_items(categories, fav_set, all_channels_flat)
            except Exception as e:
                status = f"Error al guardar canal: {e}"

        # ── Comprobar Peers / Estado del Canal (Tecla 'p' o 'P') ──
        elif key in (ord('p'), ord('P')):
            if items and selected < len(items):
                target_item = items[selected]
                if "channels" not in target_item: # Es un canal
                    cid = target_item.get("cid", "")
                    safe_addstr(stdscr, h - 2, 0, f"⏳ Consultando red P2P para '{target_item['name'][:25]}'...", curses.color_pair(3) | curses.A_BOLD)
                    stdscr.refresh()
                    stat = ace_api(f"/ace/stat/{cid}")
                    if stat and stat.get("response"):
                        resp = stat["response"]
                        p_count = resp.get("peers", 0)
                        st = resp.get("status", "inactivo")
                        speed = resp.get("speed_down", 0)
                        status = f"📊 {target_item['name']}: {p_count} peers | Estado: {st.upper()} | Vel: {speed} KB/s"
                    else:
                        status = f"📡 {target_item['name']} (CID: {cid[:16]}...) - Pulsa ENTER para arrancar stream"

        # ── Alternar Favorito (Tecla 'f' o 'F') ──
        elif key in (ord('f'), ord('F')):
            if items and selected < len(items):
                target_item = items[selected]
                if "channels" not in target_item: # Es un canal
                    ch = target_item
                    cid = ch.get("cid", "")
                    if cid in fav_set:
                        fav_set.remove(cid)
                        ch["is_fav"] = False
                        status = f"☆ Quitado de favoritos: {ch['name']}"
                    else:
                        fav_set.add(cid)
                        ch["is_fav"] = True
                        status = f"★ ¡Añadido a favoritos (Posición 1 y Fondo Dorado)!: {ch['name']}"
                    save_favorites(fav_set)

                    if current_cat is None and not search:
                        items = get_root_items(categories, fav_set, all_channels_flat)
                        selected = min(selected, max(0, len(items) - 1))
                    elif current_cat:
                        current_cat["channels"].sort(key=lambda x: (0 if x.get("is_fav") else 1))
                        items = current_cat["channels"][:]
                        try:
                            selected = items.index(ch)
                        except ValueError:
                            selected = 0
                    elif search:
                        items.sort(key=lambda x: (0 if x.get("is_fav") else 1))

        # ── Borrar Canal Localmente (Tecla 'd', 'D', 'x' o Supr) ──
        elif key in (ord('d'), ord('D'), ord('x'), ord('X'), curses.KEY_DC):
            if items and selected < len(items):
                target_item = items[selected]
                if "channels" not in target_item: # Es un canal
                    target_ch = target_item
                    prompt_text = f" ¿Eliminar localmente '{target_ch['name'][:25]}'? (s/n): "
                    safe_addstr(stdscr, h - 2, 0, prompt_text.ljust(w - 1), curses.color_pair(3) | curses.A_BOLD)
                    stdscr.refresh()
                    stdscr.timeout(-1)
                    conf_key = stdscr.getch()
                    stdscr.timeout(100)

                    if conf_key in (ord('s'), ord('S'), ord('y'), ord('Y')):
                        delete_channel_file(target_ch)
                        cid = target_ch.get("cid", "")
                        if cid in fav_set:
                            fav_set.remove(cid)
                            save_favorites(fav_set)

                        categories = load_categories(fav_set)
                        all_channels_flat = []
                        for cat in categories:
                            if cat.get("key") not in ("historial", "todos"):
                                all_channels_flat.extend(cat["channels"])
                        total_chs = len(all_channels_flat)

                        if current_cat is None and not search:
                            items = get_root_items(categories, fav_set, all_channels_flat)
                        elif current_cat:
                            for c in categories:
                                if c["key"] == current_cat["key"]:
                                    current_cat = c
                                    items = current_cat["channels"][:]
                                    break
                        elif search:
                            items = [c for c in all_channels_flat if search.lower() in c["name"].lower()]
                            items.sort(key=lambda x: (0 if x.get("is_fav") else 1))

                        selected = max(0, min(selected, len(items) - 1))
                        status = f"[OK] Canal '{target_ch['name']}' eliminado localmente."
                    else:
                        status = "Borrado cancelado."

        elif key in (27, curses.KEY_BACKSPACE, 127, 8):
            if search:
                search = ""
                items = get_root_items(categories, fav_set, all_channels_flat) if current_cat is None else current_cat["channels"][:]
                selected = 0
                scroll = 0
                status = f"{len(items)} elementos"
            elif current_cat is not None:
                current_cat = None
                items = get_root_items(categories, fav_set, all_channels_flat)
                selected = 0
                scroll = 0
                status = f"{len(categories)} carpetas  -  ENTER para abrir | +: Añadir canal"

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
            target_item = items[selected]
            if "channels" in target_item:
                # Entrar a la carpeta seleccionada
                current_cat = target_item
                items = current_cat["channels"][:]
                selected = 0
                scroll = 0
                status = f"Carpeta: {current_cat['name']} ({len(items)} canales)  -  ENTER: Reproducir | f: Fav | +: Añadir | p: Peers"
            else:
                # Reproducir canal (favorito en menú principal o canal dentro de carpeta/búsqueda)
                ch = target_item
                ensure_engine(stdscr, h, w, h // 2)
                url = ch["url"]
                cid = ch.get("cid", "")
                if not cid and "id=" in url:
                    cid = url.split("id=")[-1].split("&")[0]

                record_channel_played(ch)
                # Refrescar historial
                categories = load_categories(fav_set)
                peers = start_stream(cid, ch["name"], stdscr, h - 4, w)
                p_str = f"{peers} peers" if peers else "conectando"
                status = f">  {ch['name']} [{ch['lang']}] - {p_str}"

        elif key == curses.KEY_RESIZE:
            try:
                curses.resizeterm(*stdscr.getmaxyx())
            except Exception:
                pass

if __name__ == "__main__":
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception:
        sys.exit(0)
