"""Register candidate tables for metadata drift checks; no import-time connection/DDL."""
from app.models.base import Base
from app.modules.academic_affairs.optimizer.schema import metadata as optimizer_metadata

for table in optimizer_metadata.sorted_tables:
    if table.name not in Base.metadata.tables:
        table.to_metadata(Base.metadata)
