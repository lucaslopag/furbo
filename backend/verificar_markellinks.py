#!/usr/bin/env python3
"""
Validador y organizador de canales de MarkelLinks para Furbo
Descarga la lista, prueba los canales mediante AceStream Engine y los organiza en canales_manuales.txt / carpetas.
"""
import urllib.request
import json
import time
import threading
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

ACE_API = "http://127.0.0.1:6878"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)

def check_cid(cid, timeout=6):
    """
    Verifica si un content_id de AceStream está activo (emite señal y tiene datos/peers).
    """
    play_url = f"{ACE_API}/ace/getstream?id={cid}"
    opened = False
    peers = 0
    
    def trigger():
        nonlocal opened
        try:
            req = urllib.request.Request(play_url, headers={'User-Agent': 'VLC/3.0.0'})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                chunk = r.read(1024)
                if len(chunk) > 0:
                    opened = True
        except Exception:
            pass

    t = threading.Thread(target=trigger, daemon=True)
    t.start()

    # Sondear durante unos segundos
    for _ in range(int(timeout * 2)):
        time.sleep(0.5)
        if opened:
            return True, max(peers, 1)
        try:
            with urllib.request.urlopen(f"{ACE_API}/ace/stat/{cid}", timeout=1) as resp:
                data = json.loads(resp.read().decode())
                if "response" in data:
                    p = data["response"].get("peers", 0)
                    st = data["response"].get("status", "")
                    peers = max(peers, p)
                    if opened or (p > 0 and st in ("dl", "buf", "prebuf")):
                        return True, peers
        except Exception:
            pass

    return opened, peers

def stop_stream():
    try:
        urllib.request.urlopen(f"{ACE_API}/webui/api/service?method=stop", timeout=1)
    except Exception:
        pass

def fetch_m3u_channels():
    url = "https://listam3u.markellinks.app/lista.m3u"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    content = urllib.request.urlopen(req, timeout=15).read().decode('utf-8', errors='ignore')

    lines = content.splitlines()
    categories = {}
    current_category = "OTROS"
    current_name = "Canal"

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("#EXTINF:"):
            m = re.search(r'group-title=\"([^\"]+)\"', line)
            if m:
                current_category = m.group(1).strip()
            parts = line.split(",", 1)
            if len(parts) > 1:
                raw_title = parts[1].strip()
                clean_title = re.sub(r'\s*-->.*$', '', raw_title).strip()
                current_name = clean_title if clean_title else raw_title
            else:
                current_name = "Canal"
        elif line.startswith("acestream://") or (len(line) == 40 and not line.startswith("#")):
            cid = line.replace("acestream://", "").strip()
            categories.setdefault(current_category, []).append({
                "name": current_name,
                "cid": cid
            })
    return categories

def main():
    print("[*] Descargando canales desde markellinks.app...")
    try:
        categories = fetch_m3u_channels()
    except Exception as e:
        print(f"[!] No se pudo descargar la lista ({e}). Comprueba tu conexion e intentalo de nuevo.")
        sys.exit(1)
    total_found = sum(len(chs) for chs in categories.values())
    print(f"[+] {total_found} canales encontrados en {len(categories)} categorias.")

    # Guardar raw
    raw_path = os.path.join(ROOT_DIR, "backend", "markel_channels_raw.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(categories, f, indent=2, ensure_ascii=False)
    print(f"[OK] Canales base guardados en {raw_path}")

    # Verificar canales categoría por categoría
    results_by_cat = {}
    
    # Crear carpeta 'canales' para organizar por categorías en archivos .txt
    canales_dir = os.path.join(ROOT_DIR, "canales")
    os.makedirs(canales_dir, exist_ok=True)

    print("\n[*] Comprobando canales activos en AceStream...")
    for cat_name, ch_list in categories.items():
        print(f"\n--- Comprobando {cat_name} ({len(ch_list)} canales) ---")
        active_channels = []
        for ch in ch_list:
            cid = ch["cid"]
            name = ch["name"]
            sys.stdout.write(f"  > Verificando {name[:30]}... ")
            sys.stdout.flush()
            ok, peers = check_cid(cid, timeout=6)
            stop_stream()
            if ok:
                print(f"[ONLINE] ({peers} peers)")
                active_channels.append({
                    "name": name,
                    "cid": cid,
                    "peers": peers,
                    "category": cat_name
                })
            else:
                print("[OFFLINE]")

        results_by_cat[cat_name] = active_channels
        
        # Guardar archivo por categoría si tiene canales o dejar el template
        # Una carpeta por categoria con su canales.txt (es el formato que lee Furbo)
        cat_slug = re.sub(r'[^a-zA-Z0-9_\-]', '_', cat_name.lower())
        cat_dir = os.path.join(canales_dir, cat_slug)
        os.makedirs(cat_dir, exist_ok=True)
        cat_filepath = os.path.join(cat_dir, "canales.txt")
        with open(cat_filepath, "w", encoding="utf-8") as f:
            f.write(f"# Categoria: {cat_name}\n")
            f.write(f"# Canales comprobados y funcionando ({len(active_channels)} online)\n\n")
            for ach in active_channels:
                # Se asume espanol; cambia el idioma aqui si la lista trae canales de otros paises
                safe_name = ach['name'].replace(",", " ")
                f.write(f"{safe_name}, ES, acestream://{ach['cid']}\n")

    # Resumen y volcado general
    summary_path = os.path.join(ROOT_DIR, "backend", "canales_verificados.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(results_by_cat, f, indent=2, ensure_ascii=False)

    print("\n" + "="*50)
    print("VERIFICACION COMPLETADA")
    print("="*50)
    total_active = sum(len(l) for l in results_by_cat.values())
    print(f"Total canales activos encontrados: {total_active} / {total_found}")
    for cat, l in results_by_cat.items():
        print(f"  - {cat}: {len(l)} activos")

if __name__ == "__main__":
    main()
