import customtkinter as ctk
import threading
from pynput import mouse, keyboard
from pynput.keyboard import Key, Controller
import time

class BasketballMacroGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("🏀 Basketball Legends - Auto Perfect")
        self.root.geometry("550x750")
        self.root.resizable(False, False)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("orange")

        self.keyboard_controller = Controller()
        self.is_macro_running = False
        self.is_clicking = False
        self.listener = None
        self.auto_click_thread = None
        self.click_count = 0

        self.setup_ui()

    def setup_ui(self):
        # ===== HEADER =====
        header_frame = ctk.CTkFrame(self.root, fg_color="#1a1a1a")
        header_frame.pack(pady=20, padx=20, fill="x")

        title_label = ctk.CTkLabel(
            header_frame,
            text="🏀 Basketball Legends",
            font=("Arial", 28, "bold"),
            text_color="#ffffff"
        )
        title_label.pack()

        subtitle_label = ctk.CTkLabel(
            header_frame,
            text="Auto Perfect Macro para Roblox",
            font=("Arial", 12),
            text_color="#ff9500"
        )
        subtitle_label.pack()

        # ===== MODO =====
        mode_section = ctk.CTkFrame(self.root, fg_color="transparent")
        mode_section.pack(pady=15, padx=20, fill="x")

        ctk.CTkLabel(
            mode_section,
            text="🎮 Modo de juego:",
            font=("Arial", 13, "bold"),
            text_color="#ffffff"
        ).pack(anchor="w")

        self.mode_var = ctk.StringVar(value="timing")

        mode_frame = ctk.CTkFrame(mode_section, fg_color="transparent")
        mode_frame.pack(fill="x", pady=(8, 0))

        ctk.CTkRadioButton(
            mode_frame,
            text="Timing perfecto (Espacio en el momento)",
            variable=self.mode_var,
            value="timing",
            font=("Arial", 11),
            text_color="#ffffff",
            fg_color="#ff9500"
        ).pack(anchor="w", pady=5)

        ctk.CTkRadioButton(
            mode_frame,
            text="Auto Click cada X milisegundos",
            variable=self.mode_var,
            value="auto",
            font=("Arial", 11),
            text_color="#ffffff",
            fg_color="#ff9500"
        ).pack(anchor="w", pady=5)

        # ===== TIMING PERFECTO =====
        timing_section = ctk.CTkFrame(self.root, fg_color="#1a1a1a", corner_radius=10)
        timing_section.pack(pady=15, padx=20, fill="x")

        ctk.CTkLabel(
            timing_section,
            text="⏱️ Timing del Perfect",
            font=("Arial", 12, "bold"),
            text_color="#ffffff"
        ).pack(anchor="w", padx=15, pady=(15, 10))

        timing_inner = ctk.CTkFrame(timing_section, fg_color="transparent")
        timing_inner.pack(padx=15, pady=(0, 15), fill="x")

        ctk.CTkLabel(
            timing_inner,
            text="Intervalo entre clicks (ms):",
            font=("Arial", 10),
            text_color="#aaaaaa"
        ).pack(anchor="w", pady=(0, 5))

        interval_frame = ctk.CTkFrame(timing_inner, fg_color="transparent")
        interval_frame.pack(fill="x", pady=(0, 10))

        self.interval_slider = ctk.CTkSlider(
            interval_frame,
            from_=100,
            to=2000,
            number_of_steps=95,
            fg_color="#242424",
            progress_color="#ff9500",
            button_color="#ff9500"
        )
        self.interval_slider.set(400)
        self.interval_slider.pack(side="left", fill="x", expand=True)

        self.interval_label = ctk.CTkLabel(
            interval_frame,
            text="400ms",
            font=("Arial", 11, "bold"),
            text_color="#ff9500",
            width=60
        )
        self.interval_label.pack(side="right", padx=(10, 0))

        self.interval_slider.configure(command=self.update_interval_label)

        # Info
        ctk.CTkLabel(
            timing_inner,
            text="💡 Reduce si fallas, aumenta si hay lag",
            font=("Arial", 9),
            text_color="#666666"
        ).pack(anchor="w")

        # ===== AUTO CLICK =====
        auto_section = ctk.CTkFrame(self.root, fg_color="#1a1a1a", corner_radius=10)
        auto_section.pack(pady=15, padx=20, fill="x")

        ctk.CTkLabel(
            auto_section,
            text="🔄 Auto Click",
            font=("Arial", 12, "bold"),
            text_color="#ffffff"
        ).pack(anchor="w", padx=15, pady=(15, 10))

        auto_inner = ctk.CTkFrame(auto_section, fg_color="transparent")
        auto_inner.pack(padx=15, pady=(0, 15), fill="x")

        ctk.CTkLabel(
            auto_inner,
            text="Clicks por segundo:",
            font=("Arial", 10),
            text_color="#aaaaaa"
        ).pack(anchor="w", pady=(0, 5))

        cps_frame = ctk.CTkFrame(auto_inner, fg_color="transparent")
        cps_frame.pack(fill="x", pady=(0, 10))

        self.cps_slider = ctk.CTkSlider(
            cps_frame,
            from_=1,
            to=20,
            number_of_steps=19,
            fg_color="#242424",
            progress_color="#ff9500",
            button_color="#ff9500"
        )
        self.cps_slider.set(8)
        self.cps_slider.pack(side="left", fill="x", expand=True)

        self.cps_label = ctk.CTkLabel(
            cps_frame,
            text="8 CPS",
            font=("Arial", 11, "bold"),
            text_color="#ff9500",
            width=60
        )
        self.cps_label.pack(side="right", padx=(10, 0))

        self.cps_slider.configure(command=self.update_cps_label)

        # ===== BOTÓN DEL RATÓN =====
        button_section = ctk.CTkFrame(self.root, fg_color="transparent")
        button_section.pack(pady=15, padx=20, fill="x")

        ctk.CTkLabel(
            button_section,
            text="🖱️ Botón del ratón (activador):",
            font=("Arial", 13, "bold"),
            text_color="#ffffff"
        ).pack(anchor="w")

        self.mouse_option = ctk.CTkOptionMenu(
            button_section,
            values=["Click Izquierdo", "Click Derecho", "Rueda Central"],
            font=("Arial", 11),
            fg_color="#242424",
            button_color="#ff9500",
            text_color="#ffffff"
        )
        self.mouse_option.set("Click Izquierdo")
        self.mouse_option.pack(fill="x", pady=(8, 0))

        # ===== STATUS =====
        status_frame = ctk.CTkFrame(self.root, fg_color="#1a1a1a", corner_radius=10)
        status_frame.pack(pady=15, padx=20, fill="x")

        status_inner = ctk.CTkFrame(status_frame, fg_color="transparent")
        status_inner.pack(padx=15, pady=15, fill="x")

        self.status_indicator = ctk.CTkLabel(
            status_inner,
            text="⚪",
            font=("Arial", 20),
            text_color="#888888"
        )
        self.status_indicator.pack(side="left", padx=(0, 10))

        status_text_frame = ctk.CTkFrame(status_inner, fg_color="transparent")
        status_text_frame.pack(side="left", fill="x", expand=True)

        self.status_label = ctk.CTkLabel(
            status_text_frame,
            text="Inactivo",
            font=("Arial", 12, "bold"),
            text_color="#888888"
        )
        self.status_label.pack(anchor="w")

        self.click_counter = ctk.CTkLabel(
            status_text_frame,
            text="Clicks: 0",
            font=("Arial", 10),
            text_color="#666666"
        )
        self.click_counter.pack(anchor="w")

        # ===== BOTONES =====
        button_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        button_frame.pack(pady=15, padx=20, fill="x")

        self.start_button = ctk.CTkButton(
            button_frame,
            text="▶️ INICIAR MACRO",
            font=("Arial", 13, "bold"),
            fg_color="#ff9500",
            hover_color="#cc7700",
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

    def update_interval_label(self, value):
        self.interval_label.configure(text=f"{int(float(value))}ms")

    def update_cps_label(self, value):
        self.cps_label.configure(text=f"{int(float(value))} CPS")

    def get_mouse_button(self, button_name):
        buttons = {
            'click izquierdo': mouse.Button.left,
            'click derecho': mouse.Button.right,
            'rueda central': mouse.Button.middle,
        }
        return buttons.get(button_name.lower(), mouse.Button.left)

    def on_mouse_press(self, x, y, button, pressed):
        target_button = self.get_mouse_button(self.mouse_option.get())

        if button == target_button and pressed:
            if not self.is_clicking:
                self.is_clicking = True

                if self.mode_var.get() == "timing":
                    self._do_perfect_click()
                elif self.mode_var.get() == "auto":
                    self.auto_click_thread = threading.Thread(target=self._auto_click_loop, daemon=True)
                    self.auto_click_thread.start()

        elif button == target_button and not pressed:
            self.is_clicking = False

    def _do_perfect_click(self):
        """Simula un click perfecto"""
        try:
            self.keyboard_controller.press(Key.space)
            time.sleep(0.05)
            self.keyboard_controller.release(Key.space)

            self.click_count += 1
            self.update_click_counter()
        except:
            pass

    def _auto_click_loop(self):
        """Auto click continuo"""
        cps = int(float(self.cps_slider.get()))
        interval = 1.0 / cps

        while self.is_clicking and self.is_macro_running:
            try:
                self.keyboard_controller.press(Key.space)
                time.sleep(0.02)
                self.keyboard_controller.release(Key.space)

                self.click_count += 1
                self.update_click_counter()

                time.sleep(interval)
            except:
                break

    def update_click_counter(self):
        self.click_counter.configure(text=f"Clicks: {self.click_count}")

    def on_key_press(self, key):
        try:
            if key == Key.esc:
                self.stop_macro()
                return False
        except AttributeError:
            pass

    def start_macro(self):
        self.is_macro_running = True
        self.click_count = 0
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")

        self.mode_var.configure(state="disabled")
        self.mouse_option.configure(state="disabled")
        self.interval_slider.configure(state="disabled")
        self.cps_slider.configure(state="disabled")

        self.status_indicator.configure(text_color="#00ff00")
        self.status_indicator.configure(text="🟢")
        self.status_label.configure(text="¡Macro activa!", text_color="#00ff00")

        self.listener = mouse.Listener(on_click=self.on_mouse_press)
        self.listener.start()

        key_listener = keyboard.Listener(on_press=self.on_key_press)
        key_listener.start()

    def stop_macro(self):
        self.is_macro_running = False
        self.is_clicking = False

        if self.listener:
            self.listener.stop()

        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")

        self.mode_var.configure(state="normal")
        self.mouse_option.configure(state="normal")
        self.interval_slider.configure(state="normal")
        self.cps_slider.configure(state="normal")

        self.status_indicator.configure(text_color="#888888")
        self.status_indicator.configure(text="⚪")
        self.status_label.configure(text="Inactivo", text_color="#888888")


if __name__ == "__main__":
    root = ctk.CTk()
    app = BasketballMacroGUI(root)
    root.mainloop()
