import oss2
from app.config.settings import OSS_CONFIG
import logging
from typing import Optional
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# 创建 OSS 认证对象
auth = oss2.Auth(
    OSS_CONFIG['access_key_id'],
    OSS_CONFIG['access_key_secret']
)

# 创建 Bucket 实例
bucket = oss2.Bucket(
    auth,
    OSS_CONFIG['endpoint'],
    OSS_CONFIG['bucket_name']
)

class OSSClient:
    def __init__(self):
        self.bucket = bucket

    async def upload_file(self, file_path: str, oss_path: str) -> str:
        """
        上传文件到 OSS
        
        Args:
            file_path: 本地文件路径
            oss_path: OSS 上的文件路径
            
        Returns:
            str: 文件的 OSS URL
        """
        try:
            # 上传文件
            self.bucket.put_object_from_file(oss_path, file_path)
            
            # 生成文件 URL
            url = f"https://{OSS_CONFIG['bucket_name']}.{OSS_CONFIG['endpoint']}/{oss_path}"
            logger.info(f"File uploaded successfully: {url}")
            return url
            
        except Exception as e:
            logger.error(f"Failed to upload file to OSS: {str(e)}")
            raise

    async def delete_file(self, object_name: str) -> bool:
        """
        从OSS删除文件
        
        Args:
            object_name: OSS对象名称
        
        Returns:
            bool: 是否删除成功
        """
        try:
            self.bucket.delete_object(object_name)
            return True
        except Exception as e:
            logger.error(f"Error deleting file from OSS: {str(e)}")
            return False

    def is_configured(self) -> bool:
        """检查OSS客户端是否配置完整"""
        return all([
            OSS_CONFIG['access_key_id'],
            OSS_CONFIG['access_key_secret'],
            OSS_CONFIG['endpoint'],
            OSS_CONFIG['bucket_name']
        ])

# 创建全局 OSS 客户端实例
oss_client = OSSClient() 