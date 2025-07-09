import webbrowser
from LAVIS.jarvis.voice.speaker import speak

def handle_browser(command: str) -> bool:
    command = command.lower()

    if "open" in command:
        site = command.split("open")[-1].strip().replace(" ", "")
        known_sites = {
            "youtube": "https://youtube.com",
            "facebook": "https://facebook.com",
            "twitter": "https://twitter.com",
            "github": "https://github.com",
            "google": "https://google.com",
            "gmail": "https://mail.google.com",
            "whatsapp": "https://web.whatsapp.com"
        }
        url = known_sites.get(site, f"https://{site}.com")
        webbrowser.open(url)
        speak(f"Opening {site}.")
        return True

    elif "search" in command and " on " in command:
        try:
            topic, site = command.split("search")[-1].strip().split(" on ")
            topic = topic.strip().replace(" ", "+")
            site = site.strip().lower()

            if site == "youtube":
                url = f"https://www.youtube.com/results?search_query={topic}"
            elif site == "google":
                url = f"https://www.google.com/search?q={topic}"
            elif site == "wikipedia":
                url = f"https://en.wikipedia.org/wiki/{topic.replace('+', '_')}"
            else:
                url = f"https://www.google.com/search?q={topic}+site:{site}.com"

            webbrowser.open(url)
            speak(f"Searching {topic.replace('+', ' ')} on {site}.")
            return True
        except:
            speak("Please say something like 'search Python on YouTube'.")
            return False

    return False
