import flet as ft
import math

class OrbitDotManager:
    def __init__(self):
        self.cx = 0
        self.cy = 0
        self.radius = 0

    def set_position(self, cx, cy, radius):
        self.cx, self.cy, self.radius = cx, cy, radius

    def generate(self, angle):
        dots = []
        for i in range(8):
            a = math.radians(angle + i * 45)
            x = self.cx + math.cos(a) * self.radius * 0.95
            y = self.cy + math.sin(a) * self.radius * 0.95
            dots.append(ft.Container(
                width=8,
                height=8,
                left=x - 4,
                top=y - 4,
                bgcolor="cyan",
                border_radius=4,
                opacity=0.7
            ))
        return dots
