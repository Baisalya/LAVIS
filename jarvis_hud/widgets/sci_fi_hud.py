import os
import sys
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

# Load KV layout (optional)
Builder.load_file("jarvis_hud/kv/sci_fi.kv")


class HUDInterface(FloatLayout):
    system_status = StringProperty("sleep")         # Controls system status label
    hud_log_console = StringProperty("")            # ✅ Live console-style HUD log

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # === Layer 1: Grid overlay ===
        self.grid_overlay = GridOverlay()
        self.add_widget(self.grid_overlay)

        # === Layer 2: Moving horizontal lines ===
        self.moving_lines = MovingHorizontalLinesOverlay()
        self.add_widget(self.moving_lines)

        # === Layer 3: Particle fog effect ===
        self.fog_overlay = ParticleFogOverlay()
        self.add_widget(self.fog_overlay)

        # === Layer 4: Central Jarvis core animation ===
        self.core = JarvisCore(
            size_hint=(None, None),
            size=(500, 500),
            pos_hint={"center_x": 0.5, "center_y": 0.5}
        )
        self.add_widget(self.core)

        # === Layer 5: Side glow overlays ===
        self.side_glow = SideGlowOverlay(
            left_color=[1, 0, 0, 0.15],     # Red glow left
            right_color=[0, 1, 1, 0.15],    # Cyan glow right
        )
        self.add_widget(self.side_glow)

        # === Layer 6: Text overlay layer (replies / prompts) ===
        self.text_overlay = HUDTextOverlay()
        self.add_widget(self.text_overlay)

        # === HUD Controller (handles typed display updates) ===
        self.hud_controller = HUDController(self)

        # Optional: Live clock/date update
        Clock.schedule_interval(self.update_time, 1)

    def update_status(self, new_status):
        """Update system status label."""
        self.system_status = new_status

    def update_text(self, message: str, category="info", typing=True):
        """Used for assistant reply, prompts, etc."""
        if self.hud_controller:
            self.hud_controller.update(message, category, typing)

    def append_console_log(self, message: str):
        """Append live messages to HUD console (separate from status)."""
        logs = self.hud_log_console.splitlines()
        logs.append(message)
        self.hud_log_console = "\n".join(logs[-30:])  # Only keep last 30 lines
        Clock.schedule_once(lambda dt: self.scroll_to_bottom(), 0)
# ✅ Scroll to bottom after label updates (on next frame)
    def scroll_to_bottom(self, *_):

        scroll = self.ids.get("console_scroll")
        if scroll:
            scroll.scroll_y = 0  # 0 = bottom, 1 = top

   
    def update_time(self, dt):
        """Update any time/date labels via .kv `ids`."""
        now = datetime.now()
        time_str = now.strftime("%I:%M:%S %p")
        date_str = now.strftime("%Y.%m.%d")

        if self.ids.get("clock_label"):
            self.ids.clock_label.text = f"[b]{time_str}[/b]"

        if self.ids.get("date_label"):
            self.ids.date_label.text = date_str
