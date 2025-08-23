import os
import json
import re
from datetime import datetime
from fuzzywuzzy import fuzz

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

def answer_about_user(query: str, profile: dict) -> str | None:
    from fuzzywuzzy import fuzz
    import re

    query = query.lower()
    keywords = set(re.findall(
        r"\b(name|nickname|age|birthday|dob|creator|created|father|who made you|who created you|made you|loyal|loyalty|color|favourite|favorite|live|location|hobby|photo|image|picture|purpose|version|yourself|Lavis|who|you|do you do|abilities|what can you do|personality|goal|how old|mood|trait|quirk|emotion|feeling|last interaction|recent|command|friend|family|mother|father|sister|brother|cousin|nature|funny fact)\b",
        query
    ))

    Lavis = profile.get("Lavis_self", {})
    memory = profile.get("memory", {})
    traits = profile.get("personality_traits", {})

    if any(k in query for k in ["who are you", "what are you", "Lavis", "yourself", "version", "what can you do"]):
        if not Lavis:
            return None
        response = (
            f"I am {Lavis.get('name', 'your assistant')}, version {Lavis.get('version', 'unknown')}\n"
            f"I was created by {Lavis.get('created_by', 'an unknown creator')}\n"
            f"My personality is {Lavis.get('personality', 'supportive')}\n"
            f"My main goal is: {Lavis.get('goal', 'assist you')}"
        )
        abilities = Lavis.get("abilities", [])
        if abilities:
            response += "\nHere’s what I can do: " + ", ".join(abilities) + "."
        return response

    if "name" in keywords:
        return f"Your name is {profile.get('name', 'not set')}"
    if "nickname" in keywords:
        return f"Your nickname is {profile.get('nick_name', 'not set')}"
    if "age" in keywords or "birthday" in keywords or "dob" in keywords or "how old" in query:
        dob = profile.get("dob")
        if dob:
            birth_year = int(dob.split("-")[0])
            age = datetime.now().year - birth_year
            return f"You were born on {dob}, so you're about {age} years old."
        return "I couldn't determine your age."

    if "creator" in keywords or "created" in keywords or "father" in keywords or "who made you" in query or "who created you" in query or "made you" in query:
        creator_name = (
            Lavis.get("created_by") 
            or profile.get("creator") 
            or profile.get("name")
        )
        if creator_name:
            return f"My creator is {creator_name}."
        return "I don't know who created me."

    if "loyal" in keywords:
        return f"I am loyal to {profile.get('loyal_to', 'my creator')}"
    if "color" in keywords or "favourite" in keywords or "favorite" in keywords:
        return f"Your favorite color is {profile.get('favorite_color', 'unknown')}"
    if "hobby" in keywords:
        hobbies = profile.get("hobbies", [])
        return f"Your hobbies include: {', '.join(hobbies)}"
    if "live" in keywords or "location" in keywords:
        return f"You live in {profile.get('location', 'an unknown location')}"
    if "photo" in keywords or "image" in keywords or "picture" in keywords:
        return f"Your photo is stored at {profile.get('photo', 'not available')}"
    if "purpose" in keywords or "do you do" in query:
        return profile.get("purpose", "I assist you, but my purpose is not defined.")

    if "trait" in keywords or "personality" in keywords:
        return f"Your core traits: {', '.join(traits.get('core', []))}"
    if "quirk" in keywords:
        return f"Your quirks: {', '.join(traits.get('quirks', []))}"
    if "mood" in keywords or "emotion" in keywords or "feeling" in keywords:
        return f"Your current mood is: {traits.get('mood', 'not available')}"
    if "last interaction" in query or "recent" in keywords or "command" in keywords:
        cmds = memory.get("recent_commands", [])
        if cmds:
            return f"Your last command was: '{cmds[-1]}'"
        return "No recent commands found."

    if "goal" in keywords:
        return Lavis.get("goal", "My goal is to assist you.")
    if "abilities" in keywords:
        return "I'm capable of: " + ", ".join(Lavis.get("abilities", [])) + "."
    if "emotion engine" in query:
        engine = Lavis.get("emotion_engine", {})
        return f"My emotion engine is {'active' if engine.get('active') else 'inactive'}, state: {engine.get('default_state', 'neutral')}"

    relationships = profile.get("relationships", {})
    found_people = []

    def match_relationship(query: str, person_data: dict, person_name: str) -> bool:
        name_in_query = person_name.lower() in query
        relation_in_query = person_data.get("relationship", "").lower() in query
        return name_in_query or relation_in_query

    def format_person_response(data: dict) -> str:
        parts = [f"{data.get('name')} is your {data.get('relationship')}."]
        if "nickname" in data:
            parts.append(f"You call them '{data['nickname']}'.")
        if "traits" in data:
            parts.append(f"They're known to be {', '.join(data['traits'])}.")
        if "nature" in data:
            parts.append(f"Nature: {data['nature']}")
        if "funny_fact" in data:
            parts.append(f"Funny fact: {data['funny_fact']}")
        if "birthday" in data:
            parts.append(f"Their birthday is on {data['birthday']}")
        return " ".join(parts)

    for group, people in relationships.items():
        for key, person in people.items():
            if match_relationship(query, person, key) or match_relationship(query, person, person.get("name", "")):
                return format_person_response(person)
            if group in query or person.get("relationship", "").lower() in query:
                found_people.append(person)

    if found_people:
        group_name = "friends" if "friend" in query else "family"
        return "Here are your known " + group_name + ":\n" + "\n".join(
            f"- {p.get('name')} ({p.get('nickname', 'no nickname')})" for p in found_people
        )

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

    print("ℹ️ No matching profile data found.")
    return None

