"""毕业预审兼容投影的 ORM / 迁移容量合同。"""
from sqlalchemy import Text


def test_legacy_graduation_projection_uses_text_metadata():
    """FAST_TEST_SCHEMA/create_all 不得把完整证据 JSON 重新降回 VARCHAR(4000)。"""
    from app.models import AaGraduationAuditResult

    column_type = AaGraduationAuditResult.__table__.c.item_results_json.type
    assert isinstance(column_type, Text)
