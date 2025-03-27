from fastapi import Request, HTTPException
from app.core.db_pool import db_pool
import logging
import asyncio
import time
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class DatabaseHealthCheck:
    def __init__(self):
        self.last_check: Optional[datetime] = None
        self.is_healthy: bool = True
        self.check_interval: int = 60  # 60秒检查一次
        self.unhealthy_threshold: int = 3  # 连续失败3次认为不健康
        self.failure_count: int = 0
    
    async def check_health(self):
        """检查数据库健康状态"""
        now = datetime.now()
        
        # 如果距离上次检查时间不足间隔时间，直接返回上次的状态
        if (self.last_check and 
            (now - self.last_check).total_seconds() < self.check_interval):
            return self.is_healthy
        
        try:
            is_healthy = db_pool.check_health()
            self.last_check = now
            
            if is_healthy:
                self.failure_count = 0
                self.is_healthy = True
            else:
                self.failure_count += 1
                if self.failure_count >= self.unhealthy_threshold:
                    self.is_healthy = False
                    logger.error("Database is unhealthy after multiple failed checks")
            
            return self.is_healthy
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            self.failure_count += 1
            if self.failure_count >= self.unhealthy_threshold:
                self.is_healthy = False
            return False

health_checker = DatabaseHealthCheck()

async def db_health_middleware(request: Request, call_next):
    """数据库健康检查中间件"""
    # 检查数据库健康状态
    is_healthy = await health_checker.check_health()
    
    if not is_healthy:
        # 如果是健康检查接口，返回详细状态
        if request.url.path == "/health":
            return {
                "status": "unhealthy",
                "database": "unavailable",
                "last_check": health_checker.last_check.isoformat() if health_checker.last_check else None,
                "failure_count": health_checker.failure_count
            }
        # 其他接口返回503错误
        raise HTTPException(
            status_code=503,
            detail="Database service unavailable"
        )
    
    # 继续处理请求
    response = await call_next(request)
    return response 