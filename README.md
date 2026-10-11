# ⚽ Furbo - Ver Canales y Fútbol en Windows y Linux

Una aplicación súper sencilla para ver canales de televisión y eventos deportivos en tu ordenador con un solo clic.

---

## 🚀 ¿Cómo se instala y usa? (Súper fácil)

Solo tienes que seguir estos 3 pasos:

### 1️⃣ Descargar el programa
1. Haz clic arriba en el botón verde que dice **`Code`** y luego en **`Download ZIP`**.
2. Descomprime la carpeta ZIP donde tú quieras (por ejemplo, en tu Escritorio).

---

### 2️⃣ Instalar (Solo se hace la primera vez)
1. Entra en la carpeta descomprimida.
2. Haz **doble clic en `instalar.bat`** (o ejecuta `./install.sh` en Linux).
3. Se abrirá una ventana que preparará todo de forma 100% automática (instala dependencias y la protección antibloqueo de operadoras).
4. Cuando termine y ponga que está completado, pulsa cualquier tecla para cerrarlo.

---

### 3️⃣ ¡A disfrutar!
1. Haz **doble clic en `furbo.bat`** (o `./furbo.sh` en Linux).
   - *Furbo detectará automáticamente la ruta de AceStream y lo iniciará si está cerrado.*
2. Elige el canal que quieras con las flechas del teclado y pulsa **ENTER**. ¡Se abrirá directamente en el reproductor de vídeo!

> 💡 **Nota:** Cada vez que abras `furbo.bat`, buscará y descargará automáticamente las novedades y nuevos canales sin que tengas que hacer nada.

---

## 🎮 Controles sencillos

| Tecla | ¿Qué hace? |
| :--- | :--- |
| **⬆️ / ⬇️ Flechas** | Moverte arriba y abajo por la lista de carpetas y canales |
| **ENTER** | Entrar en una carpeta o reproducir el canal seleccionado |
| **f** | **Marcar / desmarcar como Favorito (★)**: Pasa a la primera posición y se resalta con **fondo dorado** |
| **d** o **Supr** | **Borrar canal localmente**: Elimina el canal de la lista y del archivo con confirmación |
| **/** | Buscar cualquier canal por su nombre en tiempo real |
| **ESC / Retroceso**| Volver a la lista de carpetas o cancelar la búsqueda |
| **q** | Salir del programa |

---

## ➕ ¿Cómo añadir tus propios canales?

Abre el archivo **`canales_manuales.txt`** con el Bloc de Notas, escribe el nombre, idioma y enlace separados por comas (por ejemplo: `Mi Canal, ES, acestream://...`), guarda el archivo y aparecerá en Furbo.

---

## ❓ ¿Problemas comunes?

- **"No se abre ningún canal o se queda cargando":**  
  Furbo busca e inicia AceStream automáticamente. Si tu compañía de internet (Movistar, Orange, etc.) bloquea la señal, `instalar.bat` incluye la red antibloqueo de Cloudflare WARP para solucionarlo.
- **"Da error al abrir furbo.bat":**  
  Vuelve a hacer doble clic en `instalar.bat` para verificar que todo se haya instalado correctamente.
