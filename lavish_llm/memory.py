import chromadb
from chromadb.utils import embedding_functions

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
