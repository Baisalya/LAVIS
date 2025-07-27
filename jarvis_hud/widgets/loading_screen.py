# === splash_screen.py ===
from kivy.uix.widget import Widget
from kivy.uix.floatlayout import FloatLayout
from kivy.graphics import Color, Rectangle, Line, Ellipse, InstructionGroup
from kivy.clock import Clock
from kivy.uix.label import Label
from kivy.core.audio import SoundLoader
from math import sin, cos, radians
import time, random

class SciFiSplash(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.bg_grid_lines = []
        with self.canvas.before:
            Color(0.01, 0.02, 0.03, 1)  # deep sci-fi background tint
            self.bg = Rectangle(size=self.size, pos=self.pos)

            # Futuristic Grid
            grid_color = Color(0, 1, 1, 0.04)
            self.canvas.before.add(grid_color)
            for i in range(0, 100, 5):
                self.bg_grid_lines.append(Line(points=[0, i * 10, self.width, i * 10], width=1))
                self.bg_grid_lines.append(Line(points=[i * 10, 0, i * 10, self.height], width=1))

        self.bind(size=self._update_bg, pos=self._update_bg)

        self.pulse_angle = 0
        self.rings = []
        self.particles = []

        # Neon Core Circle
        self.core = Widget(size_hint=(None, None), size=(300, 300), pos_hint={"center_x": 0.5, "center_y": 0.55})
        self.add_widget(self.core)

        # Label Overlay
        self.title = Label(text="[b]LAVIS AI SYSTEM[/b]", markup=True,
                           font_size='30sp', color=(0, 1, 1, 1),
                           pos_hint={"center_x": 0.5, "center_y": 0.27})
        self.loading = Label(text="Initializing neural subroutines...", font_size='16sp',
                             color=(1, 1, 1, 0.6), pos_hint={"center_x": 0.5, "center_y": 0.20})
        self.add_widget(self.title)
        self.add_widget(self.loading)

        # Optional startup sound
        # self.sound = SoundLoader.load('startup_sound.wav')
        # if self.sound:
        #     self.sound.play()

        Clock.schedule_interval(self.animate, 1 / 60.0)

    def _update_bg(self, *args):
        self.bg.size = self.size
        self.bg.pos = self.pos

        # Update grid lines
        self.canvas.before.remove_group('grid')
        self.canvas.before.clear()
        with self.canvas.before:
            Color(0.01, 0.02, 0.03, 1)
            self.bg = Rectangle(size=self.size, pos=self.pos)
            Color(0, 1, 1, 0.04)
            for i in range(0, int(self.height / 10), 1):
                Line(points=[0, i * 10, self.width, i * 10], width=1)
            for i in range(0, int(self.width / 10), 1):
                Line(points=[i * 10, 0, i * 10, self.height], width=1)

    def animate(self, dt):
        self.core.canvas.clear()
        cx, cy = self.core.center
        base_radius = min(self.core.size) / 2.2
        t = time.time()

        with self.core.canvas:
            for i in range(4):
                r = base_radius * (1 + i * 0.08)
                Color(0, 1, 1, 0.06 * (4 - i))
                Ellipse(pos=(cx - r, cy - r), size=(2 * r, 2 * r))

            num_dots = 8
            for i in range(num_dots):
                orbit_angle = radians(self.pulse_angle + i * (360 / num_dots))
                orbit_radius = base_radius * 1.1
                dot_x = cx + cos(orbit_angle) * orbit_radius
                dot_y = cy + sin(orbit_angle) * orbit_radius
                size = 6 + 3 * ((sin(orbit_angle) + 1) / 2)
                Color(0, 1, 1, 0.5)
                Ellipse(pos=(dot_x - size/2, dot_y - size/2), size=(size, size))

            for angle_offset in range(0, 360, 15):
                angle = radians(self.pulse_angle + angle_offset)
                end_x = cx + cos(angle) * base_radius * 1.4
                end_y = cy + sin(angle) * base_radius * 1.4
                Color(0, 1, 1, 0.03 + 0.03 * sin(t * 3 + angle_offset))
                Line(points=[cx, cy, end_x, end_y], width=1.0)

            pulse = 1 + 0.08 * sin(t * 4)
            Color(0.0, 1.0, 1.0, 0.2)
            Ellipse(pos=(cx - 20 * pulse, cy - 20 * pulse), size=(40 * pulse, 40 * pulse))
            Color(0.0, 1.0, 1.0, 0.8)
            Ellipse(pos=(cx - 8, cy - 8), size=(16, 16))
            Color(1, 1, 1, 1)
            Ellipse(pos=(cx - 2.5, cy - 2.5), size=(5, 5))

        self.pulse_angle = (self.pulse_angle + 1.4) % 360
