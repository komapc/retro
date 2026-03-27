from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openrouter_api_key: str = ""
    brave_api_key: str = ""

    gatekeeper_model: str = "bedrock/amazon.nova-micro-v1:0"
    extractor_model: str = "bedrock/amazon.nova-lite-v1:0"
    ground_truth_model: str = "bedrock/amazon.nova-lite-v1:0"

    # Optional: override API base/key (for Ollama or other OpenAI-compatible backends)
    model_api_base: str = ""
    model_api_key: str = ""

    aws_region: str = "us-east-1"

    data_dir: Path = Path("/app/data")
    vault_dir: Path = Path("")  # empty = data_dir/vault2 (avoids root-owned vault/)

    @property
    def atlas_dir(self) -> Path:
        return self.data_dir / "atlas"

    @property
    def events_dir(self) -> Path:
        return self.data_dir / "events"

    @property
    def sources_dir(self) -> Path:
        return self.data_dir / "sources"

    @property
    def progress_file(self) -> Path:
        return self.data_dir / "progress.json"


settings = Settings()
