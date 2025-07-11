# LAVIS/utils/hud_utils.py
from jarvis_hud.main import hud_interface
from jarvis_hud.components.hud_controller import HUDController
import os
os.environ["TORIO_DISABLE_EXTENSION"] = "1"

def get_hud_controller():
    if hud_interface is not None:
        return HUDController(hud_interface)
    return None
