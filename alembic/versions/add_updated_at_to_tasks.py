"""add updated_at to tasks

Revision ID: add_updated_at_to_tasks
Revises: 
Create Date: 2024-03-26 09:55:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision = 'add_updated_at_to_tasks'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # 添加 updated_at 列
    op.add_column('tasks', sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')))
    
    # 更新现有记录的 updated_at 为 created_at 的值
    op.execute("UPDATE tasks SET updated_at = created_at WHERE updated_at IS NULL")

def downgrade():
    # 删除 updated_at 列
    op.drop_column('tasks', 'updated_at') 