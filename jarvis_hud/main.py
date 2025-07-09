# === jarvis_hud/main.py ==
from kivy.app import App
from .widgets.sci_fi_hud import HUDInterface

hud_interface = None

class SciFiApp(App):
    def build(self):
        self.title = "LAVIS"
        global hud_interface
        hud_interface = HUDInterface()
        return hud_interface

def update_hud_text(message: str, category="info", typing=True):
    if hud_interface:
        hud_interface.update_text(message, category, typing)
    else:
        print(f"[HUD] Skipped: {message}")

