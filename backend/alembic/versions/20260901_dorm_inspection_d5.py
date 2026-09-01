"""D5 professional dorm inspection, evidence and rectification lifecycle.

Revision ID: 20260901_dorm_inspection_d5
Revises: 20260901_orientation_qualification_o4
"""
from __future__ import annotations

from datetime import datetime

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20260901_dorm_inspection_d5"
down_revision = "20260901_orientation_qualification_o4"
branch_labels = None
depends_on = None

TASK = "t_affairs_dorm_check_task"
RECORD = "t_affairs_dorm_check_record"
ROOM = "t_affairs_dorm_room"
STUDENT = "t_student_profile"
RECTIFICATION = "t_affairs_dorm_rectification"
CONFIG_DEFINITION = "t_config_definition"
CONFIG_OVERRIDE = "t_config_override"
CONFIG_ACTIVATION = "t_config_activation"
SYS_CONFIG = "t_sys_config"
CONFIG_KEY = "DORM_INSPECTION_POLICY"

TASK_NEW_COLUMNS = {
    "floor_scope_json", "template_key", "template_version", "template_snapshot_json",
    "client_request_id", "checker_user_id", "published_at", "completed_at",
}
RECORD_NEW_COLUMNS = {
    "severity", "score", "item_results_json", "client_request_id",
    "inspected_by_user_id", "inspected_at",
}

DEFAULT_POLICY = {
    "policyVersion": 1,
    "riskSeverities": ["HIGH", "CRITICAL"],
    "evidenceRequiredSeverities": ["HIGH", "CRITICAL"],
    "deadlineHours": {"LOW": 72, "MEDIUM": 48, "HIGH": 24, "CRITICAL": 4},
    "templates": [
        {
            "key": "DORM-HYGIENE-DEFAULT", "version": 1, "name": "日常卫生检查",
            "checkType": "HYGIENE",
            "items": [
                {"code": "FLOOR", "name": "地面", "maxScore": 20, "required": True, "severity": "LOW"},
                {"code": "DESK", "name": "桌面", "maxScore": 20, "required": True, "severity": "LOW"},
                {"code": "BED", "name": "床铺", "maxScore": 20, "required": True, "severity": "LOW"},
                {"code": "BALCONY", "name": "阳台", "maxScore": 20, "required": True, "severity": "MEDIUM"},
                {"code": "WASTE", "name": "垃圾与异味", "maxScore": 20, "required": True, "severity": "MEDIUM"},
            ],
        },
        {
            "key": "DORM-SAFETY-DEFAULT", "version": 1, "name": "用电与消防安全检查",
            "checkType": "SAFETY",
            "items": [
                {"code": "ELECTRIC", "name": "用电安全", "maxScore": 35, "required": True, "severity": "HIGH"},
                {"code": "FIRE_PASSAGE", "name": "消防通道", "maxScore": 35, "required": True, "severity": "CRITICAL"},
                {"code": "CONTRABAND", "name": "违禁电器", "maxScore": 30, "required": True, "severity": "HIGH"},
            ],
        },
        {
            "key": "DORM-CONTRABAND-DEFAULT", "version": 1, "name": "违禁品专项检查",
            "checkType": "CONTRABAND",
            "items": [
                {"code": "APPLIANCE", "name": "违禁电器", "maxScore": 50, "required": True, "severity": "HIGH"},
                {"code": "DANGEROUS_GOODS", "name": "危险物品", "maxScore": 50, "required": True, "severity": "CRITICAL"},
            ],
        },
        {
            "key": "DORM-NIGHT-DEFAULT", "version": 1, "name": "夜间在寝人工核验",
            "checkType": "NIGHT_ABSENCE",
            "items": [
                {"code": "PRESENCE", "name": "本人在寝情况", "maxScore": 70, "required": True, "severity": "HIGH"},
                {"code": "CONTACT", "name": "联系核验情况", "maxScore": 30, "required": True, "severity": "HIGH"},
            ],
        },
        {
            "key": "DORM-FIRE-DEFAULT", "version": 1, "name": "消防安全专项检查",
            "checkType": "FIRE_SAFETY",
            "items": [
                {"code": "PASSAGE", "name": "消防通道", "maxScore": 40, "required": True, "severity": "CRITICAL"},
                {"code": "EQUIPMENT", "name": "消防器材", "maxScore": 30, "required": True, "severity": "HIGH"},
                {"code": "CHARGING", "name": "违规充电", "maxScore": 30, "required": True, "severity": "HIGH"},
            ],
        },
        {
            "key": "DORM-FACILITY-DEFAULT", "version": 1, "name": "公共设施检查",
            "checkType": "FACILITY",
            "items": [
                {"code": "WATER", "name": "给排水", "maxScore": 35, "required": True, "severity": "MEDIUM"},
                {"code": "ELECTRIC", "name": "公共用电", "maxScore": 35, "required": True, "severity": "HIGH"},
                {"code": "DOOR_WINDOW", "name": "门窗与锁具", "maxScore": 30, "required": True, "severity": "MEDIUM"},
            ],
        },
        {
            "key": "DORM-OTHER-DEFAULT", "version": 1, "name": "其他宿舍检查",
            "checkType": "OTHER",
            "items": [
                {"code": "CUSTOM", "name": "自定义检查项", "maxScore": 100, "required": True, "severity": "MEDIUM"},
            ],
        },
    ],
}


