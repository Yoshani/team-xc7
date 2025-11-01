from transformers import AutoModel

embedding_model = AutoModel.from_pretrained(
    'jinaai/jina-embeddings-v2-base-en',
    trust_remote_code=True
)

def get_embedding(text: str) -> list[float]:
    return embedding_model.encode(text).tolist()
