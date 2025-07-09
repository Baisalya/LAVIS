from threading import Thread
from jarvis_hud.main import SciFiApp
from Lavis  import main  # Correctly import the function, not the module

if __name__ == "__main__":
    Thread(target=main, daemon=True).start()
    SciFiApp().run()
