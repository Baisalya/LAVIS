from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle
from kivy.graphics.texture import Texture
from kivy.properties import ListProperty
import numpy as np


class SideGlowOverlay(Widget):
    left_color = ListProperty([1, 0, 0, 0.2])   # Redish glow (RGBA)
    right_color = ListProperty([0, 1, 1, 0.2])  # Cyanish glow (RGBA)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._left_texture = None
        self._right_texture = None
        self.bind(size=self._update_canvas, pos=self._update_canvas)
        self.bind(left_color=self._update_canvas, right_color=self._update_canvas)
        self._update_canvas()

    def _generate_center_fade_texture(self, start_color, direction='left'):
        """Generate gradient texture fading from edge to center."""
        steps = 256
        arr = np.zeros((1, steps, 4), dtype='uint8')

        for i in range(steps):
            t = i / steps
            if direction == 'left':  # left → center
                alpha = 1 - t
            else:  # right → center
                alpha = t
            r, g, b, base_alpha = start_color
            arr[0, i] = [int(r * 255), int(g * 255), int(b * 255), int(alpha * base_alpha * 255)]

        texture = Texture.create(size=(steps, 1), colorfmt='rgba')
        texture.blit_buffer(arr.tobytes(), colorfmt='rgba', bufferfmt='ubyte')
        texture.wrap = 'clamp_to_edge'
        texture.uvsize = (1, -1)
        return texture

    def _update_canvas(self, *args):
        self.canvas.clear()
        with self.canvas:
            width = self.width / 2
            height = self.height

            # Generate textures
            self._left_texture = self._generate_center_fade_texture(self.left_color, direction='left')
            self._right_texture = self._generate_center_fade_texture(self.right_color, direction='right')

            Color(1, 1, 1, 1)

            # Left fade (edge = solid, fade toward center)
            Rectangle(texture=self._left_texture,
                      pos=self.pos,
                      size=(width, height))

            # Right fade (edge = solid, fade toward center)
            Rectangle(texture=self._right_texture,
                      pos=(self.x + width, self.y),
                      size=(width, height))
