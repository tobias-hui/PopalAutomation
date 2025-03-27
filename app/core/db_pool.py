import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
import yaml
from pathlib import Path
import logging
import time
from typing import Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class DatabasePoolManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabasePoolManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._initialized = True
        self.config = self._load_config()
        self.engine = None
        self.SessionLocal = None
        self.setup_engine()
        
    def _load_config(self) -> dict:
        """加载数据库配置"""
        config_path = Path(__file__).parent.parent / 'config' / 'database.yml'
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load database config: {e}")
            # 使用默认配置
            return {
                'pool': {
                    'pool_size': 20,
                    'max_overflow': 10,
                    'pool_timeout': 30,
                    'pool_recycle': 3600,
                    'pool_pre_ping': True,
                    'retry_count': 3,
                    'retry_interval': 1
                }
            }
    
    def setup_engine(self):
        """设置数据库引擎"""
        pool_config = self.config.get('pool', {})
        
        # 从环境变量获取数据库URL
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL environment variable is not set")
        
        # 创建引擎，使用基本配置
        self.engine = create_engine(
            database_url,
            poolclass=QueuePool,
            pool_size=pool_config.get('pool_size', 20),
            max_overflow=pool_config.get('max_overflow', 10),
            pool_timeout=pool_config.get('pool_timeout', 30),
            pool_recycle=pool_config.get('pool_recycle', 3600),
            pool_pre_ping=pool_config.get('pool_pre_ping', True)
        )
        
        # 创建会话工厂
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
    
    @contextmanager
    def get_db(self):
        """获取数据库会话的上下文管理器"""
        retry_count = self.config['pool']['retry_count']
        retry_interval = self.config['pool']['retry_interval']
        
        for attempt in range(retry_count):
            try:
                db = self.SessionLocal()
                try:
                    yield db
                finally:
                    db.close()
                break
            except Exception as e:
                logger.error(f"Database connection error (attempt {attempt + 1}/{retry_count}): {e}")
                if attempt < retry_count - 1:
                    time.sleep(retry_interval)
                else:
                    raise
    
    def check_health(self) -> bool:
        """检查数据库连接健康状态"""
        try:
            with self.get_db() as db:
                db.execute(text("SELECT 1"))
                db.commit()
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    def dispose(self):
        """释放所有连接"""
        if self.engine:
            self.engine.dispose()
            
# 创建全局实例
db_pool = DatabasePoolManager() 