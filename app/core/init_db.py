from app.core.database import engine, Base
from app.models.task_models import Task

def init_db():
    """初始化数据库表"""
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    init_db() 