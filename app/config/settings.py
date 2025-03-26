import os
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, Tuple

# 加载环境变量
load_dotenv()

# 基础路径配置
BASE_DIR = Path(__file__).parent.parent
TEMP_DIR = BASE_DIR / "temp"
OUTPUT_DIR = BASE_DIR / "output"
ASSETS_DIR = BASE_DIR / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"

# OSS配置
OSS_CONFIG = {
    'bucket_name': os.getenv('OSS_BUCKET_NAME', 'your-bucket-name'),
    'endpoint': os.getenv('OSS_ENDPOINT', 'your-endpoint'),
    'access_key_id': os.getenv('OSS_ACCESS_KEY_ID', 'your-access-key-id'),
    'access_key_secret': os.getenv('OSS_ACCESS_KEY_SECRET', 'your-access-key-secret')
}

# API配置
API_VERSION = "1.0.0"
API_TITLE = "Image Processing API"
API_DESCRIPTION = "API for processing product images with dimensions"

# 文件处理配置
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_EXTENSIONS = {'.zip', '.txt'}

# 画布配置
CANVAS_SIZE: Tuple[int, int] = (1000, 1000)
DEFAULT_DRAW_AREA: Dict[str, int] = {
    'x': 100,
    'y': 100,
    'width': 800,
    'height': 800
}

# 日志配置
LOG_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
    },
    'handlers': {
        'default': {
            'level': 'INFO',
            'formatter': 'standard',
            'class': 'logging.StreamHandler',
        },
        'file': {
            'level': 'INFO',
            'formatter': 'standard',
            'class': 'logging.FileHandler',
            'filename': 'app.log',
            'mode': 'a',
        },
    },
    'loggers': {
        '': {  # root logger
            'handlers': ['default', 'file'],
            'level': 'INFO',
            'propagate': True
        }
    }
}

# 任务状态配置
TASK_STATUS = {
    'PENDING': 'pending',
    'PROCESSING': 'processing',
    'COMPLETED': 'completed',
    'FAILED': 'failed'
}

# 错误消息配置
ERROR_MESSAGES = {
    'INVALID_DIMENSIONS': 'Invalid dimensions provided',
    'PROCESSING_FAILED': 'Image processing failed',
    'UPLOAD_FAILED': 'Failed to upload file to OSS',
    'FILE_NOT_FOUND': 'Required file not found',
    'INVALID_FILE_TYPE': 'Invalid file type',
    'ZIP_CORRUPTED': 'Generated ZIP file is corrupted',
    'ZIP_EMPTY': 'Generated ZIP file is empty'
} 