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

    class Config:
        env_file = ".env"


settings = Settings()