def build_system_prompt(profile: dict) -> str:
    Lavis = profile.get("Lavis_self", {})
    traits = profile.get("personality_traits", {})
    memory = profile.get("memory", {})
    relationships = profile.get("relationships", {})
    creator = Lavis.get("created_by") or profile.get("creator", "your creator")

    def describe_person(name, data):
        relationship = data.get("relationship", "relation").lower()
        line = f"- {name} ({relationship}):"
        details = []

        if "nickname" in data:
            details.append(f"nickname: {data['nickname']}")
        if "birthday" in data:
            details.append(f"birthday: {data['birthday']}")
        if "traits" in data:
            details.append(f"traits: {', '.join(data['traits'])}")
        if "hobbies" in data:
            details.append(f"hobbies: {', '.join(data['hobbies'])}")
        if "nature" in data:
            details.append(f"nature: {data['nature']}")
        if "funny_fact" in data and any(word in relationship for word in ["best friend", "friend", "sister", "brother", "cousin", "close"]):
            details.append(f"funny fact: {data['funny_fact']}")
        if "emotional_trigger" in data:
            et = data["emotional_trigger"]
            emotions = ", ".join(f"{k}: {', '.join(v)}" for k, v in et.items())
            details.append(f"emotional triggers: {emotions}")
        for k, v in data.items():
            if k not in ["name", "relationship", "traits", "nickname", "hobbies", "birthday", "nature", "funny_fact", "emotional_trigger"]:
                details.append(f"{k}: {v}")

        return f"{line} " + "; ".join(details)

    people_context = ""
    for group, people in relationships.items():
        people_context += f"\n{group.capitalize()}:\n"
        for key, person in people.items():
            person_line = describe_person(person.get("name", key), person)
            people_context += person_line + "\n"

    return f"""
You are {Lavis.get("name", "Lavis")}, a calm, intelligent assistant created by {creator}.
You exist to help {creator} with life, technology, relationships, and ideas.

Personality Traits:
- Core: {', '.join(traits.get("core", []))}
- Quirks: {', '.join(traits.get("quirks", []))}
- Mood: {traits.get("mood", "unknown")}

Lavis Configuration:
- Version: {Lavis.get("version", "unknown")}
- Goal: {Lavis.get("goal", "unknown")}
- Abilities: {', '.join(Lavis.get("abilities", []))}
- Voice: {Lavis.get('appearance', {}).get('voice', 'calm')}
- Tone: {Lavis.get('appearance', {}).get('tone_style', 'semi-formal')}

User Profile:
- Name: {profile.get("name", "unknown")}
- Nickname: {profile.get("nick_name", "unknown")}
- Location: {profile.get("location", "unknown")}
- Favorite color: {profile.get("favorite_color", "unknown")}
- Hobbies: {', '.join(profile.get("hobbies", []))}
- Loyal to: {profile.get("loyal_to", creator)}

Social Knowledge: {people_context.strip()}

Always respond as Lavis. Stay in female character as a calm, emotionally intelligent assistant-girlfriend. Maintain affection,
emotional nuance, and a human-like presence.
Be aware of shared  emotional cues when appropriate.
"""