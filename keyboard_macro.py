import threading
from pynput import mouse, keyboard
from pynput.keyboard import Key, Controller
import time

class KeyboardMacro:
    def __init__(self, mouse_button='right', key_to_press='w', hold_time=None):
        """
        Inicializa la macro del teclado.

        Args:
            mouse_button: 'left', 'right', 'middle' - qué botón del ratón dispara la macro
            key_to_press: qué tecla pulsar ('w', 'a', 's', 'd', 'space', etc.)
            hold_time: cuánto tiempo mantener la tecla pulsada (None = mientras se mantenga el botón)
        """
        self.mouse_button = mouse_button
        self.key_to_press = key_to_press
        self.hold_time = hold_time
        self.keyboard_controller = Controller()
        self.is_pressed = False
        self.thread = None

    def _get_mouse_button(self, button):
        """Convierte string a botón de pynput"""
        buttons = {
            'left': mouse.Button.left,
            'right': mouse.Button.right,
            'middle': mouse.Button.middle
        }
        return buttons.get(button.lower(), mouse.Button.right)

    def _get_key(self, key_name):
        """Convierte string a tecla de pynput"""
        key_name = key_name.lower().strip()

        # Teclas especiales
        special_keys = {
            'space': Key.space,
            'enter': Key.enter,
            'shift': Key.shift,
            'ctrl': Key.ctrl,
            'alt': Key.alt,
            'tab': Key.tab,
            'escape': Key.esc,
            'up': Key.up,
            'down': Key.down,
            'left': Key.left,
            'right': Key.right,
            'backspace': Key.backspace,
            'delete': Key.delete,
            'home': Key.home,
            'end': Key.end,
        }

        if key_name in special_keys:
            return special_keys[key_name]

        # Teclas normales (una sola letra)
        if len(key_name) == 1:
            return key_name

        return key_name

    def _press_key_loop(self):
        """Loop para mantener la tecla pulsada"""
        key = self._get_key(self.key_to_press)

        self.keyboard_controller.press(key)

        if self.hold_time:
            time.sleep(self.hold_time)
            self.keyboard_controller.release(key)

    def on_mouse_press(self, x, y, button, pressed):
        """Se ejecuta cuando se pulsa un botón del ratón"""
        target_button = self._get_mouse_button(self.mouse_button)

        if button == target_button and pressed:
            if not self.is_pressed:
                self.is_pressed = True
                self.thread = threading.Thread(target=self._press_key_loop, daemon=True)
                self.thread.start()

        elif button == target_button and not pressed:
            # Liberar la tecla cuando se suelta el botón
            if self.is_pressed:
                self.is_pressed = False
                try:
                    key = self._get_key(self.key_to_press)
                    self.keyboard_controller.release(key)
                except:
                    pass

    def start(self):
        """Inicia la macro - escucha los clicks del ratón"""
        print(f"🎮 Macro iniciada")
        print(f"📍 Botón del ratón: {self.mouse_button}")
        print(f"⌨️  Tecla a pulsar: {self.key_to_press}")
        if self.hold_time:
            print(f"⏱️  Duración: {self.hold_time} segundos")
        else:
            print(f"⏱️  Duración: mientras se mantenga el botón")
        print(f"❌ Presiona ESC para salir\n")

        listener = mouse.Listener(on_move=None, on_click=self.on_mouse_press, on_scroll=None)
        listener.start()

        # Escucha ESC para salir
        with keyboard.Listener(on_press=self._on_key_press) as key_listener:
            key_listener.join()

    def _on_key_press(self, key):
        """Detecta ESC para salir"""
        try:
            if key == Key.esc:
                print("\n❌ Macro detenida")
                return False
        except AttributeError:
            pass


# ============= CONFIGURACIÓN =============
if __name__ == "__main__":
    # Personaliza estas variables:
    MOUSE_BUTTON = "right"      # "left", "right" o "middle"
    KEY_TO_PRESS = "w"          # "w", "space", "enter", etc.
    HOLD_TIME = None            # None = mientras se mantenga el botón | 0.5 = 0.5 segundos

    macro = KeyboardMacro(
        mouse_button=MOUSE_BUTTON,
        key_to_press=KEY_TO_PRESS,
        hold_time=HOLD_TIME
    )

    macro.start()
