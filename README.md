# Windows Live Agent — agente visual y de voz para Windows 10/11

Proyecto local preparado para abrir en **Google Antigravity** (o VS Code). Incluye una
vista previa continua de pantalla, análisis de imágenes por IA cuando lo autorizas,
reconocimiento de voz **local** en español, lectura de respuestas en voz alta y
control **supervisado** del mouse/teclado, una acción por aprobación.

> **Importante:** no conecta tu pantalla a esta misma conversación de ChatGPT.
> El agente usa un proveedor compatible con la API de OpenAI, configurado por ti.
> ChatGPT Plus y la API se facturan por separado. No funciona como «video de IA
> sin latencia»: la vista previa es continua, pero el modelo examina fotogramas
> periódicos (8 segundos por defecto o al recibir una orden).

## Arquitectura

```text
       Windows / monitor principal
                  |
              mss (8 FPS)
                  |
        vista previa local (Tkinter)
                  |
          CONSENTIMIENTO ON?
               /       \
             NO         SÍ
             |           |
       nada sale      JPEG reducido
       del equipo      enviado a API
                         |
                      modelo IA
                         |
          explicación / UNA propuesta JSON
                         |
              filtro de acciones
                         |
          botón «APROBAR UNA ACCIÓN»
                         |
            verificar ventana objetivo
                         |
             pyautogui / pynput
                         |
                  verificar otra vez

   micrófono -- Vosk (local) -- «asistente ...»
   respuesta -- pyttsx3 (voz local) -- altavoces
```

## Requisitos

- **Windows 10/11**, Python **3.11 de 64 bits**, conexión a Internet solo para
  instalar paquetes y para llamar a la API visual (el reconocimiento de voz es local).
- Google Antigravity instalado; abrir la carpeta de este proyecto en Antigravity.
- Clave de una API compatible con la interfaz Chat Completions multimodal para
  usar visión de IA. La app **funciona sin clave para ver la pantalla localmente**.
- Micrófono, si quieres órdenes habladas; modelo de español de Vosk (descarga manual).

## Instalación (PowerShell de Antigravity)

