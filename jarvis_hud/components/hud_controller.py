import time
import threading
import re
from threading import Lock
from kivy.clock import Clock

class HUDController:
    def __init__(self, hud_widget):
        self.hud = hud_widget  # HUDInterface
        self.overlay = getattr(self.hud, 'text_overlay', None)  # ✅ Reference to HUDTextOverlay
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
        clean_text = self._strip_color_tags(text)

        # Avoid duplicates within 1s and not typing
        if (not typing and clean_text == self._last_text and (now - self._last_time) < 1.0):
            print(f"⚠️ Skipped duplicate: {clean_text}")
            return

        self._last_text = clean_text
        self._last_time = now

        prefix, hex_color = self.prefix_map.get(category, ("", "ffffff"))
        final_text = f"{prefix} {clean_text}".strip()
        formatted = f"[color={self._format_color(hex_color)}]{final_text}[/color]"

        print(f"🧪 HUD[{category}] >> {formatted}")

        if typing and len(clean_text) > 10:
            self._type_out_combo(clean_text, formatted)
        else:
            self.overlay.append_message(formatted)

    def type_live_text(self, partial_text: str):
        """Live plain text typing with no color"""
        Clock.schedule_once(lambda dt: self.overlay.replace_last_message(f"[color=ffffff]{partial_text}[/color]"))

    def _type_out_combo(self, plain_text: str, formatted_text: str, delay=0.02):
        def typer():
            with self._typing_lock:
                self.overlay.append_message("")  # New blank line
                output = ""
                for char in plain_text:
                    output += char
                    Clock.schedule_once(lambda dt, o=output: self.overlay.replace_last_message(o))
                    time.sleep(delay)
                Clock.schedule_once(lambda dt: self.overlay.replace_last_message(formatted_text))

        threading.Thread(target=typer, daemon=True).start()

    def speak(self, text, category="info", typing=False):
        self.update(text, category, typing)

    def raw(self, text: str, replace_last=False):
        if replace_last:
            self.overlay.replace_last_message(text)
        else:
            self.overlay.append_message(text)

    def highlight(self, text: str):
        self.overlay.append_message(f"[color=ffff00]{text}[/color]")

    @staticmethod
    def _strip_color_tags(text):
        return re.sub(r'\[/?color(?:=[^\]]*)?\]', '', text)

    @staticmethod
    def _format_color(hex_code: str):
        hex_code = hex_code.strip().lstrip('#')
        if not re.match(r'^[0-9a-fA-F]{6}$', hex_code):
            print(f"⚠️ Invalid color code: {hex_code}, using default")
            return "#ffffff"
        return f"#{hex_code.lower()}"
