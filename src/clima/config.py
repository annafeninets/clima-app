"""Application configuration loaded from the environment."""

from dataclasses import dataclass
import os


@dataclass(frozen=True, slots=True)
class Config:
    host: str = "127.0.0.1"
    port: int = 8000
    dbPath: str = "clima.sqlite3"
    photoRoot: str = "uploads"
    logLevel: str = "INFO"
    corsOrigins: tuple[str, ...] = ("http://localhost:3000", "http://localhost:5173")

    @classmethod
    def from_env(cls) -> "Config":
        try:
            port = int(os.environ.get("CLIMA_PORT", "8000"))
        except ValueError as error:
            raise ValueError("CLIMA_PORT must be an integer") from error
        if not 1 <= port <= 65535:
            raise ValueError("CLIMA_PORT must be between 1 and 65535")
        return cls(
            host=os.environ.get("CLIMA_HOST", "127.0.0.1"),
            port=port,
            dbPath=os.environ.get("CLIMA_DB_PATH", "clima.sqlite3"),
            photoRoot=os.environ.get("CLIMA_UPLOADS_PATH", "uploads"),
            logLevel=os.environ.get("CLIMA_LOG_LEVEL", "INFO").upper(),
            corsOrigins=tuple(
                origin.strip()
                for origin in os.environ.get(
                    "CLIMA_CORS_ORIGINS",
                    "http://localhost:3000,http://localhost:5173",
                ).split(",")
                if origin.strip()
            ),
        )
