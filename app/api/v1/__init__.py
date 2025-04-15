from fastapi import APIRouter
from . import images, tasks, orders, upload, listing, health

# 创建v1版本的路由器
router = APIRouter()

# 注册所有子路由
router.include_router(images.router)
router.include_router(tasks.router)
router.include_router(orders.router)
router.include_router(upload.router)
router.include_router(listing.router)
router.include_router(health.router) 