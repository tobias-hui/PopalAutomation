"""add additional_data to tasks

Revision ID: add_additional_data_to_tasks
Revises: add_updated_at_to_tasks
Create Date: 2024-03-26 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

# revision identifiers, used by Alembic.
revision = 'add_additional_data_to_tasks'
down_revision = 'add_updated_at_to_tasks'
branch_labels = None
depends_on = None

def upgrade():
    # Add additional_data column to tasks table
    op.add_column('tasks', sa.Column('additional_data', JSON, nullable=True))

def downgrade():
    # Remove additional_data column from tasks table
    op.drop_column('tasks', 'additional_data') 