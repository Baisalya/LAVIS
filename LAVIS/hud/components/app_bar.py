import flet as ft
import datetime
import asyncio

class AppBar:
    def __init__(self):
        self.clock_label = ft.Text(size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.RED)
        self.date_label = ft.Text(size=16, color=ft.Colors.ORANGE)
        self.lavis_label = ft.Text(value="Lavis", size=26, color="cyan", text_align=ft.TextAlign.CENTER)
        self.status_text = ft.Text(value="System Status", size=16, color=ft.Colors.RED)
        self.status_bar = ft.ProgressBar(value=0.8, width=150, bar_height=20, color="green",
                                         bgcolor=ft.Colors.with_opacity(0.2, "white"))

    def view(self):
        return ft.Container(
            height=60,
            padding=ft.padding.only(top=8, left=20, right=20, bottom=10),
            bgcolor=ft.Colors.with_opacity(0.15, "cyan"),
            border_radius=10,
            border=ft.border.all(1.2, ft.Colors.with_opacity(0.4, "cyan")),
            content=ft.Row(
                controls=[
                    ft.Row([self.clock_label, self.date_label], spacing=18, expand=1),
                    ft.Container(content=self.lavis_label, alignment=ft.alignment.center, expand=1),
                    ft.Row([self.status_text, self.status_bar], spacing=10, expand=1)
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN
            )
        )

    async def update_clock(self):
        while True:
            now = datetime.datetime.now()
            self.clock_label.value = now.strftime("%I:%M:%S %p")
            self.date_label.value = now.strftime("%Y.%m.%d")
            self.clock_label.update()
            self.date_label.update()
            await asyncio.sleep(1)
