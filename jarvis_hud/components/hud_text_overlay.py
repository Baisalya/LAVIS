from kivy.uix.floatlayout import FloatLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.properties import StringProperty, ListProperty
from kivy.graphics import Color, RoundedRectangle, Line


class HUDTextOverlay(FloatLayout):
    message = StringProperty("Welcome Jarvis ready")
    message_history = ListProperty([])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Configuration
        self.max_lines = 100
        self.max_width = 800
        self.default_height = 100
        self.max_height = 300
        self.width = min(624, self.max_width)  # e.g. 600 * 1.04

        self.size_hint = (None, None)
        self.height = self.default_height
        self.pos_hint = {"center_x": 0.5, "center_y": 0.5}

        # Graphics
        with self.canvas.before:
            Color(0, 1, 1, 0.15)  # Glow
            self.outer_glow = RoundedRectangle(radius=[20])
            Color(0, 0, 0.1, 0.8)  # Background
            self.bg = RoundedRectangle(radius=[15])
            Color(0, 1, 1, 0.9)  # Border
            self.border = Line(width=1.5)

        self.bind(pos=self._update_graphics, size=self._update_graphics)

        # Scroll view and label setup
        self.scroll = ScrollView(
            size_hint=(None, None),
            do_scroll_x=False
        )

        self.label = Label(
            text=self.message,
            font_size="20sp",
            color=(0, 1, 1, 1),
            size_hint_y=None,
            halign="left",
            valign="top",
            markup=True,
            text_size=(self.width - 40, None)
        )
        self.label.bind(texture_size=self._adjust_label_height)

        self.scroll.add_widget(self.label)
        self.add_widget(self.scroll)

        self.bind(message=self._update_label_text)

    def append_message(self, new_text: str):
        self.message_history.append(new_text)
        if len(self.message_history) > self.max_lines:
            self.message_history.pop(0)
        self.message = "\n".join(self.message_history)

    def replace_last_message(self, new_text: str):
        if self.message_history:
            self.message_history[-1] = new_text
        else:
            self.message_history.append(new_text)
        self.message = "\n".join(self.message_history)

    def highlight_temp_text(self, yellow_text: str):
        self.append_message(f"[color=ffff00]{yellow_text}[/color]")

    def _update_label_text(self, *_):
        self.label.text = self.message

    def _adjust_label_height(self, *_):
        self.label.height = self.label.texture_size[1]
        self.height = min(max(self.label.height + 40, 60), self.max_height)
        self.scroll.size = (self.width - 20, self.height - 20)
        self.scroll.pos = (self.x + 10, self.y + 10)
        self.scroll.scroll_y = 0
        self._update_graphics()

    def _update_graphics(self, *_):
        self.bg.pos = self.pos
        self.bg.size = (self.width, self.height)

        self.outer_glow.pos = (self.x - 10, self.y - 10)
        self.outer_glow.size = (self.width + 20, self.height + 20)

        self.border.rounded_rectangle = (self.x, self.y, self.width, self.height, 15)

        self.scroll.pos = (self.x + 10, self.y + 10)
        self.scroll.size = (self.width - 20, self.height - 20)
