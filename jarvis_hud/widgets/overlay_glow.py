from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle, InstructionGroup
from kivy.clock import Clock
from kivy.properties import ListProperty
from kivy.utils import get_color_from_hex as rgb


class OverlayGlowEffect(Widget):
    # Left and right glow colors
    left_color = ListProperty(rgb("#00FFAA"))   # Greenish
    right_color = ListProperty(rgb("#FF6600"))  # Orange-red

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Animation positions (normalized: 0.0 to 1.0)
        self.left_pos = -0.2
        self.right_pos = 1.2

        with self.canvas:
            # === Left glow group ===
            self.left_glow = InstructionGroup()
            self.left_glow.add(Color(rgba=self.left_color + [0.4]))  # semi-transparent
            self.left_rect = Rectangle(size=(self.width * 0.2, self.height), pos=(self.x, self.y))
            self.left_glow.add(self.left_rect)
            self.canvas.add(self.left_glow)

            # === Right glow group ===
            self.right_glow = InstructionGroup()
            self.right_glow.add(Color(rgba=self.right_color + [0.4]))  # semi-transparent
            self.right_rect = Rectangle(size=(self.width * 0.2, self.height), pos=(self.x, self.y))
            self.right_glow.add(self.right_rect)
            self.canvas.add(self.right_glow)

        # Update on size/position change
        self.bind(size=self._update_rect, pos=self._update_rect)

        # Start animation
        Clock.schedule_interval(self.animate_glow, 1/60.)

    def _update_rect(self, *args):
        # Sync size of rectangles to widget size
        self.left_rect.size = (self.width * 0.2, self.height)
        self.right_rect.size = (self.width * 0.2, self.height)

    def animate_glow(self, dt):
        # Move glows inward toward center
        self.left_pos += dt * 0.2
        self.right_pos -= dt * 0.2

        # Reset if past center
        if self.left_pos > 0.5:
            self.left_pos = -0.2
        if self.right_pos < 0.5:
            self.right_pos = 1.2

        # Update positions
        self.left_rect.pos = (self.x + self.left_pos * self.width, self.y)
        self.right_rect.pos = (self.x + self.right_pos * self.width, self.y)
