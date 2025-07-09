from kivy.uix.widget import Widget
from kivy.graphics import Color, Ellipse, InstructionGroup
from kivy.clock import Clock
import random


class Particle:
    def __init__(self, x, y, radius, color, drift):
        self.x = x
        self.y = y
        self.radius = radius
        self.color = color
        self.drift = drift
        self.opacity = random.uniform(0.02, 0.08)

        self.graphics = InstructionGroup()
        self.graphics.add(Color(*self.color, self.opacity))
        self.ellipse = Ellipse(pos=(self.x, self.y), size=(self.radius, self.radius))
        self.graphics.add(self.ellipse)

    def update(self):
        self.x += self.drift[0]
        self.y += self.drift[1]
        self.ellipse.pos = (self.x, self.y)


class ParticleFogOverlay(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.particles = []
        self.canvas_particles = InstructionGroup()
        self.canvas.add(self.canvas_particles)

        # Create fog particles on both sides
        for _ in range(30):  # number of particles
            # Left side
            self.add_particle(x=random.uniform(0, self.width * 0.2),
                              y=random.uniform(0, self.height),
                              color=(0.2, 1.0, 1.0))  # cyan

            # Right side
            self.add_particle(x=random.uniform(self.width * 0.8, self.width),
                              y=random.uniform(0, self.height),
                              color=(1.0, 0.5, 0.2))  # orange-red

        Clock.schedule_interval(self.update_particles, 1/30)

    def add_particle(self, x, y, color):
        radius = random.randint(40, 100)
        drift = (random.uniform(-0.3, 0.3), random.uniform(-0.2, 0.2))
        particle = Particle(x, y, radius, color, drift)
        self.particles.append(particle)
        self.canvas_particles.add(particle.graphics)

    def update_particles(self, dt):
        w, h = self.width, self.height
        for p in self.particles:
            p.update()
            # wrap around screen
            if p.x < -p.radius:
                p.x = w
            elif p.x > w:
                p.x = 0
            if p.y < -p.radius:
                p.y = h
            elif p.y > h:
                p.y = 0
