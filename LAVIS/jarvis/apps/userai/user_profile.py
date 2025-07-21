import json
import re
from datetime import datetime
from fuzzywuzzy import fuzz
import os
# Load user profile from JSON
# ✅ Load user profile from JSON
import os
import json
import json
import re
from datetime import datetime
from fuzzywuzzy import fuzz
import os

def load_user_profile(filename="user_profile.json") -> dict:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    profile_path = os.path.join(script_dir, filename)

    try:
        with open(profile_path, "r", encoding="utf-8") as f:
            profile = json.load(f)
            print(f"✅ Loaded profile from {profile_path}")
            return profile
    except FileNotFoundError:
        print(f"❌ Profile not found: {profile_path}")
    except json.JSONDecodeError as e:
        print(f"❌ Profile JSON error: {e}")
    except Exception as e:
        print(f"❌ Unknown profile error: {e}")

    return {}



# Extract keywords from question
def extract_keywords(text: str):
    text = text.lower()
    return set(re.findall(r"\b(name|nickname|age|birthday|dob|creator|created|father|loyal|loyalty|color|favourite|favorite|live|location|hobby|photo|image|picture|purpose|version|yourself|jarvis|who|you|do you do|abilities|what can you do|personality|goal|how old|mood|trait|quirk|emotion|feeling|last interaction|recent|command)\b", text))

# Answer user queries intelligently
import re
from datetime import datetime
from fuzzywuzzy import fuzz

def answer_about_user(query: str, profile: dict) -> str | None:
    query = query.lower()
    keywords = set(re.findall(
        r"\b(name|nickname|age|birthday|dob|creator|created|father|who made you|who created you|made you|loyal|loyalty|color|favourite|favorite|live|location|hobby|photo|image|picture|purpose|version|yourself|jarvis|who|you|do you do|abilities|what can you do|personality|goal|how old|mood|trait|quirk|emotion|feeling|last interaction|recent|command)\b",
        query
    ))

    jarvis = profile.get("jarvis_self", {})
    memory = profile.get("memory", {})
    traits = profile.get("personality_traits", {})

    # === JARVIS Self-Awareness ===
    if any(k in query for k in ["who are you", "what are you", "jarvis", "yourself", "version", "what can you do"]):
        if not jarvis:
            return None
        response = (
            f"I am {jarvis.get('name', 'your assistant')}, version {jarvis.get('version', 'unknown')}.\n"
            f"I was created by {jarvis.get('created_by', 'an unknown creator')}.\n"
            f"My personality is {jarvis.get('personality', 'supportive')}.\n"
            f"My main goal is: {jarvis.get('goal', 'assist you')}."
        )
        abilities = jarvis.get("abilities", [])
        if abilities:
            response += "\nHere’s what I can do: " + ", ".join(abilities) + "."
        return response

    # === User Personal Info ===
    if "name" in keywords:
        return f"Your name is {profile.get('name', 'not set')}."
    if "nickname" in keywords:
        return f"Your nickname is {profile.get('nick_name', 'not set')}."
    if "age" in keywords or "birthday" in keywords or "dob" in keywords or "how old" in query:
        dob = profile.get("dob")
        if dob:
            birth_year = int(dob.split("-")[0])
            age = datetime.now().year - birth_year
            return f"You were born on {dob}, so you're about {age} years old."
        return "I couldn't determine your age."
    
    # ✅ FIXED: Handle creator question properly
    if "creator" in keywords or "created" in keywords or "father" in keywords or "who made you" in query or "who created you" in query or "made you" in query:
        creator_name = (
            jarvis.get("created_by") 
            or profile.get("creator") 
            or profile.get("name")
        )
        if creator_name:
            return f"My creator is {creator_name}."
        return "I don't know who created me."

    if "loyal" in keywords:
        return f"I am loyal to {profile.get('loyal_to', 'my creator')}."
    if "color" in keywords or "favourite" in keywords or "favorite" in keywords:
        return f"Your favorite color is {profile.get('favorite_color', 'unknown')}."
    if "hobby" in keywords:
        hobbies = profile.get("hobbies", [])
        return f"Your hobbies include: {', '.join(hobbies)}."
    if "live" in keywords or "location" in keywords:
        return f"You live in {profile.get('location', 'an unknown location')}."
    if "photo" in keywords or "image" in keywords or "picture" in keywords:
        return f"Your photo is stored at {profile.get('photo', 'not available')}."
    if "purpose" in keywords or "do you do" in query:
        return profile.get("purpose", "I assist you, but my purpose is not defined.")

    # === Advanced Memory/Personality ===
    if "trait" in keywords or "personality" in keywords:
        return f"Your core traits: {', '.join(traits.get('core', []))}."
    if "quirk" in keywords:
        return f"Your quirks: {', '.join(traits.get('quirks', []))}."
    if "mood" in keywords or "emotion" in keywords or "feeling" in keywords:
        return f"Your current mood is: {traits.get('mood', 'not available')}."
    if "last interaction" in query or "recent" in keywords or "command" in keywords:
        cmds = memory.get("recent_commands", [])
        if cmds:
            return f"Your last command was: '{cmds[-1]}'"
        return "No recent commands found."

    # === Jarvis-specific goals or emotion engine ===
    if "goal" in keywords:
        return jarvis.get("goal", "My goal is to assist you.")
    if "abilities" in keywords:
        return "I'm capable of: " + ", ".join(jarvis.get("abilities", [])) + "."
    if "emotion engine" in query:
        engine = jarvis.get("emotion_engine", {})
        return f"My emotion engine is {'active' if engine.get('active') else 'inactive'}, state: {engine.get('default_state', 'neutral')}."

    # === Fuzzy fallback: semantic best match ===
    best_score = 0
    best_key = None
    for key in profile:
        if isinstance(profile[key], str):
            score = fuzz.partial_ratio(query, key)
            if score > best_score:
                best_score = score
                best_key = key

    if best_score > 70:
        return f"{best_key.capitalize()}: {profile[best_key]}"

    # No confident match — signal fallback to continue
    print("ℹ️ No matching profile data found.")
    return None
