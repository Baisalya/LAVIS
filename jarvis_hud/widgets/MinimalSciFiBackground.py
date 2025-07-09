from kivy.uix.widget import Widget
from kivy.graphics import Color, Line, Ellipse, Rectangle
from kivy.clock import Clock
from kivy.core.window import Window
from math import sin
import time
import random


class BlinkNode:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.radius = 1
        self.alpha = 0.6

    def update(self):
        self.radius += 0.3
        self.alpha *= 0.93
        return self.alpha > 0.01


class FuturisticBackgroundOverlay(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.blink_nodes = []
        Clock.schedule_interval(self.update_background, 1 / 60)

    def update_background(self, dt):
        self.canvas.clear()
        w, h = Window.size
        spacing = 80
        t = time.time()

        with self.canvas:
            # === Dim Background Fill (transparent to let HUD show)
            Color(0.02, 0.04, 0.06, 0.85)
            Rectangle(pos=(0, 0), size=(w, h))

            # === Subtle Grid Lines ===
            for x in range(0, int(w), spacing):
                Color(0, 1, 1, 0.015)
                Line(points=[x, 0, x, h], width=1)

            for y in range(0, int(h), spacing):
                Color(0, 1, 1, 0.015)
                Line(points=[0, y, w, y], width=1)

            # === Random Blinking Dots on Grid ===
            if random.random() < 0.006:
                gx = random.randint(1, int(w // spacing) - 1) * spacing
                gy = random.randint(1, int(h // spacing) - 1) * spacing
                self.blink_nodes.append(BlinkNode(gx, gy))

            for node in self.blink_nodes[:]:
                if node.update():
                    Color(0, 1, 1, node.alpha)
                    Ellipse(pos=(node.x - node.radius, node.y - node.radius),
                            size=(node.radius * 2, node.radius * 2))
                else:
                    self.blink_nodes.remove(node)
