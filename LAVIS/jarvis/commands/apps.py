import os
import subprocess
import win32com.client
import re
from fuzzywuzzy import fuzz

_app_cache = None  # Cache to avoid reloading every time

def get_start_menu_apps(force_reload=False):
    """Fetch and cache list of applications from Start Menu and UWP apps."""
    global _app_cache
    if _app_cache is not None and not force_reload:
        return _app_cache

    shell = win32com.client.Dispatch("WScript.Shell")
    start_menu_paths = [
        os.path.join(os.environ['APPDATA'], r'Microsoft\Windows\Start Menu\Programs'),
        os.path.join(os.environ['PROGRAMDATA'], r'Microsoft\Windows\Start Menu\Programs')
    ]

    apps = []

    # --- Add traditional apps via .lnk shortcuts ---
    for path in start_menu_paths:
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.endswith('.lnk'):
                    full_path = os.path.join(root, file)
                    try:
                        shortcut = shell.CreateShortcut(full_path)
                        apps.append({
                            "name": os.path.splitext(file)[0].lower(),
                            "target": shortcut.TargetPath,
                            "type": "desktop"
                        })
                    except Exception as e:
                        print(f"⚠️ Skipping shortcut '{file}': {e}")

    # --- Add UWP apps via Powershell ---
    try:
        result = subprocess.check_output(
            ['powershell', '-Command', 'Get-StartApps'],
            universal_newlines=True,
            stderr=subprocess.DEVNULL
        )
        lines = result.splitlines()
        for line in lines[3:]:  # skip headers
            parts = re.split(r'\s{2,}', line.strip())
            if len(parts) >= 2:
                name, app_id = parts[0].strip().lower(), parts[1].strip()
                apps.append({
                    "name": name,
                    "target": app_id,
                    "type": "uwp"
                })
    except Exception as e:
        print(f"⚠️ Failed to load UWP apps: {e}")

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
            if best_match["type"] == "desktop":
                subprocess.Popen(['start', '', best_match["target"]], shell=True)
            elif best_match["type"] == "uwp":
                subprocess.Popen(['explorer.exe', f"shell:AppsFolder\\{best_match['target']}"])
            return True
        except Exception as e:
            print(f"❌ Failed to open {best_match['name']}: {e}")
    return False
