import os
import subprocess
import win32com.client
import re
from fuzzywuzzy import fuzz

_app_cache = None  # Cache to avoid reloading every time

def get_start_menu_apps(force_reload=False):
    """
    Fetch and cache list of applications from Start Menu (.lnk) and UWP (Get-StartApps).
    App IDs are now accurately extracted for UWP launch.
    """
    global _app_cache
    if _app_cache is not None and not force_reload:
        return _app_cache

    shell = win32com.client.Dispatch("WScript.Shell")
    start_menu_paths = [
        os.path.join(os.environ['APPDATA'], r'Microsoft\Windows\Start Menu\Programs'),
        os.path.join(os.environ['PROGRAMDATA'], r'Microsoft\Windows\Start Menu\Programs')
    ]

    apps = []

    # --- Desktop (.lnk) Shortcuts ---
    for path in start_menu_paths:
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.endswith('.lnk'):
                    full_path = os.path.join(root, file)
                    try:
                        shortcut = shell.CreateShortcut(full_path)
                        target_path = shortcut.TargetPath
                        if target_path:  # skip broken shortcuts
                            apps.append({
                                "name": os.path.splitext(file)[0].lower(),
                                "target": target_path,
                                "type": "desktop"
                            })
                    except Exception as e:
                        print(f"⚠️ Skipping shortcut '{file}': {e}")

    # --- UWP Apps via PowerShell (with correct AppID formatting) ---
    try:
        result = subprocess.check_output(
            ['powershell', '-Command', 'Get-StartApps | Format-Table -HideTableHeaders Name, AppID'],
            universal_newlines=True,
            stderr=subprocess.DEVNULL
        )
        for line in result.strip().splitlines():
            parts = re.split(r'\s{2,}', line.strip())
            if len(parts) == 2:
                name = parts[0].strip().lower()
                app_id = parts[1].strip()
                if app_id and "chrome" not in app_id.lower():  # filter Chrome web apps
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

    def find_best(apps):
        best_match = None
        highest_score = 0
        for app in apps:
            score = fuzz.partial_ratio(app_name.lower(), app["name"])
            if score > highest_score:
                highest_score = score
                best_match = app
        return best_match, highest_score

    best_match, score = find_best(apps)

    # Retry if not found
    if not best_match or score < 70:
        print(f"[INFO] No good match for '{app_name}'. Reloading apps cache...")
        apps = get_start_menu_apps(force_reload=True)
        best_match, score = find_best(apps)

    if best_match and score >= 70:
        print(f"[DEBUG] 🎯 Best match: {best_match['name']} ({score}%)")
        print(f"[DEBUG] 🚀 Launch type: {best_match['type']}")
        print(f"[DEBUG] 🛣️ Launch target: {best_match['target']}")

        try:
            if best_match["type"] == "desktop":
                subprocess.Popen(['start', '', best_match["target"]], shell=True)

            elif best_match["type"] == "uwp":
                subprocess.Popen([
                    'explorer.exe', f"shell:AppsFolder\\{best_match['target']}"
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            else:
                print(f"[ERROR] Unknown app type for: {best_match['name']}")
                return False

            return True

        except Exception as e:
            print(f"[ERROR] ❌ Failed to open {best_match['name']}: {e}")
            return False

    print(f"[WARN] ❌ No matching app found for: {app_name}")
    return False
