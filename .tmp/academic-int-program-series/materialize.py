from __future__ import annotations

from pathlib import Path
import subprocess

BASE = "4d971781a9d0d1728cc7ab01daefb25de95fd23a"
FROZEN_A = "edca0064aec6a2bd34ed96261c23f1596dcceee0"
RED_CONTRACT = "cc560ca6719a56cb3125afaa4deeaf18140db9bd"


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"exact replacement guard failed for {path}: count={count}\nanchor={old[:180]!r}")
    write(path, text.replace(old, new, 1))


def show(commit: str, path: str) -> str:
    return subprocess.check_output(["git", "show", f"{commit}:{path}"], text=True)


if git("rev-parse", "HEAD^") != BASE:
    raise SystemExit(f"bootstrap parent drifted: expected {BASE}, got {git('rev-parse', 'HEAD^')}")
for commit in (BASE, FROZEN_A, RED_CONTRACT):
    subprocess.check_call(["git", "cat-file", "-e", f"{commit}^{{commit}}"])

# 1) Stable Program identity belongs to the canonical shared model, not a runtime guess.
model = "backend/app/models/academic_affairs.py"
replace_once(
    model,
    '    requirement_json: Mapped[str | None] = mapped_column(String(2000), comment="分模块学分要求")\n    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)\n',
    '    requirement_json: Mapped[str | None] = mapped_column(String(2000), comment="分模块学分要求")\n'
    '    series_key: Mapped[str | None] = mapped_column(\n'
    '        String(64), nullable=True, index=True,\n'
    '        comment="Stable Program series identity; unresolved historical rows stay NULL",\n'
    '    )\n'
    '    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)\n',
)
replace_once(
    model,
    '    workflow_instance_id: Mapped[int | None] = mapped_column(BigInteger, index=True)\n\n\nclass AaProgramCourse',
    '    workflow_instance_id: Mapped[int | None] = mapped_column(BigInteger, index=True)\n\n'
    '    __table_args__ = (\n'
    '        UniqueConstraint("tenant_id", "series_key", "version", name="uk_aa_program_series_version"),\n'
    '    )\n\n\nclass AaProgramCourse',
)

# 2) Every newly authored v1 explicitly mints a new stable series key.
core = "backend/app/modules/academic_affairs/services/academic_affairs_program_core_service.py"
replace_once(core, "import json\nfrom datetime import datetime\n", "import json\nimport uuid\nfrom datetime import datetime\n")
replace_once(
    core,
    '\n\ndef create_program(body, user) -> dict:\n',
    '\n\ndef _new_program_series_key() -> str:\n'
    '    """Mint a stable identity only for a genuinely new Program root."""\n'
    '    return f"PRG-{uuid.uuid4().hex.upper()}"\n'
    '\n\ndef create_program(body, user) -> dict:\n',
)
replace_once(
    core,
    '        p = AaProgram(tenant_id=_tid(), program_name=body.programName,\n',
    '        p = AaProgram(tenant_id=_tid(), series_key=_new_program_series_key(), program_name=body.programName,\n',
)

# 3) Overlay the already-frozen A-W2 Authority/public facade; do not create a second Authority.
authority_path = "backend/app/modules/academic_affairs/services/academic_affairs_program_authority_service.py"
write(authority_path, show(FROZEN_A, authority_path))
replace_once(
    authority_path,
    '        if old.status not in _VERSIONABLE_STATUSES:\n            raise AppException("DATA_CONFLICT", "仅已发布/启用/冻结/停用方案可新建版本（编制/退回态直接编辑即可）")\n\n        successors = db.scalars(\n',
    '        if old.status not in _VERSIONABLE_STATUSES:\n            raise AppException("DATA_CONFLICT", "仅已发布/启用/冻结/停用方案可新建版本（编制/退回态直接编辑即可）")\n'
    '        if not str(getattr(old, "series_key", "") or "").strip():\n'
    '            raise AppException(\n'
    '                "PROGRAM_SERIES_UNRESOLVED",\n'
    '                "源培养方案缺少稳定 series_key，禁止创建后继版本；请先完成证据化系列修复",\n'
    '                details={"programId": str(old.id), "version": old.version},\n'
    '                http_status=409,\n'
    '            )\n\n'
    '        successors = db.scalars(\n',
)
replace_once(
    authority_path,
    '        new_program = AaProgram(\n            tenant_id=_tid(),\n            program_name=old.program_name,\n',
    '        new_program = AaProgram(\n            tenant_id=_tid(),\n            series_key=old.series_key,\n            program_name=old.program_name,\n',
)
replace_once(
    authority_path,
    '                module=course.module,\n                credit_snapshot=course.credit_snapshot,\n            ))\n',
    '                module=course.module,\n                credit_snapshot=course.credit_snapshot,\n                formation_mode=course.formation_mode,\n            ))\n',
)

