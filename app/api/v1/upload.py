from fastapi import APIRouter, HTTPException, UploadFile, File
import logging
from datetime import datetime
import time
import os
from tempfile import TemporaryDirectory
import aiofiles
from pathlib import Path

from app.utils.oss_client import oss_client
from app.models.image_models import UploadResponse

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由
router = APIRouter(prefix="/upload", tags=["Upload"])

# 上传限制配置
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
MAX_FILENAME_LENGTH = 255
DANGEROUS_EXTENSIONS = {
    '.exe', '.bat', '.cmd', '.sh', '.php', '.py', '.js', '.jar', '.dll',
    '.so', '.dylib', '.bin', '.msi', '.app', '.apk', '.ipa'
}

def validate_file(file: UploadFile) -> None:
    """验证上传文件的有效性"""
    # 检查文件大小
    if file.size and file.size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File size exceeds the limit of {MAX_FILE_SIZE / (1024*1024)}MB"
        )
    
    # 检查文件名长度
    if len(file.filename) > MAX_FILENAME_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Filename length exceeds the limit of {MAX_FILENAME_LENGTH} characters"
        )
    
    # 检查文件扩展名
    file_ext = Path(file.filename).suffix.lower()
    if file_ext in DANGEROUS_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Uploading this type of file is not allowed for security reasons"
        )

@router.post("", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)):
    """
    统一的文件上传接口
    
    参数:
    - file: 要上传的文件
    
    返回:
    - status: 上传状态
    - file_url: 文件访问URL
    - file_name: 文件名
    - file_size: 文件大小
    - created_at: 创建时间
    """
    try:
        # 验证文件
        validate_file(file)
        
        # 创建临时目录
        with TemporaryDirectory() as temp_dir:
            temp_file_path = os.path.join(temp_dir, file.filename)
            
            # 保存文件到临时目录
            async with aiofiles.open(temp_file_path, 'wb') as out_file:
                content = await file.read()
                await out_file.write(content)

            # 获取文件大小
            file_size = os.path.getsize(temp_file_path)
            
            # 再次验证文件大小（防止内存中的文件大小与实际不符）
            if file_size > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=400,
                    detail=f"File size exceeds the limit of {MAX_FILE_SIZE / (1024*1024)}MB"
                )

            # 生成唯一的对象名称
            timestamp = int(time.time())
            object_name = f"uploads/{timestamp}_{file.filename}"

            # 上传到OSS
            file_url = await oss_client.upload_file(temp_file_path, object_name)

            return UploadResponse(
                status="success",
                file_url=file_url,
                file_name=file.filename,
                file_size=file_size,
                created_at=datetime.now()
            )

    except HTTPException as e:
        # 重新抛出已知的HTTP异常
        raise e
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error uploading file: {str(e)}"
        ) 