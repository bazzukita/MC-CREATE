import customtkinter as ctk
from CTkMessagebox import CTkMessagebox
import threading
from pynput import mouse, keyboard
from pynput.keyboard import Key, Controller
import time
import sys

class KeyboardMacroGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("⌨️ Keyboard Macro")
        self.root.geometry("500x700")
        self.root.resizable(False, False)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.keyboard_controller = Controller()
        self.is_macro_running = False
        self.is_pressed = False
        self.listener = None
        self.thread = None

        self.setup_ui()

    def setup_ui(self):
        # ===== HEADER =====
        header_frame = ctk.CTkFrame(self.root, fg_color="#1a1a1a")
        header_frame.pack(pady=20, padx=20, fill="x")

        title_label = ctk.CTkLabel(
            header_frame,
            text="⌨️ Keyboard Macro",
            font=("Arial", 28, "bold"),
            text_color="#ffffff"
        )
        title_label.pack()

        subtitle_label = ctk.CTkLabel(
            header_frame,
            text="Automatiza tus pulsaciones de teclado",
            font=("Arial", 12),
            text_color="#888888"
        )
        subtitle_label.pack()

        # ===== TECLA A PULSAR =====
        section_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        section_frame.pack(pady=15, padx=20, fill="x")

        ctk.CTkLabel(
            section_frame,
            text="🔑 Tecla a pulsar:",
            font=("Arial", 13, "bold"),
            text_color="#ffffff"
        ).pack(anchor="w")

        self.key_option = ctk.CTkOptionMenu(
            section_frame,
            values=["W", "A", "S", "D", "Space", "Enter", "Shift", "Ctrl", "Alt", "E", "Q", "R"],
            font=("Arial", 11),
            fg_color="#242424",
            button_color="#0a5cff",
            text_color="#ffffff"
        )
        self.key_option.set("W")
        self.key_option.pack(fill="x", pady=(8, 0))

        # ===== BOTÓN DEL RATÓN =====
        section_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        section_frame.pack(pady=15, padx=20, fill="x")

        ctk.CTkLabel(
            section_frame,
            text="🖱️ Botón del ratón (activador):",
            font=("Arial", 13, "bold"),
            text_color="#ffffff"
        ).pack(anchor="w")

        self.mouse_option = ctk.CTkOptionMenu(
            section_frame,
            values=["Click Izquierdo", "Click Derecho", "Rueda Central"],
            font=("Arial", 11),
            fg_color="#242424",
            button_color="#0a5cff",
            text_color="#ffffff"
        )
        self.mouse_option.set("Click Derecho")
        self.mouse_option.pack(fill="x", pady=(8, 0))

        # ===== DURACIÓN =====
        section_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        section_frame.pack(pady=15, padx=20, fill="x")

        ctk.CTkLabel(
            section_frame,
            text="⏱️ Duración de cada pulsación (segundos):",
            font=("Arial", 13, "bold"),
            text_color="#ffffff"
        ).pack(anchor="w")

        duration_inner_frame = ctk.CTkFrame(section_frame, fg_color="transparent")
        duration_inner_frame.pack(fill="x", pady=(8, 0))

        self.duration_slider = ctk.CTkSlider(
            duration_inner_frame,
            from_=0.1,
            to=5.0,
            number_of_steps=49,
            fg_color="#242424",
            progress_color="#0a5cff",
            button_color="#0a5cff"
        )
        self.duration_slider.set(1.0)
        self.duration_slider.pack(side="left", fill="x", expand=True)

        self.duration_label = ctk.CTkLabel(
            duration_inner_frame,
            text="1.0s",
            font=("Arial", 11, "bold"),
            text_color="#0a5cff",
            width=40
        )
        self.duration_label.pack(side="right", padx=(10, 0))

        self.duration_slider.configure(command=self.update_duration_label)

        # ===== MODO =====
        section_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        section_frame.pack(pady=15, padx=20, fill="x")

        ctk.CTkLabel(
            section_frame,
            text="🔄 Modo:",
            font=("Arial", 13, "bold"),
            text_color="#ffffff"
        ).pack(anchor="w")

        mode_frame = ctk.CTkFrame(section_frame, fg_color="transparent")
        mode_frame.pack(fill="x", pady=(8, 0))

        self.mode_var = ctk.StringVar(value="hold")

        ctk.CTkRadioButton(
            mode_frame,
            text="Mientras mantengo el botón",
            variable=self.mode_var,
            value="hold",
            font=("Arial", 11),
            text_color="#ffffff",
            fg_color="#0a5cff"
        ).pack(anchor="w", pady=5)

        ctk.CTkRadioButton(
            mode_frame,
            text="Pulsaciones de X segundos",
            variable=self.mode_var,
            value="pulse",
            font=("Arial", 11),
            text_color="#ffffff",
            fg_color="#0a5cff"
        ).pack(anchor="w", pady=5)

        # ===== STATUS =====
        status_frame = ctk.CTkFrame(self.root, fg_color="#1a1a1a", corner_radius=10)
        status_frame.pack(pady=15, padx=20, fill="x")

        self.status_indicator = ctk.CTkLabel(
            status_frame,
            text="⚪",
            font=("Arial", 20),
            text_color="#888888"
        )
        self.status_indicator.pack(side="left", padx=15, pady=15)

        self.status_label = ctk.CTkLabel(
            status_frame,
            text="Inactivo",
            font=("Arial", 12),
            text_color="#888888"
        )
        self.status_label.pack(side="left")

        # ===== BOTONES =====
        button_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        button_frame.pack(pady=20, padx=20, fill="x")

        self.start_button = ctk.CTkButton(
            button_frame,
            text="▶️ INICIAR",
            font=("Arial", 13, "bold"),
            fg_color="#0a5cff",
            hover_color="#0845a0",
            command=self.start_macro,
            height=45
        )
        self.start_button.pack(fill="x", pady=(0, 10))

        self.stop_button = ctk.CTkButton(
            button_frame,
            text="⏹️ DETENER",
            font=("Arial", 13, "bold"),
            fg_color="#ff3333",
            hover_color="#cc0000",
            command=self.stop_macro,
            state="disabled",
            height=45
        )
        self.stop_button.pack(fill="x")

        # ===== INFO =====
        info_frame = ctk.CTkFrame(self.root, fg_color="#1a1a1a", corner_radius=10)
        info_frame.pack(pady=15, padx=20, fill="both", expand=True)

        info_text = """ℹ️ INSTRUCCIONES:
1. Selecciona la tecla a pulsar
2. Elige el botón del ratón que activa
3. Ajusta la duración
4. Presiona INICIAR
5. Presiona ESC en cualquier momento para parar"""

        ctk.CTkLabel(
            info_frame,
            text=info_text,
            font=("Arial", 10),
            text_color="#888888",
            justify="left"
        ).pack(padx=15, pady=15, anchor="w")

    def update_duration_label(self, value):
        self.duration_label.configure(text=f"{float(value):.1f}s")

    def get_key_from_name(self, key_name):
        key_name = key_name.lower().strip()
        keys = {
            'w': 'w', 'a': 'a', 's': 's', 'd': 'd',
            'space': Key.space,
            'enter': Key.enter,
            'shift': Key.shift,
            'ctrl': Key.ctrl,
            'alt': Key.alt,
            'e': 'e', 'q': 'q', 'r': 'r',
        }
        return keys.get(key_name, 'w')

    def get_mouse_button(self, button_name):
        buttons = {
            'click izquierdo': mouse.Button.left,
            'click derecho': mouse.Button.right,
            'rueda central': mouse.Button.middle,
        }
        return buttons.get(button_name.lower(), mouse.Button.right)

    def on_mouse_press(self, x, y, button, pressed):
        target_button = self.get_mouse_button(self.mouse_option.get())

        if button == target_button and pressed:
            if not self.is_pressed:
                self.is_pressed = True
                if self.mode_var.get() == "hold":
                    key = self.get_key_from_name(self.key_option.get())
                    self.keyboard_controller.press(key)
                elif self.mode_var.get() == "pulse":
                    self.thread = threading.Thread(target=self._pulse_key, daemon=True)
                    self.thread.start()

        elif button == target_button and not pressed:
            if self.is_pressed:
                self.is_pressed = False
                if self.mode_var.get() == "hold":
                    try:
                        key = self.get_key_from_name(self.key_option.get())
                        self.keyboard_controller.release(key)
                    except:
                        pass

    def _pulse_key(self):
        key = self.get_key_from_name(self.key_option.get())
        duration = float(self.duration_slider.get())

        self.keyboard_controller.press(key)
        time.sleep(duration)
        self.keyboard_controller.release(key)

    def on_key_press(self, key):
        try:
            if key == Key.esc:
                self.stop_macro()
                return False
        except AttributeError:
            pass

    def start_macro(self):
        self.is_macro_running = True
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")

        self.key_option.configure(state="disabled")
        self.mouse_option.configure(state="disabled")
        self.duration_slider.configure(state="disabled")

        self.status_indicator.configure(text_color="#00ff00")
        self.status_indicator.configure(text="🟢")
        self.status_label.configure(text="Macro activa - Presiona ESC para detener", text_color="#00ff00")

        self.listener = mouse.Listener(on_click=self.on_mouse_press)
        self.listener.start()

        key_listener = keyboard.Listener(on_press=self.on_key_press)
        key_listener.start()

    def stop_macro(self):
        self.is_macro_running = False
        self.is_pressed = False

        if self.listener:
            self.listener.stop()

        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")

        self.key_option.configure(state="normal")
        self.mouse_option.configure(state="normal")
        self.duration_slider.configure(state="normal")

        self.status_indicator.configure(text_color="#888888")
        self.status_indicator.configure(text="⚪")
        self.status_label.configure(text="Inactivo", text_color="#888888")

        try:
            key = self.get_key_from_name(self.key_option.get())
            self.keyboard_controller.release(key)
        except:
            pass


if __name__ == "__main__":
    root = ctk.CTk()
    app = KeyboardMacroGUI(root)
    root.mainloop()
