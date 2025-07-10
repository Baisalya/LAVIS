from jarvis_hud.main import hud_interface
from jarvis_hud.components.hud_controller import HUDController

def get_hud_controller():
    if hud_interface:
        return HUDController(hud_interface)
    return None
