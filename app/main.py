from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from app.api.routes import router
from app.middleware.db_health import db_health_middleware
from app.core.db_pool import db_pool
from app.config.settings import (
    API_TITLE,
    API_DESCRIPTION,
    API_VERSION,
    TEMP_DIR,
    OUTPUT_DIR
)

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建应用
app = FastAPI(
    title=API_TITLE,
    description=API_DESCRIPTION,
    version=API_VERSION,
    openapi_url="/api/v1/openapi.json",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    # 添加更多 OpenAPI 配置
    openapi_tags=[
        {
            "name": "Images",
            "description": "图片处理相关的 API 接口"
        },
        {
            "name": "Listing",
            "description": "产品listing相关的 API 接口"
        },
        {
            "name": "Orders",
            "description": "订单管理相关的 API 接口"
        },
        {
            "name": "Tasks",
            "description": "任务管理相关的 API 接口"
        }
    ]
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该设置具体的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加数据库健康检查中间件
app.middleware("http")(db_health_middleware)

# 包含路由
app.include_router(router, prefix="/api/v1")

# 创建必要的目录
TEMP_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

@app.get("/health")
async def health_check():
    """健康检查接口"""
    is_healthy = db_pool.check_health()
    return {
        "status": "healthy" if is_healthy else "unhealthy",
        "database": "available" if is_healthy else "unavailable"
    }

@app.get("/")
async def root():
    return {
        "title": API_TITLE,
        "version": API_VERSION,
        "description": API_DESCRIPTION,
        "docs_url": "/api/v1/docs",
        "redoc_url": "/api/v1/redoc",
        "openapi_url": "/api/v1/openapi.json"
    }

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理资源"""
    db_pool.dispose() 