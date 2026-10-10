# Contexto Completo: Arquitectura de AceStream en Linux

Este documento recopila detalladamente todos los retos técnicos y las soluciones que hemos implementado para conseguir reproducir enlaces de AceStream en un entorno Linux (Fedora), de manera transparente y automatizada, simulando la experiencia que tendrías en Windows.

---

## 1. El Problema Inicial
A diferencia de Windows, donde AceStream tiene un cliente oficial con interfaz que corre en la bandeja del sistema, en Linux el soporte oficial es pobre o inexistente, y las versiones antiguas suelen estar rotas por dependencias obsoletas de Python (`pkg_resources`, etc).

Para solucionarlo de la forma más limpia posible y sin ensuciar el sistema, decidimos usar **Docker**.

## 2. El Motor AceStream (Docker)
En lugar de instalar el motor nativo, usamos la imagen de Docker `jopsis/acestream:latest`.
Este contenedor actúa como el "daemon" de fondo. Contiene la versión de Android/Linux de AceStream (`3.2.17`) y levanta un servidor HTTP local en el puerto `6878`.
La interfaz gráfica (el script de Python) se comunica con este puerto para decirle al motor: *"Oye, empieza a descargar este Content ID y devuélveme una URL local de vídeo"*.

## 3. El Bloqueo de las Operadoras (ISP) y la Solución con Tor
**El Reto:**
Aunque BitTorrent es una red P2P (difícil de bloquear), AceStream tiene un paso previo centralizado: para convertir el ID del enlace (`e572a...`) en un archivo `.torrent` real, el motor debe conectarse a los servidores de AceStream (`r.acestream.org`). En España, **las operadoras bloquean estas conexiones a nivel de DNS e IP**. El motor se quedaba "pensando" infinitamente.

**La Solución:**
1. Instalamos un segundo contenedor Docker: `dockage/tor-privoxy`. Esto levanta una red Tor privada en tu ordenador, exponiendo un puerto proxy HTTP (`8118`).
2. Arrancamos el motor de AceStream inyectándole variables de entorno (`HTTP_PROXY=http://127.0.0.1:8118`).
3. De esta forma, el motor se conecta a los servidores censurados a través de la red Tor, saltándose el bloqueo de la operadora instantáneamente.

**Evitando el "Lag":**
Si todo el tráfico de AceStream pasara por Tor, el vídeo en HD se cortaría porque Tor es lento. Para solucionarlo, añadimos la variable `NO_PROXY=127.0.0.1,localhost,192.168...` y dejamos que el P2P use la red "Host". Así, Tor **solo** se usa para el archivo inicial, pero la descarga del vídeo se hace directamente por tu fibra óptica.

## 4. El Problema de la Pantalla Negra (Códecs y Wayland)
Una vez que el streaming funcionaba, la imagen se veía en negro y solo se escuchaba el audio.

**El Reto:**
Fedora Linux incluye un paquete de códecs gratuito (`ffmpeg-free`) por motivos de patentes en EE.UU. Este paquete no puede decodificar los vídeos **H.264** ni **HEVC** que usan los canales HD de deportes. Además, VLC tiene problemas conocidos renderizando vídeo nativo en Wayland (el servidor gráfico de Fedora).

**La Solución:**
1. Cambiamos el reproductor predeterminado a **`mpv`**, que es infinitamente mejor manejando Wayland y aceleración por hardware en Linux.
2. Añadimos el repositorio de la comunidad **RPMFusion** e instalamos el paquete `ffmpeg` completo sin censura, sustituyendo a `ffmpeg-free`. Ahora tu ordenador tiene las librerías `libavcodec` completas para decodificar H.264 por hardware o software sin fallar.

## 5. El Script de Lanzamiento (acestream_launcher.py)
Para unir todas las piezas, programé un script en Python 3 usando la librería `curses` para crear un menú bonito e interactivo en la terminal.

**¿Qué hace el script de Python?**
- **Carga de Canales:** Lee dinámicamente un archivo `.ods` (hoja de cálculo) local llamado `Acestream_Links.ods` y extrae los nombres, idiomas y los enlaces (IDs).
- **Gestión Automática:** Cuando le das a reproducir, el script comprueba (con permisos sudo que debes proveer) si los contenedores Docker del Proxy Tor y de AceStream están encendidos. Si no lo están, los levanta, los configura y espera a que respondan.
- **Auto-Búfer:** Llama al API del motor y se queda esperando hasta que el canal engancha suficientes *peers* a través de la red.
- **Reproducción sin Lag:** Llama a `mpv` pasándole los parámetros especiales: `--force-window=immediate` (para evitar bugs de arranque), `--hwdec=auto` (para usar tu tarjeta gráfica) y búferes gigantes de RAM (`--cache=yes --demuxer-max-bytes=1000M`) para asegurar que el canal vaya 100% fluido.

## 6. Ejecución Rápida
Finalmente, creamos el archivo ejecutable `./lanzar.sh` para que arrancar todo este ecosistema (levantar servidores de fondo, gestionar proxys antibloqueo, parsear bases de datos de canales y abrir el reproductor) requiera tan solo un clic o un comando sencillo en tu terminal.
