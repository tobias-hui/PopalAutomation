from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File, Form, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional, Dict
import logging
from datetime import datetime, timedelta
import uuid
from pathlib import Path
import os
import json
from tempfile import TemporaryDirectory
from io import BytesIO
import zipfile
from zipfile import ZipFile, BadZipFile
import httpx
import time
import aiofiles
from PIL import Image

from app.core.image_processor import (
    DimensionProcessor,
    CarouselImageProcessor,
    WhiteBackgroundProcessor
)
from app.core.product_info_processor import ProductInfoProcessor
from app.utils.oss_client import oss_client
from app.utils.order_service import OrderService, SimpleOrderRequest
from app.models.order_models import OrderRequest, OrderResponse
from app.core.database import get_db
from app.models.task_models import Task, serialize_request_data, TaskStatus
from sqlalchemy.orm import Session

from app.models.image_models import (
    DimensionImageRequest,
    CarouselRequest,
    ProcessResponse,
    TaskQueryResponse,
    UploadResponse,
    WhiteBackgroundRequest,
    ProductInfoRequest
)

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由
router = APIRouter()

# 创建订单服务实例
order_service = OrderService()

async def process_carousel_background_task(
    task_id: str,
    zip_url: str,
    dimensions: str,
    db: Session
):
    """后台处理轮播图"""
    try:
        # 更新任务状态为处理中
        await update_task_status(db, task_id, TaskStatus.PROCESSING)
        
        # 下载ZIP文件
        async with httpx.AsyncClient() as client:
            response = await client.get(str(zip_url))
            if response.status_code != 200:
                error_msg = f"Failed to download ZIP file: HTTP {response.status_code}"
                logger.error(error_msg)
                raise HTTPException(status_code=response.status_code, detail=error_msg)
            zip_data = BytesIO(response.content)
        
        # 处理图片
        processor = CarouselImageProcessor(dimensions)
        result = await processor.process_zip(zip_data)
        
        # 更新任务状态为完成，并保存结果
        await update_task_status(
            db, 
            task_id, 
            TaskStatus.COMPLETED,
            output_url=result.get("output_url"),
            additional_data={
                "output_url": result.get("output_url"),
                "rotating_video_url": result.get("rotating_video_url"),
                "falling_bricks_video_url": result.get("falling_bricks_video_url")
            }
        )
        
    except Exception as e:
        logger.error(f"处理轮播图时出错: {str(e)}")
        await update_task_status(db, task_id, TaskStatus.FAILED, error=str(e))
        raise

