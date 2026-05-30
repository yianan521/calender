"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "AI Voice Scheduler"
    database_url: str = "sqlite:///./scheduler.db"
    llm_api_url: str = "https://api.openai.com/v1/chat/completions"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o"
    map_api_key: str = ""
    map_city: str = "北京"
    working_hour_start: int = 8
    working_hour_end: int = 22
    debug: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
