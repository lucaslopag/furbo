#!/usr/bin/env python3
"""
AceStream Launcher - Furbo (AceStream TV)
Compatible con Windows y Linux.
Navegación por Categorías, Búsqueda, Filtro por Idioma (por defecto solo
español), Favoritos (Fondo Dorado), Historial de Reproducción, Borrado/Añadido
local de canales, Comprobación de Peers, Detección Automática de AceStream
Engine y gestión automática de la VPN antibloqueo (Cloudflare WARP).
"""
import os
import sys
import subprocess
import time
import urllib.request
import urllib.error
import json
import atexit
import signal
import shutil
import threading
import traceback
import locale

try:
    # Necesario para que curses lea bien tildes y la ñ en Linux (UTF-8)
    locale.setlocale(locale.LC_ALL, "")
except Exception:
    pass

IS_WINDOWS = sys.platform.startswith('win') or os.name == 'nt'

# ── Ruta base del proyecto (compatible con PyInstaller y ejecución normal) ───
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ROOT_DIR = os.path.dirname(BASE_DIR)

FAV_FILE = os.path.join(ROOT_DIR, "favoritos.json")
HIST_FILE = os.path.join(ROOT_DIR, "historial.json")
CONFIG_FILE = os.path.join(ROOT_DIR, "config.json")
ERROR_LOG = os.path.join(BASE_DIR, "acestream_error.log")

# ── Curses para Windows y Linux (Auto-reparación si falta en Windows) ────────
try:
    import curses
except (ImportError, ModuleNotFoundError):
    if IS_WINDOWS:
        print("[*] 'windows-curses' no detectado. Intentando instalar automáticamente...")
        try:
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", "--upgrade", "windows-curses>=2.4.2"
            ])
            import curses
            print("[OK] 'windows-curses' instalado y cargado con éxito.")
        except Exception as _err:
            print("\n" + "=" * 65)
            print(" [!] ERROR: No se pudo importar o instalar 'curses' en Windows.")
            print(f" [!] Intérprete Python: {sys.executable} (v{sys.version.split()[0]})")
            print(" [!] En Windows, Furbo requiere el paquete 'windows-curses'.")
            print(" [>] Solución:")
            print(f'     1. Ejecuta: "{sys.executable}" -m pip install "windows-curses>=2.4.2"')
            print("     2. O ejecuta 'instalar.bat'")
            print("=" * 65)
            try:
                input("\nPresiona Enter para salir...")
            except Exception:
                pass
            sys.exit(1)
    else:
        raise



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


# ══════════════════════════════════════════════════════════════════════════════
#  VPN ANTIBLOQUEO (Cloudflare WARP)
#
#  Qué resuelve respecto a la versión anterior:
#   · Acepta los términos de uso (ToS) y registra el dispositivo SIN ventanas ni
#     preguntas ("--accept-tos" + "registration new"), así que ya no hace falta
#     abrir la app de WARP y pulsar "Aceptar" en cada PC.
#   · La conexión se hace en segundo plano y se espera a que de verdad esté
#     "Connected" (antes se lanzaba "connect" con 3 s de timeout y se daba por
#     buena aunque no lo estuviera).
#   · Un vigilante reconecta solo si WARP se cae, se pausa o alguien la apaga.
#   · Solo se apaga al salir si la encendió Furbo (no toca la VPN del usuario).
# ══════════════════════════════════════════════════════════════════════════════
WARP_PATHS = [
    os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"),
                 "Cloudflare", "Cloudflare WARP", "warp-cli.exe"),
    os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                 "Cloudflare", "Cloudflare WARP", "warp-cli.exe"),
    "/usr/bin/warp-cli",
    "/usr/local/bin/warp-cli",
]
_NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW (evita parpadeos de consola en Windows)

# Marca que indica "esta VPN la encendió Furbo". Sobrevive a cierres bruscos de
# la ventana, de modo que la próxima ejecución sabe que debe apagarla.
VPN_OWNER_FILE = os.path.join(ROOT_DIR, ".warp_owned")

_vpn_lock = threading.Lock()
_vpn_stop = threading.Event()
_vpn_thread = None
_vpn = {"state": "off", "owned": False, "stopped": False}
_tos_flag_supported = True
VPN_WATCH_INTERVAL = 10   # segundos entre comprobaciones del vigilante


def get_warp_bin():
    """Devuelve la ruta de warp-cli o None si WARP no está instalado."""
    found = shutil.which("warp-cli")
    if found:
        return found
    for p in WARP_PATHS:
        if os.path.isfile(p):
            return p
    return None


def _warp(args, timeout=15):
    """Ejecuta warp-cli y devuelve (código, salida). Nunca lanza excepciones.

    Usa '--accept-tos' para que no se quede esperando la aceptación de términos
    y le pasa un 'y' por stdin para los clientes antiguos que preguntan.
    """
    global _tos_flag_supported
    binp = get_warp_bin()
    if not binp:
        return 127, "warp-cli no encontrado"

    def run(a):
        kw = {"creationflags": _NO_WINDOW} if IS_WINDOWS else {}
        try:
            r = subprocess.run([binp] + a, input="y\n", capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=timeout, **kw)
            return r.returncode, ((r.stdout or "") + "\n" + (r.stderr or "")).strip()
        except subprocess.TimeoutExpired:
            return 124, "timeout"
        except Exception as e:
            return 1, str(e)

    if _tos_flag_supported:
        code, out = run(["--accept-tos"] + list(args))
        low = out.lower()
        if code != 0 and any(s in low for s in ("unexpected argument", "unrecognized", "unknown option",
                                                "found argument", "no such option")):
            _tos_flag_supported = False  # cliente antiguo: no existe el flag
        else:
            return code, out
    return run(list(args))


