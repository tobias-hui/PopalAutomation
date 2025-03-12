import oss2
import logging
from typing import Optional
import os
from pathlib import Path
from app.config.settings import (
    OSS_ACCESS_KEY_ID,
    OSS_ACCESS_KEY_SECRET,
    OSS_ENDPOINT,
    OSS_BUCKET_NAME
)

logger = logging.getLogger(__name__)

class OSSClient:
    def __init__(self):
        # 从环境变量获取配置
        self.access_key_id = os.getenv('OSS_ACCESS_KEY_ID')
        self.access_key_secret = os.getenv('OSS_ACCESS_KEY_SECRET')
        self.endpoint = os.getenv('OSS_ENDPOINT')
        self.bucket_name = os.getenv('OSS_BUCKET_NAME')
        self.base_url = os.getenv('OSS_BASE_URL')

        if not all([self.access_key_id, self.access_key_secret, self.endpoint, self.bucket_name]):
            logger.warning("OSS configuration incomplete")
            return

        # 初始化OSS客户端
        self.auth = oss2.Auth(self.access_key_id, self.access_key_secret)
        self.bucket = oss2.Bucket(self.auth, self.endpoint, self.bucket_name)

    async def upload_file(self, file_path: str, object_name: Optional[str] = None) -> str:
        """
        上传文件到OSS
        
        Args:
            file_path: 本地文件路径
            object_name: OSS对象名称（可选）
        
        Returns:
            str: 文件访问URL
        """
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")

            # 如果没有指定对象名称，使用文件名
            if object_name is None:
                object_name = os.path.basename(file_path)

            # 上传文件
            self.bucket.put_object_from_file(object_name, file_path)

            # 返回文件URL
            if self.base_url:
                return f"{self.base_url.rstrip('/')}/{object_name}"
            else:
                return f"https://{self.bucket_name}.{self.endpoint}/{object_name}"

        except Exception as e:
            logger.error(f"Error uploading file to OSS: {str(e)}")
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
            self.access_key_id,
            self.access_key_secret,
            self.endpoint,
            self.bucket_name
        ])

# 创建全局OSS客户端实例
oss_client = OSSClient() 