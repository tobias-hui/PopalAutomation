from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.task_models import Task
from app.utils.oss_client import oss_client

# 创建路由
router = APIRouter(prefix="/health", tags=["Health"])

@router.get("")
async def health_check(db: Session = Depends(get_db)):
    """健康检查端点"""
    query = db.query(Task)
    total_tasks = query.count()
    completed_tasks = query.filter(Task.status == "completed").count()
    failed_tasks = query.filter(Task.status == "failed").count()
    
    return {
        "status": "healthy",
        "oss_configured": oss_client is not None,
        "stats": {
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "failed_tasks": failed_tasks,
            "success_rate": completed_tasks / total_tasks if total_tasks > 0 else 0
        }
    } 