def warp_status():
    """Devuelve (estado, texto). Estados: on, off, connecting, noreg, nodaemon, absent, unknown."""
    code, out = _warp(["status"], 8)
    if code == 127:
        return "absent", out
    low = out.lower()
    if "registration missing" in low or "no registration" in low or "missing registration" in low:
        return "noreg", out
    if "daemon" in low and any(s in low for s in ("unable", "not running", "failed", "cannot")):
        return "nodaemon", out
    if "disconnected" in low:
        return "off", out
    if "connecting" in low or "pending" in low:
        return "connecting", out
    if "connected" in low:
        return "on", out
    return "unknown", out


def _start_warp_service():
    """Intenta arrancar el servicio de WARP si está parado (puede requerir permisos)."""
    try:
        if IS_WINDOWS:
            subprocess.run(["sc", "start", "CloudflareWARP"], capture_output=True, timeout=10,
                           creationflags=_NO_WINDOW)
        else:
            subprocess.run(["systemctl", "start", "warp-svc"], capture_output=True, timeout=10)
    except Exception:
        pass


def _register_warp():
    """Registra el dispositivo (acepta los términos automáticamente)."""
    for args in (["registration", "new"], ["register"]):
        code, out = _warp(args, 25)
        low = out.lower()
        if code == 0 or "already" in low or "old registration" in low:
            return True
    return False


def warp_connect(max_wait=30, stop_evt=None):
    """Conecta WARP y espera a que esté realmente conectado. Devuelve 'on', 'off' o 'absent'."""
    st, _ = warp_status()
    if st == "absent":
        return "absent"
    if st == "on":
        return "on"
    if st == "nodaemon":
        _start_warp_service()
        time.sleep(2)
        st, _ = warp_status()
    if st == "noreg":
        _register_warp()

    code, out = _warp(["connect"], 25)
    if code != 0 and "registration" in out.lower():
        _register_warp()
        _warp(["connect"], 25)

    t0 = time.time()
    while time.time() - t0 < max_wait:
        st, _ = warp_status()
        if st == "on":
            return "on"
        if stop_evt is not None and stop_evt.is_set():
            break
        time.sleep(1.0)
    return "off"


def _set_vpn_state(state):
    with _vpn_lock:
        _vpn["state"] = state


def get_vpn_state():
    """Estado actual para la interfaz: on / connecting / off / absent."""
    return _vpn["state"]


def _mark_owner(owned):
    _vpn["owned"] = owned
    try:
        if owned:
            with open(VPN_OWNER_FILE, "w", encoding="utf-8") as f:
                f.write("furbo\n")
        elif os.path.exists(VPN_OWNER_FILE):
            os.remove(VPN_OWNER_FILE)
    except Exception:
        pass


def _vpn_worker():
    try:
        st, _ = warp_status()
        if st == "absent":
            _set_vpn_state("absent")
            return
        if st == "on":
            # Ya estaba conectada. Solo la apagaremos al salir si la dejó encendida
            # una ejecución anterior de Furbo (marca en disco).
            _vpn["owned"] = os.path.exists(VPN_OWNER_FILE)
            _set_vpn_state("on")
        else:
            _set_vpn_state("connecting")
            _mark_owner(True)
            _set_vpn_state("on" if warp_connect(30, _vpn_stop) == "on" else "off")

        # Vigilante: si WARP se cae, se pausa o la apagan, se vuelve a conectar.
        while not _vpn_stop.wait(VPN_WATCH_INTERVAL):
            st, _ = warp_status()
            if st == "on":
                _set_vpn_state("on")
            elif st == "connecting":
                _set_vpn_state("connecting")
            elif st == "absent":
                _set_vpn_state("absent")
                return
            else:
                _set_vpn_state("connecting")
                if not _vpn["owned"]:
                    _mark_owner(True)
                _set_vpn_state("on" if warp_connect(30, _vpn_stop) == "on" else "off")
    except Exception:
        _set_vpn_state("off")


def start_vpn():
    """Arranca la gestión de la VPN en segundo plano (no bloquea la interfaz)."""
    global _vpn_thread
    if _vpn_thread is not None:
        return
    if get_warp_bin() is None:
        _set_vpn_state("absent")
        return
    _vpn_stop.clear()
    _vpn["stopped"] = False
    _set_vpn_state("connecting")
    _vpn_thread = threading.Thread(target=_vpn_worker, daemon=True)
    _vpn_thread.start()


def stop_vpn():
    """Apaga la VPN si la encendió Furbo y restaura la red normal. Es idempotente."""
    with _vpn_lock:
        if _vpn["stopped"]:
            return
        _vpn["stopped"] = True
    _vpn_stop.set()
    t = _vpn_thread
    if t is not None and t.is_alive() and t is not threading.current_thread():
        t.join(timeout=4)  # que no termine de conectar justo después de apagarla
    if _vpn["owned"]:
        _warp(["disconnect"], 10)
        _mark_owner(False)
    if get_vpn_state() != "absent":
        _set_vpn_state("off")
    if not IS_WINDOWS:
        try:
            subprocess.run(["docker", "stop", "tor-proxy"], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=3)
        except Exception:
            pass


# Compatibilidad con el nombre antiguo
connect_vpn = start_vpn
disconnect_vpn = stop_vpn

# Registrar apagado garantizado al salir del proceso
atexit.register(stop_vpn)

_console_handler_ref = None


