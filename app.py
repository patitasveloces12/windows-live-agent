"""Windows Live Agent — asistente local de escritorio, supervisado por el usuario.

Arranque: python app.py
Sin consentimiento, NO envía ninguna imagen ni mueve el mouse.
"""
import ctypes
import queue
import sys
import threading
import time
import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox, ttk

from PIL import Image, ImageTk

# Configure Windows DPI before importing PyAutoGUI: otherwise display scaling
# may cause the screenshot and injected mouse coordinates to differ.
if sys.platform == 'win32':
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

from agent import config
from agent.control import ActionExecutor
from agent.policy import parse_action
from agent.screen import ScreenStream
from agent.vision import analyze_image
from agent.voice import VoiceIO
from agent.windows import list_windows, window_title


@dataclass
class Pending:
    action: object
    frame: object
    proposed_at: float
    target_hwnd: int
    target_title: str
    generation: int


class DesktopAgentApp:
    def __init__(self, root):
        self.root = root
        self.root.title('Windows Live Agent · Control supervisado')
        self.root.geometry('1150x830')
        self.root.minsize(920, 680)
        self.events = queue.Queue()
        self.screen = ScreenStream(monitor_index=1, fps=8)
        self.control = ActionExecutor()
        self.voice = VoiceIO(config.VOSK_MODEL_PATH,
                             lambda text: self.events.put(('heard', text)),
                             lambda err: self.events.put(('error', err)))
        self.stopped = False
        self.busy = False
        self.action_running = False
        self.pending = None
        self.generation = 0
        self.active_task = ''
        self.actions_per_task = 0
        self.analyses_per_task = 0
        self.last_analysis_at = 0.0
        self.last_frame_ui = None
        self.history = []
        self.windows = {}
        self.selected_hwnd = None
        self.selected_title = ''
        self.monitor_var = tk.StringVar()
        self.target_var = tk.StringVar()
        self.share_var = tk.BooleanVar(value=False)
        self.auto_var = tk.BooleanVar(value=False)
        self.mic_var = tk.BooleanVar(value=False)
        self.speak_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value='Solo captura LOCAL · sin IA conectada')
        self.approval_var = tk.StringVar(value='Sin acciones pendientes')
        self._build_ui()
        self.refresh_windows()
        self.screen.start()
        self.log('Inicio seguro. Vista local activa; las imágenes NO se envían a la IA.')
        self.log('Parada de emergencia: Ctrl+Mayús+F12 o botón rojo. Alternativa: mouse a la esquina superior izquierda.')
        self._hotkeys = None
        self._start_hotkey()
        self.root.after(160, self._tick)
        self.root.protocol('WM_DELETE_WINDOW', self.close)

    def _build_ui(self):
        base = ttk.Frame(self.root, padding=12)
        base.pack(fill='both', expand=True)
        ttk.Label(base, text='Windows Live Agent', font=('Segoe UI', 19, 'bold')).pack(anchor='w')
        ttk.Label(base, text='Pantalla en vivo · voz local · IA visual opcional · una acción por aprobación',
                  foreground='#555').pack(anchor='w', pady=(1, 9))
        toolbar = ttk.Frame(base)
        toolbar.pack(fill='x', pady=(0, 8))
        tk.Button(toolbar, text='PARADA DE EMERGENCIA', command=self.emergency_stop,
                  bg='#b91c1c', fg='white', activebackground='#7f1d1d',
                  activeforeground='white', relief='flat', font=('Segoe UI', 9, 'bold'),
                  padx=9, pady=5).pack(side='left', padx=(0, 8))
        ttk.Button(toolbar, text='Rearmar', command=self.rearm).pack(side='left', padx=(0, 12))
        ttk.Label(toolbar, textvariable=self.status_var).pack(side='left')

        settings = ttk.LabelFrame(base, text='Configuración y consentimiento', padding=8)
        settings.pack(fill='x')
        first = ttk.Frame(settings)
        first.pack(fill='x')
        monitors = ScreenStream.monitors()
        self.monitor_mapping = {label: i for i, label in monitors}
        choices = list(self.monitor_mapping)
        self.monitor_var.set(choices[0] if choices else 'Sin monitor')
        ttk.Label(first, text='Monitor:').pack(side='left')
        cb = ttk.Combobox(first, textvariable=self.monitor_var, values=choices,
                          width=26, state='readonly')
        cb.pack(side='left', padx=(4, 12))
        cb.bind('<<ComboboxSelected>>', self.change_monitor)
        ttk.Label(first, text='Ventana objetivo:').pack(side='left')
        self.target_combo = ttk.Combobox(first, textvariable=self.target_var,
                                        width=46, state='readonly')
        self.target_combo.pack(side='left', padx=(4, 7), fill='x', expand=True)
        self.target_combo.bind('<<ComboboxSelected>>', self.select_target)
        ttk.Button(first, text='Actualizar', command=self.refresh_windows).pack(side='left')
        second = ttk.Frame(settings)
        second.pack(fill='x', pady=(8, 0))
        ttk.Checkbutton(second, text='Autorizo enviar capturas a la API de IA',
                        variable=self.share_var, command=self.toggle_sharing).pack(side='left', padx=(0, 16))
        ttk.Checkbutton(second, text='Observación periódica',
                        variable=self.auto_var, command=self.toggle_auto).pack(side='left', padx=(0, 16))
        ttk.Checkbutton(second, text='Micrófono ("asistente ...")',
                        variable=self.mic_var, command=self.toggle_microphone).pack(side='left', padx=(0, 16))
        ttk.Checkbutton(second, text='Hablar respuestas',
                        variable=self.speak_var).pack(side='left')

        body = ttk.Frame(base)
        body.pack(fill='both', expand=True, pady=(10, 8))
        left = ttk.LabelFrame(body, text='Vista previa LOCAL (nunca se guarda automáticamente)', padding=7)
        left.pack(side='left', fill='both', expand=True)
        self.preview = ttk.Label(left, text='Preparando captura...', anchor='center')
        self.preview.pack(fill='both', expand=True)
        right = ttk.Frame(body, width=320)
        right.pack(side='right', fill='y', padx=(10, 0))
        right.pack_propagate(False)
        task_frame = ttk.LabelFrame(right, text='Tu solicitud', padding=8)
        task_frame.pack(fill='x')
        self.task_entry = tk.Text(task_frame, height=5, wrap='word', font=('Segoe UI', 10))
        self.task_entry.pack(fill='x')
        self.task_entry.insert('1.0', 'Describe lo que ves en la pantalla.')
        ttk.Button(task_frame, text='Enviar solicitud', command=self.submit_task).pack(fill='x', pady=(7, 3))
        ttk.Button(task_frame, text='Analizar ahora (solo observar)',
                   command=lambda: self.request_analysis(observe_only=True, manual=True)).pack(fill='x', pady=3)
        ttk.Button(task_frame, text='Cancelar tarea actual', command=self.cancel_task).pack(fill='x', pady=3)

        approval = ttk.LabelFrame(right, text='Aprobación de cada acción', padding=8)
        approval.pack(fill='x', pady=(10, 0))
        ttk.Label(approval, textvariable=self.approval_var,
                  wraplength=300, justify='left').pack(fill='x')
        approval_buttons = ttk.Frame(approval)
        approval_buttons.pack(fill='x', pady=(9, 0))
        self.approve_button = ttk.Button(approval_buttons, text='APROBAR UNA ACCIÓN',
                                         command=self.approve, state='disabled')
        self.approve_button.pack(side='left', fill='x', expand=True, padx=(0, 4))
        self.reject_button = ttk.Button(approval_buttons, text='Rechazar',
                                        command=self.reject, state='disabled')
        self.reject_button.pack(side='left', fill='x', expand=True)
        ttk.Label(right, text='Ninguna frase de voz aprueba acciones.\nSolo este botón permite ejecutarlas.',
                  foreground='#555', justify='left').pack(anchor='w', pady=(7, 0))

        log_frame = ttk.LabelFrame(base, text='Registro local en memoria (no escribas claves en las tareas)', padding=7)
        log_frame.pack(fill='both', expand=False)
        self.log_box = tk.Text(log_frame, height=9, wrap='word', state='disabled', font=('Consolas', 9))
        self.log_box.pack(fill='both', expand=True)

    def log(self, text):
        self.log_box.config(state='normal')
        self.log_box.insert('end', time.strftime('%H:%M:%S') + '  ' + str(text)[:1000] + '\n')
        self.log_box.see('end')
        self.log_box.config(state='disabled')

    def _tick(self):
        if not self.root.winfo_exists():
            return
        for _ in range(15):
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            self._process_event(event)
        if not self.stopped:
            frame = self.screen.snapshot()
            if frame:
                image = frame.image
                # La imagen del monitor completo se muestra en tamaño reducido.
                w = max(240, self.preview.winfo_width() - 12)
                h = max(180, self.preview.winfo_height() - 12)
                preview_img = image.copy()
                preview_img.thumbnail((w, h), Image.Resampling.BILINEAR)
                self.last_frame_ui = ImageTk.PhotoImage(preview_img)
                self.preview.config(image=self.last_frame_ui, text='')
            if (self.share_var.get() and not self.busy and not self.pending and
                time.monotonic() - self.last_analysis_at >= config.ANALYSIS_INTERVAL and
                (self.active_task or self.auto_var.get())):
                self.request_analysis(observe_only=not bool(self.active_task))
        self.root.after(170, self._tick)

    def _process_event(self, event):
        kind = event[0]
        if kind == 'error':
            self.log('ERROR: ' + str(event[1]))
        elif kind == 'heard':
            self.on_heard(event[1])
        elif kind == 'emergency':
            self.emergency_stop()
        elif kind == 'analysis':
            _, generation, frame, target_hwnd, target_title, result = event
            if generation != self.generation or self.stopped:
                return
            self.busy = False
            self.status_var.set('Respuesta recibida')
            self.log('IA: ' + result['message'])
            self.history.append(result['message'][:400])
            self.history = self.history[-5:]
            if self.speak_var.get() and result['message']:
                self.voice.say(result['message'])
            if result['status'] == 'propose' and self.active_task:
                if self.actions_per_task >= config.MAX_ACTIONS_PER_TASK:
                    self.log('Límite de 12 acciones alcanzado. Tarea cancelada.')
                    self.cancel_task()
                    return
                try:
                    action = parse_action(result['action'])
                except Exception as exc:
                    self.log('Propuesta rechazada por política: ' + str(exc))
                    self.cancel_task()
                    return
                self.pending = Pending(action, frame, time.monotonic(),
                                       target_hwnd, target_title, generation)
                self.approval_var.set(f'Propuesta: {action.describe()}\nDestino: {target_title}\nComprueba la pantalla antes de aprobar.')
                self.approve_button.config(state='normal')
                self.reject_button.config(state='normal')
                self.status_var.set('Esperando aprobación humana')
            elif result['status'] == 'done' and self.active_task:
                self.active_task = ''
                self.log('Tarea finalizada por IA; ninguna acción adicional pendiente.')
        elif kind == 'analysis_error':
            _, generation, error = event
            if generation == self.generation:
                self.busy = False
                self.active_task = ''
                self.log('ERROR DE ANÁLISIS: ' + error)
                self.status_var.set('Error de IA; revisar registro')
        elif kind == 'executed':
            _, generation, result = event
            if generation != self.generation:
                return
            self.busy = False
            self.action_running = False
            self.status_var.set('Acción terminada; verificando en nueva captura')
            self.log(result)
            if 'NO completada' in result:
                self.cancel_task()
            else:
                self.last_analysis_at = time.monotonic() - config.ANALYSIS_INTERVAL + 1.5

    def refresh_windows(self):
        windows = [(hwnd, title) for hwnd, title in list_windows()
                   if title != self.root.title()]
        self.windows = {f'{title[:63]} · #{hwnd}': (hwnd, title) for hwnd, title in windows}
        self.target_combo.config(values=list(self.windows))
        if self.target_var.get() not in self.windows:
            self.target_var.set('')
            self.selected_hwnd = None
            self.selected_title = ''
        self.log(f'{len(self.windows)} ventanas candidatas. Elige explícitamente una para acciones.')

    def select_target(self, _=None):
        value = self.windows.get(self.target_var.get())
        if value:
            self.selected_hwnd, self.selected_title = value
            self.cancel_task(silent=True)
            self.log('Ventana objetivo seleccionada: ' + self.selected_title)

    def change_monitor(self, _=None):
        monitor = self.monitor_mapping.get(self.monitor_var.get())
        if monitor:
            self.cancel_task(silent=True)
            self.screen.select_monitor(monitor)
            self.log('Monitor de captura cambiado. Para acciones, usa monitor principal (1).')

    def toggle_sharing(self):
        if self.share_var.get():
            if not config.API_KEY:
                self.share_var.set(False)
                messagebox.showinfo('Configurar API',
                    'Falta OPENAI_API_KEY en .env. Configura la clave y reinicia la aplicación.')
                return
            consent = messagebox.askyesno('Consentimiento explícito',
                'Las capturas podrán enviarse a tu proveedor de IA configurado para analizarlas.\n\n'
                'Podrían incluir ventanas, mensajes, información privada o notificaciones.\n'
                '¿Autorizas el envío de capturas mientras esta opción esté activada?')
            if not consent:
                self.share_var.set(False)
                return
            self.log('Consentimiento activo: permites análisis visual por API.')
        else:
            self.auto_var.set(False)
            self.cancel_task(silent=True)
            self.log('Envío de capturas desactivado. Solicitudes en curso no pueden retirarse.')

    def toggle_auto(self):
        if self.auto_var.get() and not self.share_var.get():
            self.auto_var.set(False)
            messagebox.showinfo('Permiso necesario', 'Primero autoriza expresamente el envío de capturas.')
            return
        self.log('Observación periódica ' + ('activada' if self.auto_var.get() else 'desactivada'))

    def toggle_microphone(self):
        if self.mic_var.get():
            try:
                self.voice.start_mic()
                self.log('Micrófono activado. Usa: "asistente qué ves" o "asistente abre...".')
            except Exception as exc:
                self.mic_var.set(False)
                messagebox.showerror('Micrófono no disponible', str(exc))
        else:
            self.voice.stop_mic()
            self.log('Micrófono desactivado.')

    def submit_task(self):
        text = self.task_entry.get('1.0', 'end').strip()
        self.start_task(text)

    def start_task(self, text):
        if self.action_running:
            self.log('Hay una acción en curso; espera a que termine o usa la parada de emergencia.')
            return
        if not text:
            return
        if self.stopped:
            messagebox.showwarning('Agente detenido', 'Pulsa Rearmar primero.')
            return
        if not self.share_var.get():
            messagebox.showinfo('Consentimiento', 'Activa primero "Autorizo enviar capturas a la API de IA".')
            return
        if not self.selected_hwnd:
            messagebox.showinfo('Ventana objetivo',
                'Elige una ventana objetivo para que las acciones nunca se ejecuten en una ventana equivocada.')
            return
        self.cancel_task(silent=True)
        self.active_task = text[:1000]
        self.actions_per_task = 0
        self.analyses_per_task = 0
        self.history.clear()
        self.log('Solicitud: ' + text[:250])
        self.last_analysis_at = 0
        self.request_analysis(observe_only=False, manual=True)

    def request_analysis(self, observe_only=False, manual=False):
        if self.stopped or self.busy or self.pending:
            return
        if not self.share_var.get():
            if manual:
                messagebox.showinfo('Permiso necesario', 'No se envían capturas sin autorizar primero la API.')
            return
        frame = self.screen.snapshot()
        if not frame or time.monotonic() - frame.captured_at > 2:
            if manual:
                self.log('Sin captura reciente. Comprueba el monitor o la captura.')
            return
        if not observe_only and (not self.selected_hwnd or not window_title(self.selected_hwnd)):
            self.log('No hay ventana objetivo válida seleccionada')
            return
        target_hwnd = self.selected_hwnd
        # Títulos de ventanas (p. ej. Bloc de notas *) pueden cambiar al editar.
        # Tomamos el título actual para detectar cambios SOLO entre proponer y aprobar.
        target_title = window_title(target_hwnd) if target_hwnd else ''
        if not observe_only:
            if self.analyses_per_task >= config.MAX_ANALYSES_PER_TASK:
                self.log('Límite de 20 análisis por tarea alcanzado. Tarea cancelada para limitar costes.')
                self.cancel_task()
                return
            self.analyses_per_task += 1
        request = '¿Qué observas ahora? Resume solo los cambios relevantes.' if observe_only else self.active_task
        generation = self.generation
        self.busy = True
        self.last_analysis_at = time.monotonic()
        self.status_var.set('Analizando captura por IA ...')

        def worker():
            try:
                result = analyze_image(frame, request, observe_only, self.history[-5:])
                self.events.put(('analysis', generation, frame, target_hwnd, target_title, result))
            except Exception as exc:
                self.events.put(('analysis_error', generation, str(exc)))

        threading.Thread(target=worker, daemon=True, name='vision-api').start()

    def approve(self):
        p = self.pending
        if not p or self.stopped or self.busy:
            return
        if (p.generation != self.generation or
            time.monotonic() - p.proposed_at > config.PROPOSAL_TIMEOUT_SECONDS or
            time.monotonic() - p.frame.captured_at > config.PROPOSAL_TIMEOUT_SECONDS):
            self.log('Propuesta caducada. No se ejecutó nada; realiza un nuevo análisis.')
            self.cancel_task()
            return
        if (self.selected_hwnd != p.target_hwnd or
                window_title(p.target_hwnd) != p.target_title):
            self.log('Ventana objetivo diferente. Acción descartada.')
            self.cancel_task()
            return
        if p.frame.monitor_index != self.screen.monitor_index:
            self.log('Monitor diferente. Acción descartada.')
            self.cancel_task()
            return
        if not messagebox.askyesno('Confirmar UNA acción',
                f'¿Ejecutar exactamente esta acción en la ventana indicada?\n\n'
                f'{p.action.describe()}\n\nDestino: {p.target_title}\n\n'
                'No se ejecutará ninguna otra acción sin otra aprobación.'):
            self.reject()
            return
        # Consumir la propuesta ANTES de arrancar el worker: nunca es reutilizable.
        self.pending = None
        self.approve_button.config(state='disabled')
        self.reject_button.config(state='disabled')
        self.approval_var.set('Acción aprobada; ejecutando exactamente un paso ...')
        self.busy = True
        self.action_running = True
        self.actions_per_task += 1
        gen = self.generation

        def worker():
            try:
                self.control.execute(p.action, p.frame, p.target_hwnd, p.target_title)
                self.events.put(('executed', gen, 'Acción ejecutada: ' + p.action.describe()))
            except Exception as exc:
                self.events.put(('executed', gen, 'Acción NO completada: ' + str(exc)))
        threading.Thread(target=worker, daemon=True, name='approved-action').start()

    def reject(self):
        if self.pending:
            self.log('Acción rechazada por el usuario.')
        self.cancel_task()

    def cancel_task(self, silent=False):
        self.generation += 1
        self.pending = None
        self.active_task = ''
        self.actions_per_task = 0
        self.analyses_per_task = 0
        if not self.action_running:
            self.busy = False
        # No ejecuta ninguna acción nueva. Si hay una en curso, usar PARADA.
        self.approve_button.config(state='disabled')
        self.reject_button.config(state='disabled')
        self.approval_var.set('Sin acciones pendientes')
        if not silent:
            self.log('Tarea cancelada; no quedan propuestas aprobables.')

    def emergency_stop(self):
        self.stopped = True
        self.control.emergency_stop()
        self.screen.stop()
        self.voice.stop_mic()
        self.share_var.set(False)
        self.auto_var.set(False)
        self.mic_var.set(False)
        self.cancel_task(silent=True)
        self.status_var.set('DETENIDO · sin captura nueva ni acciones')
        self.log('PARADA DE EMERGENCIA. Puede haber una solicitud ya enviada a la API; su resultado se descartará.')

    def rearm(self):
        if not self.stopped:
            return
        self.stopped = False
        self.control.rearm()
        index = self.monitor_mapping.get(self.monitor_var.get(), 1)
        self.screen = ScreenStream(monitor_index=index, fps=8)
        self.screen.start()
        self.busy = False
        self.action_running = False
        self.status_var.set('Rearmado · solo captura local; reactiva permisos por separado')
        self.log('Agente rearmado. Necesitas volver a activar el envío de capturas.')

    def on_heard(self, transcript):
        if self.stopped or not self.mic_var.get():
            return
        # La escucha ambiental no inicia órdenes sin palabra de activación.
        normalized = transcript.casefold()
        pos = normalized.find('asistente')
        if pos < 0:
            return
        phrase = transcript[pos + len('asistente'):].strip(' ,.:;')
        if not phrase:
            return
        self.log('Voz reconocida: ' + phrase[:200])
        if any(word in phrase.casefold() for word in ('detente', 'para ya', 'parada de emergencia')):
            self.emergency_stop()
            return
        if phrase.casefold().startswith('cancela'):
            self.cancel_task()
            return
        # La voz NUNCA se usa para aprobar una acción.
        if 'aprueba' in phrase.casefold() or 'autoriza' in phrase.casefold():
            self.log('La aprobación por voz está deshabilitada: utiliza el botón.')
            return
        self.task_entry.delete('1.0', 'end')
        self.task_entry.insert('1.0', phrase)
        self.start_task(phrase)

    def _start_hotkey(self):
        try:
            from pynput import keyboard
            self._hotkeys = keyboard.GlobalHotKeys({
                '<ctrl>+<shift>+<f12>': lambda: self.events.put(('emergency',))
            })
            self._hotkeys.daemon = True
            self._hotkeys.start()
            self.log('Atajo global de parada registrado: Ctrl+Mayús+F12.')
        except Exception as exc:
            self.log('Atajo global no disponible: ' + str(exc))

    def close(self):
        self.emergency_stop()
        self.voice.close()
        if self._hotkeys:
            try:
                self._hotkeys.stop()
            except Exception:
                pass
        self.root.destroy()


def set_dpi_awareness():
    if sys.platform != 'win32':
        return
    try:
        # Windows 10+, DPI-aware por monitor (coordenadas físicas de MSS).
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def main():
    if sys.platform != 'win32':
        raise SystemExit('Este proyecto está diseñado para Windows 10/11.')
    set_dpi_awareness()
    root = tk.Tk()
    style = ttk.Style(root)
    if 'vista' in style.theme_names():
        style.theme_use('vista')
    DesktopAgentApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
