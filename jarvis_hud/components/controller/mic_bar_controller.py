from kivy.clock import Clock

class MicBarController:
    def __init__(self, hud):
        self.hud = hud  # HUDInterface reference

    def update_level(self, rms_level):
        """Convert RMS (volume level) to a percent and update the HUD."""
        level = min(100, int(rms_level / 3))
        Clock.schedule_once(lambda dt: self.hud.update_mic_level(level))
