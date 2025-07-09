import flet as ft
import math
import random

class Particle:
    def __init__(self, cx, cy):
        angle = math.radians(random.uniform(0, 360))
        speed = random.uniform(1.5, 3)
        self.x = cx
        self.y = cy
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.alpha = 1.0
        self.radius = 2 + random.random() * 2

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.alpha -= 0.02
        return self.alpha > 0

class ParticleSystem:
    def __init__(self):
        self.particles = []
        self.cx = 0
        self.cy = 0

    def set_center(self, cx, cy):
        self.cx, self.cy = cx, cy

    def maybe_emit(self):
        if random.random() < 0.2:
            self.particles.append(Particle(self.cx, self.cy))

    def update(self):
        visuals = []
        for p in self.particles[:]:
            if p.update():
                visuals.append(ft.Container(
                    width=p.radius * 2,
                    height=p.radius * 2,
                    left=p.x - p.radius,
                    top=p.y - p.radius,
                    bgcolor="white",
                    border_radius=p.radius,
                    opacity=p.alpha
                ))
            else:
                self.particles.remove(p)
        return visuals
