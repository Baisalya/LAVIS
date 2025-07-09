import flet as ft
import asyncio

class AnimatedSmokeOverlay:
    def __init__(self, direction="left_to_right", speed=0.5, color="cyan"):
        self.direction = direction
        self.offset = 0.0
        self.speed = speed
        self.color = color
        self.running = True
        self.width = 0
        self.height = 0

    def update_size(self, width, height):
        self.width = width
        self.height = height

    async def animate(self):
        while self.running:
            self.offset += self.speed
            if self.offset > self.width * 2:
                self.offset = -self.width
            await asyncio.sleep(1 / 60)

    def get_overlay(self):
        bar_width = int(self.width * 0.35)
        if self.direction == "left_to_right":
            position = max(-bar_width, self.offset)
        else:
            position = min(self.width, self.width - self.offset - bar_width)

        gradient = ft.LinearGradient(
            begin=ft.alignment.center_left if self.direction == "left_to_right" else ft.alignment.center_right,
            end=ft.alignment.center_right if self.direction == "left_to_right" else ft.alignment.center_left,
            colors=[
                ft.Colors.TRANSPARENT,
                ft.Colors.with_opacity(0.08, self.color),
                ft.Colors.with_opacity(0.14, self.color),
                ft.Colors.with_opacity(0.08, self.color),
                ft.Colors.TRANSPARENT,
            ],
            tile_mode="clamp"
        )

        return ft.Container(
            left=position,
            top=0,
            width=bar_width,
            height=self.height,
            gradient=gradient
        )
