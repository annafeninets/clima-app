"""Application configuration loaded from the environment."""

from dataclasses import dataclass
import os


@dataclass(frozen=True, slots=True)
class Config:
    databaseUrl: str = ""
    dbSchema: str | None = None
    dbPoolMax: int = 10
    redisUrl: str = ""
    host: str = "127.0.0.1"
    port: int = 8000
    photoRoot: str = "uploads"
    logLevel: str = "INFO"
    openWeatherApiKey: str = ""
    corsOrigins: tuple[str, ...] = ("http://localhost:3000", "http://localhost:5173")

    @classmethod
    def from_env(cls) -> "Config":
        try:
            port = int(os.environ.get("CLIMA_PORT", "8000"))
        except ValueError as error:
            raise ValueError("CLIMA_PORT must be an integer") from error
        if not 1 <= port <= 65535:
            raise ValueError("CLIMA_PORT must be between 1 and 65535")
        try:
            poolMax = int(os.environ.get("CLIMA_DB_POOL_MAX", "10"))
        except ValueError as error:
            raise ValueError("CLIMA_DB_POOL_MAX must be an integer") from error
        if poolMax < 1:
            raise ValueError("CLIMA_DB_POOL_MAX must be at least 1")
        databaseUrl = os.environ.get("CLIMA_DATABASE_URL", "").strip()
        if not databaseUrl:
            raise ValueError(
                "CLIMA_DATABASE_URL не задан, пример: postgresql://clima:пароль@localhost:5432/clima"
            )
        return cls(
            databaseUrl=databaseUrl,
            dbSchema=os.environ.get("CLIMA_DB_SCHEMA", "").strip() or None,
            dbPoolMax=poolMax,
            redisUrl=os.environ.get("CLIMA_REDIS_URL", "").strip(),
            host=os.environ.get("CLIMA_HOST", "127.0.0.1"),
            port=port,
            photoRoot=os.environ.get("CLIMA_UPLOADS_PATH", "uploads"),
            logLevel=os.environ.get("CLIMA_LOG_LEVEL", "INFO").upper(),
            openWeatherApiKey=os.environ.get("CLIMA_OPENWEATHER_API_KEY", "").strip(),
            corsOrigins=tuple(
                origin.strip()
                for origin in os.environ.get(
                    "CLIMA_CORS_ORIGINS",
                    "http://localhost:3000,http://localhost:5173",
                ).split(",")
                if origin.strip()
            ),
        )
