from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    datahub_gms_url: str = "http://localhost:8080"
    datahub_gms_token: str = ""
    openai_api_key: str = ""
    changeproof_model: str = Field(
        default="gpt-5.4-mini",
        validation_alias="CHANGE_PROOF_MODEL",
    )
    metadata_max_age_hours: float = 24.0
    demo_project_dir: str = "demo/sonicledger"
    changeproof_writeback_mode: str = Field(
        default="datahub",
        validation_alias="CHANGE_PROOF_WRITEBACK_MODE",
    )

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    @classmethod
    def from_env(cls) -> "Settings":
        return cls()
