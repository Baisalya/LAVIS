# LAVIS/utils/hud_utils.py

_hud_controller_instance = None  # global cache

def set_hud_controller(controller):
    global _hud_controller_instance
    _hud_controller_instance = controller

def get_hud_controller():
    return _hud_controller_instance
