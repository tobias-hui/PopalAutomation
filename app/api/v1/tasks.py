from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
import logging

from app.core.database import get_db
from app.models.task_models import Task, TaskStatus
from app.models.image_models import TaskQueryResponse, ImageProcessingTask
from app.utils.oss_client import oss_client

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由
router = APIRouter(prefix="/tasks", tags=["Tasks"])

@router.get("/{task_id}/result")
async def get_task_result(task_id: str, db: Session = Depends(get_db)):
    """获取任务处理结果"""
    task = db.query(Task).filter(Task.task_id == task_id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status not in ["completed", "failed"]:
        raise HTTPException(
            status_code=400, 
            detail="Task is still processing or pending"
        )
    
    return task.to_dict()

@router.get("/{task_id}", response_model=TaskQueryResponse)
async def get_task_status(task_id: str, db: Session = Depends(get_db)):
    """获取任务状态"""
    task = db.query(Task).filter(Task.task_id == task_id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 计算进度和预计时间
    progress = None
    estimated_time = None
    if task.status == "processing":
        elapsed_time = (datetime.now() - task.created_at).total_seconds()
        if elapsed_time < 300:  # 5分钟内的任务
            progress = min(elapsed_time / 300 * 100, 99)
            estimated_time = max(300 - elapsed_time, 1)
    
    # 创建ImageProcessingTask实例
    task_data = ImageProcessingTask(
        task_id=task.task_id,
        status=task.status,
        created_at=task.created_at,
        completed_at=task.completed_at,
        output_url=task.output_url,
        error=task.error,
        message=task.message,
        progress=progress,
        estimated_time=estimated_time,
        result=task.additional_data
    )
    
    return TaskQueryResponse(
        status=task.status,
        task=task_data,
        error=task.error
    )

@router.get("", response_model=List[TaskQueryResponse])
async def list_tasks(
    limit: int = 10,
    status: Optional[str] = None,
    created_after: Optional[datetime] = None,
    db: Session = Depends(get_db)
):
    """获取任务列表"""
    query = db.query(Task)
    
    if status:
        query = query.filter(Task.status == status)
    if created_after:
        query = query.filter(Task.created_at > created_after)
        
    tasks = query.order_by(Task.created_at.desc()).limit(limit).all()
    
    return [
        TaskQueryResponse(
            status=task.status,
            task=ImageProcessingTask(
                task_id=task.task_id,
                status=task.status,
                created_at=task.created_at,
                completed_at=task.completed_at,
                output_url=task.output_url,
                error=task.error,
                message=task.message,
                progress=None,
                estimated_time=None,
                result=task.additional_data
            ),
            error=task.error
        ) for task in tasks
    ]

@router.delete("/{task_id}")
async def delete_task(task_id: str, db: Session = Depends(get_db)):
    """删除任务记录"""
    task = db.query(Task).filter(Task.task_id == task_id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.output_url:
        try:
            file_path = task.output_url.split("/")[-1]
            oss_client.delete_file(file_path)
        except Exception as e:
            logger.error(f"Error deleting file from OSS: {str(e)}")
    
    db.delete(task)
    db.commit()
    
    return {"status": "success", "message": "Task deleted successfully"} 