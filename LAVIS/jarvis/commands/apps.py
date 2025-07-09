# apps.py
import os
import subprocess
import win32com.client
from fuzzywuzzy import fuzz

_app_cache = None  # Cache to avoid reloading every time

def get_start_menu_apps(force_reload=False):
    """Fetch and cache list of applications from Start Menu."""
    global _app_cache
    if _app_cache is not None and not force_reload:
        return _app_cache

    shell = win32com.client.Dispatch("WScript.Shell")
    start_menu_paths = [
        os.path.join(os.environ['APPDATA'], r'Microsoft\Windows\Start Menu\Programs'),
        os.path.join(os.environ['PROGRAMDATA'], r'Microsoft\Windows\Start Menu\Programs')
    ]

    apps = []
    for path in start_menu_paths:
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.endswith('.lnk'):
                    full_path = os.path.join(root, file)
                    try:
                        shortcut = shell.CreateShortcut(full_path)
                        apps.append({
                            "name": os.path.splitext(file)[0].lower(),
                            "target": shortcut.TargetPath
                        })
                    except Exception as e:
                        print(f"⚠️ Skipping shortcut '{file}': {e}")
    _app_cache = apps
    return _app_cache


def open_windows_app(app_name: str) -> bool:
    apps = get_start_menu_apps()

    best_match = None
    highest_score = 0

    for app in apps:
        score = fuzz.partial_ratio(app_name.lower(), app["name"])
        if score > highest_score:
            highest_score = score
            best_match = app

    if best_match and highest_score >= 70:
        try:
            subprocess.Popen(['start', '', best_match["target"]], shell=True)
            return True
        except Exception as e:
            print(f"❌ Failed to open {best_match['name']}: {e}")
    return False