async def update_task_status(
    db: Session, 
    task_id: str, 
    status: TaskStatus, 
    output_url: str = None, 
    additional_data: dict = None,
    error: str = None
):
    """更新任务状态"""
    task = db.query(Task).filter(Task.task_id == task_id).first()
    if task:
        task.status = status
        if output_url:
            task.output_url = output_url
        if additional_data:
            task.additional_data = additional_data
        if error:
            task.error = error
        if status == TaskStatus.COMPLETED:
            task.completed_at = datetime.utcnow()
        task.updated_at = datetime.utcnow()
        db.commit()

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
            message=f"轮播图处理任务已创建"
        )
        db.add(task)
        db.commit()
        
        # 添加后台任务
        background_tasks.add_task(process_carousel_background_task, task_id, request.zip_url, request.dimensions_text, db)
        
        return ProcessResponse(
            task_id=task_id,
            status="pending",
            message="轮播图处理任务已提交",
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
            message="尺寸图处理任务已提交",
            created_at=task.created_at
        )
        
    except Exception as e:
        logger.error(f"Error creating dimension task: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def process_dimension_background(task_id: str, request: DimensionImageRequest, db: Session):
    """后台处理尺寸图"""
    try:
        # 更新任务状态为处理中
        await update_task_status(db, task_id, TaskStatus.PROCESSING)
        
        # 创建处理器
        processor = DimensionProcessor(
            length=request.length,
            height=request.height
        )
        
        # 下载图片
        async with httpx.AsyncClient() as client:
            response = await client.get(str(request.image_url))
            if response.status_code != 200:
                error_msg = f"Failed to download image: HTTP {response.status_code}"
                logger.error(error_msg)
                raise HTTPException(status_code=response.status_code, detail=error_msg)
            image_data = response.content
        
        # 处理图片
        try:
            with Image.open(BytesIO(image_data)) as img:
                # 验证图片格式和通道
                if img.mode not in ['RGBA', 'LA']:
                    error_msg = "Image must have an alpha channel (RGBA or LA mode)"
                    logger.error(error_msg)
                    raise ValueError(error_msg)
                
                # 验证图片尺寸
                if img.size[0] < 100 or img.size[1] < 100:  # 最小尺寸限制
                    error_msg = "Image dimensions too small"
                    logger.error(error_msg)
                    raise ValueError(error_msg)
                
                # 处理图片
                result = processor.process_image(img)
                
                # 验证处理结果
                if result is None or result.size != processor.canvas_size:
                    error_msg = "Image processing failed: invalid output"
                    logger.error(error_msg)
                    raise ValueError(error_msg)
        except Exception as e:
            error_msg = f"Error processing image: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # 创建临时目录保存处理后的图片
        with TemporaryDirectory() as temp_dir:
            temp_dir = Path(temp_dir)
            output_path = temp_dir / f"processed_{task_id}.png"
            
            # 保存处理后的图片
            try:
                result.save(output_path, "PNG")
            except Exception as e:
                error_msg = f"Error saving processed image: {str(e)}"
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            # 生成OSS对象名称
            oss_filename = f"processed_images/dimension_{task_id}.png"
            
            # 上传到OSS
            try:
                output_url = await oss_client.upload_file(str(output_path), oss_filename)
                logger.info(f"Successfully uploaded processed image to OSS: {output_url}")
            except Exception as e:
                error_msg = f"Error uploading to OSS: {str(e)}"
                logger.error(error_msg)
                raise HTTPException(status_code=500, detail=error_msg)
            
            # 更新任务状态为完成
            await update_task_status(db, task_id, TaskStatus.COMPLETED, output_url)
            
            return {"status": "success", "output_url": output_url}
        
    except ValueError as e:
        error_msg = str(e)
        logger.error(f"Validation error processing dimension image: {error_msg}")
        await update_task_status(db, task_id, TaskStatus.FAILED, error_msg)
        raise HTTPException(status_code=400, detail=error_msg)
    except HTTPException as e:
        error_msg = str(e.detail)
        logger.error(f"HTTP error processing dimension image: {error_msg}")
        await update_task_status(db, task_id, TaskStatus.FAILED, error_msg)
        raise e
    except Exception as e:
        error_msg = f"Unexpected error processing dimension image: {str(e)}"
        logger.error(error_msg)
        await update_task_status(db, task_id, TaskStatus.FAILED, error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/tasks/{task_id}/result")
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

@router.get("/tasks/{task_id}", response_model=TaskQueryResponse)
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
    
    return TaskQueryResponse(
        task_id=task.task_id,
        status=task.status,
        progress=progress,
        message=task.message,
        created_at=task.created_at,
        completed_at=task.completed_at,
        output_url=task.output_url,
        error=task.error,
        estimated_time=estimated_time,
        result=task.result
    )

@router.get("/tasks", response_model=List[TaskQueryResponse])
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
            task_id=task.task_id,
            status=task.status,
            progress=None,
            message=task.message,
            created_at=task.created_at,
            completed_at=task.completed_at,
            output_url=task.output_url,
            error=task.error,
            estimated_time=None,
            result=task.result
        ) for task in tasks
    ]

@router.delete("/tasks/{task_id}")
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

@router.get("/health")
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

