"""Enumeración y selección explícita de la ventana que recibirá las acciones."""
import ctypes
import sys
from ctypes import wintypes


def _user32():
    """Firmas Win32 explícitas para evitar truncar HWND en Windows x64."""
    user32 = ctypes.windll.user32
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsWindow.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.IsIconic.restype = wintypes.BOOL
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetForegroundWindow.argtypes = []
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.ShowWindow.restype = wintypes.BOOL
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetWindowRect.restype = wintypes.BOOL
    return user32


def list_windows():
    if sys.platform != 'win32':
        return []
    user32 = _user32()
    results = []
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length < 2:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        title = buffer.value.strip()
        if title and not user32.IsIconic(hwnd):
            results.append((int(hwnd), title))
        return True

    cb = WNDENUMPROC(callback)
    user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.EnumWindows(cb, 0)
    return sorted(results, key=lambda x: x[1].casefold())


def window_title(hwnd):
    if sys.platform != 'win32' or hwnd is None:
        return ''
    user32 = _user32()
    if not user32.IsWindow(hwnd):
        return ''
    buffer = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, buffer, 512)
    return buffer.value


def focus_window(hwnd):
    """Devuelve False si no consigue enfocarla; nunca envía teclas en ese caso."""
    if sys.platform != 'win32' or hwnd is None:
        return False
    user32 = _user32()
    if not user32.IsWindow(hwnd) or not user32.IsWindowVisible(hwnd):
        return False
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    user32.SetForegroundWindow(hwnd)
    return int(user32.GetForegroundWindow() or 0) == int(hwnd)


def window_rectangle(hwnd):
    """(left, top, right, bottom) in desktop pixels, or None."""
    if sys.platform != 'win32' or hwnd is None:
        return None
    user32 = _user32()
    rectangle = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rectangle)):
        return None
    return rectangle.left, rectangle.top, rectangle.right, rectangle.bottom
