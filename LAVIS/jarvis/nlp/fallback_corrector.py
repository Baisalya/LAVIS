import json
import os
import difflib

# ✅ Use correct import path for latest optimum
try:
    from transformers import T5Tokenizer
    from optimum.onnxruntime.modeling_ort import ORTModelForConditionalGeneration

    # Set ONNX model path (relative to this file)
    ONNX_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../t5-small-onnx"))
    tokenizer = T5Tokenizer.from_pretrained(ONNX_DIR)
    model = ORTModelForConditionalGeneration.from_pretrained(ONNX_DIR)
    T5_AVAILABLE = True
except Exception as e:
    print("⚠️ T5-ONNX model could not be loaded:", e)
    T5_AVAILABLE = False

# === Config ===
COMMAND_FILE = os.path.join(os.path.dirname(__file__), "user_commands.json")
DEFAULT_COMMANDS = [
    "open chrome", "open calculator", "what is your name",
    "play music", "stop music", "shutdown", "restart",
    "pause listening", "resume listening", "what is the weather",
    "turn on the lights", "turn off the lights", "exit session",
    "start session", "hello jarvis", "goodbye"
]

def load_commands():
    if os.path.exists(COMMAND_FILE):
        try:
            with open(COMMAND_FILE, "r") as f:
                return list(set(DEFAULT_COMMANDS + json.load(f)))
        except:
            return DEFAULT_COMMANDS.copy()
    return DEFAULT_COMMANDS.copy()

def save_new_command(new_command: str):
    try:
        existing = []
        if os.path.exists(COMMAND_FILE):
            with open(COMMAND_FILE, "r") as f:
                existing = json.load(f)
        if new_command not in existing:
            existing.append(new_command)
            with open(COMMAND_FILE, "w") as f:
                json.dump(existing, f, indent=2)
    except:
        pass

# === Correction pipeline ===
def correct_command(text: str) -> str:
    if not text:
        return ""

    original = text
    text = text.strip().lower()

    # Step 1: T5 grammar correction
    if T5_AVAILABLE:
        try:
            input_text = f"fix: {text}"
            inputs = tokenizer(input_text, return_tensors="pt")
            outputs = model.generate(**inputs, max_length=32)
            text = tokenizer.decode(outputs[0], skip_special_tokens=True)
            print(f"🤖 T5-ONNX corrected: '{original}' → '{text}'")
        except Exception as e:
            print("⚠️ T5 correction failed, using fallback fuzzy:", e)

    # Step 2: Fuzzy match to known commands
    all_commands = load_commands()
    matches = difflib.get_close_matches(text, all_commands, n=1, cutoff=0.6)
    corrected = matches[0] if matches else text

    if corrected != text:
        print(f"🛠️ Fuzzy corrected: '{text}' → '{corrected}'")
    elif corrected not in all_commands:
        print(f"💡 New command learned: '{corrected}'")
        save_new_command(corrected)

    return corrected
    