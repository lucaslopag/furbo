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
   - *Por defecto solo verás los canales **en español**. Los de otros idiomas están ocultos y puedes mostrarlos con la tecla **L** (ver [Filtro de idioma](#-filtro-de-idioma)).*
   - *La VPN antibloqueo (Cloudflare WARP) se conecta sola al abrir Furbo, sin ventanas ni cookies que aceptar, y se apaga al cerrarlo.*

> 💡 **Nota:** Cada vez que abras `furbo.bat`, buscará y descargará automáticamente las novedades y nuevos canales sin que tengas que hacer nada.

---

## 🎮 Controles sencillos

| Tecla | ¿Qué hace? |
| :--- | :--- |
| **⬆️ / ⬇️ Flechas** | Moverte arriba y abajo por la lista de carpetas y canales |
| **ENTER** | Entrar en una carpeta o reproducir el canal seleccionado |
| **f** | **Marcar / desmarcar como Favorito (★)**: Pasa a la primera posición y se resalta con **fondo dorado** |
| **+** | **Añadir canal nuevo**: Añadir un canal directamente desde la interfaz gráfica |
| **p** | **Comprobar peers/estado**: Verifica si el canal seleccionado está emitiendo en directo y muestra peers |
| **d** o **Supr** | **Borrar canal localmente**: Elimina el canal de la lista y del archivo con confirmación |
| **l** | **Filtro de idioma**: elige qué idiomas se muestran (por defecto solo español) |
| **/** | Buscar cualquier canal por su nombre en tiempo real, sin importar mayúsculas ni tildes (solo entre los idiomas visibles, favoritos arriba) |
| **ESC / Retroceso**| Volver a la lista de carpetas o cancelar la búsqueda |
| **q** | Salir del programa limpiamente |

---

## 🌍 Filtro de idioma

Cada canal tiene un idioma (`ES`, `EN`, `DE`, `PL`, `PT`, `RU`...). **Por defecto Furbo solo muestra los canales en español** y oculta el resto, tanto en las carpetas como en la búsqueda y en "TODOS LOS CANALES".

- Arriba a la derecha (línea separadora) siempre verás el filtro activo, por ejemplo `Idioma: ES (L)`.
- En la barra de estado aparece cuántos canales están ocultos por idioma.
- Pulsa **`L`** para abrir el selector:

| Tecla | ¿Qué hace? |
| :--- | :--- |
| **⬆️ / ⬇️** | Moverte por la lista de idiomas (con el número de canales de cada uno) |
| **ESPACIO** | Marcar / desmarcar un idioma |
| **a** | Marcar todos los idiomas |
| **e** | Dejar solo español |
| **ENTER** | Aplicar |
| **ESC** | Cancelar sin cambiar nada |

- La elección se **guarda en `config.json`** y se mantiene la próxima vez que abras Furbo (cada ordenador tiene la suya). Para volver al valor por defecto basta con borrar ese archivo o pulsar `L` → `e` → `ENTER`.
- Los idiomas se leen del segundo campo de cada línea de los archivos de canales (`Nombre, ES, acestream://...`), así que cualquier idioma nuevo que añadas aparece solo en el selector. Se aceptan también `es`, `ESP`, `Español`, `EN`, `ENG`, etc.
- Si añades un canal con `+` en un idioma que está oculto, Furbo te avisa de que lo verás al pulsar `L`.

---

## ➕ ¿Cómo añadir tus propios canales?

Puedes pulsar **`+`** directamente dentro de la aplicación para añadir un canal de forma guiada (el idioma por defecto es `ES`: si escribes otro, sustituye al anterior), o bien abrir el archivo **`canales_manuales.txt`** con el Bloc de Notas y escribir: `Nombre, ES, acestream://...`.
Si el canal ya existe en tu lista, Furbo no lo duplica. El ID debe tener 40 caracteres hexadecimales.

---

## 💻 Uso en Windows (PowerShell y CMD)
- Para iniciar Furbo ejecuta: `.\furbo.bat`
- Para subir cambios a tu repositorio ejecuta: `.\subir.bat`
*(Nota: En Windows usa los archivos `.bat`. No ejecutes los archivos `.sh` ya que pertenecen a Linux).*

---

## 🛡️ VPN antibloqueo (Cloudflare WARP)

Furbo gestiona WARP por ti:

- **Se activa sola**: al abrir Furbo acepta los términos de uso y registra el equipo automáticamente (no hay que abrir la app de WARP ni aceptar cookies/avisos) y espera a que la conexión esté realmente establecida. La cabecera muestra el estado real: `[VPN: ● ON]`, `[VPN: ◌ ...]` (conectando), `[VPN: ○ OFF]` o `[VPN: sin WARP]`.
- **Se mantiene sola**: mientras Furbo está abierto, un vigilante comprueba WARP cada 10 segundos y la reconecta si se cae o alguien la apaga.
- **Se apaga sola al salir** (con `q`, Ctrl+C o cerrando la ventana), pero **solo si la encendió Furbo**: si ya tenías WARP conectado tú, no te la toca.
- Si pulsas ENTER en un canal mientras WARP aún está conectando, Furbo espera unos segundos antes de abrir el stream.

---

## ❓ ¿Problemas comunes?

- **"No se abre ningún canal o se queda cargando":**  
  Furbo busca e inicia AceStream automáticamente. Si tu compañía de internet (Movistar, Orange, etc.) bloquea la señal, `instalar.bat` incluye la red antibloqueo de Cloudflare WARP para solucionarlo.
- **"Da error al abrir furbo.bat":**  
  Vuelve a hacer doble clic en `instalar.bat` para verificar que todo se haya instalado correctamente. Si Furbo se cierra por un fallo interno, el detalle queda guardado en `backend/acestream_error.log`.
- **"La VPN sale como `[VPN: ○ OFF]` o `[VPN: sin WARP]`":**  
  `sin WARP` significa que Cloudflare WARP no está instalado: ejecuta `instalar.bat`. Si sale `OFF`, abre la app de WARP una vez y comprueba que no hay otra VPN activa; Furbo seguirá intentando reconectar cada 10 segundos.
- **"No veo un canal que sé que existe":**  
  Mira si está en otro idioma: pulsa **`L`** y marca los idiomas que quieras ver. La barra de estado indica cuántos canales hay ocultos.
- **"Cerré la ventana de golpe y WARP se quedó encendida":**  
  Abre Furbo y ciérralo con `q`: detecta que la dejó encendida Furbo y la apaga.

---

## 🆕 Cambios recientes

- **Filtro de idioma** (tecla `L`): por defecto solo se muestran canales en español; la elección se guarda en `config.json`.
- **VPN WARP más fiable**: acepta términos y se registra sola, espera a estar conectada, se reconecta si se cae, muestra el estado real y solo se apaga al salir si la encendió Furbo. Se ha corregido `instalar.bat`, que no registraba WARP cuando la instalación iba bien.
- **Búsqueda mejorada**: ignora tildes y mayúsculas, sin resultados repetidos, respeta el filtro de idioma y permite escribir tildes y ñ.
- **Arreglos**: nombres de canal con comas, línea seleccionada cortada, cursor que podía quedar fuera de pantalla, añadir canales desde "Historial"/"Todos" (iban al archivo equivocado), líneas en blanco al añadir canales, borrado que podía eliminar canales distintos con el mismo nombre, congelación de la interfaz con AceStream apagado, errores silenciosos (ahora se guardan en `backend/acestream_error.log`) y mensaje claro si falta `mpv`.
- **`furbo.bat`**: las actualizaciones ya no se bloquean si tienes canales modificados en local (usa `--autostash`) y avisa si no se pudieron aplicar.

