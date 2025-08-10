import pydantic

class Settings(pydantic.BaseSettings):
    APP_NAME: str = "Game Recommendation Engine"
    RAWG_API_KEY: str
    STEAM_API_KEY: str
    OLLAMA_MODEL: str = "llama3.1"
    OLLAMA_HOST: str = "http://localhost:11434"

    class Config:
        env_file = ".env"

settings = Settings()