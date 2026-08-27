import os
from typing import Any, Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # 应用配置
    app_name: str = "TravelMate"
    app_version: str = "1.0.0"
    app_env: str = "development"
    debug: bool = True
    log_level: str = "DEBUG"

    # ===== 多模型配置 =====
    # 默认模型（目前先写死 DeepSeek，后续再改为配置驱动）
    default_llm_model: str = "deepseek:deepseek-chat"

    # 各提供商 API Key
    openai_api_key: str = ""
    qwen_api_key: str = ""
    deepseek_api_key: str = ""
    moonshot_api_key: str = ""

    # 高德地图
    amap_api_key: str = ""
    
    # 和风天气
    qweather_api_key: str = ""
    qweather_api_host: str = ""

    # Redis
    redis_url: str = ""
    redis_max_connections: int = 20           # 连接池最大连接数
    redis_socket_timeout: int = 5             # 读写超时（秒）
    redis_socket_connect_timeout: int = 5     # 连接超时（秒）
    redis_protocol: int = 2                   # RESP2 协议（兼容低版本 Redis）

     # 数据库配置
    database_dir: str = os.getenv("DATABASE_DIR", "./data")

    # langgraph 数据库文件名
    database_filename: str = "checkpoint.db"

    # tracing 专用库（与 checkpointer 分离）
    tracing_database_filename: str = "tracing.db"

    # ChromaDB
    chroma_persist_dir: str = "./data"
    chroma_collection_prefs: str = "user_preferences"  # 偏好集合名
    chroma_collection_actions: str = "user_actions"    # 行为日志集合名
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    @property
    def database_path(self) -> str:
        """获取完整的数据库文件路径"""
        return str(Path(self.database_dir) / self.database_filename)

    @property
    def tracing_database_path(self) -> str:
        """tracing 用：traces / spans / llm_events 表所在库"""
        return str(Path(self.database_dir) / self.tracing_database_filename)

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, value: Any) -> Any:
        if isinstance(value, str) and value.lower() in {"release", "prod", "production"}:
            return False
        return value


settings = Settings()