@router.post("/upload/image", response_model=UploadResponse)
async def upload_image(file: UploadFile = File(...)):
    """
    上传单个图片文件
    """
    try:
        # 验证文件类型
        if not file.content_type.startswith('image/'):
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Only images are allowed."
            )

        # 创建临时目录
        with TemporaryDirectory() as temp_dir:
            temp_file_path = os.path.join(temp_dir, file.filename)
            
            # 保存文件到临时目录
            async with aiofiles.open(temp_file_path, 'wb') as out_file:
                content = await file.read()
                await out_file.write(content)

            # 获取文件大小
            file_size = os.path.getsize(temp_file_path)

            # 生成唯一的对象名称
            timestamp = int(time.time())
            object_name = f"uploads/images/{timestamp}_{file.filename}"

            # 上传到OSS
            file_url = await oss_client.upload_file(temp_file_path, object_name)

            return UploadResponse(
                file_url=file_url,
                file_name=file.filename,
                file_size=file_size,
                created_at=datetime.now()
            )

    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error uploading file: {str(e)}"
        )

@router.post("/upload", response_model=UploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    file_type: str = Form(..., description="文件类型：image 或 zip")
):
    """
    统一的文件上传接口
    
    参数:
    - file: 要上传的文件
    - file_type: 文件类型（image/zip）
    
    返回:
    - file_url: 文件访问URL
    - file_name: 文件名
    - file_size: 文件大小
    - created_at: 创建时间
    """
    try:
        # 验证文件类型
        if file_type == "image":
            if not file.content_type.startswith('image/'):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid file type. Only images are allowed."
                )
            folder = "images"
        elif file_type == "zip":
            if file.content_type != 'application/zip':
                raise HTTPException(
                    status_code=400,
                    detail="Invalid file type. Only ZIP files are allowed."
                )
            folder = "zips"
        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid file_type. Must be either 'image' or 'zip'"
            )

        # 创建临时目录
        with TemporaryDirectory() as temp_dir:
            temp_file_path = os.path.join(temp_dir, file.filename)
            
            # 保存文件到临时目录
            async with aiofiles.open(temp_file_path, 'wb') as out_file:
                content = await file.read()
                await out_file.write(content)

            # 如果是ZIP文件，验证其完整性
            if file_type == "zip":
                try:
                    with ZipFile(temp_file_path, 'r') as zip_ref:
                        if zip_ref.testzip() is not None:
                            raise HTTPException(
                                status_code=400,
                                detail="Invalid or corrupted ZIP file"
                            )
                except BadZipFile:
                    raise HTTPException(
                        status_code=400,
                        detail="Invalid ZIP file format"
                    )

            # 获取文件大小
            file_size = os.path.getsize(temp_file_path)

            # 生成唯一的对象名称
            timestamp = int(time.time())
            object_name = f"uploads/{folder}/{timestamp}_{file.filename}"

            # 上传到OSS
            file_url = await oss_client.upload_file(temp_file_path, object_name)

            return UploadResponse(
                file_url=file_url,
                file_name=file.filename,
                file_size=file_size,
                created_at=datetime.now()
            )

    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error uploading file: {str(e)}"
        )

@router.post("/orders", response_model=OrderResponse)
async def create_order(request: OrderRequest):
    """
    创建订单API端点
    
    Args:
        request: OrderRequest - 订单请求数据
        
    Returns:
        OrderResponse - 订单创建响应
    """
    try:
        # 转换请求数据
        simple_request = SimpleOrderRequest(
            orderid=request.orderid,
            num=request.num,
            photo=str(request.photo),
            urgent=request.urgent,
            delivery=request.delivery,
            specsCode=request.specsCode,
            receiverName=request.receiverName,
            receiverContact=request.receiverContact,
            receiverAddress=request.receiverAddress
        )
        
        # 调用订单服务
        result = order_service.create_order(simple_request)
        
        # 检查响应
        if isinstance(result, dict) and result.get("error"):
            return OrderResponse(
                success=False,
                message=f"订单创建失败: {result['error']}",
                data=result
            )
            
        return OrderResponse(
            success=True,
            message="订单创建成功",
            data=result
        )
        
    except Exception as e:
        logger.error(f"创建订单失败: {str(e)}")
        return OrderResponse(
            success=False,
            message=f"订单创建失败: {str(e)}",
            data=None
        )

