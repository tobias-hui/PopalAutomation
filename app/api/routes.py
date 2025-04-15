from fastapi import APIRouter
from .v1 import router as v1_router

# 创建主路由
router = APIRouter()

# 注册v1版本的路由
router.include_router(v1_router)