import flet as ft
import asyncio
import datetime
import math

from components.app_bar import AppBar
from components.moving_lines import MovingHorizontalLinesOverlay
from components.particle import ParticleSystem
from components.pulse import PulseRingManager
from components.orbit import OrbitDotManager
from components.grid import generate_grid_overlay
from components.effects import generate_glow_rings, generate_rotating_layers
from widgets.hud_text_overlay import HUDTextOverlay
from components.smoke_overlay import AnimatedSmokeOverlay  # ✅ NEW


async def main(page: ft.Page):
    page.bgcolor = "#000b1a"
    page.title = "Lavis HUD"
    page.vertical_alignment = ft.MainAxisAlignment.START

    # === Initialize components ===
    overlay = MovingHorizontalLinesOverlay()
    particle_system = ParticleSystem()
    pulse_manager = PulseRingManager()
    orbit_manager = OrbitDotManager()
    app_bar_component = AppBar()
    hud_overlay = HUDTextOverlay()

    # ✅ Initialize smoke overlays
    smoke_left = AnimatedSmokeOverlay(direction="left_to_right", speed=1.2, color="cyan")
    smoke_right = AnimatedSmokeOverlay(direction="right_to_left", speed=1.0, color="magenta")

    orbit_angle = 0

    # === Layout ===
    app_bar = app_bar_component.view()
    core_stack = ft.Stack(expand=True)
    layout = ft.Stack(
        expand=True,
        controls=[
            core_stack,
            ft.Container(content=app_bar, alignment=ft.alignment.top_center, padding=ft.padding.only(top=10)),
            ft.Container(content=hud_overlay.view, alignment=ft.alignment.center),
        ]
    )

    page.add(layout)
    asyncio.create_task(app_bar_component.update_clock())

    # === Animate HUD ===
    async def animate():
        nonlocal orbit_angle
        while True:
            now = asyncio.get_event_loop().time()
            width = page.width
            height = page.height - app_bar.height - 20
            cx, cy = width / 2, height / 2
            base_radius = height / 2.8

            overlay.update_size(width, height)
            smoke_left.update_size(width, height)
            smoke_right.update_size(width, height)
            particle_system.set_center(cx, cy)
            pulse_manager.set_center(cx, cy)
            orbit_manager.set_position(cx, cy, base_radius)
            pulse_manager.maybe_pulse(now)
            particle_system.maybe_emit()

            visuals = []
            visuals += overlay.get_lines()
            visuals += pulse_manager.update()
            visuals += generate_glow_rings(cx, cy, base_radius)
            visuals += generate_rotating_layers(cx, cy, base_radius, orbit_angle)
            visuals += orbit_manager.generate(orbit_angle)
            visuals += particle_system.update()

            # Pulse core
            scale = 1 + 0.1 * math.sin(now * 4)
            visuals.append(ft.Container(
                width=40 * scale,
                height=40 * scale,
                left=cx - 20 * scale,
                top=cy - 20 * scale,
                border_radius=20 * scale,
                bgcolor="cyan",
                opacity=0.25
            ))
            visuals.append(ft.Container(
                width=8,
                height=8,
                left=cx - 4,
                top=cy - 4,
                bgcolor="white",
                border_radius=4
            ))

            # ✅ Add smoke overlays before grid
            visuals.append(smoke_left.get_overlay())
            visuals.append(smoke_right.get_overlay())

            visuals += generate_grid_overlay(width, height)

            core_stack.controls = visuals
            core_stack.update()

            orbit_angle = (orbit_angle + 1.5) % 360
            await asyncio.sleep(1 / 60)

    async def simulate_messages():
        await asyncio.sleep(2)
        hud_overlay.append_message("Jarvis boot complete.")
        await asyncio.sleep(2)
        hud_overlay.highlight_temp_text("System listening...")
        await asyncio.sleep(2)
        hud_overlay.append_message("Command: [Launch Protocol]")
        await asyncio.sleep(1)
        hud_overlay.replace_last_message("Command executed: [Launch Protocol]")

    await asyncio.gather(
        animate(),
        overlay.animate_lines(),
        smoke_left.animate(),
        smoke_right.animate(),
        simulate_messages()
    )


ft.app(target=main, view=ft.AppView.FLET_APP_HIDDEN)