def _install_console_close_handler():
    """En Windows, apaga la VPN también si se cierra la ventana con la X."""
    global _console_handler_ref
    if not IS_WINDOWS:
        return
    try:
        import ctypes
        handler_type = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_uint)

        def _handler(ctrl_type):
            # 2 = cierre de consola, 5 = cierre de sesión, 6 = apagado del sistema
            if ctrl_type in (2, 5, 6):
                try:
                    stop_vpn()
                except Exception:
                    pass
            return 0  # seguir con el manejador por defecto (cerrar)

        _console_handler_ref = handler_type(_handler)
        ctypes.windll.kernel32.SetConsoleCtrlHandler(_console_handler_ref, True)
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
#  CONFIGURACIÓN Y FILTRO DE IDIOMA
# ══════════════════════════════════════════════════════════════════════════════
DEFAULT_LANGS = ["ES"]   # por defecto solo se muestran canales en español

LANG_NAMES = {
    "ES": "Español", "EN": "Inglés", "DE": "Alemán", "PL": "Polaco",
    "PT": "Portugués", "RU": "Ruso", "FR": "Francés", "IT": "Italiano",
    "NL": "Neerlandés", "TR": "Turco", "AR": "Árabe", "GR": "Griego",
    "RO": "Rumano", "SE": "Sueco", "NO": "Noruego", "DK": "Danés",
    "HR": "Croata", "RS": "Serbio", "CZ": "Checo", "HU": "Húngaro",
}

# Alias frecuentes -> código normalizado
LANG_ALIASES = {
    "ESP": "ES", "SPA": "ES", "CAS": "ES", "ESPAÑOL": "ES", "ESPANOL": "ES", "SPANISH": "ES",
    "ENG": "EN", "ENGLISH": "EN", "INGLES": "EN", "INGLÉS": "EN", "UK": "EN", "GB": "EN",
    "GER": "DE", "DEU": "DE", "GERMAN": "DE", "ALEMAN": "DE", "ALEMÁN": "DE",
    "POR": "PT", "PORTUGUES": "PT", "PORTUGUÊS": "PT", "PORTUGUESE": "PT", "BR": "PT",
    "FRA": "FR", "FRE": "FR", "FRENCH": "FR", "FRANCES": "FR", "FRANCÉS": "FR",
    "ITA": "IT", "ITALIAN": "IT", "ITALIANO": "IT",
    "RUS": "RU", "RUSSIAN": "RU", "RUSO": "RU",
    "POL": "PL", "POLISH": "PL", "POLACO": "PL",
    "TUR": "TR", "TURKISH": "TR", "TURCO": "TR",
    "NED": "NL", "NLD": "NL", "DUTCH": "NL",
    "ARA": "AR", "ARABIC": "AR", "ARABE": "AR", "ÁRABE": "AR",
}


def normalize_lang(raw):
    """Normaliza el idioma de una línea de canales ('es', 'Español', ' ESP ' -> 'ES')."""
    code = (raw or "").strip().upper()
    if not code:
        return "ES"  # sin idioma indicado = español (valor por defecto de Furbo)
    return LANG_ALIASES.get(code, code)


def lang_label(langs):
    """Texto corto para la cabecera: 'ES', 'ES+EN' o 'TODOS'."""
    if langs is None:
        return "TODOS"
    return "+".join(sorted(langs, key=lambda c: (c != "ES", c))) or "NINGUNO"


def load_config():
    """Lee config.json. Si no existe o está roto, devuelve la configuración por defecto."""
    cfg = {"langs": list(DEFAULT_LANGS)}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            if isinstance(data, dict):
                langs = data.get("langs")
                if langs == "all":
                    cfg["langs"] = "all"
                elif isinstance(langs, list):
                    cleaned = [normalize_lang(x) for x in langs if str(x).strip()]
                    if cleaned:
                        cfg["langs"] = sorted(set(cleaned))
        except Exception:
            pass
    return cfg


def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


def langs_from_config(cfg):
    """Convierte la config en el conjunto de idiomas visibles (None = todos)."""
    langs = cfg.get("langs")
    if langs == "all":
        return None
    return set(langs) if langs else set(DEFAULT_LANGS)


def config_from_langs(langs):
    return {"langs": "all" if langs is None else sorted(langs)}


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
            with open(FAV_FILE, "r", encoding="utf-8-sig") as f:
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
            with open(HIST_FILE, "r", encoding="utf-8-sig") as f:
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
    # Se deduplica solo por ID: dos canales distintos pueden llamarse igual
    hist = [h for h in hist if h.get("cid") != entry["cid"]]
    hist.insert(0, entry)
    save_history(hist)

# ── Lectura de líneas de canales ─────────────────────────────────────────────
def parse_channel_line(line):
    """Interpreta 'Nombre, Idioma, acestream://ID'. Devuelve (nombre, idioma, cid) o None.

    Se corta por la DERECHA, así los nombres que llevan comas
    ('Movistar, LaLiga 1') ya no rompen la línea.
    """
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    parts = [p.strip() for p in line.rsplit(",", 2)]
    if len(parts) < 3:
        return None
    name, lang, link = parts
    link = link.replace("acestream://", "").strip()
    cid = link.split()[0].split("?")[0] if link else ""
    if not name or not cid:
        return None
    return name, normalize_lang(lang), cid


def read_channel_file(fpath):
    """Devuelve la lista de (nombre, idioma, cid) de un .txt de canales."""
    out = []
    try:
        with open(fpath, "r", encoding="utf-8-sig", errors="replace") as fl:
            for line in fl:
                parsed = parse_channel_line(line)
                if parsed:
                    out.append(parsed)
    except Exception:
        pass
    return out


