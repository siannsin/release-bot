"""Create ChatSettings table

Revision ID: 7f96fae84d5f
Revises: 
Create Date: 2024-09-25 17:48:10.951594

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7f96fae84d5f'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('chat_settings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('lang', sa.String(length=2), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('chat_settings')
    # ### end Alembic commands ###
