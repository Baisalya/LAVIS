from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.properties import StringProperty, ListProperty
from kivy.graphics import Color, RoundedRectangle, Line


class HUDTextOverlay(FloatLayout):
    message = StringProperty("Welcome Lavis ready")
    message_history = ListProperty([])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # HUD size config
        self.max_lines = 100
        self.size_hint = (None, None)
        self.width = 600
        self.height = 150
        self.pos_hint = {"center_x": 0.5, "top": 0.59}

        # === Main HUD container (vertical stack)
        self.container = BoxLayout(orientation="vertical", padding=10, spacing=5)
        self.container.size_hint = (1, 1)
        self.container.pos_hint = {"center_x": 0.5, "center_y": 0.5}
        self.add_widget(self.container)

        # === Live Input Label
        self.live_label = Label(
            text="",
            font_size="18sp",
            color=(0, 1, 1, 0.9),
            markup=True,
            size_hint=(1, None),
            height=30,
            halign="left",
            valign="middle"
        )
        self.container.add_widget(self.live_label)

        # === Scroll Area
        self.scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
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
        self.container.add_widget(self.scroll)

        # === Background and border
        with self.canvas.before:
            Color(0, 1, 1, 0.15)
            self.outer_glow = RoundedRectangle(radius=[20])
            Color(0, 0, 0.1, 0.8)
            self.bg = RoundedRectangle(radius=[15])
            Color(0, 1, 1, 0.9)
            self.border = Line(width=1.5)

        self.bind(pos=self._update_graphics, size=self._update_graphics)
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

    def update_live_input(self, partial_text: str):
        self.live_label.text = f"[color=00ffff]🗣️ {partial_text}[/color]"

    def clear_live_input(self):
        self.live_label.text = ""

    def _update_label_text(self, *_):
        self.label.text = self.message

    def _adjust_label_height(self, *_):
        self.label.height = self.label.texture_size[1]

    def _update_graphics(self, *_):
        self.bg.pos = self.pos
        self.bg.size = (self.width, self.height)
        self.outer_glow.pos = (self.x - 10, self.y - 10)
        self.outer_glow.size = (self.width + 20, self.height + 20)
        self.border.rounded_rectangle = (self.x, self.y, self.width, self.height, 15)


# ✅ Updated HUDInterface wrapper to expose `text_overlay`
from kivy.uix.boxlayout import BoxLayout

class HUDInterface(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.text_overlay = HUDTextOverlay()
        self.add_widget(self.text_overlay)

    def update_text(self, message, category="info", typing=False):
        from .hud_controller import HUDController
        controller = HUDController(self)
        controller.update(message, category, typing)

    def update_status(self, new_status):
        self.text_overlay.highlight_temp_text(f"[STATUS] {new_status}")
