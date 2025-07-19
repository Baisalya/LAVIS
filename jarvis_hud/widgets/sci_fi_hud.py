# sci_fi_hud.py
from datetime import datetime
from kivy.uix.floatlayout import FloatLayout
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.properties import StringProperty

from .radar import RadarWidget
from .grid_overlay import GridOverlay
from .movinghorizontal import MovingHorizontalLinesOverlay
from .core_hud import JarvisCore
from .fogoverlay import ParticleFogOverlay
from .SideGlowOverlay import SideGlowOverlay
from ..components.hud_text_overlay import HUDTextOverlay
from ..components.hud_controller import HUDController
from ..components.mic_bar import MicVolumeBar
from ..components.controller.mic_bar_controller import MicBarController
from LAVIS.utils.hud_utils import set_hud_controller  # ✅ import fixed setter

# Load .kv files
Builder.load_file("jarvis_hud/kv/sci_fi.kv")
Builder.load_file("jarvis_hud/kv/mic_bar.kv")

class HUDInterface(FloatLayout):
    system_status = StringProperty("sleep")
    hud_log_console = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # === Layered HUD Elements ===
        self.grid_overlay = GridOverlay()
        self.add_widget(self.grid_overlay)

        self.moving_lines = MovingHorizontalLinesOverlay()
        self.add_widget(self.moving_lines)

        self.fog_overlay = ParticleFogOverlay()
        self.add_widget(self.fog_overlay)

        self.core = JarvisCore(size_hint=(None, None), size=(500, 500),
                               pos_hint={"center_x": 0.5, "center_y": 0.5})
        self.add_widget(self.core)

        self.side_glow = SideGlowOverlay(left_color=[1, 0, 0, 0.15],
                                         right_color=[0, 1, 1, 0.15])
        self.add_widget(self.side_glow)

        self.text_overlay = HUDTextOverlay()
        self.add_widget(self.text_overlay)

        self.hud_controller = HUDController(self)
        set_hud_controller(self.hud_controller)  # ✅ SET controller globally
 # === Mic Volume Bar (from mic_bar.kv)
        self.mic_bar = MicVolumeBar()
        self.add_widget(self.mic_bar)  # ✅ Display mic bar on top

        self.mic_controller = MicBarController(self)
        # Optional live clock updater
        Clock.schedule_interval(self.update_time, 1)

    def update_mic_level(self, rms):
        level = min(100, int(rms / 3))
       # print(f"[HUD] Mic Bar Level = {level}")
        self.mic_bar.level = level

    def update_status(self, new_status):
        self.system_status = new_status

    def update_text(self, message: str, category="info", typing=True):
        if self.hud_controller:
            self.hud_controller.update(message, category, typing)

    def append_console_log(self, message: str):
        logs = self.hud_log_console.splitlines()
        logs.append(message)
        self.hud_log_console = "\n".join(logs[-30:])
        Clock.schedule_once(self.scroll_console_to_bottom, 0.01)

    def scroll_console_to_bottom(self, *args):
        try:
            self.ids.console_scroll.scroll_y = 0
        except Exception as e:
            print("[LogScrollError]", e)

    def update_time(self, dt):
        now = datetime.now()
        time_str = now.strftime("%I:%M:%S %p")
        date_str = now.strftime("%Y.%m.%d")

        if self.ids.get("clock_label"):
            self.ids.clock_label.text = f"[b]{time_str}[/b]"

        if self.ids.get("date_label"):
            self.ids.date_label.text = date_str
