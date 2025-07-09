from kivy.uix.widget import Widget
from kivy.clock import Clock
from kivy.graphics import Color, Ellipse, Line, PushMatrix, PopMatrix, Rotate
from math import sin, cos, radians
import time
import random


class PulseRing:
    def __init__(self, cx, cy, base_radius):
        self.cx = cx
        self.cy = cy
        self.radius = base_radius * 0.5
        self.alpha = 0.25

    def expand(self):
        self.radius += 2.5
        self.alpha -= 0.01
        return self.alpha > 0


class Particle:
    def __init__(self, cx, cy):
        angle = radians(random.uniform(0, 360))
        speed = random.uniform(1.5, 3)
        self.x = cx
        self.y = cy
        self.vx = cos(angle) * speed
        self.vy = sin(angle) * speed
        self.alpha = 1.0
        self.radius = 2 + random.random() * 2

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.alpha -= 0.02
        return self.alpha > 0


class JarvisCore(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.angle = 0
        self.pulse_rings = []
        self.last_pulse_time = 0
        self.particles = []
        Clock.schedule_interval(self.animate, 1 / 60)

    def animate(self, dt):
        self.canvas.clear()
        cx, cy = self.center
        base_radius = min(self.size) / 2.8
        t = time.time()

        if t - self.last_pulse_time > 0.6:
            self.pulse_rings.append(PulseRing(cx, cy, base_radius))
            self.last_pulse_time = t

        if random.random() < 0.2:
            self.particles.append(Particle(cx, cy))

        with self.canvas:
            for i in range(3):
                r = base_radius * (1.2 + i * 0.1)
                Color(0, 1, 1, 0.04 * (3 - i))
                Ellipse(pos=(cx - r, cy - r), size=(2 * r, 2 * r))

            for ring in self.pulse_rings[:]:
                if ring.expand():
                    Color(0, 1, 1, ring.alpha)
                    Ellipse(pos=(ring.cx - ring.radius, ring.cy - ring.radius),
                            size=(ring.radius * 2, ring.radius * 2))
                else:
                    self.pulse_rings.remove(ring)

            num_dots = 8
            for i in range(num_dots):
                orbit_angle = radians(self.angle + i * (360 / num_dots))
                depth = (sin(orbit_angle) + 1) / 2
                orbit_radius = base_radius * (0.9 + 0.1 * depth)
                dot_x = cx + cos(orbit_angle) * orbit_radius
                dot_y = cy + sin(orbit_angle) * orbit_radius
                dot_size = 6 + 4 * depth
                Color(0, 1, 1, 0.4 + 0.4 * depth)
                Ellipse(pos=(dot_x - dot_size / 2, dot_y - dot_size / 2), size=(dot_size, dot_size))
                if depth > 0.7:
                    Color(0, 1, 1, 0.1)
                    Ellipse(pos=(dot_x - dot_size, dot_y - dot_size), size=(dot_size * 1.4, dot_size * 1.4))

            for i in range(0, 360, 12):
                beam_angle = radians(i + self.angle * 0.8)
                beam_len = base_radius * 1.4
                alpha = 0.05 + 0.05 * sin(t * 2 + i)
                Color(0, 1, 1, alpha)
                Line(points=[cx, cy, cx + cos(beam_angle) * beam_len, cy + sin(beam_angle) * beam_len], width=0.8)

            for offset in range(0, 360, 30):
                angle_rad = radians(self.angle + offset)
                length = base_radius * (0.75 + 0.1 * sin(angle_rad))
                x1 = cx + cos(angle_rad) * length
                y1 = cy + sin(angle_rad) * length
                ctrl_angle = angle_rad + radians(30)
                ctrl_radius = length * 0.5
                ctrl_x = cx + cos(ctrl_angle) * ctrl_radius
                ctrl_y = cy + sin(ctrl_angle) * ctrl_radius
                Color(0, 1, 1, 0.3 + 0.2 * sin(angle_rad))
                Line(bezier=[cx, cy, ctrl_x, ctrl_y, x1, y1], width=1.1)

            for p in self.particles[:]:
                if p.update():
                    Color(1, 1, 1, p.alpha)
                    Ellipse(pos=(p.x - p.radius, p.y - p.radius), size=(p.radius * 2, p.radius * 2))
                else:
                    self.particles.remove(p)

            for i in range(6):
                r = base_radius * (1 - i * 0.08)
                Color(0, 1, 1, 0.04 + 0.02 * (6 - i))
                Ellipse(pos=(cx - r, cy - r), size=(2 * r, 2 * r))

            beam_radius = base_radius * 0.3 + sin(t * 3) * 2
            Color(0, 1, 1, 0.08)
            Line(circle=(cx, cy, beam_radius), width=4)

            for i in range(90):
                angle = radians(i * 4)
                offset = 3 * sin(t * 3 + i)
                r = base_radius * 1.2 + offset
                x1 = cx + cos(angle) * r
                y1 = cy + sin(angle) * r
                x2 = cx + cos(angle + 0.1) * r
                y2 = cy + sin(angle + 0.1) * r
                Color(0, 1, 1, 0.03)
                Line(points=[x1, y1, x2, y2], width=1.0)

            for i in range(3):
                r = base_radius * (0.8 - i * 0.15)
                PushMatrix()
                Rotate(angle=(self.angle + i * 60), origin=(cx, cy))
                if i == 2:
                    Color(0.0, 0.0, 0.4, 1.0)
                    Line(circle=(cx, cy, r), width=3.0)
                Color(0, 1, 1, 0.06 + 0.04 * (3 - i))
                Line(circle=(cx, cy, r), width=1.2)
                PopMatrix()

            core_pulse = 1 + 0.1 * sin(t * 4)
            Color(0.0, 0.0, 0.0, 0.8)
            Line(circle=(cx, cy, 20 * core_pulse), width=3.5)
            Color(0.0, 1.0, 1.0, 0.25)
            Ellipse(pos=(cx - 20 * core_pulse, cy - 20 * core_pulse), size=(40 * core_pulse, 40 * core_pulse))
            Color(0.0, 1.0, 1.0, 0.6 + 0.3 * sin(t * 2))
            Ellipse(pos=(cx - 12, cy - 12), size=(24, 24))
            Color(1, 1, 1, 0.95)
            Ellipse(pos=(cx - 4, cy - 4), size=(8, 8))

        self.angle = (self.angle + 1.5) % 360