service_path = "backend/app/modules/academic_affairs/services/academic_affairs_program_service.py"
write(service_path, show(FROZEN_A, service_path))

# 4) Expand-only shared DDL. Historical rows remain NULL; nullable unique key is safe on MySQL.
write(
    "backend/alembic/versions/20260817_academic_int_program_series.py",
    '''"""Add stable Program series identity after Academic/Control Plane convergence.\n\nRevision ID: 20260817_acad_int_program_series\nRevises: 20260817_acad_int_ctrl_merge\n\nHistorical Program rows deliberately remain NULL.  This migration never guesses\nseries identity and performs no semantic backfill.\n"""\nfrom __future__ import annotations\n\nfrom alembic import op\nimport sqlalchemy as sa\n\nrevision = "20260817_acad_int_program_series"\ndown_revision = "20260817_acad_int_ctrl_merge"\nbranch_labels = None\ndepends_on = None\n\n\ndef upgrade() -> None:\n    op.add_column(\n        "t_aa_program",\n        sa.Column(\n            "series_key",\n            sa.String(length=64),\n            nullable=True,\n            comment="Stable Program series identity; unresolved historical rows stay NULL",\n        ),\n    )\n    op.create_unique_constraint(\n        "uk_aa_program_series_version",\n        "t_aa_program",\n        ["tenant_id", "series_key", "version"],\n    )\n\n\ndef downgrade() -> None:\n    op.drop_constraint("uk_aa_program_series_version", "t_aa_program", type_="unique")\n    op.drop_column("t_aa_program", "series_key")\n''',
)

# 5) Preserve the already-frozen RED source contract and add a real MySQL writer/DDL gate.
red_path = "backend/tests/test_academic_int_program_series_schema_red.py"
write(red_path, show(RED_CONTRACT, red_path))

