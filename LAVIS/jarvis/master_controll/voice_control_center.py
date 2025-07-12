from command_handler import handle_voice_command
from LAVIS.jarvis.voice.recognizer import recognize_voice_input  # your existing recognizer

def start_voice_control_loop():
    print("🎤 Voice Control Active. Say a command.")
    while True:
        query = recognize_voice_input()
        if query:
            print(f"🗣️ You said: {query}")
            handle_voice_command(query)
