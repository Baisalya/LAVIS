import flet as ft

class PulseRingManager:
    def __init__(self):
        self.cx = 0
        self.cy = 0
        self.rings = []
        self.last_pulse = 0

    def set_center(self, cx, cy):
        self.cx, self.cy = cx, cy

    def maybe_pulse(self, now):
        if now - self.last_pulse > 0.6:
            self.rings.append((0, 0.4))
            self.last_pulse = now

    def update(self):
        visuals = []
        new_rings = []
        for r, a in self.rings:
            r += 3.5
            a -= 0.015
            if a > 0:
                visuals.append(ft.Container(
                    width=r * 2,
                    height=r * 2,
                    left=self.cx - r,
                    top=self.cy - r,
                    border_radius=r,
                    bgcolor="cyan",
                    opacity=a
                ))
                new_rings.append((r, a))
        self.rings = new_rings
        return visuals
