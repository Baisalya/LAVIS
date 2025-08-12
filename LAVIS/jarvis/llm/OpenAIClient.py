import os
import google.generativeai as genai

class Jarvis:
    def __init__(self, api_key: str, high_quality: bool = False):
        if not api_key:
            raise ValueError("API key is required for Jarvis to work.")

        os.environ["GEMINI_API_KEY"] = api_key
        genai.configure(api_key=api_key)

        # Choose correct Gemini model
        self.model_name = (
            "gemini-1.5-pro-latest" if high_quality else "gemini-1.5-flash-latest"
        )
        self.model = genai.GenerativeModel(self.model_name)

    def ask(self, prompt: str) -> str:
        try:
            response = self.model.generate_content([prompt])
            return response.text
        except Exception as e:
            return f"❌ Gemini API error: {str(e)}"

    def chat(self):
        print(f"🤖 Jarvis is online using {self.model_name}")
        print("Type 'exit' to quit.\n")
        
        while True:
            user_input = input("You: ")
            if user_input.lower() in ["exit", "quit"]:
                print("Jarvis: Goodbye!")
                break
            reply = self.ask(user_input)
            print(f"Jarvis: {reply}\n")


if __name__ == "__main__":
    API_KEY = "AIzaSyCf29NxuCUdPvdwSdxyoHTjW-G10e6EiGo"
    jarvis = Jarvis(api_key=API_KEY, high_quality=False)

    print("Example single Q&A:")
    print(jarvis.ask("Write a fun fact about space."))
