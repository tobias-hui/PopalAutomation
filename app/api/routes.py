from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional, Dict
import logging
from datetime import datetime, timedelta
import uuid
from app.core.image_processor import process_images, ImageProcessor
from app.utils.oss_client import oss_client
from app.utils.order_service import OrderService, SimpleOrderRequest
from app.models.order_models import OrderRequest, OrderResponse
from pathlib import Path
import os
import json
import aiohttp
from tempfile import TemporaryDirectory
from PIL import Image
from io import BytesIO
import zipfile
import aiofiles
import hashlib
import time
from zipfile import ZipFile, BadZipFile

from app.models.image_models import (
    DimensionImageRequest,
    CarouselRequest,
    ProcessResponse,
    ImageProcessingTask,
    DimensionSet,
    TaskQueryResponse,
    UploadResponse
)
from app.core.image_processor import create_processor

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由
router = APIRouter()

# 内存中存储任务信息（实际应用中应该使用数据库）
tasks = {}

# 创建订单服务实例
order_service = OrderService()

async def process_carousel_background(task_id: str, request: CarouselRequest):
    """后台处理轮播图"""
    try:
        tasks[task_id]["status"] = "processing"
        tasks[task_id]["message"] = "Processing carousel images..."
        
        # 解析尺寸文本
        dimensions = {}
        if request.dimensions_text:
            # 解析格式如 "Length:11.2cmWidth:10.4cmHeight:13.1cm"
            dim_parts = request.dimensions_text.lower().replace('cm', ' cm').split()
            for part in dim_parts:
                if ':' in part:
                    key, value = part.split(':')
                    if key.lower() in ['length', 'width', 'height']:
                        dimensions[key.lower()] = float(value)
        
        # 创建处理器
        dimension_processor = create_processor(
            'dimension',
            dimensions={
                "length": {
                    "value": dimensions.get("length", 0),
                    "unit": "cm",
                    "inch": round(dimensions.get("length", 0) / 2.54, 2)
                },
                "width": {
                    "value": dimensions.get("width", 0),
                    "unit": "cm", 
                    "inch": round(dimensions.get("width", 0) / 2.54, 2)
                },
                "height": {
                    "value": dimensions.get("height", 0),
                    "unit": "cm",
                    "inch": round(dimensions.get("height", 0) / 2.54, 2)
                }
            }
        ) if dimensions else None
        
        # 创建临时目录
        with TemporaryDirectory() as temp_dir:
            temp_dir = Path(temp_dir)
            output_dir = temp_dir / "output"
            output_dir.mkdir(exist_ok=True)
            
            # 下载ZIP文件
            async with aiohttp.ClientSession() as session:
                async with session.get(request.zip_url) as response:
                    if response.status != 200:
                        raise HTTPException(status_code=response.status, detail="Failed to download ZIP file")
                    zip_data = await response.read()
            
            # 保存ZIP文件
            zip_path = temp_dir / "input.zip"
            zip_path.write_bytes(zip_data)
            
            # 处理ZIP文件中的图片
            with ZipFile(zip_path, 'r') as zip_ref:
                image_files = [f for f in zip_ref.namelist() if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
                image_files.sort()  # 确保文件顺序
                
                for image_file in image_files:
                    # 提取图片
                    with zip_ref.open(image_file) as f:
                        img_data = f.read()
                        img = Image.open(BytesIO(img_data)).convert("RGBA")
                        
                        # 根据文件名决定处理方式
                        filename = Path(image_file).stem.lower()  # 只获取文件名，不包含扩展名
                        
                        # 检查文件名中是否包含 "_2"
                        if "_2" in filename and dimension_processor:
                            # 文件名包含"_2"的图片：添加白色背景和尺寸标注
                            white_bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
                            white_bg.paste(img, (0, 0), img)
                            processed_img = dimension_processor.process_image(white_bg)
                            output_name = f"{Path(image_file).stem}_dimension_{uuid.uuid4()}.png"
                        # 检查文件名中是否包含其他数字序号（如 _1, _3, _4 等）
                        elif any(f"_{i}" in filename for i in range(10) if i != 2):
                            # 其他序号图片：只添加白色背景
                            white_bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
                            white_bg.paste(img, (0, 0), img)
                            processed_img = white_bg
                            output_name = f"{Path(image_file).stem}_white_{uuid.uuid4()}.png"
                        else:
                            # 其他图片：保持原样
                            processed_img = img
                            output_name = f"{Path(image_file).stem}_original_{uuid.uuid4()}.png"
                        
                        # 保存处理后的图片
                        output_path = output_dir / output_name
                        processed_img.save(output_path, "PNG")
            
            # 创建新的ZIP文件，使用唯一标识符
            zip_unique_id = uuid.uuid4()
            output_zip = temp_dir / f"carousel_images_{zip_unique_id}.zip"
            with ZipFile(output_zip, 'w') as zip_out:
                for img_path in output_dir.glob("*.png"):
                    zip_out.write(img_path, img_path.name)
            
            # 上传到OSS，使用唯一的文件名
            oss_filename = f"carousel_images/carousel_{zip_unique_id}.zip"
            output_url = await oss_client.upload_file(output_zip, oss_filename)
            
            tasks[task_id].update({
                "status": "completed",
                "output_url": output_url,
                "completed_at": datetime.now(),
                "message": "Carousel processing completed successfully",
                "result": {
                    "total_images": len(image_files),
                    "output_url": output_url,
                    "dimensions": dimensions
                }
            })
            
    except Exception as e:
        logger.error(f"Error processing carousel task {task_id}: {str(e)}")
        tasks[task_id].update({
            "status": "failed",
            "error": str(e),
            "completed_at": datetime.now(),
            "message": "Task failed - see error for details"
        })

async def process_dimension_background(task_id: str, request: DimensionImageRequest):
    """后台处理尺寸图"""
    try:
        tasks[task_id]["status"] = "processing"
        tasks[task_id]["message"] = "Processing dimension image..."
        
        async with aiohttp.ClientSession() as session:
            async with session.get(str(request.image_url)) as response:
                if response.status != 200:
                    raise HTTPException(status_code=response.status, detail="Failed to download image")
                image_data = await response.read()

        with TemporaryDirectory() as temp_dir:
            temp_dir = Path(temp_dir)
            image_path = temp_dir / "original.png"
            # 使用UUID生成唯一的输出文件名
            unique_id = uuid.uuid4()
            output_path = temp_dir / f"dimension_{unique_id}.png"

            # 保存原始图片
            image_path.write_bytes(image_data)

            try:
                # 创建处理器并处理图片
                processor = create_processor(
                    'dimension',
                    dimensions=request.dimensions.to_processor_format()
                )

                with Image.open(image_path).convert("RGBA") as original_image:
                    final_image = processor.process_image(original_image)
                    final_image.save(output_path)

                # 上传到OSS，使用唯一的文件名
                oss_filename = f"dimension_images/dimension_{unique_id}.png"
                output_url = await oss_client.upload_file(output_path, oss_filename)

                tasks[task_id].update({
                    "status": "completed",
                    "output_url": output_url,
                    "completed_at": datetime.now(),
                    "message": "Image processing completed successfully",
                    "result": {
                        "original_size": os.path.getsize(image_path),
                        "processed_size": os.path.getsize(output_path),
                        "dimensions": request.dimensions.dict(),
                        "output_url": output_url
                    }
                })

            except Exception as e:
                logger.error(f"Error in image processing: {str(e)}")
                raise Exception(f"Image processing failed: {str(e)}")

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error processing dimension task {task_id}: {error_msg}")
        tasks[task_id].update({
            "status": "failed",
            "error": error_msg,
            "completed_at": datetime.now(),
            "message": "Task failed - see error for details"
        })

@router.post("/carousel", response_model=ProcessResponse)
async def process_carousel(request: CarouselRequest, background_tasks: BackgroundTasks):
    """
    处理轮播图API端点
    """
    task_id = str(uuid.uuid4())
    created_at = datetime.now()
    
    tasks[task_id] = {
        "status": "pending",
        "created_at": created_at,
        "request": request.dict()
    }
    
    background_tasks.add_task(process_carousel_background, task_id, request)
    
    return ProcessResponse(
        task_id=task_id,
        status="pending",
        message="Carousel processing task created successfully",
        created_at=created_at
    )

@router.post("/dimension", response_model=ProcessResponse)
async def process_dimension(request: DimensionImageRequest, background_tasks: BackgroundTasks):
    """
    处理尺寸图API端点
    """
    task_id = str(uuid.uuid4())
    created_at = datetime.now()
    
    tasks[task_id] = {
        "status": "pending",
        "created_at": created_at,
        "request": request.dict()
    }
    
    background_tasks.add_task(process_dimension_background, task_id, request)
    
    return ProcessResponse(
        task_id=task_id,
        status="pending",
        message="Dimension image processing task created successfully",
        created_at=created_at
    )

@router.get("/tasks/{task_id}/result")
async def get_task_result(task_id: str):
    """
    获取任务处理结果
    
    参数:
    - task_id: 任务ID
    
    返回:
    - 任务的详细结果，包括:
      - 处理状态
      - 输出URL
      - 处理参数
      - 错误信息（如果有）
    """
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = tasks[task_id]
    
    if task["status"] not in ["completed", "failed"]:
        raise HTTPException(
            status_code=400, 
            detail="Task is still processing or pending"
        )
    
    result = {
        "status": task["status"],
        "completed_at": task["completed_at"],
        "output_url": task.get("output_url"),
        "error": task.get("error"),
        "result": task.get("result"),
        "original_request": task.get("request")
    }
    
    return result

@router.get("/tasks/{task_id}", response_model=TaskQueryResponse)
async def get_task_status(task_id: str):
    """
    获取任务状态
    
    参数:
    - task_id: 任务ID
    
    返回:
    - 任务的当前状态信息
    
    注意:
    - 如果需要获取完整的处理结果，请使用 /tasks/{task_id}/result 端点
    """
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = tasks[task_id]
    
    # 计算进度和预计时间
    progress = None
    estimated_time = None
    if task["status"] == "processing":
        elapsed_time = (datetime.now() - task["created_at"]).total_seconds()
        if elapsed_time < 300:  # 5分钟内的任务
            progress = min(elapsed_time / 300 * 100, 99)
            estimated_time = max(300 - elapsed_time, 1)
    
    return TaskQueryResponse(
        task_id=task_id,
        status=task["status"],
        progress=progress,
        message=task.get("message", "Task found"),
        created_at=task["created_at"],
        completed_at=task.get("completed_at"),
        output_url=task.get("output_url"),
        error=task.get("error"),
        estimated_time=estimated_time,
        result=task.get("result")
    )

@router.get("/tasks", response_model=List[TaskQueryResponse])
async def list_tasks(
    limit: int = 10,
    status: Optional[str] = None,
    created_after: Optional[datetime] = None
):
    """
    获取任务列表
    
    参数:
    - limit: 返回的最大任务数量（默认10）
    - status: 筛选特定状态的任务（可选）
    - created_after: 筛选特定时间之后创建的任务（可选）
    
    返回:
    任务状态列表，每个任务包含与单个任务查询相同的字段
    
    示例请求:
    ```bash
    # 获取所有处理中的任务
    curl -X GET "http://your-api-host/tasks?status=processing"
    
    # 获取最近1小时创建的任务
    curl -X GET "http://your-api-host/tasks?created_after=2024-03-15T10:00:00"
    ```
    """
    filtered_tasks = []
    for task_id, task in tasks.items():
        if status and task["status"] != status:
            continue
        if created_after and task["created_at"] < created_after:
            continue
            
        # 计算进度和预计时间
        progress = None
        estimated_time = None
        if task["status"] == "processing":
            elapsed_time = (datetime.now() - task["created_at"]).total_seconds()
            if elapsed_time < 300:
                progress = min(elapsed_time / 300 * 100, 99)
                estimated_time = max(300 - elapsed_time, 1)
        
        filtered_tasks.append(TaskQueryResponse(
            task_id=task_id,
            status=task["status"],
            progress=progress,
            message=task.get("message", "Task found"),
            created_at=task["created_at"],
            completed_at=task.get("completed_at"),
            output_url=task.get("output_url"),
            error=task.get("error"),
            estimated_time=estimated_time
        ))
    
    # 按创建时间排序并限制数量
    filtered_tasks.sort(key=lambda x: x.created_at, reverse=True)
    return filtered_tasks[:limit]

@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    """删除任务记录"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = tasks.pop(task_id)
    if task.get("output_url"):
        try:
            file_path = task["output_url"].split("/")[-1]
            oss_client.delete_file(file_path)
        except Exception as e:
            logger.error(f"Error deleting file from OSS: {str(e)}")
    
    return {"status": "success", "message": "Task deleted successfully"}

@router.get("/health")
async def health_check():
    """健康检查端点"""
    total_tasks = len(tasks)
    completed_tasks = sum(1 for task in tasks.values() if task["status"] == "completed")
    failed_tasks = sum(1 for task in tasks.values() if task["status"] == "failed")
    
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

# 将原有的 upload_zip 标记为弃用
@router.post("/upload/zip", response_model=UploadResponse, deprecated=True)
async def upload_zip(file: UploadFile = File(...)):
    """
    上传ZIP文件（已弃用，请使用 /upload 接口）
    """
    try:
        # 验证文件类型
        if file.content_type != 'application/zip':
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Only ZIP files are allowed."
            )

        # 创建临时目录
        with TemporaryDirectory() as temp_dir:
            temp_file_path = os.path.join(temp_dir, file.filename)
            
            # 保存文件到临时目录
            async with aiofiles.open(temp_file_path, 'wb') as out_file:
                content = await file.read()
                await out_file.write(content)

            # 验证ZIP文件
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
            object_name = f"uploads/zips/{timestamp}_{file.filename}"

            # 上传到OSS
            file_url = await oss_client.upload_file(temp_file_path, object_name)

            return UploadResponse(
                file_url=file_url,
                file_name=file.filename,
                file_size=file_size,
                created_at=datetime.now()
            )

    except Exception as e:
        logger.error(f"Error uploading ZIP file: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error uploading ZIP file: {str(e)}"
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
            urgent=request.urgent
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