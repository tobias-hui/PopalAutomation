from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional
import logging
from datetime import datetime
import time
import os
from tempfile import TemporaryDirectory
import aiofiles
from zipfile import ZipFile, BadZipFile

from app.utils.oss_client import oss_client
from app.models.image_models import UploadResponse

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由
router = APIRouter(prefix="/upload", tags=["Upload"])

@router.post("/image", response_model=UploadResponse)
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
                status="success",
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

@router.post("", response_model=UploadResponse)
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
                status="success",
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