from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    nvidia_api_key: str = ""
    nvidia_embedding_model: str = "nvidia/nv-embedqa-e5-v5"
    nvidia_chat_model: str = "meta/llama-3.3-70b-instruct"
    nvidia_rerank_model: str = "nvidia/nv-rerankqa-mistral-4b-v3"

    confluence_url: str = ""
    confluence_username: str = ""
    confluence_api_token: str = ""

    gitlab_url: str = "https://gitlab.com"
    gitlab_token: str = ""

    api_key: str = ""

    database_url: str = "postgresql://rag:rag@localhost:5437/rag"

    chunk_token_size: int = 1000
    chunk_overlap: int = 200
    top_k: int = 5


settings = Settings()