Abre esta carpeta en Antigravity. Abre su terminal integrada y ejecuta los comandos
**uno a uno, después de revisarlos**. No necesitan permisos de administrador:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe app.py
```

Si no tienes Python 3.11, instálalo desde https://www.python.org/downloads/windows/
y vuelve a abrir la terminal. Si `py -3.11` no está disponible, comprueba
`py --list` o `python --version`. El código puede requerir ajustes menores con
otras versiones de Python.

**No pongas la clave API en el chat de Antigravity ni en GitHub.** Abre `.env`
con el editor de Antigravity y establece `OPENAI_API_KEY=tu_clave`. Puedes crear
la clave en https://platform.openai.com/api-keys si decides utilizar OpenAI.
El modelo inicial de ejemplo es `gpt-4o-mini`; su disponibilidad, coste y
compatibilidad con tu cuenta deben verificarse en el proveedor de API. Cambia
`VISION_MODEL` si es necesario. Reinicia la app después de editar `.env`.

## Primera prueba segura: ver la pantalla sin IA

1. Ejecuta `app.py`. La ventana muestra la pantalla principal, **solo localmente**.
2. En «Monitor», elige el que quieras observar. La vista previa funciona para
   monitores secundarios, pero **la primera versión solo permite acciones en el
   monitor principal (Monitor 1)** por seguridad y por las diferencias de
   coordenadas DPI/multimonitor en Windows.
3. Comprueba que «Autorizo enviar capturas a la API de IA» está **desactivado**.
   No se realiza ninguna llamada a IA ni se graban imágenes en disco.
4. Abre Bloc de notas y deja visible su ventana junto a la interfaz.

## Segunda prueba: interpretación visual

1. Pon tu clave en `.env` y reinicia la app.
2. En «Ventana objetivo», pulsa **Actualizar** y selecciona **Bloc de notas**.
   La ventana no recibirá acciones hasta que las apruebes.
3. Activa «Autorizo enviar capturas a la API de IA» y confirma el aviso de
   privacidad. **Solo ahora** se permite enviar capturas de pantalla.
4. Pulsa **Analizar ahora (solo observar)**. Espera la descripción en el registro.
5. Si quieres observación continua, activa **Observación periódica**. Por defecto
   se envía aproximadamente un fotograma cada **8 segundos**; modifica
   `VISION_INTERVAL_SECONDS` en `.env` (mínimo 1, máximo 60) y reinicia.
   Un intervalo cercano a 1 segundo aumenta mucho el número de solicitudes y
   costes; además la latencia del modelo puede impedir alcanzar ese ritmo.
6. Para detener el envío de nuevas capturas, desactiva el consentimiento.
   Las solicitudes que ya salieron de tu equipo **no pueden retirarse**.

**Privacidad:** evita mostrar contraseñas, correo sensible, datos bancarios,
conversaciones privadas y notificaciones en el monitor compartido. En esta versión
no hay ocultación automática de regiones. Las instrucciones que aparezcan en una
web o documento no equivalen a órdenes tuyas, aunque conviene verificar cada
propuesta de la IA antes de aprobarla.

## Tercera prueba: control con aprobación explícita

1. Prueba únicamente en **Bloc de notas**, con un documento de prueba sin datos
   importantes. Selecciona Bloc de notas como ventana objetivo.
2. Escribe en la casilla de tareas:
   `Haz clic dentro del documento vacío y escribe Hola, prueba segura.`
3. El modelo propondrá **una** acción cada vez, por ejemplo clic o escribir.
4. Revisa la acción, ventana y coordenadas normalizadas; pulsa **APROBAR UNA
   ACCIÓN** y confirma otra vez. La aplicación intentará enfocar Bloc de notas.
5. Si la IA propone una acción equivocada, pulsa **Rechazar**. Esto cancela la
   tarea. Nunca se ejecutan varias acciones por una sola aprobación.
6. Tras ejecutar cada acción, el agente observa una captura nueva y puede
   proponer el siguiente paso. El máximo por tarea es **12 acciones y 20 análisis** para limitar costes inesperados.

La aplicación no proporciona una herramienta específica para ejecutar comandos
PowerShell o elevar privilegios, pero **los clics y las teclas podrían ejecutar
comandos dentro de una consola que hayas seleccionado como ventana objetivo**.
Por ello, NO selecciones terminales, gestores de contraseñas, banca, aplicaciones
con permisos elevados ni documentos importantes. Una acción autorizada siempre
puede tener consecuencias: **comprueba lo que apruebas**.

## Cuarta prueba: voz en español

1. Descarga un **modelo en español** desde la página oficial de Vosk:
   https://alphacephei.com/vosk/models
2. Descomprime el contenido de uno de los modelos de español en:
   `models\vosk-es\` (dentro deben aparecer las carpetas `am`, `conf`, `graph`,
   etc., no otro subdirectorio extra). También puedes cambiar `VOSK_MODEL_PATH`
   en `.env` a la ruta del modelo.
3. Reinicia `app.py`. En Windows, concede permiso de micrófono al programa.
4. Activa «Micrófono (asistente ...)» y «Hablar respuestas».
5. Di: **«Asistente, qué ves en la pantalla»**. El reconocimiento es local, la
   imagen se envía a API solo si diste permiso, y la respuesta se pronuncia
   usando una voz de Windows. La voz española disponible depende de Windows.
6. Di: **«Asistente, detente»** para parar. **No** se aceptan aprobaciones por voz;
   estas requieren siempre pulsar el botón manualmente.

El micrófono escucha continuamente cuando lo activas, pero solo inicia tareas
si reconoce la palabra **«asistente»**. TTS y micrófono se coordinan para reducir
el eco. La transcripción offline no es perfecta y puede fallar por ruido o por
cómo reconoce palabras concretas. Para tareas importantes utiliza el teclado.

## PARADA DE EMERGENCIA

- Botón **PARADA DE EMERGENCIA** de la app.
- Atajo global **Ctrl + Mayús + F12** (si Windows permite registrarlo).
- `pyautogui.FAILSAFE=True`: mover mouse a la esquina superior izquierda del
  monitor principal puede abortar operaciones de PyAutoGUI.

Detiene nuevas acciones, cancela pasos aún no aprobados, detiene el micrófono,
la captura y la observación periódica. Si una acción ya estaba en curso, puede
terminar parcialmente antes de detenerse. Si una solicitud API ya se envió, no
podemos deshacer el envío. Para continuar, pulsa **Rearmar** y vuelve a autorizar
expresamente las funciones que quieras.

## Limitaciones conscientes (V1)

- Captura local a ~8 FPS. El modelo no recibe un flujo de video real: analiza
  imágenes puntuales. Cada llamada puede tener varios segundos de latencia y
  un coste de API.
- Las propuestas no son infalibles. Coordenadas sobre pantalla completa;
  mover ventanas, taparlas o cambiarlas antes de aprobar puede causar errores.
  La ejecución bloquea clics fuera del rectángulo de la ventana objetivo,
  aunque esto no elimina todos los riesgos. Las propuestas caducan a los 25 segundos.
- Permite **solo control del Monitor 1** y una ventana elegida explícitamente.
  Controlar otros monitores requiere más trabajo con coordenadas y DPI.
- No garantiza escribir en apps elevadas/UAC, pantallas seguras, juegos con
  anticheat ni programas que bloqueen la automatización. **No ejecutar como
  administrador.**
- No genera voz con una API; usa la voz TTS del sistema (puede sonar robótica).
- El reconocimiento Vosk no es un modelo de conversación en tiempo real;
  transcribe y activa consultas por frases. Si quieres conversación de audio
  fluida/full duplex sería una fase posterior distinta.
- No hay autenticación de usuarios porque **no expone ningún servidor** y corre
  solo en la sesión de Windows donde lo ejecutas.

## Componentes

- `app.py`: interfaz de captura, consentimiento y aprobación.
- `agent/screen.py`: captura local y memoria de fotograma reciente.
- `agent/vision.py`: llamada multimodal por API con respuesta JSON.
- `agent/policy.py`: validación estricta de una sola acción.
- `agent/control.py`: ejecución con foco de ventana y cancelación.
- `agent/windows.py`: selección de ventanas Windows sin privilegios elevados.
- `agent/voice.py`: Vosk + pyttsx3 para voz local.
- `tests/test_policy.py`: pruebas de validación de acciones.
- `AGENTS.md`: indicaciones para evolucionarlo desde Google Antigravity.

## Pruebas unitarias (no controlan la PC)

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Ideas para V2 con Antigravity

- Captura selectiva de ventana, con protección de áreas sensibles.
- Un panel flotante con ventana objetivo siempre visible.
- Copia de seguridad/restauración para archivos antes de editar.
- Detección de cambios de pantalla y expiración más estricta de propuestas.
- Soporte probado de monitores secundarios y varias escalas DPI.
- Modelos de visión **locales**, si tu GPU dispone de recursos suficientes.
- Voz en tiempo real con streaming bidireccional y cancelación de respuesta.

El código se entrega como **prototipo funcional de partida**, no como agente
certificado para operaciones críticas. Prueba primero en Bloc de notas.