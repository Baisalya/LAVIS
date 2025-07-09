from chatterbot import ChatBot
from chatterbot.trainers import ChatterBotCorpusTrainer, ListTrainer

chatbot = ChatBot(
    "Jarvis",
    storage_adapter="chatterbot.storage.SQLStorageAdapter",
    database_uri="sqlite:///jarvis.sqlite3"
)

def train_chatbot():
    print("🔁 Training chatbot...")
    corpus = ChatterBotCorpusTrainer(chatbot)
    corpus.train("chatterbot.corpus.english")

    custom = ListTrainer(chatbot)
    custom.train([
        "Who created you?", "I was created by Baishalya Roul.",
        "What's your name?", "My name is Jarvis.",
        "Tell me a joke", "Why did the computer get cold? Because it forgot to close Windows!",
        "hello", "Hi there!",
        "how are you", "I'm doing great, thank you!",
    ])
    print("✅ Training complete.")
