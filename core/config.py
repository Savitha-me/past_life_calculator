from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ---- QA Engine (D1 chart API) ----
    qa_api_base_url: str
    d1_chart_endpoint: str
    token_refresh_endpoint: str
    qa_access_token: str
    qa_refresh_token: str | None = None
    access_token_ttl_seconds: int = 86400
    http_timeout_seconds: int = 30

    # ---- LLM (OpenAI) ----
    llm_api_key: str
    llm_model: str = "gpt-4o-mini"
    llm_fallback_model: str | None = None
    llm_api_url: str = "https://api.openai.com/v1/chat/completions"
    llm_max_tokens: int = 800
    llm_temperature: float | None = None
    llm_timeout_seconds: int = 60

    # ---- MongoDB ----
    mongodb_uri: str
    mongodb_db_name: str = "astrovedpedia"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()