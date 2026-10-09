from sentence_transformers import SentenceTransformer

# Load model globally on module import so it's loaded once at startup
model = SentenceTransformer('all-MiniLM-L6-v2')

def get_embeddings(texts: list) -> list:
    """Compute embeddings for a list of texts.
    Returns a list of list of floats representing the embeddings.
    """
    if not texts:
        return []
    embeddings = model.encode(texts)
    return embeddings.tolist()
