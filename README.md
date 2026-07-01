# MC Create

Gestor de servidores de Minecraft para Windows con interfaz gráfica. Permite crear, configurar y administrar múltiples servidores simultáneamente sin tocar la terminal.

## Características

- Múltiples servidores corriendo a la vez, cada uno con su propia consola
- Descarga automática del servidor (Vanilla, Paper, Fabric, Forge)
- Java integrado — no necesitas instalarlo
- Consola en tiempo real por servidor
- Backups manuales y automáticos
- Gestión de jugadores (whitelist, op, ban)
- Instalación de mods (.jar)
- Edición visual de `server.properties`
- Minimiza a la bandeja del sistema si hay servidores activos al cerrar

---

## Instalación

1. Descarga la carpeta `MC Create` desde [Releases](../../releases)
2. Ejecuta `MC Create.exe`

No requiere instalación ni Python.

---

## Paneles y opciones

### Barra lateral — Lista de servidores

Muestra todos los servidores creados. Los servidores activos aparecen resaltados en verde con un indicador `●`. Puedes tener varios corriendo a la vez.

- **＋ Nuevo servidor** — abre el diálogo de creación.

---

### Diálogo: Nuevo servidor

Formulario para crear un servidor desde cero. Descarga el archivo `.jar` automáticamente.

| Campo | Descripción |
|---|---|
| **Nombre** | Identificador único del servidor (ej. `mi-servidor`) |
| **Tipo** | `Vanilla` · `Paper` · `Fabric` · `Forge` |
| **Versión** | Lista de versiones disponibles cargada en tiempo real desde la API oficial |
| **Memoria RAM** | Presets de 512 MB a 32 GB, o valor personalizado en MB (mínimo 256 MB) |
| **Núcleos de CPU** | `Todos (auto)` o un número específico de núcleos lógicos |

---

### Panel principal — Cabecera

Muestra el nombre del servidor seleccionado y su estado actual (`● Ejecutando` en verde / `● Detenido` en rojo).

---

### Barra de controles

| Botón | Función |
|---|---|
| **▶ Iniciar** | Arranca el servidor. Si Java no está disponible, lo descarga automáticamente. |
| **■ Detener** | Envía el comando `stop` para un cierre limpio. |
| **⚡ Kill** | Mata el proceso del servidor forzosamente. Puede haber pérdida de datos no guardados. |
| **🧩 Mods** | Gestiona los mods instalados (solo Fabric, Forge y Paper). |
| **👥 Jugadores** | Abre la gestión de jugadores. |
| **💾 Backup** | Abre el panel de backups. |
| **📁 Carpeta** | Abre la carpeta del servidor en el Explorador de Windows. |
| **⚙ Ajustes** | Abre el editor visual de `server.properties`. |
| **🗑 Eliminar** | Elimina el servidor y todos sus archivos (pide confirmación). |

---

### Tarjetas de información

Fila superior (clicables):

| Tarjeta | Función al hacer clic |
|---|---|
| **🌐 IP LOCAL** | Copia `IP:PUERTO` al portapapeles |
| **🔌 PUERTO** | Abre un diálogo para cambiar el puerto (1024–65535) |
| **💾 RAM** | Abre el diálogo para cambiar la RAM asignada |
| **⚡ NÚCLEOS** | Abre el diálogo para cambiar los núcleos de CPU asignados |

Fila inferior (solo lectura):

| Tarjeta | Descripción |
|---|---|
| **📦 VERSIÓN** | Tipo y versión del servidor |
| **👥 JUGADORES** | Jugadores conectados en tiempo real |
| **⏱ TIEMPO** | Tiempo de actividad desde el último inicio (`HH:MM:SS`) |

---

### Consola

Muestra la salida del servidor seleccionado en tiempo real. Cada servidor tiene su propia consola independiente — al cambiar de servidor en la barra lateral se carga su historial.

- **Campo de comando** — escribe comandos de Minecraft directamente (sin `/`).
- **Enter / botón Enviar** — envía el comando al servidor.

---

### Comportamiento al cerrar

- **Con servidores activos** — la app se minimiza a la bandeja del sistema (icono junto al reloj). Doble clic para volver a abrirla. Clic derecho → "Detener servidor y salir" para parar todo y cerrar.
- **Sin servidores activos** — se cierra directamente.
- **Al reabrir con servidores corriendo** — detecta automáticamente los servidores que siguen activos y los muestra como en ejecución. La consola no estará disponible para esos servidores; usa "⚡ Kill" para detenerlos.

---

### Diálogo: Ajustes (`server.properties`)

