from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    KORSERVICE_API_KEY: str
    KAKAO_REST_API_KEY: str
    KAKAO_JS_API_KEY: str
    FRONTEND_BASE_URL: str
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


settings = Settings()