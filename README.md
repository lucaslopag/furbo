<div align="center">
  <h1>Furbo - AceStream TV</h1>
  <p>Lanzador de canales AceStream con interfaz de terminal.<br>Compatible con <b>Windows</b> y <b>Linux</b>.</p>
</div>

---

## Windows - Instalacion

1. **Descarga el proyecto:** Haz clic en el boton verde **"Code"** > **"Download ZIP"** y descomprimelo. O bien:
   ```cmd
   git clone https://github.com/lucaslopag/furbo.git
   cd furbo
   ```

2. **Ejecuta el instalador** (solo la primera vez):
   Haz doble clic en **`instalar.bat`**. Esto instalara automaticamente Python, Git, VLC y las dependencias necesarias.

3. **Usa Furbo:**
   - Abre **AceStream Engine** (el icono azul en la bandeja del sistema)
   - Haz doble clic en **`furbo.bat`**
   - Elige canal con las flechas y pulsa ENTER

> **Actualizaciones automaticas:** Cada vez que abras `furbo.bat`, se descargaran automaticamente los ultimos cambios del repositorio (nuevos canales, mejoras, etc).

---

## Linux - Instalacion

```bash
git clone https://github.com/lucaslopag/furbo.git
cd furbo
chmod +x lanzar.sh install.sh
./install.sh        # Instala Docker + mpv (solo la primera vez)
./lanzar.sh         # Lanza Furbo
```

---

## Actualizar la lista de canales

Edita el archivo `Acestream_Links.ods` con LibreOffice o Excel. Formato: Nombre | Idioma | Enlace AceStream.

---

## Controles

| Tecla | Accion |
|-------|--------|
| Flechas | Mover por la lista |
| ENTER | Reproducir canal |
| / | Buscar canal |
| ESC | Limpiar busqueda |
| PgUp/PgDn | Pagina arriba/abajo |
| q | Salir |

---

*Disclaimer: Este proyecto es un lanzador que facilita la conexion a la red publica P2P de AceStream. No aloja, transmite ni distribuye contenido multimedia.*
