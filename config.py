# config.py
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Quản lý cấu hình cho ứng dụng, đọc từ biến môi trường hoặc file .env.
    """
    UPLOAD_DIR: Path = Path("uploaded_images")
    SWEEP_INTERVAL: int = 30
    TTL_LIMIT: int = 60 * 60 * 24  # 24 giờ

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra='ignore'
    )

settings = Settings()