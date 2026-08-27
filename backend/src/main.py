from contextlib import asynccontextmanager
from src.services.redis_client import close_redis, init_redis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config.settings import settings
from src.core.logging import setup_logging, get_logger
from src.core.exceptions import setup_exception_handlers
from src.graph.graph import close_graph_checkpointers, get_graph_async
from src.models.common import ApiResponse
from src.models.health import ServiceInfoData
from src.services.vector_store import init_vector_store, close_vector_store

# 初始化日志
setup_logging()
logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🔄 初始化应用...")
    # 初始化 LangGraph 图（提前构建，避免首次请求延迟）
    try:
        graph = await get_graph_async()
        logger.info(f"✅ LangGraph 图已初始化，checkpointer: SQLite")
    except Exception as e:
        logger.error(f"❌ LangGraph 图初始化失败: {e}")
        raise
    
    # 初始化 Redis 连接池
    logger.info("初始化Redis...")
    await init_redis()
    # 初始化 ChromaDB 客户端
    init_vector_store()
    logger.info("✅ ChromaDB 初始化完成")
    
    yield

    logger.info("🔄 关闭应用...")
    # 关闭 Redis 连接池
    await close_redis()
    await close_graph_checkpointers()
    # 关闭 ChromaDB 连接
    close_vector_store()
    logger.info("✅ 应用已关闭")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/api/docs" if settings.debug else None,
    lifespan=lifespan,
)

# CORS 配置（开发环境全开）
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# 注册异常处理
setup_exception_handlers(app)


# -------------------- 注册路由占位（方便测试） --------------------
@app.get("/", response_model=ApiResponse[ServiceInfoData])
async def root():
    return ApiResponse(
        code=200,
        message="服务运行正常",
        data=ServiceInfoData(
            service=settings.app_name,
            version=settings.app_version,
            status="running",
        ),
    )


from src.api.v1 import health
from src.api.v1 import chat
from src.api.v1 import preferences
from src.api.v1 import sessions
from src.api.v1 import traces
app.include_router(health.router, prefix="/api/v1", tags=["系统运维"])
app.include_router(chat.router, prefix="/api/v1", tags=["AI 对话和行程生成"])
app.include_router(preferences.router, prefix="/api/v1", tags=["用户画像"])
app.include_router(sessions.router, prefix="/api/v1", tags=["行程管理"])
app.include_router(traces.router, prefix="/api/v1", tags=["评估系统"])
