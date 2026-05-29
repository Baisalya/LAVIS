import os
import platform
import subprocess
import shutil
import json
import requests

OLLAMA_TIMEOUT_SECONDS = float(os.getenv("LAVIS_OLLAMA_TIMEOUT", "12"))

# =========================
# CONFIG LOAD
# =========================
def load_config(config_file="config.json"):
    if not os.path.isabs(config_file):
        config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), config_file)
    if os.path.exists(config_file):
        with open(config_file, "r") as f:
            return json.load(f)
    return {"ollama_model": "llama3.1"}  # default

# =========================
# INTERNET CHECK
# =========================
def is_connected():
    try:
        requests.get("https://www.google.com", timeout=3)
        return True
    except:
        return False

# =========================
# OLLAMA REQUEST
# =========================
def ask_ollama(prompt: str, model: str = "llama3.1") -> str:
    try:
        system_prompt = (
            "You are Lavis, a smart AI assistant like Jarvis. "
            "You were created by Lala. Always be respectful, helpful, and friendly. "
            "Give short, clear answers unless more detail is needed."
        )

        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model,
                "prompt": f"{system_prompt}\n\nUser: {prompt}\nLavis:",
                "stream": False,
                "options": {
                    "temperature": 0.7
                }
            },
            timeout=OLLAMA_TIMEOUT_SECONDS
        )

        if response.status_code == 404:
            print(f"❌ Ollama error: Model '{model}' not found. Please run 'ollama pull {model}' in your terminal.")
            return ""

        data = response.json()
        return data.get("response", "").strip()

    except Exception as e:
        print("❌ Ollama error:", e)
        return "Sorry, I couldn't respond."
        return ""

# =========================
# INSTALL OLLAMA (WINDOWS)
# =========================
def install_ollama_windows():
    print("⬇️ Downloading Ollama installer...")
    subprocess.run([
        "powershell", "-Command",
        "Invoke-WebRequest -Uri https://ollama.com/download/OllamaSetup.exe -OutFile OllamaSetup.exe; Start-Process OllamaSetup.exe"
    ], shell=True)
    print("📦 Install Ollama and re-run.")
    exit()

# =========================
# CHECK + SETUP OLLAMA
# =========================
def check_and_setup_ollama():
    config = load_config()
    model = config.get("ollama_model", "llama3.1")

    # Check Ollama installed
    if not shutil.which("ollama"):
        print("🛠️ Ollama not found.")
        if platform.system() == "Windows":
            install_ollama_windows()
        else:
            print("Install Ollama manually from https://ollama.com")
            exit()

    # Check model
    print("🔍 Checking model...")
    result = subprocess.run(["ollama", "list"], capture_output=True, text=True)

    if model not in result.stdout:
        if is_connected():
            print(f"⬇️ Downloading model: {model} ...")
            subprocess.run(["ollama", "pull", model])
        else:
            print("⚠️ Offline and model not found!")
            exit()
    else:
        print(f"✅ Model '{model}' ready.")

# =========================
# MAIN CHAT LOOP
# =========================
def main():
    check_and_setup_ollama()
    config = load_config()
    model = config.get("ollama_model", "llama3.1")

    print(f"\n🤖 Lavis (Jarvis Mode) using {model}")
    print("Type 'exit' to quit\n")

    while True:
        user_input = input("You: ").strip()

        if user_input.lower() in {"exit", "quit"}:
            print("👋 Goodbye!")
            break

        response = ask_ollama(user_input, model)
        print(f"Lavis: {response}\n")

# =========================
# RUN
# =========================
if __name__ == "__main__":
    main()
