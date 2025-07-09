import flet as ft
import asyncio

class MovingHorizontalLinesOverlay:
    def __init__(self, speed=1, spacing=6, color="#00ffff"):
        self.speed = speed
        self.spacing = spacing
        self.offset = 0
        self.line_color = color
        self.running = True
        self.width = 0
        self.height = 0

    def update_size(self, width, height):
        self.width = width
        self.height = height

    async def animate_lines(self):
        while self.running:
            self.offset += self.speed
            if self.offset >= self.spacing:
                self.offset = 0
            await asyncio.sleep(1 / 60)

    def get_lines(self):
        lines = []
        y = self.offset
        while y < self.height:
            lines.append(ft.Container(
                left=0,
                top=y,
                width=self.width,
                height=1.5,
                bgcolor=self.line_color,
                opacity=0.12
            ))
            y += self.spacing
        return lines
