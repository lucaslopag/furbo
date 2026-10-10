<div align="center">
  <h1>⚽ Furbo (AceStream TV para Linux)</h1>
  <p>Una aplicación de terminal elegante y automática para reproducir canales de AceStream en Linux (especialmente Fedora/Wayland), eludiendo bloqueos de ISP y asegurando una reproducción en alta calidad.</p>
</div>

---

## 📺 Características

- **Menú Interactivo en Terminal:** Interfaz TUI construida con `curses` para moverse con las flechas, buscar canales fácilmente e iniciar la reproducción.
- **Antibloqueo de ISP Integrado:** Configura automáticamente un túnel transparente a través de la red Tor para eludir los bloqueos de operadoras (Movistar, Orange, Vodafone) a los *trackers* de AceStream en España, asegurando que la conexión P2P se establezca siempre.
- **Reproducción Fluida y Optimizada:** Utiliza `mpv` (en lugar de VLC) configurado con búferes gigantes de RAM y aceleración por hardware (GPUHQ), evitando la pantalla negra y los *lags* comunes en Wayland.
- **Gestión Automática del Motor:** Arranca y gestiona de fondo los contenedores Docker del motor de AceStream y Tor sin que el usuario tenga que interactuar con ellos.
- **Lista de Canales Desacoplada:** Añade o modifica canales simplemente editando el archivo `Acestream_Links.ods` adjunto (formato Excel/LibreOffice).

## 🚀 Instalación y Uso (Versión Precompilada)

Si no quieres tocar código fuente, ve a la pestaña de **[Releases](https://github.com/lucaslopag/furbo/releases)** y descarga el archivo `acestream-tv-linux.zip`.

1. **Descomprime** el archivo zip en una carpeta.
2. **Prepara el sistema (Solo la primera vez):** Abre una terminal en esa carpeta y ejecuta el instalador para asegurar que tienes Docker y mpv instalados:
   ```bash
   ./install.sh
   ```
   *(Nota: Se te pedirá reiniciar el ordenador tras la instalación para que Docker funcione sin contraseña).*
3. **¡A disfrutar!** Haz doble clic en el archivo ejecutable `acestream-tv` (o córrelo desde la terminal con `./acestream-tv`) para abrir el menú de canales.

## 📝 Actualizar la lista de Canales

Para añadir tus propios enlaces o actualizar los canales:
1. Abre el archivo `Acestream_Links.ods` que está junto al ejecutable.
2. Sigue el formato (Nombre, Idioma, Enlace AceStream).
3. Guarda el archivo. La aplicación cargará automáticamente los nuevos canales la próxima vez que la abras.

## 💻 Para Desarrolladores (Instalar desde el código fuente)

Si quieres clonar este repositorio y correr/compilar el código Python tú mismo:

### Requisitos Previos:
- Docker instalado y corriendo (y tu usuario añadido al grupo `docker`).
- Reproductor de vídeo `mpv` instalado (`sudo dnf install mpv` o `sudo apt install mpv`).
- Instalar las dependencias de Python:
  ```bash
  pip install -r requirements.txt
  ```

### Ejecutar:
Puedes iniciar la interfaz usando:
```bash
./lanzar.sh
# o bien:
python3 acestream_launcher.py
```

### Compilar a Ejecutable:
```bash
pip install pyinstaller
pyinstaller --onefile --name acestream-tv acestream_launcher.py
```
El archivo final compilado aparecerá en la carpeta `dist/`.

---
*Disclaimer: Este proyecto es meramente un lanzador que facilita la conexión a la red pública P2P de AceStream. No aloja, transmite ni distribuye ningún contenido multimedia protegido por derechos de autor.*