async def process_white_background(task_id: str, request: WhiteBackgroundRequest, db: Session):
    """后台处理白色背景"""
    try:
        # 更新任务状态为处理中
        await update_task_status(db, task_id, TaskStatus.PROCESSING)
        
        # 创建处理器
        processor = WhiteBackgroundProcessor()
        
        # 处理图片
        result = processor.process_image(request.image)
        
        # 保存处理后的图片
        output_path = f"processed_{task_id}.png"
        result.save(output_path)
        
        # 更新任务状态为完成
        await update_task_status(db, task_id, TaskStatus.COMPLETED, output_path)
        
        return {"status": "success", "output_path": output_path}
        
    except Exception as e:
        logger.error(f"Error processing white background: {str(e)}")
        await update_task_status(db, task_id, TaskStatus.FAILED, str(e))
        raise HTTPException(status_code=500, detail=str(e))

async def process_product_info_background(task_id: str, request: ProductInfoRequest, db: Session):
    """后台处理产品信息图片"""
    try:
        # 更新任务状态为处理中
        await update_task_status(db, task_id, TaskStatus.PROCESSING)
        
        # 创建临时目录
        with TemporaryDirectory() as temp_dir:
            temp_dir = Path(temp_dir)
            input_path = temp_dir / f"input_{task_id}.png"
            
            # 下载输入图片
            async with httpx.AsyncClient() as client:
                response = await client.get(str(request.image_url))
                if response.status_code != 200:
                    error_msg = f"Failed to download image: HTTP {response.status_code}"
                    logger.error(error_msg)
                    raise HTTPException(status_code=response.status_code, detail=error_msg)
                input_path.write_bytes(response.content)
            
            # 创建处理器实例
            processor = ProductInfoProcessor(
                product_info={
                    "title": request.title,
                    "pcs": request.pcs,
                    "height_cm": request.height_cm,
                    "length_cm": request.length_cm,
                    "product_image_path": str(input_path)
                }
            )
            
            # 处理图片
            processed_image = processor.process_image()
            
            # 保存处理后的图片
            output_path = temp_dir / f"processed_{task_id}.png"
            processed_image.save(output_path)
            
            # 生成OSS对象名称
            oss_filename = f"processed_images/product_info_{task_id}.png"
            
            # 上传到OSS
            try:
                output_url = await oss_client.upload_file(str(output_path), oss_filename)
                logger.info(f"Successfully uploaded processed image to OSS: {output_url}")
            except Exception as e:
                error_msg = f"Error uploading to OSS: {str(e)}"
                logger.error(error_msg)
                raise HTTPException(status_code=500, detail=error_msg)
            
            # 更新任务状态为完成
            await update_task_status(
                db, 
                task_id, 
                TaskStatus.COMPLETED,
                output_url=output_url,
                additional_data={"output_url": output_url}
            )
            
            return {"status": "success", "output_url": output_url}
            
    except ValueError as e:
        error_msg = str(e)
        logger.error(f"Validation error processing product info image: {error_msg}")
        await update_task_status(db, task_id, TaskStatus.FAILED, error=error_msg)
        raise HTTPException(status_code=400, detail=error_msg)
    except HTTPException as e:
        error_msg = str(e.detail)
        logger.error(f"HTTP error processing product info image: {error_msg}")
        await update_task_status(db, task_id, TaskStatus.FAILED, error=error_msg)
        raise e
    except Exception as e:
        error_msg = f"Unexpected error processing product info image: {str(e)}"
        logger.error(error_msg)
        await update_task_status(db, task_id, TaskStatus.FAILED, error=error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@router.post("/product-info", response_model=ProcessResponse)
async def process_product_info(
    request: ProductInfoRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    处理产品信息图片API端点
    
    Args:
        request: ProductInfoRequest - 产品信息处理请求
        background_tasks: BackgroundTasks - FastAPI后台任务
        db: Session - 数据库会话
        
    Returns:
        ProcessResponse - 处理响应
    """
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
            message="产品信息处理任务已提交",
            created_at=task.created_at
        )
        
    except Exception as e:
        logger.error(f"创建产品信息处理任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))