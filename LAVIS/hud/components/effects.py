import flet as ft
import math

def generate_glow_rings(cx, cy, radius):
    rings = []
    for i in range(4):
        r = radius * (1 - i * 0.1)
        opacity = 0.06 + 0.04 * (4 - i)
        rings.append(ft.Container(
            width=r * 2,
            height=r * 2,
            left=cx - r,
            top=cy - r,
            border_radius=r,
            bgcolor="cyan",
            opacity=opacity
        ))
    return rings

def generate_rotating_layers(cx, cy, radius, angle):
    layers = []
    for i in range(3):
        r = radius * (0.8 - i * 0.15)
        offset = (angle + i * 60) % 360
        x = cx - r + math.sin(math.radians(offset)) * 4
        y = cy - r + math.cos(math.radians(offset)) * 4
        fade = 0.06 + 0.04 * (3 - i)
        layers.append(ft.Container(
            width=2 * r,
            height=2 * r,
            left=x,
            top=y,
            border_radius=r,
            bgcolor="#00ffff",
            opacity=fade
        ))
    return layers
