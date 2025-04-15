from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
import logging
from datetime import datetime
import uuid
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.task_models import Task, TaskStatus, serialize_request_data
from app.models.image_models import (
    DimensionImageRequest,
    CarouselRequest,
    ProcessResponse,
    ProductInfoRequest,
    ComplianceLabelRequest
)
from .utils import (
    process_carousel_background_task,
    process_dimension_background,
    process_product_info_background,
    process_compliance_label_background
)

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由
router = APIRouter(prefix="/images", tags=["Images"])

@router.post("/carousel", response_model=ProcessResponse)
async def process_carousel(
    request: CarouselRequest, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """处理轮播图API端点"""
    try:
        # 创建任务记录
        task_id = str(uuid.uuid4())
        task = Task(
            task_id=task_id,
            status=TaskStatus.PENDING,
            created_at=datetime.utcnow(),
            message="轮播图处理任务已创建",
            request_data=serialize_request_data(request.dict())
        )
        db.add(task)
        db.commit()
        
        # 添加后台任务
        background_tasks.add_task(
            process_carousel_background_task, 
            task_id, 
            request.zip_url, 
            request.dimensions_text,
            request.title,
            request.pcs,
            db
        )
        
        return ProcessResponse(
            task_id=task_id,
            status="pending",
            created_at=task.created_at
        )
        
    except Exception as e:
        logger.error(f"Error creating carousel task: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/dimension", response_model=ProcessResponse)
async def process_dimension(
    request: DimensionImageRequest, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """处理尺寸图API端点"""
    try:
        # 创建任务记录
        task_id = str(uuid.uuid4())
        task = Task(
            task_id=task_id,
            status=TaskStatus.PENDING,
            created_at=datetime.utcnow(),
            message="尺寸图处理任务已创建",
            request_data=serialize_request_data(request.dict())
        )
        db.add(task)
        db.commit()
        
        # 添加后台任务
        background_tasks.add_task(process_dimension_background, task_id, request, db)
        
        return ProcessResponse(
            task_id=task_id,
            status="pending",
            created_at=task.created_at
        )
        
    except Exception as e:
        logger.error(f"Error creating dimension task: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/product-info", response_model=ProcessResponse)
async def process_product_info(
    request: ProductInfoRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """处理产品信息图片API端点"""
    try:
        # 创建任务记录
        task_id = str(uuid.uuid4())
        task = Task(
            task_id=task_id,
            status=TaskStatus.PENDING,
            created_at=datetime.utcnow(),
            message="产品信息处理任务已创建",
            request_data=serialize_request_data(request.dict())
        )
        db.add(task)
        db.commit()
        
        # 添加后台任务
        background_tasks.add_task(process_product_info_background, task_id, request, db)
        
        return ProcessResponse(
            task_id=task_id,
            status="pending",
            created_at=task.created_at
        )
        
    except Exception as e:
        logger.error(f"Error creating product info task: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/compliance-label", response_model=ProcessResponse)
async def process_compliance_label(
    request: ComplianceLabelRequest,
    db: Session = Depends(get_db)
):
    """处理合规标签API端点"""
    try:
        # 创建任务记录
        task_id = str(uuid.uuid4())
        task = Task(
            task_id=task_id,
            status=TaskStatus.PENDING,
            created_at=datetime.utcnow(),
            message="合规标签处理任务已创建",
            request_data=serialize_request_data(request.dict())
        )
        db.add(task)
        db.commit()
        
        # 直接调用处理函数
        result = await process_compliance_label_background(task_id, request, db)
        
        return ProcessResponse(
            task_id=task_id,
            status="completed",
            output_url=result["output_url"],
            created_at=task.created_at
        )
        
    except Exception as e:
        logger.error(f"Error processing compliance label: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 