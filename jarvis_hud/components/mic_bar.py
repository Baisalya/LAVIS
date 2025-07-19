# mic_bar.py
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import NumericProperty
from kivy.graphics import Color, Rectangle

class MicVolumeBar(BoxLayout):
    level = NumericProperty(0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.size_hint = (None, None)
        self.size = (40, 200)
        self.pos_hint = {"left": 100, "center_y": 0.5, "center_x": 0.15}

        with self.canvas.before:
            Color(0, 1, 1, 1)  # Light background for visibility
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)

        with self.canvas:
            self.color = Color(0, 1, 0, 0.9)  # Green bar
            self.rect = Rectangle(pos=self.pos, size=(self.width, 0))

        self.bind(pos=self.update_rect, size=self.update_rect, level=self.update_rect)

    def update_rect(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

        bar_height = self.height * (self.level / 100)
        self.rect.pos = self.pos
        self.rect.size = (self.width, bar_height)
