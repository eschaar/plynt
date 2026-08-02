"""Settings for generic gRPC client transport."""

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from plynth.base.settings import Settings

__all__ = ["GrpcSettings"]


class GrpcSettings(Settings):
    """Settings model for async gRPC connectivity."""

    target: str = ""
    timeout: float | None = 30.0
    secure: bool = True
    metadata: dict[str, str] = Field(default_factory=dict)

    model_config = SettingsConfigDict(
        env_prefix="PLYNTH_GRPC_",
        env_file=".env",
        env_file_encoding="utf-8",
    )