# ── Carga canales organizados por categorías/carpetas ─────────────────────────
def load_categories(fav_set=None, langs=None, lang_cids=None):
    """Carga todas las categorías.

    langs     -> conjunto de idiomas visibles (None = todos).
    lang_cids -> dict opcional que se rellena con {idioma: {ids}} de TODOS los
                 canales (sin filtrar), para poder mostrar el selector de idioma
                 y cuántos canales están ocultos.
    """
    if fav_set is None:
        fav_set = load_favorites()
    if lang_cids is None:
        lang_cids = {}

    def visible(lang):
        return langs is None or lang in langs

    def register(lang, cid):
        lang_cids.setdefault(lang, set()).add(cid)

    categories = []

    # 1. Historial de reproducción
    hist_entries = load_history()
    if hist_entries:
        hist_chs = []
        for h in hist_entries:
            cid = h.get("cid", "")
            lang = normalize_lang(h.get("lang", "ES"))
            if not visible(lang):
                continue
            hist_chs.append({
                "name": h.get("name", "Canal"),
                "lang": lang,
                "cid": cid,
                "url": f"http://127.0.0.1:6878/ace/getstream?id={cid}",
                "category": "historial",
                "fpath": h.get("fpath", ""),
                "is_fav": (cid in fav_set)
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
        if not (os.path.exists(c_dir) and os.path.isdir(c_dir)):
            continue
        for root, dirs, files in os.walk(c_dir):
            dirs.sort()
            for f in sorted(files):
                if not f.endswith(".txt"):
                    continue
                rel = os.path.relpath(root, c_dir).replace('\\', '/')
                stem = os.path.splitext(f)[0]
                # canales.txt da nombre a la carpeta; cualquier otro .txt es su propia categoría
                if f == "canales.txt":
                    key = rel if rel != "." else "canales"
                else:
                    key = stem if rel == "." else f"{rel}/{stem}"
                if key in seen_keys:
                    continue
                seen_keys.add(key)

                fpath = os.path.join(root, f)
                chs = []
                for name, lang, cid in read_channel_file(fpath):
                    register(lang, cid)
                    if not visible(lang):
                        continue
                    chs.append({
                        "name": name,
                        "lang": lang,
                        "cid": cid,
                        "url": f"http://127.0.0.1:6878/ace/getstream?id={cid}",
                        "category": key,
                        "fpath": fpath,
                        "is_fav": (cid in fav_set)
                    })
                if not chs:
                    continue

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

                cat_name, order = CAT_META.get(key, (key.upper().replace("_", " "), 900))
                categories.append({
                    "name": cat_name,
                    "key": key,
                    "order": order,
                    "fpath": fpath,
                    "channels": chs
                })

    # 3. Canales manuales sueltos en raíz
    manual_chs = []
    manual_file = None
    for mf in (os.path.join(ROOT_DIR, "canales_manuales.txt"),
               os.path.join(BASE_DIR, "canales_manuales.txt")):
        if os.path.exists(mf):
            manual_file = mf
            break
    if manual_file:
        for name, lang, cid in read_channel_file(manual_file):
            register(lang, cid)
            if not visible(lang):
                continue
            manual_chs.append({
                "name": name,
                "lang": lang,
                "cid": cid,
                "url": f"http://127.0.0.1:6878/ace/getstream?id={cid}",
                "category": "manuales",
                "fpath": manual_file,
                "is_fav": (cid in fav_set)
            })
    if manual_chs:
        manual_chs.sort(key=lambda x: (0 if x.get("is_fav") else 1))
        categories.append({
            "name": "CANALES AÑADIDOS MANUALMENTE",
            "key": "manuales",
            "order": 9100,
            "fpath": manual_file,
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
                all_unique_chs.append(ch.copy())

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

# ── Edición local de archivos de canales ─────────────────────────────────────
def delete_channel_file(ch):
    """Borra el canal del .txt donde está definido. Casa por ID (o por nombre solo si no hay ID)."""
    fpath = ch.get("fpath")
    cid = ch.get("cid")
    name = ch.get("name")
    if not fpath or not os.path.exists(fpath):
        return False
    try:
        with open(fpath, "r", encoding="utf-8-sig") as f:
            lines = f.readlines()

        new_lines = []
        deleted = False
        for line in lines:
            parsed = parse_channel_line(line)
            if parsed:
                l_name, _l_lang, l_cid = parsed
                if (cid and l_cid == cid) or (not cid and name and l_name == name):
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


def append_channel(dest_file, name, lang, cid):
    """Añade una línea de canal al final del archivo sin dejar líneas en blanco de más."""
    name = name.replace(",", " ").replace("\n", " ").strip()
    need_newline = False
    if os.path.exists(dest_file) and os.path.getsize(dest_file) > 0:
        with open(dest_file, "rb") as f:
            f.seek(-1, os.SEEK_END)
            need_newline = f.read(1) not in (b"\n", b"\r")
    with open(dest_file, "a", encoding="utf-8") as f:
        if need_newline:
            f.write("\n")
        f.write(f"{name}, {lang}, acestream://{cid}\n")


def remove_from_history(cid):
    if not cid:
        return
    hist = load_history()
    new_hist = [h for h in hist if h.get("cid") != cid]
    if len(new_hist) != len(hist):
        save_history(new_hist)

# ── Colores por idioma ───────────────────────────────────────────────────────
LANG_COLORS = {"ES": 1, "EN": 2, "DE": 3, "PL": 4, "PT": 5, "RU": 6, "FR": 5, "IT": 3}

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

# ── Lectura de teclado con soporte de tildes y ñ ─────────────────────────────
def get_key(stdscr):
    """Lee una tecla. Devuelve el código curses (flechas, etc.) o ord(carácter).

    Usa get_wch() para que las letras con tilde/ñ lleguen bien tanto en Linux
    (UTF-8) como en Windows. Devuelve -1 si no hay tecla (timeout) o es un
    carácter fuera de Latin-1.
    """
    try:
        k = stdscr.get_wch()
    except AttributeError:
        return stdscr.getch()
    except curses.error:
        return -1
    if isinstance(k, str):
        if len(k) == 1 and ord(k) < 256:
            return ord(k)
        return -1
    return k

def is_text_key(k):
    """True si la tecla es un carácter imprimible (ASCII o Latin-1: á é ñ ü ...)."""
    return 32 <= k <= 126 or 160 <= k <= 255

def fold_text(s):
    """Minúsculas y sin tildes, para buscar 'futbol' y encontrar 'Fútbol'."""
    import unicodedata
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")

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
    fresh = bool(default_val)   # el primer carácter escrito sustituye al valor por defecto
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

        ch = get_key(stdscr)
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
            fresh = False
        elif is_text_key(ch):
            if fresh:
                val = ""
                fresh = False
            val += chr(ch)

# ── Selector de idiomas (tecla L) ────────────────────────────────────────────
def choose_languages(stdscr, lang_cids, active_langs):
    """Diálogo para elegir qué idiomas se muestran.

    Devuelve (True, langs) si el usuario aplica cambios (langs=None significa
    'todos los idiomas') o (False, None) si cancela.
    """
    codes = set(lang_cids.keys()) | {"ES"}
    if active_langs:
        codes |= set(active_langs)
    codes = sorted(codes, key=lambda c: (c != "ES", -len(lang_cids.get(c, ())), c))
    checked = set(codes) if active_langs is None else set(active_langs)
    cur = 0
    top = 0
    msg = ""
    stdscr.timeout(-1)
    try:
        while True:
            h, w = stdscr.getmaxyx()
            box_w = min(62, max(30, w - 4))
            list_rows = max(1, min(len(codes), h - 11))
            box_h = list_rows + 7
            box_y = max(0, (h - box_h) // 2)
            box_x = max(0, (w - box_w) // 2)

            if cur < top:
                top = cur
            elif cur >= top + list_rows:
                top = cur - list_rows + 1

            stdscr.erase()
            for dy in range(box_h):
                safe_addstr(stdscr, box_y + dy, box_x, " " * box_w, curses.color_pair(8))
            safe_addstr(stdscr, box_y + 1, box_x + 2, "=== FILTRO DE IDIOMA ===", curses.color_pair(8) | curses.A_BOLD)
            safe_addstr(stdscr, box_y + 2, box_x + 2, "Marca los idiomas que quieres ver:"[:box_w - 4], curses.color_pair(8))

            for i in range(list_rows):
                idx = top + i
                if idx >= len(codes):
                    break
                code = codes[idx]
                n = len(lang_cids.get(code, ()))
                mark = "x" if code in checked else " "
                line = f" [{mark}] {code:<3} {LANG_NAMES.get(code, code):<12} ({n} canales)"
                attr = (curses.color_pair(10) | curses.A_BOLD) if idx == cur else curses.color_pair(8)
                safe_addstr(stdscr, box_y + 3 + i, box_x + 1, line.ljust(box_w - 2)[:box_w - 2], attr)

            foot_y = box_y + 3 + list_rows
            safe_addstr(stdscr, foot_y, box_x + 2, (msg or "")[:box_w - 4], curses.color_pair(8) | curses.A_BOLD)
            safe_addstr(stdscr, foot_y + 1, box_x + 2, "ESPACIO: marcar | A: todos | E: solo español"[:box_w - 4],
                        curses.color_pair(8) | curses.A_DIM)
            safe_addstr(stdscr, foot_y + 2, box_x + 2, "ENTER: aplicar | ESC: cancelar"[:box_w - 4],
                        curses.color_pair(8) | curses.A_DIM)
            stdscr.refresh()

            key = get_key(stdscr)
            msg = ""
            if key in (27, ord('q'), ord('Q')):
                return False, None
            elif key == curses.KEY_UP:
                cur = max(0, cur - 1)
            elif key == curses.KEY_DOWN:
                cur = min(len(codes) - 1, cur + 1)
            elif key == curses.KEY_PPAGE:
                cur = max(0, cur - list_rows)
            elif key == curses.KEY_NPAGE:
                cur = min(len(codes) - 1, cur + list_rows)
            elif key == curses.KEY_HOME:
                cur = 0
            elif key == curses.KEY_END:
                cur = len(codes) - 1
            elif key == ord(' '):
                code = codes[cur]
                if code in checked:
                    checked.discard(code)
                else:
                    checked.add(code)
            elif key in (ord('a'), ord('A')):
                checked = set(codes)
            elif key in (ord('e'), ord('E')):
                checked = {"ES"}
            elif key in (10, 13, curses.KEY_ENTER):
                if not checked:
                    msg = "Elige al menos un idioma."
                    continue
                if len(codes) > 1 and checked == set(codes):
                    return True, None      # todos los idiomas
                return True, set(checked)
    finally:
        stdscr.timeout(100)


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

    # Si la VPN aún se está conectando, esperar un momento (hasta 20 s) antes de pedir el stream
    for i in range(40):
        if get_vpn_state() != "connecting":
            break
        msg = f"{spinner[i % len(spinner)]} Esperando a que la VPN (WARP) conecte... {i // 2}s"
        safe_addstr(stdscr, status_y, 2, msg.ljust(w - 4), curses.color_pair(7) | curses.A_BOLD)
        stdscr.refresh()
        time.sleep(0.5)

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
        try:
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
        except FileNotFoundError:
            safe_addstr(stdscr, status_y, 2,
                        "ERROR: mpv no encontrado. Instalalo con ./install.sh".ljust(w - 4),
                        curses.color_pair(1) | curses.A_BOLD)
            stdscr.refresh()
            time.sleep(2.5)
    return peers

# ── Interfaz Curses ──────────────────────────────────────────────────────────
def draw_ui(stdscr, current_cat, items, selected, scroll, search, search_mode, status, engine_online,
            vpn_state="off", lang_text="ES"):
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

    # Indicador REAL del estado de la VPN (antes siempre mostraba "ON")
    if vpn_state == "on":
        safe_addstr(stdscr, 0, 0, " [VPN: ● ON] ", curses.color_pair(12) | curses.A_BOLD)
    elif vpn_state == "connecting":
        safe_addstr(stdscr, 0, 0, " [VPN: ◌ ...] ", curses.color_pair(7) | curses.A_BOLD)
    elif vpn_state == "absent":
        safe_addstr(stdscr, 0, 0, " [VPN: sin WARP] ", curses.color_pair(7) | curses.A_BOLD)
    else:
        safe_addstr(stdscr, 0, 0, " [VPN: ○ OFF] ", curses.color_pair(1) | curses.A_BOLD)

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
        nav = " Favoritos arriba | CARPETAS abajo (ENTER: Abrir | /: Buscar | l: Idioma | +: Añadir | q: Salir) "
    elif current_cat is None and search:
        nav = f" Búsqueda Global: '{search}' (ENTER: Fijar | ESC: Volver) "
    else:
        nav = f" [CARPETA: {current_cat['name']}]  (ESC: Volver | ENTER: Reproducir | f: Favorito | l: Idioma | p: Peers) "
    safe_addstr(stdscr, 1, 0, nav.center(w - 1), curses.color_pair(9))

    # ── Separador ──
    safe_hline(stdscr, 2, 0, curses.ACS_HLINE, w - 1)
    lang_chip = f" Idioma: {lang_text} (L) "
    safe_addstr(stdscr, 2, max(0, w - len(lang_chip) - 2), lang_chip, curses.color_pair(3) | curses.A_BOLD)
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
                name_w = max(1, w - len(count) - 12)
                line_name = cat_name[:name_w].ljust(name_w)

                if is_sel:
                    line = f" > [DIR]  {line_name}{count}"
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
    controls_bot = " ENTER: Abrir/Reproducir | f: Fav (★) | l: Idioma | /: Buscar | +: Añadir | p: Peers | d: Borrar | ESC: Volver | q: Salir"
    safe_addstr(stdscr, h - 1, 0, controls_bot[:w - 1], curses.color_pair(9) | curses.A_DIM)
    stdscr.refresh()

# ── Main ─────────────────────────────────────────────────────────────────────
def item_id(it):
    """Identificador estable de un elemento de la lista (canal o carpeta)."""
    if "channels" in it:
        return ("dir", it.get("key"))
    return ("ch", it.get("cid"))


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

    # ── Estado: idioma, favoritos y datos ──
    cfg = load_config()
    active_langs = langs_from_config(cfg)      # None = todos; por defecto {"ES"}
    fav_set = load_favorites()

    categories = []
    all_channels_flat = []
    known_cids = set()
    lang_cids = {}
    total_chs = 0
    hidden_chs = 0

    def reload_data():
        """Recarga canales desde disco aplicando el filtro de idioma activo."""
        nonlocal categories, all_channels_flat, known_cids, lang_cids, total_chs, hidden_chs
        new_cids = {}
        categories = load_categories(fav_set, active_langs, new_cids)
        lang_cids = new_cids
        all_channels_flat = []
        for cat in categories:
            if cat.get("key") not in ("historial", "todos"):
                all_channels_flat.extend(cat["channels"])
        visible_cids = {c["cid"] for c in all_channels_flat}
        known_cids = set()
        for s in lang_cids.values():
            known_cids |= s
        total_chs = len(visible_cids)
        hidden_chs = len(known_cids - visible_cids)

    def do_search(query):
        """Búsqueda por nombre (sin distinguir tildes/mayúsculas) sobre los idiomas visibles."""
        q = fold_text(query)
        seen, out = set(), []
        for c in all_channels_flat:
            if q in fold_text(c["name"]) and c["cid"] not in seen:
                seen.add(c["cid"])
                out.append(c)
        out.sort(key=lambda x: (0 if x.get("is_fav") else 1, x["name"].lower()))
        return out

    def rebind_cat(cat):
        if cat is None:
            return None
        for c in categories:
            if c["key"] == cat["key"]:
                return c
        return None

    def build_items(cat, query):
        if query:
            return do_search(query)
        if cat is None:
            return get_root_items(categories, fav_set, all_channels_flat)
        return cat["channels"][:]

    def home_status():
        s = f"{len(categories)} carpetas ({total_chs} canales) | Idioma: {lang_label(active_langs)}"
        if hidden_chs:
            s += f" | {hidden_chs} ocultos por idioma (L: cambiar)"
        return s

    reload_data()
    if not categories:
        stdscr.erase()
        if hidden_chs:
            safe_addstr(stdscr, 2, 2, f"No hay canales en el idioma elegido ({lang_label(active_langs)}).")
            safe_addstr(stdscr, 3, 2, f"Hay {hidden_chs} canales en otros idiomas.")
            safe_addstr(stdscr, 5, 2, "Borra config.json para volver al español o pulsa una tecla para salir...")
        else:
            safe_addstr(stdscr, 2, 2, "ERROR: No se encontraron canales en la carpeta canales/")
            safe_addstr(stdscr, 4, 2, "Pulsa una tecla para salir...")
        stdscr.refresh()
        stdscr.timeout(-1)
        stdscr.getch()
        return

    current_cat = None
    items = build_items(None, "")
    selected = 0
    scroll = 0
    search = ""
    search_mode = False
    status = home_status() + "  -  ENTER: abrir | f: Favorito | +: Añadir"

    h, w = stdscr.getmaxyx()
    ensure_engine(stdscr, h, w, h // 2)

    # Estado del motor en segundo plano: así la interfaz no se congela si AceStream está apagado
    engine_flag = {"online": False, "stop": False}

    def _engine_poll():
        while not engine_flag["stop"]:
            engine_flag["online"] = ace_api("/webui/api/service?method=get_version") is not None
            for _ in range(30):
                if engine_flag["stop"]:
                    return
                time.sleep(0.1)

    threading.Thread(target=_engine_poll, daemon=True).start()

    def refresh_items(keep_id=None):
        """Reconstruye la lista actual y recoloca el cursor sobre el mismo elemento."""
        nonlocal items, selected, scroll
        items = build_items(current_cat, search)
        if keep_id is not None:
            for i, it in enumerate(items):
                if item_id(it) == keep_id:
                    selected = i
                    return
        selected = max(0, min(selected, len(items) - 1))

    try:
        while True:
            h, w = stdscr.getmaxyx()
            list_h = max(1, h - 6)

            # Mantener el cursor siempre visible (evita que quede fuera de pantalla)
            selected = max(0, min(selected, max(0, len(items) - 1)))
            if selected < scroll:
                scroll = selected
            elif selected >= scroll + list_h:
                scroll = selected - list_h + 1
            scroll = max(0, min(scroll, max(0, len(items) - list_h)))

            draw_ui(stdscr, current_cat, items, selected, scroll, search, search_mode, status,
                    engine_flag["online"], get_vpn_state(), lang_label(active_langs))

            key = get_key(stdscr)
            if key == -1:
                continue

            # ── Modo búsqueda global ──
            if search_mode:
                if key == 27:  # ESC cancelar
                    search_mode = False
                    search = ""
                    refresh_items()
                    selected = 0
                    scroll = 0
                    status = home_status() if current_cat is None else f"{current_cat['name']} - {len(items)} canales"
                elif key in (curses.KEY_BACKSPACE, 127, 8):
                    search = search[:-1]
                    refresh_items()
                    selected = 0
                    scroll = 0
                elif key in (10, 13, curses.KEY_ENTER):  # ENTER fija búsqueda
                    search_mode = False
                    status = f"'{search}' - {len(items)} resultado(s) en idioma {lang_label(active_langs)}"
                    if hidden_chs:
                        status += f" | {hidden_chs} ocultos (L: cambiar idioma)"
                elif is_text_key(key):
                    search += chr(key)
                    refresh_items()
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
                refresh_items()
                selected = 0
                scroll = 0

            # ── Filtro de idioma (Tecla 'l') ──
            elif key in (ord('l'), ord('L')):
                changed, new_langs = choose_languages(stdscr, lang_cids, active_langs)
                if changed:
                    active_langs = new_langs
                    save_config(config_from_langs(active_langs))
                    reload_data()
                    search = ""
                    search_mode = False
                    current_cat = rebind_cat(current_cat)
                    refresh_items()
                    selected = 0
                    scroll = 0
                    status = f"Idioma: {lang_label(active_langs)} | {total_chs} canales visibles"
                    if hidden_chs:
                        status += f" | {hidden_chs} ocultos"
                else:
                    status = "Filtro de idioma sin cambios."

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
                lang_in = normalize_lang(lang_in)

                cid_in = prompt_input(stdscr, "AÑADIR CANAL (3/3)", "Enlace acestream:// o Content ID:")
                if not cid_in:
                    status = "Añadir canal cancelado."
                    continue
                cid_clean = cid_in.replace("acestream://", "").strip().split("?")[0]
                if not cid_clean:
                    status = "Error: El ID de AceStream no puede estar vacío."
                    continue
                if len(cid_clean) != 40 or any(c not in "0123456789abcdefABCDEF" for c in cid_clean):
                    status = "Error: el ID debe tener 40 caracteres hexadecimales (copia el enlace acestream:// completo)."
                    continue
                if cid_clean in known_cids:
                    status = "Ese canal ya existe en tu lista (se ha omitido)."
                    continue

                dest_file = os.path.join(ROOT_DIR, "canales_manuales.txt")
                if current_cat and current_cat.get("key") not in ("historial", "todos") and current_cat.get("fpath"):
                    dest_file = current_cat["fpath"]

                try:
                    append_channel(dest_file, ch_name_in, lang_in, cid_clean)
                    status = f"[OK] ¡Canal '{ch_name_in}' añadido correctamente a {os.path.basename(dest_file)}!"
                    if active_langs is not None and lang_in not in active_langs:
                        status += f" (idioma {lang_in} oculto por el filtro: pulsa L para verlo)"
                    reload_data()
                    current_cat = rebind_cat(current_cat)
                    refresh_items(("ch", cid_clean))
                except Exception as e:
                    status = f"Error al guardar canal: {e}"

            # ── Comprobar Peers / Estado del Canal (Tecla 'p' o 'P') ──
            elif key in (ord('p'), ord('P')):
                if items and selected < len(items):
                    target_item = items[selected]
                    if "channels" not in target_item:  # Es un canal
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
                    if "channels" not in target_item:  # Es un canal
                        ch = target_item
                        cid = ch.get("cid", "")
                        if cid in fav_set:
                            fav_set.remove(cid)
                            status = f"☆ Quitado de favoritos: {ch['name']}"
                        else:
                            fav_set.add(cid)
                            status = f"★ ¡Añadido a favoritos (Posición 1 y Fondo Dorado)!: {ch['name']}"
                        save_favorites(fav_set)
                        reload_data()
                        current_cat = rebind_cat(current_cat)
                        refresh_items(("ch", cid))

            # ── Borrar Canal Localmente (Tecla 'd', 'D', 'x' o Supr) ──
            elif key in (ord('d'), ord('D'), ord('x'), ord('X'), curses.KEY_DC):
                if items and selected < len(items):
                    target_item = items[selected]
                    if "channels" not in target_item:  # Es un canal
                        target_ch = target_item
                        prompt_text = f" ¿Eliminar localmente '{target_ch['name'][:25]}'? (s/n): "
                        safe_addstr(stdscr, h - 2, 0, prompt_text.ljust(w - 1), curses.color_pair(3) | curses.A_BOLD)
                        stdscr.refresh()
                        stdscr.timeout(-1)
                        conf_key = get_key(stdscr)
                        stdscr.timeout(100)

                        if conf_key in (ord('s'), ord('S'), ord('y'), ord('Y')):
                            cid = target_ch.get("cid", "")
                            delete_channel_file(target_ch)
                            remove_from_history(cid)
                            if cid in fav_set:
                                fav_set.remove(cid)
                                save_favorites(fav_set)

                            reload_data()
                            current_cat = rebind_cat(current_cat)
                            refresh_items()
                            status = f"[OK] Canal '{target_ch['name']}' eliminado localmente."
                        else:
                            status = "Borrado cancelado."

            elif key in (27, curses.KEY_BACKSPACE, 127, 8):
                if search:
                    search = ""
                    refresh_items()
                    selected = 0
                    scroll = 0
                    status = f"{len(items)} elementos"
                elif current_cat is not None:
                    current_cat = None
                    refresh_items()
                    selected = 0
                    scroll = 0
                    status = home_status() + "  -  ENTER: abrir | +: Añadir canal"

            elif key == curses.KEY_UP:
                if selected > 0:
                    selected -= 1

            elif key == curses.KEY_DOWN:
                if items and selected < len(items) - 1:
                    selected += 1

            elif key == curses.KEY_PPAGE:
                selected = max(0, selected - list_h)

            elif key == curses.KEY_NPAGE:
                if items:
                    selected = min(len(items) - 1, selected + list_h)

            elif key == curses.KEY_HOME:
                selected = 0

            elif key == curses.KEY_END:
                if items:
                    selected = len(items) - 1

            elif key in (10, 13, curses.KEY_ENTER) and items:  # ENTER
                target_item = items[selected]
                if "channels" in target_item:
                    # Entrar a la carpeta seleccionada
                    current_cat = target_item
                    items = current_cat["channels"][:]
                    selected = 0
                    scroll = 0
                    status = f"Carpeta: {current_cat['name']} ({len(items)} canales)  -  ENTER: Reproducir | f: Fav | l: Idioma | +: Añadir | p: Peers"
                else:
                    # Reproducir canal (favorito en menú principal o canal dentro de carpeta/búsqueda)
                    ch = target_item
                    ensure_engine(stdscr, h, w, h // 2)
                    url = ch["url"]
                    cid = ch.get("cid", "")
                    if not cid and "id=" in url:
                        cid = url.split("id=")[-1].split("&")[0]

                    record_channel_played(ch)
                    peers = start_stream(cid, ch["name"], stdscr, h - 4, w)
                    p_str = f"{peers} peers" if peers else "conectando"
                    status = f">  {ch['name']} [{ch['lang']}] - {p_str}"
                    # Refrescar historial manteniendo la posición del cursor
                    reload_data()
                    current_cat = rebind_cat(current_cat)
                    refresh_items(item_id(ch))

            elif key == curses.KEY_RESIZE:
                try:
                    curses.resizeterm(*stdscr.getmaxyx())
                except Exception:
                    pass
    finally:
        engine_flag["stop"] = True


def _handle_exit_signal(signum, frame):
    stop_vpn()
    sys.exit(0)


def _log_error(tb_text):
    try:
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n{tb_text}\n")
    except Exception:
        pass


if __name__ == "__main__":
    exit_code = 0
    try:
        signal.signal(signal.SIGINT, _handle_exit_signal)
        signal.signal(signal.SIGTERM, _handle_exit_signal)
        if hasattr(signal, 'SIGBREAK'):
            signal.signal(signal.SIGBREAK, _handle_exit_signal)
    except Exception:
        pass
    _install_console_close_handler()

    try:
        start_vpn()                 # en segundo plano: la interfaz arranca al instante
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass
    except Exception:
        # Antes los errores se tragaban en silencio y el programa se cerraba sin explicación
        exit_code = 1
        tb_text = traceback.format_exc()
        _log_error(tb_text)
        print("\n[!] Furbo se ha cerrado por un error inesperado.")
        print(f"    Detalles guardados en: {ERROR_LOG}")
        print(f"    {tb_text.strip().splitlines()[-1]}")
    finally:
        stop_vpn()
    sys.exit(exit_code)
