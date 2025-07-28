# Required installations:
# pip install transformers chromadb langchain openai tiktoken celery apscheduler datasets

import os
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
import datetime
import webbrowser
from transformers import pipeline
from langchain.agents import initialize_agent, Tool
from langchain.agents.agent_types import AgentType
from langchain.memory import ConversationBufferMemory
from langchain_community.llms import HuggingFacePipeline
from langchain_experimental.tools import PythonREPLTool


from langchain.tools.file_management import ReadFileTool, WriteFileTool
from apscheduler.schedulers.background import BackgroundScheduler
from celery import Celery
from datasets import load_dataset
import chromadb
from chromadb.utils import embedding_functions

# === Basic Utility Functions ===
def get_time():
    return f"Current time is: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

def open_website(url):
    webbrowser.open(url)
    return f"Opening {url}"

# === Memory Store Class ===
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

# === LLM Engine Class ===
class LLMEngine:
    def __init__(self, model_name="tiiuae/falcon-7b-instruct"):
        pipe = pipeline("text-generation", model=model_name, max_new_tokens=256)
        self.llm = HuggingFacePipeline(pipeline=pipe)

# === Knowledge Loader Class ===
class KnowledgeLoader:
    def __init__(self):
        self.knowledge_chunks = []

    def load_general_knowledge(self):
        wiki = load_dataset("wikitext", "wikitext-2-raw-v1", split="train[:1%]")
        self.knowledge_chunks.extend([x["text"] for x in wiki if x["text"].strip()])

    def load_dialogue(self):
        dialog = load_dataset("daily_dialog", split="train[:1%]")
        for d in dialog:
            self.knowledge_chunks.append("Dialog: " + d["dialog"])

    def load_commonsense(self):
        commonsense = load_dataset("commonsense_qa", split="train[:1%]")
        for cs in commonsense:
            q = cs["question"]
            a = cs["answerKey"]
            self.knowledge_chunks.append(f"Q: {q} A: {a}")

    def load_code_knowledge(self):
        try:
            code = load_dataset("codeparrot/github-jupyter-code-to-text", split="train[:1%]")
            for c in code:
                self.knowledge_chunks.append(c["code"][:500])
        except:
            pass

    def load_emotional_knowledge(self):
        try:
            emotions = load_dataset("go_emotions", split="train[:1%]")
            for e in emotions:
                if e["labels"]:
                    self.knowledge_chunks.append(f"Text: {e['text']} | Emotions: {e['labels']}")
        except:
            pass

    def load_all(self):
        self.load_general_knowledge()
        self.load_dialogue()
        self.load_commonsense()
        self.load_code_knowledge()
        self.load_emotional_knowledge()
        return self.knowledge_chunks[:500]

# === Celery Task Queue ===
celery_app = Celery('jarvis_tasks', broker='redis://localhost:6379/0')

@celery_app.task
def run_scheduled_task():
    print("[Celery Task] Performing background job at", datetime.datetime.now())
    return get_time()

# === APScheduler ===
scheduler = BackgroundScheduler()
scheduler.add_job(run_scheduled_task.delay, 'interval', seconds=30)
scheduler.start()

# === Main Loop ===
def main():
    llm_engine = LLMEngine()
    memory = MemoryStore()
    knowledge = KnowledgeLoader().load_all()

    agent = initialize_agent(
        tools=[
            Tool(name="Get Time", func=get_time, description="Gets the current time"),
            Tool(name="Open Google", func=lambda: open_website("https://www.google.com"), description="Opens Google"),
            PythonREPLTool(),
            ReadFileTool(),
            WriteFileTool()
        ],
        llm=llm_engine.llm,
        agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        memory=ConversationBufferMemory(memory_key="chat_history"),
        verbose=True
    )

    print("\n🤖 Jarvis AI (Console) | Type 'exit' to quit\n")
    while True:
        user_input = input("You: ")
        if user_input.lower() == "exit":
            break

        mem_hits = memory.search_memory(user_input)
        if mem_hits:
            print("\n🧠 Memory Match:", mem_hits)

        context_prompt = f"Answer the user query using available knowledge. Knowledge base: {knowledge}\nUser: {user_input}"
        response = agent.run(context_prompt)
        print("Jarvis:", response)
        memory.add_memory(user_input, response)

if __name__ == "__main__":
    main()
