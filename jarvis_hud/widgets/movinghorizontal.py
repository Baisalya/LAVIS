from kivy.uix.widget import Widget
from kivy.graphics import Color, Line
from kivy.clock import Clock

class MovingHorizontalLinesOverlay(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.offset = 0
        self.speed = 1  # pixels per frame
        self.spacing = 4  # distance between horizontal lines

        self.bind(size=self.update_lines, pos=self.update_lines)
        Clock.schedule_interval(self.update_lines, 1 / 60)

    def update_lines(self, *args):
        self.canvas.after.clear()
        with self.canvas.after:
            Color(0.0, 1.0, 1.0, 0.1)  # Very faint cyan

            y = self.y + self.offset
            while y < self.top:
                Line(points=[self.x, y, self.right, y], width=1)
                y += self.spacing

        self.offset += self.speed
        if self.offset >= self.spacing:
            self.offset = 0
