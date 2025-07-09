from langchain.vectorstores import Chroma
from langchain.embeddings import SentenceTransformerEmbeddings
import os

class JarvisMemory:
    def __init__(self, path="jarvis/memory/storage"):
        self.embeddings = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")
        self.db = Chroma(
            persist_directory=path,
            embedding_function=self.embeddings
        )

    def add_memory(self, text: str, metadata: dict = {}):
        self.db.add_texts([text], metadatas=[metadata])

    def retrieve_relevant(self, query: str, k=3):
        results = self.db.similarity_search(query, k=k)
        return [(res.page_content, res.metadata) for res in results]
