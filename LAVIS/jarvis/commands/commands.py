# commands.py
from LAVIS.jarvis.commands.system import handle_system
from LAVIS.jarvis.web.browser import handle_browser
from LAVIS.jarvis.web.fallback import handle_fallback
from LAVIS.jarvis.commands.apps import open_windows_app
from LAVIS.jarvis.commands.explorer import handle_explorer
from LAVIS.jarvis.commands.input_control import handle_input_control

def handle_command(command: str) -> bool:
    command = command.lower().strip()

  
    # App opening
    if command.startswith("open "):
        app_name = command[5:].strip()
        if open_windows_app(app_name):
            return True

    for handler in [
        handle_input_control,
        handle_explorer,
        handle_system,
        handle_browser,
        handle_fallback
    ]:
        try:
            if handler(command):
                return True
        except Exception as e:
            print(f"❌ Error in {handler.__name__}: {e}")

    return False
