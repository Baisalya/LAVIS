import flet as ft

def generate_grid_overlay(width, height, rows=40, cols=40):
    lines = []
    color = ft.Colors.with_opacity(0.1, "#00ffff")
    for i in range(cols + 1):
        x = (width / cols) * i
        lines.append(ft.Container(left=x, top=0, width=2, height=height, bgcolor=color))
    for j in range(rows + 1):
        y = (height / rows) * j
        lines.append(ft.Container(left=0, top=y, width=width, height=2, bgcolor=color))
    return lines
