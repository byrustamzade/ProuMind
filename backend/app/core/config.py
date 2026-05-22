from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "ProuMind"
    app_env: str = "local"

    postgres_host: str
    postgres_port: int
    postgres_db: str
    postgres_user: str
    postgres_password: str

    elasticsearch_url: str

    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str

    redis_url: str

    llm_provider: str = "ollama"

    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_model: str = "qwen2.5:3b"

    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"

    class Config:
        env_file = ".env"


settings = Settings()