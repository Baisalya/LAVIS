# mic_bar_controller.py
from kivy.clock import Clock

class MicBarController:
    def __init__(self, hud):
        self.hud = hud

    def update_level(self, rms_level):
        level = min(100, int(rms_level / 3))
        #print(f"[MIC UPDATE] Level: {level}")
        Clock.schedule_once(lambda dt: self.hud.update_mic_level(level))
