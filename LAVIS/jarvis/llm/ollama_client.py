import os
import platform
import subprocess
import shutil
import json
import time
import requests
from LAVIS.jarvis.apps.userai.user_profile import load_user_profile, build_system_prompt

def load_config(config_file="config.json"):
    if os.path.exists(config_file):
        with open(config_file, "r") as f:
            return json.load(f)
    return {"ollama_model": "tinyllama"}

def is_connected():
    try:
        requests.get("https://www.google.com", timeout=3)
        return True
    except:
        return False
# llm_integration/ollama_utils.py



def ask_ollama(prompt: str, model: str = "tinyllama") -> str:
    try:
        # 🔁 Load latest profile & build system prompt
        profile = load_user_profile()
        system_context = build_system_prompt(profile)

        full_prompt = f"{system_context.strip()}\n\nUser said: {prompt.strip()}\nRespond as Jarvis."

        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": model, "prompt": full_prompt, "stream": False},
        )

        if response.status_code != 200:
            print("❌ Ollama API error:", response.status_code, response.text)
            return ""

        data = response.json()
        return data.get("response", "").strip()

    except Exception as e:
        print("❌ Ollama error:", e)
        return ""

def install_ollama_windows():
    print("⬇️ Downloading Ollama installer...")
    subprocess.run([
        "powershell", "-Command",
        "Invoke-WebRequest -Uri https://ollama.com/download/OllamaSetup.exe -OutFile OllamaSetup.exe; Start-Process OllamaSetup.exe"
    ], shell=True)
    print("📦 Please install Ollama, then re-run the program.")
    exit()

def check_and_setup_ollama():
    config = load_config()
    model = config.get("ollama_model", "tinyllama")

    # 1. Check if Ollama is installed
    if not shutil.which("ollama"):
        print("🛠️ Ollama not found.")
        if platform.system() == "Windows":
            install_ollama_windows()
        else:
            print("❌ Automatic install only supported on Windows. Install Ollama manually from https://ollama.com/download")
            exit()

    # 2. Check if model is downloaded
    if is_connected():
        print("🔍 Checking if model is available locally...")
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
        if model not in result.stdout:
            print(f"⬇️ Model '{model}' not found. Pulling...")
            subprocess.run(["ollama", "pull", model])
        else:
            print(f"✅ Model '{model}' already present.")
    else:
        print("⚠️ Offline. Can't pull model. Will attempt to run if already present.")

