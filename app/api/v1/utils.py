from fastapi import HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
import logging
import httpx
from io import BytesIO
from pathlib import Path
import zipfile
from tempfile import TemporaryDirectory
from PIL import Image
import os

from app.models.task_models import Task, TaskStatus
from app.core.image_processor import (
    CarouselImageProcessor, 
    DimensionProcessor,
)
from app.core.product_info_processor import ProductInfoProcessor
from app.core.compliance_label_processor import ComplianceLabelProcessor, BricksComplianceLabelProcessor
from app.models.image_models import (
    DimensionImageRequest,
    ProductInfoRequest,
    ComplianceLabelRequest,
    BricksComplianceLabelRequest
)
from app.utils.oss_client import oss_client

# 配置日志
logger = logging.getLogger(__name__)

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

async def process_carousel_background_task(
    task_id: str,
    zip_url: str,
    dimensions_text: str,
    title: str,
    pcs: int,
    db: Session
):
    """后台处理轮播图任务"""
    try:
        # 更新任务状态为处理中
        task = db.query(Task).filter(Task.task_id == task_id).first()
        if task:
            task.status = TaskStatus.PROCESSING
            task.message = "开始处理轮播图"
            db.commit()
        
        # 下载ZIP文件
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(str(zip_url))
                if response.status_code != 200:
                    error_msg = f"下载ZIP文件失败: HTTP {response.status_code}"
                    logger.error(error_msg)
                    raise HTTPException(status_code=response.status_code, detail=error_msg)
                zip_data = BytesIO(response.content)
        except httpx.RequestError as e:
            error_msg = f"下载ZIP文件时发生网络错误: {str(e)}"
            logger.error(error_msg)
            raise HTTPException(status_code=500, detail=error_msg)
        except Exception as e:
            error_msg = f"下载ZIP文件时发生未知错误: {str(e)}"
            logger.error(error_msg)
            raise HTTPException(status_code=500, detail=error_msg)
        
        # 初始化处理器并处理
        try:
            processor = CarouselImageProcessor(dimensions_text=dimensions_text)
            dimensions = processor.dimensions
            with TemporaryDirectory() as temp_dir:
                temp_dir = Path(temp_dir)
                temp_zip = temp_dir / "input.zip"
                temp_zip.write_bytes(zip_data.getvalue())
                with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
                product_image_path = str(temp_dir / 'media' / 'image' / 'transparent_bg_images' / '1.png')
                product_info = {
                    'title': title,
                    'pcs': pcs,
                    'height_cm': dimensions.get('height', 0),
                    'length_cm': dimensions.get('length', 0),
                    'product_image_path': 'media/image/transparent_bg_images/1.png'
                }
                result = await processor.process_info_zip(zip_data, product_info)
                
                if not result or not isinstance(result, dict):
                    raise ValueError("处理结果无效")
                
                if task:
                    task.status = TaskStatus.COMPLETED
                    task.message = "轮播图处理完成"
                    task.additional_data = {
                        "output_url": result.get("output_url"),
                        "info_url": result.get("info_url"),
                        "rotating_video_url": result.get("rotating_video_url"),
                        "falling_bricks_video_url": result.get("falling_bricks_video_url"),
                        "dimensions": dimensions,
                        "product_info": {
                            "title": title,
                            "pcs": pcs,
                            "height_cm": dimensions.get('height', 0),
                            "length_cm": dimensions.get('length', 0)
                        }
                    }
                    db.commit()
                
                return result
                
        except ValueError as e:
            error_msg = f"处理结果验证失败: {str(e)}"
            logger.error(error_msg)
            raise HTTPException(status_code=400, detail=error_msg)
        except HTTPException as e:
            logger.error(f"处理轮播图任务 {task_id} 时发生HTTP错误: {str(e)}")
            if task:
                task.status = TaskStatus.FAILED
                task.message = f"处理失败: {str(e.detail)}"
                task.error = str(e.detail)
                db.commit()
            raise e
        except Exception as e:
            error_msg = f"处理ZIP文件失败: {str(e)}"
            logger.error(error_msg)
            if task:
                task.status = TaskStatus.FAILED
                task.message = f"处理失败: {str(e)}"
                task.error = str(e)
                db.commit()
            raise HTTPException(status_code=500, detail=error_msg)
    except Exception as e:
        logger.error(f"处理轮播图任务 {task_id} 时发生未知错误: {str(e)}")
        if task:
            task.status = TaskStatus.FAILED
            task.message = f"处理失败: {str(e)}"
            task.error = str(e)
            db.commit()
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
        await update_task_status(db, task_id, TaskStatus.FAILED, error=error_msg)
        raise HTTPException(status_code=400, detail=error_msg)
    except HTTPException as e:
        error_msg = str(e.detail)
        logger.error(f"HTTP error processing dimension image: {error_msg}")
        await update_task_status(db, task_id, TaskStatus.FAILED, error=error_msg)
        raise e
    except Exception as e:
        error_msg = f"Unexpected error processing dimension image: {str(e)}"
        logger.error(error_msg)
        await update_task_status(db, task_id, TaskStatus.FAILED, error=error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

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

async def process_compliance_label_background(task_id: str, request: ComplianceLabelRequest, db: Session):
    """后台处理合规标签"""
    try:
        # 更新任务状态为处理中
        await update_task_status(db, task_id, TaskStatus.PROCESSING)
        
        # 创建处理器实例
        processor = ComplianceLabelProcessor(
            batch_code=request.batch_code,
            barcode_url=request.barcode_url
        )
        
        # 处理图片
        try:
            processed_image = processor.process_image()
            
            # 创建临时目录保存处理后的图片
            with TemporaryDirectory() as temp_dir:
                temp_dir = Path(temp_dir)
                output_path = temp_dir / f"processed_{task_id}.png"
                
                # 保存处理后的图片
                processed_image.save(output_path, "PNG")
                
                # 生成OSS对象名称
                oss_filename = f"processed_images/compliance_label_{task_id}.png"
                
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
            logger.error(f"Validation error processing compliance label: {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)
        except Exception as e:
            error_msg = f"Error processing compliance label: {str(e)}"
            logger.error(error_msg)
            raise HTTPException(status_code=500, detail=error_msg)
            
    except HTTPException as e:
        error_msg = str(e.detail)
        logger.error(f"HTTP error processing compliance label: {error_msg}")
        await update_task_status(db, task_id, TaskStatus.FAILED, error=error_msg)
        raise e
    except Exception as e:
        error_msg = f"Unexpected error processing compliance label: {str(e)}"
        logger.error(error_msg)
        await update_task_status(db, task_id, TaskStatus.FAILED, error=error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

async def process_bricks_compliance_label_background(
    task_id: str,
    request: BricksComplianceLabelRequest,
    db: Session
):
    """后台处理积木合规标签"""
    try:
        # 更新任务状态为处理中
        await update_task_status(db, task_id, TaskStatus.PROCESSING)
        
        # 创建处理器实例
        processor = BricksComplianceLabelProcessor(
            batch_code=request.batch_code,
            model=request.model,
            barcode_url=request.barcode_url
        )
        
        # 处理图片
        try:
            processed_image = processor.process_image()
            
            # 创建临时目录保存处理后的图片
            with TemporaryDirectory() as temp_dir:
                temp_dir = Path(temp_dir)
                output_path = temp_dir / f"processed_{task_id}.png"
                
                # 保存处理后的图片
                processed_image.save(output_path, "PNG")
                
                # 生成OSS对象名称
                oss_filename = f"processed_images/bricks_compliance_label_{task_id}.png"
                
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
            logger.error(f"Validation error processing bricks compliance label: {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)
        except Exception as e:
            error_msg = f"Error processing bricks compliance label: {str(e)}"
            logger.error(error_msg)
            raise HTTPException(status_code=500, detail=error_msg)
            
    except HTTPException as e:
        error_msg = str(e.detail)
        logger.error(f"HTTP error processing bricks compliance label: {error_msg}")
        await update_task_status(db, task_id, TaskStatus.FAILED, error=error_msg)
        raise e
    except Exception as e:
        error_msg = f"Unexpected error processing bricks compliance label: {str(e)}"
        logger.error(error_msg)
        await update_task_status(db, task_id, TaskStatus.FAILED, error=error_msg)
        raise HTTPException(status_code=500, detail=error_msg)