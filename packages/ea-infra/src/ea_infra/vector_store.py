import chromadb
# from chromadb.utils import embedding_functions
from typing import List, Dict, Any, Optional
from ea_infra.indexer import Resource

class VectorStore:
    """
    Manages semantic indexing and retrieval of resources using ChromaDB.
    Layer 1 Persistence Engine.
    """
    def __init__(self, persistence_path: str = "./ea_vectors", collection_name: str = "ea_resources", embedding_function=None):
        # Disable telemetry to prevent hanging threads in tests
        from chromadb.config import Settings
        self.client = chromadb.PersistentClient(
            path=persistence_path,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Use provided embedding function or default deterministic model (No ML)
        if embedding_function:
            self.embedding_fn = embedding_function
        else:
            self.embedding_fn = DeterministicEmbeddingFunction()
        
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.embedding_fn
        )

    def add_resources(self, resources: List[Resource]):
        """Upserts resources into the vector store."""
        if not resources:
            return

        ids = [r.uri for r in resources]
        documents = [r.content for r in resources if r.content] # Only if content exists
        metadatas = [{
            "path": r.path,
            "name": r.name,
            "type": r.content_type,
            "last_modified": r.last_modified
        } for r in resources]

        # Filter out resources with no content for embedding purposes
        # (Though we might want to store them just for metadata in a different way)
        valid_indices = [i for i, r in enumerate(resources) if r.content]
        
        if not valid_indices:
            return

        self.collection.upsert(
            ids=[ids[i] for i in valid_indices],
            documents=[documents[i] for i in valid_indices],
            metadatas=[metadatas[i] for i in valid_indices]
        )

    def query(self, query_text: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """
        Performs a semantic search against the resource base.
        Returns a list of results with metadata and distance.
        """
        results = self.collection.query(
            query_texts=[query_text],
            n_results=n_results
        )
        
        # Parse Chroma result format into a friendlier list of dicts
        parsed_results = []
        if results["ids"]:
            for i in range(len(results["ids"][0])):
                parsed_results.append({
                    "id": results["ids"][0][i],
                    "document": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "distance": results["distances"][0][i] if results["distances"] else None
                })
                
        return parsed_results

class DeterministicEmbeddingFunction:
    """
    A simple, non-ML embedding function for infrastructure that doesn't strictly need semantic search yet.
    Maps text to a fixed-size vector using consistent hashing. 
    Ensures 'chromadb' works without downloading heavy models.
    """
    def __init__(self, dim: int = 384):
        self.dim = dim

    def __call__(self, input: List[str]) -> List[List[float]]:
        return [self._embed(text) for text in input]

    def embed_query(self, input: List[str]) -> List[List[float]]:
        return [self._embed(text) for text in input]

    def embed_documents(self, input: List[str]) -> List[List[float]]:
        return [self._embed(text) for text in input]
        
    def _embed(self, text: str) -> List[float]:
        # Simple consistent hashing to generate a pseudo-vector
        import hashlib
        import math
        
        # Seed with text hash
        seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)
        
        # Generate 'dim' float values roughly between -1 and 1
        # deterministic random generator based on seed
        vector = []
        current = seed
        for _ in range(self.dim):
            current = (current * 1664525 + 1013904223) & 0xFFFFFFFF
            # Normalize to -1.0 to 1.0
            val = (current / 0xFFFFFFFF) * 2.0 - 1.0
            vector.append(val)
            
        # Normalize vector length to 1 (unit vector) usually helps cos sim
        norm = math.sqrt(sum(x*x for x in vector))
        if norm > 0:
            vector = [x/norm for x in vector]
            
        return vector

    def name(self):
        return "deterministic_cpu"
