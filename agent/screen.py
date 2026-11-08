import threading
import time
from dataclasses import dataclass

import mss
from PIL import Image


@dataclass
class Frame:
    image: Image.Image
    captured_at: float
    monitor_index: int
    left: int
    top: int


class ScreenStream:
    """Captura continua local. No envía imágenes a ningún sitio."""

    def __init__(self, monitor_index=1, fps=8):
        self.monitor_index = monitor_index
        self.fps = min(15, max(1, fps))
        self._lock = threading.Lock()
        self._frame = None
        self._stop = threading.Event()
        self._thread = None
        self.last_error = ''

    @staticmethod
    def monitors():
        with mss.mss() as capture:
            return [(i, f'Monitor {i} · {m["width"]}×{m["height"]}')
                    for i, m in enumerate(capture.monitors) if i > 0]

    def select_monitor(self, index):
        with self._lock:
            self.monitor_index = int(index)
            self._frame = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name='screen-capture')
        self._thread.start()

    def stop(self):
        self._stop.set()

    def snapshot(self):
        with self._lock:
            f = self._frame
            if f is None:
                return None
            return Frame(f.image.copy(), f.captured_at, f.monitor_index, f.left, f.top)

    def _loop(self):
        try:
            with mss.mss() as capture:
                while not self._stop.is_set():
                    start = time.monotonic()
                    with self._lock:
                        index = self.monitor_index
                    if index < 1 or index >= len(capture.monitors):
                        self.last_error = 'Monitor no disponible'
                        self._stop.wait(0.5)
                        continue
                    mon = capture.monitors[index]
                    shot = capture.grab(mon)
                    image = Image.frombytes('RGB', shot.size, shot.rgb)
                    frame = Frame(image, time.monotonic(), index, mon['left'], mon['top'])
                    with self._lock:
                        self._frame = frame
                    self._stop.wait(max(0.0, 1.0 / self.fps - (time.monotonic() - start)))
        except Exception as exc:
            self.last_error = f'Error de captura: {exc}'
