import sys
import os
import ctypes
import traceback
import customtkinter as ctk
from app import MCCreateApp

def resource_path(filename):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, filename)

def _log(msg):
    log_path = os.path.join(os.path.dirname(sys.executable if getattr(sys, "frozen", False) else __file__), "mc_create_error.log")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

if __name__ == "__main__":
    try:
        _log("=== startup ===")
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("MCCreate.ServerManager.1")
        _log("AppUserModelID set")

        # Ocultar consola si se lanza directamente con python.exe (no desde el exe compilado)
        if not getattr(sys, "frozen", False):
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 0)

        _log("setting CTK appearance")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("green")
        _log("creating MCCreateApp")
        app = MCCreateApp()
        _log("MCCreateApp created")

        icon = resource_path("icon.ico")
        if os.path.exists(icon):
            app.iconbitmap(icon)

        _log("entering mainloop")
        app.mainloop()
        _log("mainloop exited normally")
    except Exception:
        _log(traceback.format_exc())
