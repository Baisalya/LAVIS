from threading import Thread
from jarvis_hud.main import SciFiApp
from LAVIS.Lavis  import main  # Correctly import the function, not the module

if __name__ == "__main__":
    Thread(target=main, daemon=False).start()
    SciFiApp().run()
