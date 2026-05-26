import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_WEBHOOK_PATH = "/x/webhook"


@dataclass(slots=True)
class Config:
    root_dir: Path
    data_dir: Path
    state_dir: Path
    openai_api_key: str | None
    x_api_key: str | None
    x_api_secret: str | None
    x_bearer_token: str | None
    x_access_token: str | None
    x_access_token_secret: str | None
    x_oauth2_user_token: str | None
    bot_username: str | None
    public_base_url: str | None
    openai_model: str
    openai_max_output_tokens: int
    openai_timeout_seconds: int
    log_level: str
    reply_char_limit: int
    x_timeout_seconds: int
    webhook_path: str = DEFAULT_WEBHOOK_PATH

    @classmethod
    def from_env(cls) -> "Config":
        load_dotenv(ROOT_DIR / ".env")
        load_dotenv()
        return cls(
            root_dir=ROOT_DIR,
            data_dir=ROOT_DIR / "data",
            state_dir=ROOT_DIR / "state",
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            x_api_key=os.getenv("X_API_KEY"),
            x_api_secret=os.getenv("X_API_SECRET"),
            x_bearer_token=os.getenv("X_BEARER_TOKEN"),
            x_access_token=os.getenv("X_ACCESS_TOKEN"),
            x_access_token_secret=os.getenv("X_ACCESS_TOKEN_SECRET"),
            x_oauth2_user_token=os.getenv("X_OAUTH2_USER_TOKEN"),
            bot_username=os.getenv("BOT_USERNAME"),
            public_base_url=os.getenv("PUBLIC_BASE_URL"),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-5-mini"),
            openai_max_output_tokens=int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "220")),
            openai_timeout_seconds=int(os.getenv("OPENAI_TIMEOUT_SECONDS", "45")),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            reply_char_limit=int(os.getenv("REPLY_CHAR_LIMIT", "260")),
            x_timeout_seconds=int(os.getenv("X_TIMEOUT_SECONDS", "30")),
        )

    @property
    def bot_handle(self) -> str:
        if not self.bot_username:
            return ""
        return self.bot_username.lstrip("@").strip()

    @property
    def webhook_url(self) -> str:
        if not self.public_base_url:
            return self.webhook_path
        return self.public_base_url.rstrip("/") + self.webhook_path

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def require_runtime(self) -> None:
        self.require(
            [
                "OPENAI_API_KEY",
                "X_API_KEY",
                "X_API_SECRET",
                "X_ACCESS_TOKEN",
                "X_ACCESS_TOKEN_SECRET",
                "BOT_USERNAME",
            ]
        )
        self.require_data_files(["fighter_info.csv", "event_data_sherdog.csv"])

    def require_x_admin(self) -> None:
        self.require(
            [
                "X_API_KEY",
                "X_API_SECRET",
                "X_BEARER_TOKEN",
                "BOT_USERNAME",
                "PUBLIC_BASE_URL",
            ]
        )
        self.validate_public_base_url()

    def require_reply_posting(self) -> None:
        self.require(
            [
                "X_API_KEY",
                "X_API_SECRET",
                "X_ACCESS_TOKEN",
                "X_ACCESS_TOKEN_SECRET",
            ]
        )

    def require(self, variable_names: Iterable[str]) -> None:
        missing = [name for name in variable_names if not getattr(self, self._field_name(name))]
        if missing:
            joined = ", ".join(missing)
            raise RuntimeError(f"Missing required environment variables: {joined}")

    def require_data_files(self, filenames: Iterable[str]) -> None:
        missing = [name for name in filenames if not (self.data_dir / name).exists()]
        if missing:
            joined = ", ".join(missing)
            raise RuntimeError(f"Missing required data files in {self.data_dir}: {joined}")

    def validate_public_base_url(self) -> None:
        if not self.public_base_url:
            raise RuntimeError("PUBLIC_BASE_URL is required")
        parsed = urlparse(self.public_base_url)
        if parsed.scheme != "https":
            raise RuntimeError("PUBLIC_BASE_URL must use https")
        if not parsed.netloc:
            raise RuntimeError("PUBLIC_BASE_URL must include a host")
        if parsed.port:
            raise RuntimeError("PUBLIC_BASE_URL must not include an explicit port")

    @staticmethod
    def _field_name(env_name: str) -> str:
        return env_name.lower()