write(
    "backend/tests/test_academic_int_program_series_mysql.py",
    '''"""Focused MySQL acceptance for INT Program stable-series writer semantics."""\nfrom __future__ import annotations\n\nfrom types import SimpleNamespace\nimport uuid\n\nimport pytest\nfrom sqlalchemy import select\nfrom sqlalchemy.exc import IntegrityError\n\nTID = 1000000000000000001\n\n\ndef _patch_tenant(monkeypatch):\n    from app.modules.academic_affairs.services import academic_affairs_program_authority_service as authority\n    from app.modules.academic_affairs.services import academic_affairs_program_core_service as core\n\n    monkeypatch.setattr(authority, "_tid", lambda: TID)\n    monkeypatch.setattr(core, "_tid", lambda: TID)\n    return core, authority\n\n\n@pytest.mark.usefixtures("db_mode")\ndef test_root_mints_prg_series_and_successor_inherits_locked_source(monkeypatch):\n    from app.db.session import get_sessionmaker\n    from app.models import AaProgram, AaProgramCourse\n\n    core, authority = _patch_tenant(monkeypatch)\n    body = SimpleNamespace(\n        programName=f"INT稳定系列-{uuid.uuid4().hex[:8]}",\n        majorId=None,\n        gradeYear="2026",\n        totalCredits=3,\n        requirement={},\n    )\n    root_result = core.create_program(body, None)\n    root_id = int(root_result["programId"])\n\n    db = get_sessionmaker()()\n    root = db.get(AaProgram, root_id)\n    assert root.series_key and root.series_key.startswith("PRG-")\n    assert len(root.series_key) <= 64\n    root_series = root.series_key\n    root.status = "PUBLISHED"\n    db.add(AaProgramCourse(\n        tenant_id=TID,\n        program_id=root.id,\n        course_id=930001,\n        course_name="INT稳定系列课程",\n        open_term_no=1,\n        module="MAJOR_CORE",\n        credit_snapshot=3,\n        formation_mode="ADMIN_FIXED",\n    ))\n    db.commit()\n    db.close()\n\n    created = authority.create_new_version(root_id, None)\n    successor_id = int(created["programId"])\n\n    db = get_sessionmaker()()\n    successor = db.get(AaProgram, successor_id)\n    courses = db.scalars(select(AaProgramCourse).where(\n        AaProgramCourse.tenant_id == TID,\n        AaProgramCourse.program_id == successor_id,\n        AaProgramCourse.is_deleted.is_(False),\n    )).all()\n    assert successor.prev_version_id == root_id\n    assert successor.version == 2\n    assert successor.series_key == root_series\n    assert len(courses) == 1\n    assert courses[0].formation_mode == "ADMIN_FIXED"\n    db.close()\n\n\n@pytest.mark.usefixtures("db_mode")\ndef test_unresolved_legacy_source_fails_closed_without_creating_successor(monkeypatch):\n    from app.core.exceptions import AppException\n    from app.db.session import get_sessionmaker\n    from app.models import AaProgram\n\n    _core, authority = _patch_tenant(monkeypatch)\n    db = get_sessionmaker()()\n    source = AaProgram(\n        tenant_id=TID,\n        series_key=None,\n        program_name=f"INT旧脏系列-{uuid.uuid4().hex[:8]}",\n        major_id=None,\n        grade_year="2025",\n        version=3,\n        status="PUBLISHED",\n    )\n    db.add(source)\n    db.commit()\n    source_id = int(source.id)\n    db.close()\n\n    with pytest.raises(AppException) as raised:\n        authority.create_new_version(source_id, None)\n    assert getattr(raised.value, "code", None) == "PROGRAM_SERIES_UNRESOLVED"\n\n    db = get_sessionmaker()()\n    successors = db.scalars(select(AaProgram).where(\n        AaProgram.tenant_id == TID,\n        AaProgram.prev_version_id == source_id,\n        AaProgram.is_deleted.is_(False),\n    )).all()\n    assert successors == []\n    db.close()\n\n\n@pytest.mark.usefixtures("db_mode")\ndef test_mysql_unique_series_version_rejects_duplicate_non_null_identity(monkeypatch):\n    from app.db.session import get_sessionmaker\n    from app.models import AaProgram\n\n    _patch_tenant(monkeypatch)\n    series = f"PRG-TEST-{uuid.uuid4().hex.upper()}"\n    db = get_sessionmaker()()\n    db.add(AaProgram(\n        tenant_id=TID, series_key=series, program_name="INT唯一系列A",\n        version=9, status="DRAFT",\n    ))\n    db.commit()\n    db.add(AaProgram(\n        tenant_id=TID, series_key=series, program_name="INT唯一系列B",\n        version=9, status="DRAFT",\n    ))\n    with pytest.raises(IntegrityError):\n        db.commit()\n    db.rollback()\n    db.close()\n''',
)

