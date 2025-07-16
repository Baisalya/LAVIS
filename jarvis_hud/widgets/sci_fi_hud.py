import os
from datetime import datetime

from kivy.uix.floatlayout import FloatLayout
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.properties import StringProperty

# Custom Widgets
from .radar import RadarWidget
from .grid_overlay import GridOverlay
from .movinghorizontal import MovingHorizontalLinesOverlay
from .core_hud import JarvisCore
from .fogoverlay import ParticleFogOverlay
from .SideGlowOverlay import SideGlowOverlay
from ..components.hud_text_overlay import HUDTextOverlay
from ..components.hud_controller import HUDController

# Load KV layout
Builder.load_file("jarvis_hud/kv/sci_fi.kv")


class HUDInterface(FloatLayout):
    system_status = StringProperty("sleep")         # System state label
    hud_log_console = StringProperty("")            # ✅ Live console log display

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # === Layered HUD Elements ===
        self.grid_overlay = GridOverlay()
        self.add_widget(self.grid_overlay)

        self.moving_lines = MovingHorizontalLinesOverlay()
        self.add_widget(self.moving_lines)

        self.fog_overlay = ParticleFogOverlay()
        self.add_widget(self.fog_overlay)

        self.core = JarvisCore(
            size_hint=(None, None),
            size=(500, 500),
            pos_hint={"center_x": 0.5, "center_y": 0.5}
        )
        self.add_widget(self.core)

        self.side_glow = SideGlowOverlay(
            left_color=[1, 0, 0, 0.15],
            right_color=[0, 1, 1, 0.15],
        )
        self.add_widget(self.side_glow)

        self.text_overlay = HUDTextOverlay()
        self.add_widget(self.text_overlay)

        self.hud_controller = HUDController(self)

        # Optional live clock updater
        Clock.schedule_interval(self.update_time, 1)

    def update_status(self, new_status):
        """Update status label text."""
        self.system_status = new_status

    def update_text(self, message: str, category="info", typing=True):
        """Display reply/prompt on the HUD."""
        if self.hud_controller:
            self.hud_controller.update(message, category, typing)

    def append_console_log(self, message: str):
        """Append message to live log with scroll."""
        logs = self.hud_log_console.splitlines()
        logs.append(message)
        self.hud_log_console = "\n".join(logs[-30:])  # Keep last 30 lines
        Clock.schedule_once(self.scroll_console_to_bottom, 0.01)

    def scroll_console_to_bottom(self, *args):
        """Auto-scroll to the bottom of log display."""
        try:
            self.ids.console_scroll.scroll_y = 0
        except Exception as e:
            print("[LogScrollError]", e)

    def update_time(self, dt):
        """Update date/time labels via KV IDs."""
        now = datetime.now()
        time_str = now.strftime("%I:%M:%S %p")
        date_str = now.strftime("%Y.%m.%d")

        if self.ids.get("clock_label"):
            self.ids.clock_label.text = f"[b]{time_str}[/b]"

        if self.ids.get("date_label"):
            self.ids.date_label.text = date_str
