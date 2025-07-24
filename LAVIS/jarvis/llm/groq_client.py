import requests
import json

# ✅ Your actual Groq API key (safe for local use; do NOT commit to GitHub)
GROQ_API_KEY = "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"
GROQ_MODEL = "llama3-70b-8192"  # ✅ Recommended

def ask_groq(prompt: str) -> str:
    if not GROQ_API_KEY:
        print("❌ Groq API key not set.")
        return None

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7
            },
            timeout=15
        )

        if response.status_code != 200:
            print(f"❌ Groq API error: {response.status_code}")
            print(response.text)
            return None

        data = response.json()
        if "choices" not in data or not data["choices"]:
            print("❌ Groq API returned no choices:")
            print(json.dumps(data, indent=2))
            return None

        return data["choices"][0]["message"]["content"].strip()

    except Exception as e:
        print("❌ Exception in Groq API:", e)
        return None
