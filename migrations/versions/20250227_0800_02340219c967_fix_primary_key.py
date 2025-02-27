"""fix primary key

Revision ID: 02340219c967
Revises: 045ee516f619
Create Date: 2025-02-27 08:00:11.473244+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '02340219c967'
down_revision = '045ee516f619'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Drop existing primary key constraint
    op.execute('ALTER TABLE images DROP CONSTRAINT images_pkey')
    
    # 2. Make analysis_id nullable and remove primary key
    op.alter_column('images', 'analysis_id',
                    existing_type=sa.String(),
                    nullable=True)
    
    # 3. Add new primary key on id column
    op.create_primary_key('images_pkey', 'images', ['id'])

def downgrade() -> None:
    # 1. Drop new primary key
    op.execute('ALTER TABLE images DROP CONSTRAINT images_pkey')
    
    # 2. Make analysis_id not nullable
    op.alter_column('images', 'analysis_id',
                    existing_type=sa.String(),
                    nullable=False)
    
    # 3. Restore original primary key
    op.create_primary_key('images_pkey', 'images', ['analysis_id']) 