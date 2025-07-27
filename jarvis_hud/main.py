# === jarvis_hud/main.py ==
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.clock import Clock
from kivy.uix.label import Label

from .widgets.sci_fi_hud import HUDInterface
from .widgets.loading_screen import SciFiSplash

hud_interface = None

# Load KV files
Builder.load_file("jarvis_hud/kv/sci_fi.kv")

class SplashScreenWrapper(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.add_widget(SciFiSplash())

class MainHUDScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        global hud_interface
        try:
            hud_interface = HUDInterface()
            self.add_widget(hud_interface)
        except Exception as e:
            print("[ERROR] Failed to load HUDInterface:", e)
            self.add_widget(Label(text="HUD crashed. Check console."))

class SciFiApp(App):
    def build(self):
        self.title = "LAVIS"
        self.sm = ScreenManager()
        
        self.splash_screen = SplashScreenWrapper(name="splash")
        self.main_hud_screen = MainHUDScreen(name="main")

        self.sm.add_widget(self.splash_screen)
        self.sm.add_widget(self.main_hud_screen)

        # Auto transition after 2.5 seconds
        Clock.schedule_once(self.load_main_hud, 2.5)
        return self.sm

    def load_main_hud(self, dt):
        self.sm.current = "main"

# External control functions
def update_hud_status(new_status: str):
    if hud_interface:
        hud_interface.update_status(new_status)

def update_hud_text(message: str, category="info", typing=True):
    if hud_interface:
        hud_interface.update_text(message, category, typing)
    else:
        print(f"[HUD] Skipped: {message}")

def append_hud_console(message: str):
    if hud_interface:
        hud_interface.append_console_log(message)
    else:
        print(f"[HUD CONSOLE] Skipped: {message}")

if __name__ == "__main__":
    SciFiApp().run()
