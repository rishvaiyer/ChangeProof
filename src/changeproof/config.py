from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    datahub_gms_url: str = "http://localhost:8080"
    datahub_gms_token: str = ""
    openai_api_key: str = ""
    changeproof_model: str = "gpt-5.4-mini"
    metadata_max_age_hours: float = 24.0
    demo_project_dir: str = "demo/sonicledger"

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    @classmethod
    def from_env(cls) -> "Settings":
        return cls()
