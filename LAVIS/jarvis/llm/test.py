import os
import platform
import subprocess
import json
from ctransformers import AutoModelForCausalLM
from apps.userai.user_profile import load_user_profile, build_system_prompt, answer_about_user


# 🔁 MODE: "fast" or "smart"
MODE = "fast"  # Change to "smart" for deeper answers


# ✅ Load GGUF model
llm = AutoModelForCausalLM.from_pretrained(
    'llm',
    model_file='ggml-model-q4_0.gguf',  # Use a bigger GGUF like Q4_K_M if needed
    model_type='llama',
    max_new_tokens=64 if MODE == "fast" else 128,
    context_length=512,  # Upgrade to 2048+ if your model allows
    temperature=0.7 if MODE == "smart" else 0.2,
    top_k=40 if MODE == "smart" else 10,
    stream=True,  # ⬅️ Enables streaming output
    gpu_layers=0
)


# 🧠 Load user profile & system context
profile = load_user_profile()
system_prompt = build_system_prompt(profile)


# 💬 Prompt formatting
def format_prompt(question: str) -> str:
    return (
        f"{system_prompt.strip()}\n\n"
        "You are Lavish, a smart assistant.\n"
        f"User: {question.strip()}\n"
        "Lavish:"
    )

def extract_reply(output: str) -> str:
    return output.split("Lavish:")[-1].strip()


# 🔧 Handle basic commands (e.g., open apps)
def handle_command(text: str) -> bool:
    command = text.lower()

    if "open chrome incognito" in command:
        return open_chrome_incognito()

    # Add more command patterns here
    return False

def open_chrome_incognito() -> bool:
    try:
        if platform.system() == "Windows":
            subprocess.Popen(["start", "chrome", "--incognito"], shell=True)
        elif platform.system() == "Darwin":
            subprocess.Popen(["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "--incognito"])
        elif platform.system() == "Linux":
            subprocess.Popen(["google-chrome", "--incognito"])
        else:
            print("❌ Unsupported OS for Chrome command.")
            return False
        return True
    except Exception as e:
        print("❌ Error launching Chrome:", e)
        return False


# 🌀 Main interactive loop
def start_chat():
    print(f"💖 Chat with Lavish ({MODE.title()} Mode). Type 'exit' to quit.")

    while True:
        try:
            user_input = input("\nYou: ").strip()
            if user_input.lower() in ["exit", "quit"]:
                print("Lavish: Take care, love 🫶")
                break

            # Step 1: Command handler
            if handle_command(user_input):
                print("Lavish: I've done that for you 💻")
                continue

            # Step 2: Memory-based profile response
            answer = answer_about_user(user_input, profile)
            if answer:
                print("Lavish:", answer)
                continue
            else:
                print("ℹ️ No matching profile data found. Answering anyway...")

            # Step 3: Generate response using LLM (streamed)
            full_prompt = format_prompt(user_input)
            print("Lavish:", end=' ', flush=True)
            for token in llm(full_prompt):
                print(token, end='', flush=True)
            print()  # end line after stream

        except KeyboardInterrupt:
            print("\nLavish: Goodbye for now 💫")
            break


if __name__ == "__main__":
    start_chat()
