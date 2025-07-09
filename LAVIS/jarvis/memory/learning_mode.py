import os
import time
import psutil
import json
from  LAVIS.jarvis.voice.speaker import speak

# ✅ Memory file to store learned actions
MEMORY_FILE = "jarvis_learned_actions.json"

def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    return {}

def save_memory(memory):
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=4)

def get_foreground_app_details():
    try:
        import win32gui
        import win32process

        window = win32gui.GetForegroundWindow()
        if not window:
            return None

        tid, pid = win32process.GetWindowThreadProcessId(window)
        process = psutil.Process(pid)
        title = win32gui.GetWindowText(window)
        exe = process.name()
        exe_path = process.exe()

        # UWP apps
        if exe.lower() == "applicationframehost.exe":
            for child in process.children(recursive=True):
                try:
                    if "whatsapp" in child.name().lower():
                        return {
                            "exe": child.name(),
                            "path": child.exe(),
                            "title": title
                        }
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

        return {
            "exe": exe,
            "path": exe_path,
            "title": title
        }

    except Exception as e:
        print("❌ Foreground process error:", e)
        return None

# ✅ Inject `listen()` to avoid circular import
def learning_mode(listen_func):
    speak("Learning started. Do your tasks. Say 'stop learning' when done.")
    memory = load_memory()
    learned_sequence = []
    observed = set()
    start_time = time.time()

    while True:
        app_info = get_foreground_app_details()
        if app_info:
            identifier = app_info["path"]
            if identifier not in observed:
                print(f"🧠 Detected new action: {app_info}")
                learned_sequence.append(app_info)
                observed.add(identifier)

        try:
            user_input = listen_func(timeout=2, phrase_time_limit=4).lower()
            if "stop learning" in user_input:
                break
        except:
            pass

        if time.time() - start_time > 120:
            speak("Learning timeout.")
            break

    if learned_sequence:
        speak("What should I call this sequence?")
        label = listen_func(timeout=5, phrase_time_limit=5).lower()
        memory[label] = learned_sequence
        save_memory(memory)
        speak(f"Learned sequence '{label}' with {len(learned_sequence)} steps.")
    else:
        speak("No actions were detected to learn.")

def open_learned_app(command):
    memory = load_memory()
    for label, steps in memory.items():
        if label in command:
            try:
                if isinstance(steps, list):
                    for step in steps:
                        path = step.get("path")
                        if path and os.path.exists(path):
                            os.startfile(path)
                            time.sleep(1)
                    speak(f"Completed sequence '{label}'.")
                else:
                    path = steps.get("path")
                    if path and os.path.exists(path):
                        os.startfile(path)
                        speak(f"Opening {label}.")
                return True
            except Exception as e:
                print("❌ Failed to open learned item:", e)
                speak("Failed to open it.")
                return False
    return False

def list_learned_commands():
    memory = load_memory()
    if not memory:
        speak("I haven't learned anything yet.")
    else:
        speak("Here are the things I've learned:")
        for label in memory:
            speak(label)

def rename_learned_command(listen_func):
    memory = load_memory()
    speak("Which command would you like to rename?")
    old = listen_func(timeout=5, phrase_time_limit=5).lower()
    if old in memory:
        speak("What should I call it now?")
        new = listen_func(timeout=5, phrase_time_limit=5).lower()
        memory[new] = memory.pop(old)
        save_memory(memory)
        speak(f"Renamed '{old}' to '{new}'.")
    else:
        speak("I couldn't find that command.")

def delete_learned_command(listen_func):
    memory = load_memory()
    speak("Which command should I forget?")
    target = listen_func(timeout=5, phrase_time_limit=5).lower()
    if target in memory:
        del memory[target]
        save_memory(memory)
        speak(f"I have forgotten '{target}'.")
    else:
        speak("I couldn't find that command.")
