import oss2
import os
import time
from pathlib import Path
from app.config.settings import (
    OSS_ACCESS_KEY_ID,
    OSS_ACCESS_KEY_SECRET,
    OSS_ENDPOINT,
    OSS_BUCKET_NAME
)

class OSSClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(OSSClient, cls).__new__(cls)
            cls._instance._init_oss()
        return cls._instance

    def _init_oss(self):
        """初始化OSS客户端"""
        if not all([OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET]):
            raise ValueError("OSS credentials not properly configured")
        
        # 创建Auth对象
        self.auth = oss2.Auth(OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET)
        # 创建Bucket对象
        self.bucket = oss2.Bucket(self.auth, OSS_ENDPOINT, OSS_BUCKET_NAME)

    def upload_file(self, local_file_path: str | Path, remote_directory: str = 'uploads') -> str:
        """
        上传文件到OSS
        :param local_file_path: 本地文件路径
        :param remote_directory: 远程目录名
        :return: 文件的URL
        """
        try:
            local_file_path = Path(local_file_path)
            if not local_file_path.exists():
                raise FileNotFoundError(f"File not found: {local_file_path}")

            # 生成唯一的文件名
            timestamp = int(time.time())
            remote_file_name = f"{remote_directory}/{timestamp}_{local_file_path.name}"

            # 上传文件
            with local_file_path.open('rb') as fileobj:
                self.bucket.put_object(remote_file_name, fileobj)

            # 生成文件URL
            return f"https://{OSS_BUCKET_NAME}.{OSS_ENDPOINT}/{remote_file_name}"

        except Exception as e:
            raise Exception(f"Failed to upload file to OSS: {str(e)}")

    def delete_file(self, remote_file_path: str) -> None:
        """
        删除OSS上的文件
        :param remote_file_path: 远程文件路径
        """
        try:
            self.bucket.delete_object(remote_file_path)
        except Exception as e:
            raise Exception(f"Failed to delete file from OSS: {str(e)}")

# 创建全局OSS客户端实例
oss_client = OSSClient() 