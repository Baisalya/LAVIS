from kivy.uix.widget import Widget
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.clock import Clock
from kivy.graphics import Color, Ellipse, Line, PushMatrix, PopMatrix, Rotate, Translate

class RadarWidget(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = 10
        self.spacing = 10

        self.radar_display = RadarCanvasWidget()
        self.stats_layout = BoxLayout(orientation='horizontal', size_hint=(1, None), height=30, spacing=10)

  

class RadarCanvasWidget(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.angle = 0
        self.friendlies = [(0.3, 0.5), (0.7, 0.4)]
        self.hostiles = [(0.5, 0.8), (0.8, 0.2), (0.2, 0.3)]
        Clock.schedule_interval(self.update_radar, 1/30)

    def update_radar(self, dt):
        self.canvas.clear()
        center = self.center
        radius = min(self.width, self.height) / 2.5

        with self.canvas:
            Color(0, 1, 1, 0.15)
            for r in range(1, 4):
                Ellipse(pos=(center[0] - r * radius/3, center[1] - r * radius/3),
                        size=(r * 2 * radius/3, r * 2 * radius/3),
                        angle_start=0, angle_end=360)

            for fx, fy in self.friendlies:
                Color(0, 1, 0, 0.9)
                Ellipse(pos=(center[0] + (fx - 0.5)*radius, center[1] + (fy - 0.5)*radius), size=(8, 8))

            for hx, hy in self.hostiles:
                Color(1, 0, 0, 0.9)
                Ellipse(pos=(center[0] + (hx - 0.5)*radius, center[1] + (hy - 0.5)*radius), size=(8, 8))

            Color(0, 1, 0.4, 0.6)
            PushMatrix()
            Translate(*center)
            Rotate(angle=self.angle, origin=(0, 0))
            Line(points=[0, 0, 0, radius], width=1.5)
            PopMatrix()

        self.angle = (self.angle + 1.5) % 360
