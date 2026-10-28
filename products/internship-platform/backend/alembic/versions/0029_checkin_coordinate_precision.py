"""Widen coordinates without changing existing evidence or fence decisions.

MySQL FLOAT text-protocol readback can shift a longitude by metres. Use DOUBLE
for future inputs and faithful readback. Old stored values are preserved exactly;
lost precision in historical inputs cannot be reconstructed by this migration.
"""
from alembic import op
import sqlalchemy as sa

revision = 'ix0029'
down_revision = 'ix0028'
branch_labels = None
depends_on = None


def upgrade():
    for table, column, comment in (
        ('t_internship_checkin', 'lat', None),
        ('t_internship_checkin', 'lng', None),
        ('t_internship_position', 'geofence_lat', '岗位围栏中心纬度'),
        ('t_internship_position', 'geofence_lng', '岗位围栏中心经度'),
    ):
        op.alter_column(table, column, type_=sa.Double(), existing_type=sa.Float(),
                        existing_nullable=True, existing_comment=comment)


def downgrade():
    raise RuntimeError('Narrowing stored location evidence can lose precision; retain data and roll forward')
