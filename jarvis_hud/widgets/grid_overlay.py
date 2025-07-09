from kivy.uix.widget import Widget
from kivy.graphics import Color, Line
from kivy.clock import Clock

class GridOverlay(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(size=self.update_grid, pos=self.update_grid)
        Clock.schedule_once(lambda dt: self.update_grid())

    def update_grid(self, *args):
        self.canvas.after.clear()
        with self.canvas.after:
            Color(0.1, 1, 1, 0.1)  # Cyan grid, 20% transparent

            rows = 40   # More rows = smaller boxes
            cols = 40   # More columns = smaller boxes
            w, h = self.width, self.height

            # Vertical lines
            for i in range(1, cols):
                x = self.x + (w / cols) * i
                Line(points=[x, self.y, x, self.top], width=1)

            # Horizontal lines
            for j in range(1, rows):
                y = self.y + (h / rows) * j
                Line(points=[self.x, y, self.right, y], width=1)
