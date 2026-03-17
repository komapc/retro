from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openrouter_api_key: str = ""

    gatekeeper_model: str = "openrouter/nousresearch/hermes-3-llama-3.1-8b"
    extractor_model: str = "openrouter/deepseek/deepseek-chat"
    ground_truth_model: str = "openrouter/deepseek/deepseek-chat"

    data_dir: Path = Path("../data")

    @property
    def matrix_dir(self) -> Path:
        return self.data_dir / "matrix"

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
