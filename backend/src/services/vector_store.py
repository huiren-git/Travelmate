import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from sentence_transformers import SentenceTransformer

from src.config.settings import settings

logger = logging.getLogger("travelmate.services.vector_store")

# 全局 Chroma 客户端和 LangChain VectorStore 实例
_chroma_client = None
_pref_vectorstore = None
_action_vectorstore = None
_embedding_function = None


def _get_embedding_function():
    """初始化嵌入模型（支持 OpenAI 或本地模型）"""
    global _embedding_function
    if _embedding_function is None:
        if settings.embedding_model.startswith("openai:"):
            _embedding_function = OpenAIEmbeddings(
                api_key=settings.openai_api_key,
                model=settings.embedding_model.replace("openai:", "")
            )
        else:
          # 使用 sentence-transformers 本地模型
          model = SentenceTransformer(settings.embedding_model)
          # LangChain 需要包装一下；方法内引用局部 model，避免闭包 late-binding 自引用
          class LocalEmbedding:
              def embed_query(self, text):
                  return model.encode(text).tolist()
              def embed_documents(self, texts):
                  return model.encode(texts).tolist()
          _embedding_function = LocalEmbedding()

    return _embedding_function


def init_vector_store():
    """初始化 ChromaDB 持久化客户端和集合"""
    global _chroma_client, _pref_vectorstore, _action_vectorstore
    
    persist_dir = Path(settings.chroma_persist_dir)
    persist_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"初始化 ChromaDB，持久化目录: {persist_dir}")
    
    _chroma_client = chromadb.PersistentClient(
        path=str(persist_dir),
        settings=ChromaSettings(anonymized_telemetry=False)
    )
    
    embedding_func = _get_embedding_function()
    
    # 创建/获取用户偏好集合
    _pref_vectorstore = Chroma(
        client=_chroma_client,
        collection_name=settings.chroma_collection_prefs,
        embedding_function=embedding_func,
    )
    
    # 创建/获取用户操作日志集合
    _action_vectorstore = Chroma(
        client=_chroma_client,
        collection_name=settings.chroma_collection_actions,
        embedding_function=embedding_func,
    )
    
    logger.info("✅ ChromaDB 初始化完成")


def close_vector_store():
    """关闭 ChromaDB 客户端（实际上 ChromaDB 会自动落盘）"""
    global _chroma_client
    if _chroma_client:
        # ChromaDB PersistentClient 不需要显式 close
        _chroma_client = None
        logger.info("ChromaDB 已关闭")