Editor visual de los parámetros más comunes. Requiere haber iniciado el servidor al menos una vez.

| Parámetro | Descripción |
|---|---|
| **Modo de juego** | Supervivencia · Creativo · Aventura · Espectador |
| **Dificultad** | Pacífica · Fácil · Normal · Difícil |
| **Espacios** | Número máximo de jugadores (1–200) |
| **Lista blanca** | Activa/desactiva la whitelist |
| **Modo online (premium)** | Si está activo, solo cuentas de pago pueden entrar |
| **Volar** | Permite volar en modo supervivencia |
| **PvP** | Permite el daño entre jugadores |
| **Forzar modo de juego** | Aplica el modo de juego configurado a todos al entrar |
| **Protección de spawn** | Radio de bloques protegidos alrededor del spawn (0–100) |
| **Mobs hostiles** | Activa/desactiva la generación de enemigos |
| **Animales** | Activa/desactiva la generación de animales |
| **NPCs (aldeanos)** | Activa/desactiva la generación de aldeanos |
| **Bloques de comandos** | Permite el uso de bloques de comandos |
| **Distancia de visión** | Chunks cargados alrededor de cada jugador (2–32) |
| **Dist. simulación** | Chunks con lógica activa (mobs, redstone) (2–32) |
| **Descripción (MOTD)** | Texto que aparece en la lista de servidores de Minecraft |
| **Puerto** | Puerto de red del servidor |

- **Aplicar** — guarda los cambios en `server.properties`.
- **Abrir archivo raw** — abre el archivo directamente en el editor de texto predeterminado.

> Los cambios solo se aplican al reiniciar el servidor.

---

### Diálogo: Jugadores

Lista todos los jugadores que han entrado al servidor al menos una vez.

| Columna | Descripción |
|---|---|
| **Jugador** | Nombre. Muestra `⭐ Admin` si tiene op o `🚫 Baneado` si está baneado. |
| **Horas** | Tiempo total jugado en el servidor |
| **Whitelist** | `✓` (verde) si está en la whitelist, `✗` (rojo) si no. Clic para cambiar. |
| **Admin** | `⭐` (naranja) si tiene op, `☆` si no. Clic para dar/quitar op. |
| **Ban** | `Banear` / `Desbanear`. Banear requiere confirmación. |

---

### Diálogo: Mods

Gestiona los archivos `.jar` de la carpeta `mods/` del servidor.

> Solo disponible en servidores de tipo Fabric, Forge o Paper.

- **＋ Añadir mod (.jar)** — abre un selector de archivos para instalar uno o varios mods.
- **Eliminar** — borra el mod de la carpeta (pide confirmación).

---

### Diálogo: Backup

#### Backup automático

| Opción | Descripción |
|---|---|
| **Intervalo** | Desactivado · Cada hora · Cada 2/4/6/12/24 horas |
| **Guardar** | Activa el intervalo seleccionado |

El backup automático genera y sobreescribe el archivo `auto_backup.zip` en cada ejecución.

#### Backup manual

- **💾 Crear backup ahora** — crea un archivo `backup_YYYYMMDD_HHMMSS.zip` con la carpeta `world`.
- Barra de progreso durante la compresión.

#### Lista de backups

| Botón | Descripción |
|---|---|
| **Restaurar** | Reemplaza la carpeta `world` con la del backup (pide confirmación). El servidor debe estar detenido. |
| **Eliminar** | Borra el archivo de backup (pide confirmación). |

---

## Estructura del proyecto

```
mc-create/
├── main.py              # Punto de entrada
├── app.py               # Interfaz gráfica (CustomTkinter)
├── server_manager.py    # Lógica de gestión de servidores
├── icon.ico             # Icono de la aplicación
├── jre/                 # Java Runtime incluido
└── mc_create.spec       # Configuración de PyInstaller
```

---

## Compilar el ejecutable

Requiere Python 3.11+ y las dependencias instaladas.

```bash
pip install customtkinter pillow requests pyinstaller pystray
pyinstaller mc_create.spec -y
```

El ejecutable se genera en `dist/MC Create/`.

---

## Aviso legal

MC Create descarga automáticamente el software de servidor de Minecraft desde los servidores oficiales de Mojang/Microsoft. Al usar MC Create aceptas el [EULA de Minecraft](https://www.minecraft.net/es-es/eula).

MC Create no está afiliado ni respaldado por Mojang ni Microsoft. Minecraft es una marca registrada de Mojang AB.

---

## Licencia

GNU General Public License v3 — ver [LICENSE](LICENSE)
