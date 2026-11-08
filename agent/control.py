"""Ejecución limitada a una única acción aprobada. Solo equipo local."""
import threading
import time

from pynput.keyboard import Controller as KeyboardController
from pynput.mouse import Controller as MouseController, Button
import pyautogui

from .policy import Action
from .windows import focus_window, window_title, window_rectangle

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.10


class ActionExecutor:
    def __init__(self):
        self.cancel = threading.Event()
        self.keyboard = KeyboardController()
        self.mouse = MouseController()

    def emergency_stop(self):
        self.cancel.set()

    def rearm(self):
        self.cancel.clear()

    def execute(self, action: Action, frame, target_hwnd, target_title):
        if self.cancel.is_set():
            raise RuntimeError('Parada de emergencia activa')
        if frame.monitor_index != 1:
            raise RuntimeError('Por seguridad, la versión inicial solo controla el monitor 1 (principal).')
        if not window_title(target_hwnd) or window_title(target_hwnd) != target_title:
            raise RuntimeError('La ventana objetivo ha cambiado o se ha cerrado')
        if not focus_window(target_hwnd):
            raise RuntimeError('No se pudo enfocar la ventana objetivo. No se envió ninguna acción.')
        time.sleep(0.15)
        if self.cancel.is_set():
            return
        if action.type in ('move', 'click'):
            x = frame.left + min(frame.image.width - 1, round(action.x * frame.image.width / 1000))
            y = frame.top + min(frame.image.height - 1, round(action.y * frame.image.height / 1000))
            rect = window_rectangle(target_hwnd)
            if not rect or not (rect[0] <= x < rect[2] and rect[1] <= y < rect[3]):
                raise RuntimeError('El punto propuesto cae fuera de la ventana objetivo. Acción bloqueada.')
            # pyautogui conserva su FAILSAFE (esquina superior izquierda).
            pyautogui.moveTo(x, y, duration=0.18)
            if self.cancel.is_set():
                return
            if action.type == 'click':
                pyautogui.click(button=action.button)
        elif action.type == 'scroll':
            pyautogui.scroll(action.amount)
        elif action.type == 'press_key':
            pyautogui.press(action.key)
        elif action.type == 'hotkey':
            pyautogui.hotkey(*action.keys, interval=0.08)
        elif action.type == 'type_text':
            for letter in action.text:
                if self.cancel.is_set():
                    break
                self.keyboard.type(letter)
                time.sleep(0.025)