# 6) Candidate-only targeted gate; never broad-run the frozen lines for this handoff.
write(
    ".github/workflows/academic-int-program-series-targeted.yml",
    '''name: Academic INT Program Stable Series Targeted\n\non:\n  push:\n    branches:\n      - tmp/academic-int-program-series-green-20260817\n      - integration/academic-school-gold\n    paths:\n      - 'backend/alembic/versions/20260817_academic_int_program_series.py'\n      - 'backend/app/models/academic_affairs.py'\n      - 'backend/app/modules/academic_affairs/services/academic_affairs_program_core_service.py'\n      - 'backend/app/modules/academic_affairs/services/academic_affairs_program_authority_service.py'\n      - 'backend/app/modules/academic_affairs/services/academic_affairs_program_service.py'\n      - 'backend/tests/test_academic_int_program_series_schema_red.py'\n      - 'backend/tests/test_academic_int_program_series_mysql.py'\n      - '.github/workflows/academic-int-program-series-targeted.yml'\n\nconcurrency:\n  group: academic-int-program-series-${{ github.ref }}\n  cancel-in-progress: false\n\njobs:\n  program-stable-series:\n    name: Program stable-series exact-head MySQL gate\n    runs-on: ubuntu-24.04\n    timeout-minutes: 25\n    services:\n      mysql:\n        image: mysql:8.0\n        env:\n          MYSQL_ROOT_PASSWORD: root\n          MYSQL_DATABASE: student_lifecycle_test\n        ports:\n          - 3306:3306\n        options: >-\n          --health-cmd="mysqladmin ping -h 127.0.0.1 -uroot -proot --silent"\n          --health-interval=10s\n          --health-timeout=5s\n          --health-retries=15\n    env:\n      DB_ENABLED: 'true'\n      DB_DRIVER: mysql\n      DATABASE_URL: mysql+pymysql://root:root@127.0.0.1:3306/student_lifecycle_test?charset=utf8mb4\n      TEST_DATABASE_URL: mysql+pymysql://root:root@127.0.0.1:3306/student_lifecycle_test?charset=utf8mb4\n      FAST_TEST_SCHEMA: '1'\n      APP_ENV: test\n      SECRET_KEY: academic-int-program-series-targeted\n    steps:\n      - name: Checkout exact candidate\n        uses: actions/checkout@v4\n        with:\n          fetch-depth: 0\n\n      - name: Prove exact atomic base\n        run: |\n          set -euo pipefail\n          test "$(git rev-parse HEAD)" = "$GITHUB_SHA"\n          test "$(git rev-parse HEAD^)" = "4d971781a9d0d1728cc7ab01daefb25de95fd23a"\n          test "$(git rev-list --count 4d971781a9d0d1728cc7ab01daefb25de95fd23a..HEAD)" = "1"\n\n      - uses: actions/setup-python@v5\n        with:\n          python-version: '3.12'\n          cache: pip\n          cache-dependency-path: backend/requirements.txt\n\n      - name: Install backend dependencies\n        working-directory: backend\n        run: pip install -r requirements.txt\n\n      - name: Prove source contract and single Alembic head\n        working-directory: backend\n        run: |\n          set -euo pipefail\n          FILE=alembic/versions/20260817_academic_int_program_series.py\n          grep -F 'revision = "20260817_acad_int_program_series"' "$FILE"\n          grep -F 'down_revision = "20260817_acad_int_ctrl_merge"' "$FILE"\n          grep -F 'uk_aa_program_series_version' "$FILE"\n          ! grep -Ei 'UPDATE[[:space:]]+t_aa_program|LEGACY-' "$FILE"\n          grep -F '.with_for_update()' app/modules/academic_affairs/services/academic_affairs_program_authority_service.py\n          grep -F 'PROGRAM_SERIES_UNRESOLVED' app/modules/academic_affairs/services/academic_affairs_program_authority_service.py\n          HEADS="$(alembic heads)"\n          echo "$HEADS"\n          test "$(printf '%s\\n' "$HEADS" | grep -c ' (head)')" = "1"\n          printf '%s\\n' "$HEADS" | grep -F '20260817_acad_int_program_series (head)'\n\n      - name: Fresh MySQL upgrade\n        working-directory: backend\n        run: |\n          set -euo pipefail\n          alembic upgrade head\n          alembic current | grep -F '20260817_acad_int_program_series (head)'\n\n      - name: Run only stable-series targeted contracts\n        working-directory: backend\n        run: |\n          set -euo pipefail\n          pytest -q \\\n            tests/test_academic_int_program_series_schema_red.py \\\n            tests/test_academic_int_program_series_mysql.py\n''',
)

print("materialized Program stable-series candidate files")
