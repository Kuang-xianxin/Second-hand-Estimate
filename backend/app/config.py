from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    deepseek_api_key: Optional[str] = None
    qwen_api_key: Optional[str] = None
    doubao_api_key: Optional[str] = None

    deepseek_model: str = "deepseek-chat"
    qwen_model: str = "qwen-max"
    doubao_model: str = "ep-m-20260327193150-m6442"
    doubao_model_display: str = "doubao-seed-2.0-pro"
    doubao_vision_model: str = "ep-m-20260327193150-m6442"
    doubao_vision_model_display: str = "doubao-seed-2.0-pro-vision"

    deepseek_base_url: str = "https://api.deepseek.com"
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode"
    doubao_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    doubao_vision_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    llm_timeout_seconds: int = 30

    database_url: str = "sqlite+aiosqlite:///./guessr.db"
    backend_port: int = 8000
    frontend_url: str = "http://localhost:5173"

    crawl_interval_seconds: int = 300
    max_items_per_query: int = 60
    bargain_threshold: float = 120.0

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