def _scalar(sql: str, params: dict | None = None) -> int:
    return int(op.get_bind().execute(sa.text(sql), params or {}).scalar() or 0)


def _columns(table: str) -> set[str]:
    return {column["name"] for column in inspect(op.get_bind()).get_columns(table)}


def _preflight() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "mysql":
        raise RuntimeError("20260901_dorm_inspection_d5 requires MySQL")
    tables = set(inspect(bind).get_table_names())
    required = {TASK, RECORD, ROOM, STUDENT, CONFIG_DEFINITION, CONFIG_OVERRIDE, CONFIG_ACTIVATION, SYS_CONFIG}
    missing = sorted(required - tables)
    if missing:
        raise RuntimeError("D5 requires existing authority tables: " + ",".join(missing))
    if RECTIFICATION in tables:
        raise RuntimeError("D5 rectification table already exists outside this revision")
    task_collisions = sorted(TASK_NEW_COLUMNS & _columns(TASK))
    record_collisions = sorted(RECORD_NEW_COLUMNS & _columns(RECORD))
    if task_collisions or record_collisions:
        raise RuntimeError(
            "D5 target columns already exist outside this revision: "
            f"task={task_collisions}, record={record_collisions}"
        )

    unsupported_task = _scalar(f"""
        SELECT COUNT(*) FROM {TASK}
        WHERE is_deleted=0 AND (
          check_type NOT IN ('HYGIENE','SAFETY','CONTRABAND','NIGHT_ABSENCE','FIRE_SAFETY','FACILITY','OTHER')
          OR status NOT IN ('DRAFT','PUBLISHED','RUNNING','DONE','CANCELLED')
        )
    """)
    unsupported_record = _scalar(f"""
        SELECT COUNT(*) FROM {RECORD}
        WHERE is_deleted=0 AND result NOT IN ('NORMAL','ABNORMAL','正常','合格','需整改','异常')
    """)
    abnormal_without_scope = _scalar(f"""
        SELECT COUNT(*)
        FROM {RECORD} r
        LEFT JOIN {TASK} t ON t.id=r.task_id AND t.tenant_id=r.tenant_id AND t.is_deleted=0
        LEFT JOIN {ROOM} room ON room.id=r.room_id AND room.tenant_id=r.tenant_id AND room.is_deleted=0
        WHERE r.is_deleted=0 AND r.result IN ('ABNORMAL','需整改','异常')
          AND (t.id IS NULL OR room.id IS NULL OR (t.building_id IS NOT NULL AND t.building_id<>room.building_id))
    """)
    normal_with_risk = _scalar(f"""
        SELECT COUNT(*) FROM {RECORD}
        WHERE is_deleted=0 AND result IN ('NORMAL','正常','合格') AND related_risk_id IS NOT NULL
    """)
    risk_without_student = _scalar(f"""
        SELECT COUNT(*)
        FROM {RECORD} r
        LEFT JOIN {STUDENT} s
          ON s.id=(CASE
              WHEN JSON_VALID(r.student_ids_json)=1 AND JSON_LENGTH(r.student_ids_json)>0
              THEN CAST(JSON_UNQUOTE(JSON_EXTRACT(r.student_ids_json,'$[0]')) AS UNSIGNED)
              ELSE NULL END)
         AND s.tenant_id=r.tenant_id AND s.is_deleted=0
        WHERE r.is_deleted=0 AND r.related_risk_id IS NOT NULL AND s.id IS NULL
    """)
    invalid_config = _scalar(f"""
        SELECT COUNT(*) FROM {CONFIG_DEFINITION}
        WHERE config_key=:key AND (is_deleted<>0 OR value_type<>'JSON' OR status<>'ACTIVE')
    """, {"key": CONFIG_KEY})
    if any((unsupported_task, unsupported_record, abnormal_without_scope,
            normal_with_risk, risk_without_student, invalid_config)):
        raise RuntimeError(
            "D5 preflight failed before DDL: "
            f"unsupported_task={unsupported_task}, unsupported_record={unsupported_record}, "
            f"abnormal_without_scope={abnormal_without_scope}, normal_with_risk={normal_with_risk}, "
            f"risk_without_student={risk_without_student}, invalid_config={invalid_config}"
        )


