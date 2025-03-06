from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import logging
from app.core.image_processor import process_images
from app.utils.oss_client import oss_client
from pathlib import Path
import os

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由
router = APIRouter()

class ProcessRequest(BaseModel):
    zip_url: str
    dimensions_text: str

class ProcessResponse(BaseModel):
    status: str
    message: str
    output_url: str

@router.post("/process", response_model=ProcessResponse)
async def process_images_endpoint(request: ProcessRequest):
    """
    处理图片API端点
    """
    try:
        # 处理图片
        output_zip = process_images(request.zip_url, request.dimensions_text)
        
        if not os.path.exists(output_zip):
            raise HTTPException(
                status_code=500,
                detail="Failed to generate processed images zip file"
            )

        try:
            # 上传到OSS
            output_url = oss_client.upload_file(output_zip)
            
            # 删除本地文件
            os.remove(output_zip)
            
            return ProcessResponse(
                status="success",
                message="Images processed and uploaded successfully",
                output_url=output_url
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload to OSS: {str(e)}"
            )
            
    except Exception as e:
        logger.error(f"Error in process_images_endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "oss_configured": oss_client is not None
    }