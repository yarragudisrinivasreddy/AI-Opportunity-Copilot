"""Settings from environment variables. Production refuses unsafe development modes."""
from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: Literal["development", "test", "production"] = "development"
    auth_mode: Literal["dev", "firebase"] = "dev"
    llm_mode: Literal["fake", "vertex"] = "fake"
    store_mode: Literal["memory", "firestore"] = "memory"
    media_mode: Literal["memory", "gcs"] = "memory"
    privacy_mode: Literal["fake", "gcp"] = "fake"

    gcp_project: str = ""
    gcp_location: str = ""  # TBD: choose a region that offers the chosen Gemini model
    gemini_model: str = ""  # TBD: set after verifying current Vertex AI model IDs
    media_bucket: str = ""

    allowed_origins: str = "http://localhost:5173"
    enforce_app_check: bool = False

    # TBD values from PRD section 30; defaults are conservative placeholders.
    daily_case_cap: int = 5
    rate_limit_per_minute: int = 30
    max_upload_files: int = 6
    # When false, photo/video upload is rejected; text descriptions still work.
    # Keep false in production until Cloud Vision + DLP are verified on real frames.
    uploads_enabled: bool = True
    # Named Native Firestore DB (default (default) may be Datastore-mode in older projects).
    firestore_database: str = "(default)"

    @model_validator(mode="after")
    def _production_guard(self) -> "Settings":
        if self.env == "production":
            problems = []
            if self.auth_mode != "firebase":
                problems.append("AUTH_MODE must be 'firebase'")
            if self.llm_mode != "vertex":
                problems.append("LLM_MODE must be 'vertex'")
            if self.store_mode != "firestore":
                problems.append("STORE_MODE must be 'firestore'")
            if self.privacy_mode != "gcp":
                problems.append("PRIVACY_MODE must be 'gcp'")
            if self.media_mode != "gcs":
                problems.append("MEDIA_MODE must be 'gcs'")
            if problems:
                raise ValueError("unsafe production configuration: " + "; ".join(problems))
        if self.llm_mode == "vertex" and not (
            self.gcp_project and self.gcp_location and self.gemini_model
        ):
            raise ValueError("GCP_PROJECT, GCP_LOCATION and GEMINI_MODEL are required for vertex")
        if self.store_mode == "firestore" and not self.gcp_project:
            raise ValueError("GCP_PROJECT is required for firestore")
        if self.media_mode == "gcs" and not self.media_bucket:
            raise ValueError("MEDIA_BUCKET is required for gcs")
        return self

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
