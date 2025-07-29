import os
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
import datetime
import webbrowser

from apscheduler.schedulers.background import BackgroundScheduler
from celery import Celery
from datasets import load_dataset
import chromadb
from chromadb.utils import embedding_functions

from langchain.agents import initialize_agent, Tool
from langchain.agents.agent_types import AgentType
from langchain.memory import ConversationBufferMemory
from langchain_experimental.tools import PythonREPLTool
from langchain_community.tools import ReadFileTool, WriteFileTool

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from LAVIS.jarvis.llm.llm_wrappers import GroqLLM, OllamaLLM

# === Utility Functions ===
def get_time():
    return f"Current time is: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

def open_website(url):
    webbrowser.open(url)
    return f"Opening {url}"

# === Memory ===
class MemoryStore:
    def __init__(self):
        self.client = chromadb.Client()
        self.ef = embedding_functions.DefaultEmbeddingFunction()
        self.collection = self.client.get_or_create_collection(name="jarvis-memory")

    def add_memory(self, user_input, response):
        self.collection.add(
            documents=[response],
            metadatas=[{"user_input": user_input}],
            ids=[str(len(self.collection.get()["ids"]))]
        )

    def search_memory(self, query):
        results = self.collection.query(query_texts=[query], n_results=2)
        return results.get("documents", [[]])[0]

# === Knowledge Loader ===
from datasets import load_dataset

import os
from datasets import load_dataset, load_from_disk, DatasetDict

import os
from datasets import load_dataset, load_from_disk

class KnowledgeLoader:
    def __init__(self, cache_dir="datasets"):
        self.knowledge_chunks = []
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def _load_or_cache_dataset(self, dataset_name, split, local_name=None, config_name=None, **kwargs):
        local_path = os.path.join(self.cache_dir, local_name or dataset_name.replace("/", "_"))
        if os.path.exists(local_path):
            print(f"📂 Loading from cache: {local_path}")
            return load_from_disk(local_path)
        else:
            print(f"⬇️ Downloading {dataset_name} from Hugging Face...")
            dataset = load_dataset(dataset_name, name=config_name, split=split, **kwargs)
            dataset.save_to_disk(local_path)
            print(f"✅ Saved to: {local_path}")
            return dataset

    def load_general_knowledge(self):
        wiki = self._load_or_cache_dataset(
            dataset_name="wikitext",
            split="train[:1%]",
            config_name="wikitext-2-raw-v1",
            local_name="wikitext-2-raw-v1"
        )
        self.knowledge_chunks.extend([x["text"] for x in wiki if x["text"].strip()])

    def load_dialogue(self):
        try:
            dataset = self._load_or_cache_dataset("Cynaptics/persona-chat", split="train[:1%]")
            for entry in dataset:
                persona = entry.get("persona", [])
                dialog = entry.get("utterances", [])
                persona_text = " | ".join(persona)
                for turn in dialog:
                    history = " ".join(turn.get("history", []))
                    candidate = turn.get("candidates", [""])[0]
                    self.knowledge_chunks.append(
                        f"Persona: {persona_text} | Dialog: {history} → {candidate}"
                    )
        except Exception as e:
            print("⚠️ Dialogue dataset could not be loaded:", e)

    def load_commonsense(self):
        commonsense = self._load_or_cache_dataset("commonsense_qa", split="train[:1%]")
        for cs in commonsense:
            q = cs["question"]
            a = cs["answerKey"]
            self.knowledge_chunks.append(f"Q: {q} A: {a}")

    def load_code_knowledge(self):
        try:
            code = self._load_or_cache_dataset("codeparrot/github-jupyter-code-to-text", split="train[:1%]")
            for c in code:
                self.knowledge_chunks.append(c["code"][:500])
        except Exception as e:
            print("⚠️ Error loading code knowledge:", e)

    def load_emotional_knowledge(self):
        try:
            emotions = self._load_or_cache_dataset("go_emotions", split="train[:1%]")
            for e in emotions:
                if e["labels"]:
                    self.knowledge_chunks.append(
                        f"Text: {e['text']} | Emotions: {e['labels']}"
                    )
        except Exception as e:
            print("⚠️ Error loading emotional knowledge:", e)

    def load_all(self):
        self.load_general_knowledge()
        self.load_dialogue()
        self.load_commonsense()
        self.load_code_knowledge()
        self.load_emotional_knowledge()
        return self.knowledge_chunks[:500]

# === Celery Task ===
celery_app = Celery('jarvis_tasks', broker='redis://localhost:6379/0')

@celery_app.task
def run_scheduled_task():
    print("[Celery Task] Background job at", datetime.datetime.now())
    return get_time()

# === Scheduler ===
scheduler = BackgroundScheduler()
scheduler.add_job(run_scheduled_task.delay, 'interval', seconds=30)
scheduler.start()

# === LLM Engine ===
class LLMEngine:
    def __init__(self, backend="groq", model_name="tinyllama"):
        if backend == "groq":
            self.llm = GroqLLM()
        elif backend == "ollama":
            self.llm = OllamaLLM(model_name=model_name)
        else:
            raise ValueError(f"Unsupported LLM backend: {backend}")

# === Main ===
def main():
    llm_engine = LLMEngine(backend="groq")  # ← Change to "ollama" if needed
    memory = MemoryStore()
    knowledge = KnowledgeLoader().load_all()

    agent = initialize_agent(
        tools=[
            Tool(name="Get Time", func=get_time, description="Gets the current time"),
            Tool(name="Open Google", func=lambda: open_website("https://www.google.com"), description="Opens Google"),
            PythonREPLTool(),
            ReadFileTool(),
            #WriteFileTool()
        ],
        llm=llm_engine.llm,
        agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        memory=ConversationBufferMemory(memory_key="chat_history"),
        verbose=True
    )

    print("\n🤖 Jarvis AI | Type 'exit' to quit\n")
    while True:
        user_input = input("You: ")
        if user_input.lower() == "exit":
            break

        mem_hits = memory.search_memory(user_input)
        if mem_hits:
            print("\n🧠 Memory Match:", mem_hits)

        context_prompt = f"Answer using available knowledge. Knowledge base: {knowledge}\nUser: {user_input}"
        response = agent.run(context_prompt)
        print("Jarvis:", response)
        memory.add_memory(user_input, response)

if __name__ == "__main__":
    main()
