import time
import threading
import re
from threading import Lock


class HUDController:
    def __init__(self, hud_widget):
        self.hud = hud_widget  # Instance of HUDTextOverlay
        self._last_text = ""
        self._last_time = 0
        self._typing_lock = Lock()

        self.prefix_map = {
            "command": ("Command:", "00ffff"),
            "reply": ("Reply:", "00ff00"),
            "error": ("Error:", "ff3333"),
            "info": ("", "ffffff")
        }

    def update(self, text: str, category="info", typing=False):
        now = time.time()
        if text == self._last_text and (now - self._last_time) < 1.0:
            return  # Avoid redundant spam

        self._last_text = text
        self._last_time = now

        prefix, hex_color = self.prefix_map.get(category, ("", "ffffff"))
        clean_text = self._strip_color_tags(text)
        final_text = f"{prefix} {clean_text}".strip()
        formatted = f"[color={self._format_color(hex_color)}]{final_text}[/color]"

        print(f"🧪 HUD[{category}] >> {formatted}")

        if typing:
            self._type_out(formatted)
        else:
            self.hud.append_message(formatted)

    def speak(self, text, category="info", typing=False):
        self.update(text, category, typing)

    def raw(self, text: str, replace_last=False):
        if replace_last:
            self.hud.replace_last_message(text)
        else:
            self.hud.append_message(text)

    def highlight(self, text: str):
        self.hud.append_message(f"[color=ffff00]{text}[/color]")

    def _type_out(self, text: str, delay=0.02):
        def typer():
            if self._typing_lock.locked():
                return
            with self._typing_lock:
                output = ""
                for char in text:
                    output += char
                    self.hud.replace_last_message(output)
                    time.sleep(delay)
                self.hud.replace_last_message(text)

        threading.Thread(target=typer, daemon=True).start()

    @staticmethod
    def _strip_color_tags(text):
        return re.sub(r'\[/?color(?:=[^\]]*)?\]', '', text)

    @staticmethod
    def _format_color(hex_code: str):
        hex_code = hex_code.strip().lstrip('#')
        if not re.match(r'^[0-9a-fA-F]{6}$', hex_code):
            return "#ffffff"
        return f"#{hex_code.lower()}"
