from LAVIS.jarvis.llm.gemini_client import  ask_gemini 
from LAVIS.jarvis.llm.groq_client import ask_groq
from LAVIS.jarvis.llm.ollama_client import  ask_ollama  

class LLMFallback:
    def __init__(self):
        # Import your existing functions
        self.ask_groq = ask_groq
        self.ask_gemini = ask_gemini
        self.ask_ollama = ask_ollama

    def ask(self, prompt: str) -> str:
        """Try Gemini→ Groq  → Ollama until one works."""
        for provider_name, func in [
            ("Gemini", self.ask_gemini),
            ("Groq", self.ask_groq),
            ("Ollama", self.ask_ollama)
        ]:
            try:
                result = func(prompt)
                if result and isinstance(result, str):
                    print(f"✅ Answered by {provider_name}")
                    return result
            except Exception as e:
                print(f"⚠️ {provider_name} failed: {e}")

        return "❌ All providers failed."

# -------------------------
# Example usage
# -------------------------
if __name__ == "__main__":
    llm = LLMFallback()
    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in {"exit", "quit"}:
            break
        print("Lavis:", llm.ask(user_input), "\n")
