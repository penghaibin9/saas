"""D4-U 培养方案治理摘要批量查询合同。"""
from contextlib import contextmanager
from types import SimpleNamespace


class _SourceQuery:
    def __init__(self, db, models):
        self.db = db
        self.models = models

    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def join(self, *_args, **_kwargs):
        return self

    def all(self):
        from app.models import AaProgram

        if len(self.models) == 1 and self.models[0] is AaProgram:
            return list(self.db.programs)
        return []


class _SourceDb:
    def __init__(self, program_count: int):
        self.query_calls = 0
        self.programs = [
            SimpleNamespace(
                id=index,
                tenant_id=1,
                is_deleted=False,
                program_name=f"软件技术{2025 + index}级",
                major_id=10,
                grade_year=str(2025 + index),
                version=1,
                status="DRAFT",
                total_credits=100,
            )
            for index in range(1, program_count + 1)
        ]

    def query(self, *models):
        self.query_calls += 1
        return _SourceQuery(self, models)


def _run_summary(monkeypatch, program_count: int):
    from app.modules.academic_affairs.services import academic_affairs_program_governance_summary_service as service

    db = _SourceDb(program_count)
    canonical_calls = []

    @contextmanager
    def _session():
        yield db

    def _canonical(snapshot_db, program_id):
        canonical_calls.append((snapshot_db, program_id))
        assert isinstance(snapshot_db, service._ValidationSnapshotDb)
        return {
            "creditSum": 100.0,
            "courseCount": 20,
            "counts": {"blocker": 0, "warning": 0, "info": 0},
            "canSubmit": True,
            "conclusion": "校验通过，可提交审核",
        }

    monkeypatch.setattr(service, "session", _session)
    monkeypatch.setattr(service, "_tid", lambda: 1)
    monkeypatch.setattr(service.governance, "_scope", lambda _user, _db: SimpleNamespace(scope_type="TENANT_ALL"))
    monkeypatch.setattr(service.governance, "_allowed_major_ids", lambda _db, _scope: set())
    monkeypatch.setattr(service.governance, "validate_program_db", _canonical)

    result = service.program_governance_summary(SimpleNamespace())
    return db.query_calls, canonical_calls, result


def test_governance_summary_source_query_count_does_not_scale_with_program_count(monkeypatch):
    one_queries, one_calls, one_result = _run_summary(monkeypatch, 1)
    many_queries, many_calls, many_result = _run_summary(monkeypatch, 50)

    assert one_queries == many_queries
    assert len(one_calls) == 1
    assert len(many_calls) == 50
    assert one_result["totalPrograms"] == 1
    assert many_result["totalPrograms"] == 50
    assert many_result["readyPrograms"] == 50


def test_validation_snapshot_filters_class_and_cross_program_conflicts():
    from app.models import AaProgram, AaProgramBinding, SchoolClass
    from app.modules.academic_affairs.services import academic_affairs_program_governance_summary_service as service

    current = SimpleNamespace(id=1)
    other_a = SimpleNamespace(id=2, program_name="方案A")
    other_b = SimpleNamespace(id=3, program_name="方案B")
    same_key = SimpleNamespace(id=21, program_id=2, major_id=10, grade_year="2026", class_id=None)
    other_key = SimpleNamespace(id=22, program_id=3, major_id=11, grade_year="2026", class_id=None)
    own_key = SimpleNamespace(id=23, program_id=1, major_id=10, grade_year="2026", class_id=None)
    classes = [SimpleNamespace(id=7), SimpleNamespace(id=9)]

    snapshot = service._ValidationSnapshotDb(
        program=current,
        courses=[],
        requirements=[],
        practices=[],
        bindings=[],
        catalog_rows=[],
        enabled_codes=set(),
        standard_bound=False,
        classes=classes,
        conflict_pairs=[(same_key, other_a), (other_key, other_b), (own_key, current)],
    )

    selected_class = snapshot.query(SchoolClass).filter(SchoolClass.id == 9).first()
    assert selected_class.id == 9

    conflicts = snapshot.query(AaProgramBinding, AaProgram).join(
        AaProgram, AaProgram.id == AaProgramBinding.program_id,
    ).filter(
        AaProgramBinding.program_id != 1,
        AaProgramBinding.major_id == 10,
        AaProgramBinding.grade_year == "2026",
        AaProgramBinding.class_id.is_(None),
        AaProgramBinding.status == "ACTIVE",
        AaProgram.status.in_(["ENABLED", "FROZEN", "PUBLISHED"]),
    ).all()
    assert conflicts == [(same_key, other_a)]


def test_program_quality_router_keeps_contract_and_switches_only_summary_reader():
    from app.modules.academic_affairs.routers import program_quality_router as router_module
    from app.modules.academic_affairs.services import academic_affairs_program_governance_summary_service as service

    paths = {route.path for route in router_module.router.routes}
    assert "/academic-affairs/programs/{program_id}/validation" in paths
    assert "/academic-affairs/program-governance/summary" in paths
    assert "/academic-affairs/opening-plan/differences" in paths
    assert router_module.summary_svc.program_governance_summary is service.program_governance_summary
