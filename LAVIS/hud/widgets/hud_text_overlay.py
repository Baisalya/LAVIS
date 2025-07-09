import flet as ft

class HUDTextOverlay:
    def __init__(self, width=600, max_height=300):
        self.max_lines = 100
        self.width = min(int(width * 1.04), 800)
        self.default_height = 100
        self.max_height = max_height
        self.message_history = []

        # Text label
        self.label = ft.Text(
            value="Welcome Jarvis ready",
            size=16,
            color="cyan",
            selectable=True,
            text_align=ft.TextAlign.LEFT,
            max_lines=None,
        )

        # Scrollable container
        self.scroll = ft.Container(
            content=ft.Column(
                controls=[self.label],
                scroll=ft.ScrollMode.AUTO
            ),
            width=self.width - 20,
            height=self.default_height - 20,
            padding=10
        )

        # Final visible component
        self.view = ft.Container(
            content=self.scroll,
            alignment=ft.alignment.center,
            width=self.width,
            height=self.default_height,
            border_radius=15,
            border=ft.border.all(1.5, "cyan"),
            bgcolor=ft.Colors.with_opacity(0.85, "#000b1a"),
            shadow=ft.BoxShadow(
                spread_radius=8,
                blur_radius=15,
                color=ft.Colors.CYAN,
                offset=ft.Offset(0, 0),
                blur_style=ft.ShadowBlurStyle.OUTER,
            )
        )

    def append_message(self, text):
        self.message_history.append(text)
        if len(self.message_history) > self.max_lines:
            self.message_history.pop(0)
        self.update_text()

    def replace_last_message(self, text):
        if self.message_history:
            self.message_history[-1] = text
        else:
            self.message_history.append(text)
        self.update_text()

    def highlight_temp_text(self, yellow_text):
        self.append_message(f"[yellow]{yellow_text}[/yellow]")

    def update_text(self):
        self.label.value = "\n".join(self.message_history)
        self.label.update()
