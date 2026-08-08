"""
Agent 公共基础设施

支持多模型动态切换（OpenAI / Qwen / DeepSeek / Moonshot 等）
"""

import os
from typing import Optional

from langchain.chat_models import init_chat_model
from langchain_openai import OpenAIEmbeddings
from langchain_core.language_models import BaseChatModel
from src.config.settings import settings

# ============================================================
# 模型提供商的环境变量映射（确保 API Key 自动注入）
# ============================================================

def _ensure_env_vars(model_string: str) -> None:
    """根据模型字符串，自动设置对应的环境变量"""
    if model_string.startswith("openai:"):
        os.environ["OPENAI_API_KEY"] = settings.openai_api_key
    elif model_string.startswith("qwen:"):
        os.environ["DASHSCOPE_API_KEY"] = settings.qwen_api_key
    elif model_string.startswith("deepseek:"):
        os.environ["DEEPSEEK_API_KEY"] = settings.deepseek_api_key
    elif model_string.startswith("moonshot:"):
        os.environ["MOONSHOT_API_KEY"] = settings.moonshot_api_key
    # 如果还需要其他提供商，在此处继续添加


# ============================================================
# 全局 LLM 工厂（核心修改点）
# ============================================================

def get_llm(
    model_string: Optional[str] = None,
    temperature: float = 0.3,
) -> "BaseChatModel":
    """
    获取 LLM 实例，支持动态切换模型提供商
    
    Args:
        model_string: 模型标识符，格式为 "provider:model_name"
                      例如: "openai:gpt-4o-mini", "qwen:qwen-flash", "deepseek:deepseek-reasoner"
                      如果不传，则使用 settings.DEFAULT_LLM_MODEL
        temperature: 温度参数 (0-1)
    
    Returns:
        LangChain 兼容的 ChatModel 实例
    """
    if model_string is None:
        model_string = settings.default_llm_model
    
    # 自动设置对应提供商的环境变量
    _ensure_env_vars(model_string)
    
    # 使用 LangChain 官方工厂函数，一行代码支持所有模型
    return init_chat_model(
        model_string,
        temperature=temperature,
    )


def get_embeddings():
    """获取全局嵌入模型实例（用于 ChromaDB 向量化）"""
    # 可以根据需要切换嵌入模型提供商
    return OpenAIEmbeddings(
        api_key=settings.openai_api_key,
        model="text-embedding-3-small",
    )


# 公共常量
MAX_VALIDATION_ATTEMPTS = 3
DEFAULT_TEMPERATURE = 0.3