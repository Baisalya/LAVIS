import os
import json
from rapidfuzz import process, fuzz
from symspellpy.symspellpy import SymSpell, Verbosity

# === Paths and Constants ===
BASE_DIR = os.path.dirname(__file__)
DICT_PATH = os.path.join(BASE_DIR, "dict", "frequency_dictionary_en_82_765.txt")
COMMAND_FILE = os.path.join(BASE_DIR, "user_commands.json")
DEFAULT_COMMANDS = [
    "open chrome", "open whatsapp", "start calculator", "launch notepad",
    "play music", "stop music", "shutdown", "restart",
    "pause listening", "resume listening", "turn on the lights", "turn off the lights",
    "exit session", "start session", "hello jarvis", "goodbye"
]

# === Load SymSpell ===

sym_spell = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
if not sym_spell.load_dictionary(DICT_PATH, term_index=0, count_index=1):
    print("⚠️ SymSpell dictionary not found or failed to load. Download it from:")
    print("🔗 https://github.com/wolfgarbe/SymSpell/tree/master/SymSpell/frequency_dictionary")

# === Load & Save Commands ===

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
    except Exception as e:
        print(f"❌ Error saving new command: {e}")

# === Main Correction Function ===

def correct_command(text: str) -> str:
    if not text:
        return ""

    original = text.strip().lower()

    # Step 1: SymSpell spelling correction
    suggestions = sym_spell.lookup_compound(original, max_edit_distance=2)
    corrected = suggestions[0].term if suggestions else original
    if corrected != original:
        print(f"🔤 SymSpell corrected: '{original}' → '{corrected}'")

    # Step 2: RapidFuzz best match
    all_commands = load_commands()
    match, score, _ = process.extractOne(corrected, all_commands, scorer=fuzz.ratio)

    if score > 80:
        if match != corrected:
            print(f"🧠 Matched to known command: '{corrected}' → '{match}'")
        return match

    # Step 3: Learn unknown commands
    if corrected not in all_commands:
        print(f"💡 Learned new command: '{corrected}'")
        save_new_command(corrected)

    return corrected
