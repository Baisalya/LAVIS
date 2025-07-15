# === jarvis_hud/main.py ==
from kivy.app import App
from .widgets.sci_fi_hud import HUDInterface
from kivy.lang import Builder


hud_interface = None

class SciFiApp(App):
    def build(self):
        self.title = "LAVIS"
        Builder.load_file("jarvis_hud/kv/sci_fi.kv")

        global hud_interface
        try:
            hud_interface = HUDInterface()
        except Exception as e:
            print("[ERROR] Failed to load HUDInterface:", e)
            from kivy.uix.label import Label
            return Label(text="HUD crashed. Check console.")
        
        return hud_interface

    
def update_hud_status(new_status: str):
    if hud_interface:
        hud_interface.update_status(new_status)


def update_hud_text(message: str, category="info", typing=True):
    if hud_interface:
        hud_interface.update_text(message, category, typing)
    else:
        print(f"[HUD] Skipped: {message}")

