from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM — Claude is what the recording must declare
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-5"
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1"

    # Gnani Agent Platform (live outbound calls)
    gnani_platform_api_key: str = ""
    gnani_bot_id: str = ""
    gnani_environment: str = "development"
    gnani_platform_base: str = "https://api.inya.ai/platform"

    # Gnani Vachana STT (live voice-note transcription)
    gnani_stt_api_key: str = ""
    gnani_api_key: str = ""  # fallback alias used in existing .env
    gnani_stt_base: str = "https://api.vachana.ai"

    # WhatsApp Cloud API
    wa_access_token: str = ""
    wa_phone_number_id: str = ""
    wa_waba_id: str = ""
    wa_verify_token: str = "gharpass-verify"
    wa_app_secret: str = ""
    wa_graph_version: str = "v21.0"

    # Google Sheets
    google_service_account_file: str = ""
    google_sheet_id: str = ""

    # Pine Labs (optional live UAT; otherwise curtain)
    pinelabs_live: bool = False
    pinelabs_client_id: str = ""
    pinelabs_client_secret: str = ""
    pinelabs_merchant_id: str = ""
    pinelabs_base: str = "https://pluraluat.v2.pinepg.in"

    # Delhivery (optional live staging; otherwise curtain)
    delhivery_live: bool = False
    delhivery_api_token: str = ""
    delhivery_base: str = "https://staging-express.delhivery.com"
    delhivery_client_name: str = ""
    delhivery_pickup_location: str = ""

    # Actor phones (10 digits, no country code)
    ritika_phone: str = "9800000022"
    sunita_phone: str = "9800000010"
    ramesh_phone: str = "9800000033"

    public_base_url: str = "http://127.0.0.1:8000"
    host: str = "0.0.0.0"
    port: int = 8000

    @property
    def stt_key(self) -> str:
        return self.gnani_stt_api_key or self.gnani_api_key

    @property
    def llm_provider(self) -> str:
        if self.anthropic_api_key:
            return "anthropic"
        if self.openai_api_key:
            return "openai"
        return "none"

    @property
    def llm_model(self) -> str:
        if self.anthropic_api_key:
            return self.anthropic_model
        if self.openai_api_key:
            return self.openai_model
        return "unconfigured"


@lru_cache
def get_settings() -> Settings:
    return Settings()