def _register_default_policy() -> None:
    if _scalar(f"SELECT COUNT(*) FROM {CONFIG_DEFINITION} WHERE config_key=:key", {"key": CONFIG_KEY}):
        return
    now = datetime.utcnow()
    table = sa.table(
        CONFIG_DEFINITION,
        sa.column("config_key", sa.String()), sa.column("domain_code", sa.String()),
        sa.column("config_name", sa.String()), sa.column("value_type", sa.String()),
        sa.column("validation_json", sa.JSON()), sa.column("default_json", sa.JSON()),
        sa.column("platform_floor_json", sa.JSON()), sa.column("school_editable", sa.Boolean()),
        sa.column("owner_code", sa.String()), sa.column("consumer_json", sa.JSON()),
        sa.column("cache_scope", sa.String()), sa.column("risk_level", sa.String()),
        sa.column("status", sa.String()), sa.column("created_at", sa.DateTime()),
        sa.column("created_by", sa.BigInteger()), sa.column("updated_at", sa.DateTime()),
        sa.column("updated_by", sa.BigInteger()), sa.column("is_deleted", sa.Boolean()),
        sa.column("version", sa.Integer()),
    )
    op.bulk_insert(table, [{
        "config_key": CONFIG_KEY,
        "domain_code": "STUDENT_AFFAIRS",
        "config_name": "宿舍检查模板与风险阈值",
        "value_type": "JSON",
        "validation_json": {"requiredKeys": ["templates", "riskSeverities", "deadlineHours"]},
        "default_json": {"value": DEFAULT_POLICY},
        "platform_floor_json": {},
        "school_editable": True,
        "owner_code": "DORM_D5",
        "consumer_json": {"items": [
            "dorm_inspection_service.template_snapshot",
            "dorm_inspection_service.evidence_requirement",
            "dorm_inspection_service.risk_creation_threshold",
        ]},
        "cache_scope": "TENANT",
        "risk_level": "NORMAL",
        "status": "ACTIVE",
        "created_at": now, "created_by": None, "updated_at": now, "updated_by": None,
        "is_deleted": False, "version": 1,
    }])


