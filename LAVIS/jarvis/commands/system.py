import datetime
from LAVIS.jarvis.voice.speaker import speak

# Will be set by LavisRunner at runtime
core_instance = None

def set_core_instance(core):
    global core_instance
    core_instance = core

def handle_system(command: str) -> bool:
    command = command.lower().strip()

    # 🔧 Sleep triggers
    if any(x in command for x in ["exit", "shutdown", "quit", "go to sleep"]):
        speak("Okay, going to sleep 🛌")
        if core_instance:
            try:
                core_instance.core.session_state = "sleep"
            except Exception:
                pass
        return True

    elif "time" in command:
        now = datetime.datetime.now().strftime("%I:%M %p")
        speak(f"The time is {now}.")
        return True

    elif "date" in command:
        today = datetime.datetime.now().strftime("%A, %B %d, %Y")
        speak(f"Today is {today}.")
        return True

    return False
