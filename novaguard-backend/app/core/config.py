from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache # For caching settings

class Settings(BaseSettings):
    # Database settings
    DATABASE_URL: str = "postgresql://novaguard_user:novaguard_password@postgres_db:5432/novaguard_db" # Default for docker-compose

    # JWT settings
    SECRET_KEY: str = "your-super-secret-key-please-change-this" # CHANGE THIS IN PRODUCTION!
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 # 1 day for simplicity in MVP, adjust as needed

    # Ollama settings (sẽ dùng sau)
    OLLAMA_BASE_URL: str = "http://ollama:11434" # Default for docker-compose, map tới 11435 trên host

    # GitHub OAuth settings (sẽ dùng sau)
    GITHUB_CLIENT_ID: str | None = None
    GITHUB_CLIENT_SECRET: str | None = None
    GITHUB_REDIRECT_URI: str | None = "http://localhost:8000/auth/github/callback" # Ví dụ

    # Model configuration for Pydantic-Settings to load from .env file if present
    # For this MVP, we'll primarily rely on defaults or environment variables set in docker-compose.yml
    # model_config = SettingsConfigDict(env_file=".env", env_file_encoding='utf-8', extra='ignore')
    
    # Kafka settings
    KAFKA_BOOTSTRAP_SERVERS: str = "kafka:29092" # Địa chỉ Kafka bên trong Docker network
    KAFKA_PR_ANALYSIS_TOPIC: str = "pr_analysis_tasks" # Tên topic cho tác vụ phân tích PR


@lru_cache() # Cache the settings object to avoid re-reading .env file or re-creating object
def get_settings() -> Settings:
    return Settings()

# Instance of settings to be imported by other modules
settings = get_settings()

if __name__ == "__main__":
    # Example of how to access settings
    print("Database URL:", settings.DATABASE_URL)
    print("Secret Key:", settings.SECRET_KEY)
    if settings.SECRET_KEY == "your-super-secret-key-please-change-this":
        print("\nWARNING: Default SECRET_KEY is used. Please change this for production environments!")
        print("You can set it via an environment variable, e.g., export SECRET_KEY='your_actual_secure_key'")