def upgrade() -> None:
    _preflight()

    for column in (
        sa.Column("floor_scope_json", sa.JSON(), nullable=True, comment="任务覆盖楼层快照；空表示整栋"),
        sa.Column("template_key", sa.String(160), nullable=True),
        sa.Column("template_version", sa.Integer(), nullable=True),
        sa.Column("template_snapshot_json", sa.JSON(), nullable=True),
        sa.Column("client_request_id", sa.String(100), nullable=True),
        sa.Column("checker_user_id", sa.BigInteger(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    ):
        op.add_column(TASK, column)
    op.execute(sa.text(f"""
        UPDATE {TASK}
        SET template_key=CASE
              WHEN check_type='HYGIENE' THEN 'DORM-HYGIENE-DEFAULT'
              ELSE 'DORM-SAFETY-DEFAULT' END,
            template_version=1,
            template_snapshot_json=JSON_OBJECT(
              'legacyBackfill',TRUE,'checkType',check_type,'templateVersion',1
            ),
            published_at=CASE WHEN status IN ('PUBLISHED','RUNNING','DONE') THEN created_at ELSE NULL END,
            completed_at=CASE WHEN status='DONE' THEN updated_at ELSE NULL END
    """))
    op.alter_column(TASK, "template_key", existing_type=sa.String(160), nullable=False)
    op.alter_column(TASK, "template_version", existing_type=sa.Integer(), nullable=False)
    op.create_unique_constraint("uk_dorm_check_task_client_request", TASK, ["tenant_id", "client_request_id"])
    op.create_check_constraint(
        "ck_dorm_check_task_type", TASK,
        "check_type IN ('HYGIENE','SAFETY','CONTRABAND','NIGHT_ABSENCE','FIRE_SAFETY','FACILITY','OTHER')",
    )
    op.create_check_constraint(
        "ck_dorm_check_task_status", TASK,
        "status IN ('DRAFT','PUBLISHED','RUNNING','DONE','CANCELLED')",
    )
    op.create_check_constraint("ck_dorm_check_task_template_version", TASK, "template_version >= 1")
    op.create_index("ix_t_affairs_dorm_check_task_checker_user_id", TASK, ["checker_user_id"])
    op.create_index(
        "ix_dorm_check_task_building_status", TASK,
        ["tenant_id", "building_id", "status", "is_deleted"],
    )

    for column in (
        sa.Column("severity", sa.String(20), nullable=True),
        sa.Column("score", sa.Numeric(5, 2), nullable=True),
        sa.Column("item_results_json", sa.JSON(), nullable=True),
        sa.Column("client_request_id", sa.String(100), nullable=True),
        sa.Column("inspected_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("inspected_at", sa.DateTime(), nullable=True),
    ):
        op.add_column(RECORD, column)
    op.execute(sa.text(f"""
        UPDATE {RECORD}
        SET result=CASE WHEN result IN ('NORMAL','正常','合格') THEN 'NORMAL' ELSE 'ABNORMAL' END,
            severity=CASE
              WHEN result IN ('NORMAL','正常','合格') THEN 'NONE'
              WHEN related_risk_id IS NOT NULL THEN 'HIGH'
              ELSE 'MEDIUM' END,
            inspected_at=created_at
    """))
    op.alter_column(RECORD, "severity", existing_type=sa.String(20), nullable=False)
    op.create_unique_constraint(
        "uk_dorm_check_record_client_request", RECORD,
        ["tenant_id", "task_id", "client_request_id"],
    )
    op.create_check_constraint("ck_dorm_check_record_result", RECORD, "result IN ('NORMAL','ABNORMAL')")
    op.create_check_constraint(
        "ck_dorm_check_record_severity", RECORD,
        "severity IN ('NONE','LOW','MEDIUM','HIGH','CRITICAL')",
    )
    op.create_check_constraint(
        "ck_dorm_check_record_score", RECORD,
        "score IS NULL OR (score >= 0 AND score <= 100)",
    )
    op.create_index("ix_t_affairs_dorm_check_record_inspected_by_user_id", RECORD, ["inspected_by_user_id"])
    op.create_index(
        "ix_dorm_check_record_task_result", RECORD,
        ["tenant_id", "task_id", "result", "is_deleted"],
    )

    common = [
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, comment="逻辑删除"),
        sa.Column("version", sa.Integer(), nullable=False, comment="乐观锁"),
    ]
    op.create_table(
        RECTIFICATION,
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False, comment="租户(学校)ID，行级隔离"),
        sa.Column("check_record_id", sa.BigInteger(), nullable=False),
        sa.Column("task_id", sa.BigInteger(), nullable=False),
        sa.Column("building_id", sa.BigInteger(), nullable=False),
        sa.Column("room_id", sa.BigInteger(), nullable=False),
        sa.Column("student_id", sa.BigInteger(), nullable=True, comment="房间级整改保持 NULL"),
        sa.Column("related_exception_id", sa.BigInteger(), nullable=True),
        sa.Column("related_risk_id", sa.BigInteger(), nullable=True),
        sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("requirement", sa.String(1000), nullable=False),
        sa.Column("deadline_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("assignee_type", sa.String(20), nullable=False),
        sa.Column("assignee_id", sa.BigInteger(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("rectify_note", sa.String(1000), nullable=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("recheck_note", sa.String(1000), nullable=True),
        sa.Column("rechecked_at", sa.DateTime(), nullable=True),
        sa.Column("rechecked_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("escalated_at", sa.DateTime(), nullable=True),
        sa.Column("last_client_request_id", sa.String(100), nullable=True),
        sa.Column("last_submission_hash", sa.String(64), nullable=True),
        *common,
        sa.UniqueConstraint("tenant_id", "check_record_id", name="uk_dorm_rectification_record"),
        sa.UniqueConstraint("tenant_id", "last_client_request_id", name="uk_dorm_rectification_client_request"),
        sa.CheckConstraint(
            "source_type IN ('LEGACY_BACKFILL','INSPECTION_RUNTIME')",
            name="ck_dorm_rectification_source_type",
        ),
        sa.CheckConstraint(
            "severity IN ('LOW','MEDIUM','HIGH','CRITICAL')",
            name="ck_dorm_rectification_severity",
        ),
        sa.CheckConstraint(
            "status IN ('OPEN','RECTIFYING','WAITING_RECHECK','CLOSED','ESCALATED')",
            name="ck_dorm_rectification_status",
        ),
        sa.CheckConstraint(
            "assignee_type IN ('STUDENT','DORM_MANAGER')",
            name="ck_dorm_rectification_assignee_type",
        ),
        sa.CheckConstraint(
            "status <> 'WAITING_RECHECK' OR submitted_at IS NOT NULL",
            name="ck_dorm_rectification_waiting",
        ),
        sa.CheckConstraint(
            "status <> 'CLOSED' OR closed_at IS NOT NULL",
            name="ck_dorm_rectification_closed",
        ),
        sa.CheckConstraint(
            "status <> 'ESCALATED' OR escalated_at IS NOT NULL",
            name="ck_dorm_rectification_escalated",
        ),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    for column in ("tenant_id", "check_record_id", "task_id", "building_id", "room_id", "student_id", "assignee_id", "deadline_at", "status"):
        op.create_index(f"ix_{RECTIFICATION}_{column}", RECTIFICATION, [column])
    op.create_index(
        "ix_dorm_rectification_building_status", RECTIFICATION,
        ["tenant_id", "building_id", "status", "is_deleted"],
    )
    op.create_index(
        "ix_dorm_rectification_student_status", RECTIFICATION,
        ["tenant_id", "student_id", "status", "is_deleted"],
    )
    op.create_index(
        "ix_dorm_rectification_deadline", RECTIFICATION,
        ["tenant_id", "status", "deadline_at", "is_deleted"],
    )
    op.execute(sa.text(f"""
        INSERT INTO {RECTIFICATION}
          (tenant_id,check_record_id,task_id,building_id,room_id,student_id,
           related_exception_id,related_risk_id,source_type,severity,requirement,deadline_at,
           status,assignee_type,assignee_id,started_at,submitted_at,closed_at,escalated_at,
           last_client_request_id,last_submission_hash,
           created_at,created_by,updated_at,updated_by,is_deleted,version)
        SELECT r.tenant_id,r.id,r.task_id,room.building_id,r.room_id,
               CASE WHEN JSON_VALID(r.student_ids_json)=1 AND JSON_LENGTH(r.student_ids_json)>0
                    THEN CAST(JSON_UNQUOTE(JSON_EXTRACT(r.student_ids_json,'$[0]')) AS UNSIGNED)
                    ELSE NULL END,
               r.related_exception_id,r.related_risk_id,'LEGACY_BACKFILL',
               CASE WHEN r.severity='NONE' THEN 'MEDIUM' ELSE r.severity END,
               COALESCE(NULLIF(TRIM(r.detail),''),'历史宿舍检查异常，请按宿管要求完成整改'),
               COALESCE(r.rectify_deadline,DATE_ADD(r.created_at,INTERVAL 48 HOUR)),
               CASE WHEN r.status='CLOSED' THEN 'CLOSED'
                    WHEN r.status='RECTIFYING' THEN 'RECTIFYING' ELSE 'OPEN' END,
               CASE WHEN JSON_VALID(r.student_ids_json)=1 AND JSON_LENGTH(r.student_ids_json)>0
                    THEN 'STUDENT' ELSE 'DORM_MANAGER' END,
               CASE WHEN JSON_VALID(r.student_ids_json)=1 AND JSON_LENGTH(r.student_ids_json)>0
                    THEN CAST(JSON_UNQUOTE(JSON_EXTRACT(r.student_ids_json,'$[0]')) AS UNSIGNED)
                    ELSE NULL END,
               CASE WHEN r.status='RECTIFYING' THEN r.updated_at ELSE NULL END,
               NULL,
               CASE WHEN r.status='CLOSED' THEN r.updated_at ELSE NULL END,
               NULL,NULL,NULL,r.created_at,r.created_by,r.updated_at,r.updated_by,0,1
        FROM {RECORD} r
        JOIN {ROOM} room ON room.id=r.room_id AND room.tenant_id=r.tenant_id AND room.is_deleted=0
        WHERE r.is_deleted=0 AND r.result='ABNORMAL'
    """))

    _register_default_policy()


def downgrade() -> None:
    runtime_rectifications = _scalar(
        f"SELECT COUNT(*) FROM {RECTIFICATION} WHERE source_type<>'LEGACY_BACKFILL' OR version<>1"
    )
    runtime_tasks = _scalar(f"SELECT COUNT(*) FROM {TASK} WHERE client_request_id IS NOT NULL")
    runtime_records = _scalar(f"SELECT COUNT(*) FROM {RECORD} WHERE client_request_id IS NOT NULL")
    config_overrides = _scalar(
        f"SELECT COUNT(*) FROM {CONFIG_OVERRIDE} WHERE config_key=:key AND is_deleted=0",
        {"key": CONFIG_KEY},
    ) + _scalar(
        f"SELECT COUNT(*) FROM {CONFIG_ACTIVATION} WHERE config_key=:key",
        {"key": CONFIG_KEY},
    ) + _scalar(
        f"SELECT COUNT(*) FROM {SYS_CONFIG} WHERE config_key=:key AND is_deleted=0",
        {"key": CONFIG_KEY},
    )
    if any((runtime_rectifications, runtime_tasks, runtime_records, config_overrides)):
        raise RuntimeError(
            "D5 downgrade blocked: runtime inspection authority exists; "
            f"rectifications={runtime_rectifications}, tasks={runtime_tasks}, "
            f"records={runtime_records}, config_overrides={config_overrides}"
        )

    op.execute(sa.text(
        f"DELETE FROM {CONFIG_DEFINITION} WHERE config_key=:key AND owner_code='DORM_D5'"
    ).bindparams(key=CONFIG_KEY))
    op.drop_index("ix_dorm_rectification_deadline", table_name=RECTIFICATION)
    op.drop_index("ix_dorm_rectification_student_status", table_name=RECTIFICATION)
    op.drop_index("ix_dorm_rectification_building_status", table_name=RECTIFICATION)
    for column in ("status", "deadline_at", "assignee_id", "student_id", "room_id", "building_id", "task_id", "check_record_id", "tenant_id"):
        op.drop_index(f"ix_{RECTIFICATION}_{column}", table_name=RECTIFICATION)
    op.drop_table(RECTIFICATION)

    op.drop_index("ix_dorm_check_record_task_result", table_name=RECORD)
    op.drop_index("ix_t_affairs_dorm_check_record_inspected_by_user_id", table_name=RECORD)
    op.drop_constraint("ck_dorm_check_record_score", RECORD, type_="check")
    op.drop_constraint("ck_dorm_check_record_severity", RECORD, type_="check")
    op.drop_constraint("ck_dorm_check_record_result", RECORD, type_="check")
    op.drop_constraint("uk_dorm_check_record_client_request", RECORD, type_="unique")
    for column in ("inspected_at", "inspected_by_user_id", "client_request_id", "item_results_json", "score", "severity"):
        op.drop_column(RECORD, column)

    op.drop_index("ix_dorm_check_task_building_status", table_name=TASK)
    op.drop_index("ix_t_affairs_dorm_check_task_checker_user_id", table_name=TASK)
    op.drop_constraint("ck_dorm_check_task_template_version", TASK, type_="check")
    op.drop_constraint("ck_dorm_check_task_status", TASK, type_="check")
    op.drop_constraint("ck_dorm_check_task_type", TASK, type_="check")
    op.drop_constraint("uk_dorm_check_task_client_request", TASK, type_="unique")
    for column in ("completed_at", "published_at", "checker_user_id", "client_request_id", "template_snapshot_json", "template_version", "template_key", "floor_scope_json"):
        op.drop_column(TASK, column)
