"""岗位实习 V9.3 便捷性批次二 · 剩余 6 个实体的首次创建并发实测（总册 §9）。

方法照抄上一批挖出真 bug 的路子：先 `grep -c with_for_update`，0 的才需要写并发测试。
六个实体分成三档，每档结论不同，都必须用真实 MySQL 实测，不能靠读代码推断：

┌──────────────┬────────────────┬──────────────┬────────────────────────────┐
│ 实体          │ FOR UPDATE     │ DB 唯一约束   │ 静态推断                    │
├──────────────┼────────────────┼──────────────┼────────────────────────────┤
│ 变更申请      │ 无（创建函数）  │ 无            │ 高危：与请假/补卡同一形状   │
│ 意向          │ 无（创建函数）  │ 无            │ 高危：与请假/补卡同一形状   │
│ 免修/豁免     │ 无             │ 无            │ 最高危：连查重代码都没写    │
│ 知情同意      │ 有             │ 无（只有普通索引）│ 未知：间隙锁是否真的挡住 │
│ 特殊备案      │ 有             │ 无（索引缺 filing_type/status）│ 未知               │
│ 安全课程完成  │ 有             │ 有（uk_ix_safety_completion）│ 应该安全（回归锁） │
└──────────────┴────────────────┴──────────────┴────────────────────────────┘

注：`test_internship_v93_leave_makeup_first_create.py` 的文档曾把变更申请/知情同意/特殊备案
列为「都带了 FOR UPDATE」的对照组，暗示它们是安全的——但本仓库里从未有测试真正跑过这三个
实体的并发首次创建。核实后发现变更申请的创建函数（`student_apply`）其实完全没有 FOR UPDATE，
这份对照组说明本身是不准确的。本文件是这六个实体第一次被真实并发测试覆盖。

真实 MySQL（db_mode 夹具）：SQLite 不会以同样方式暴露间隙锁/唯一约束竞争。
"""
from __future__ import annotations

import threading
import uuid
from types import SimpleNamespace

import pytest

TID = 1000000000000000001

ADMIN_USER = {"userId": "1", "tenantId": str(TID), "realName": "管理员",
              "userType": "ADMIN", "currentRoleCode": "SCHOOL_ADMIN"}


def _admin_ctx():
    """contextvars 不跨线程共享：每个并发线程都要各自设置一次租户上下文，
    否则 service 层的 `_tid()` 拿不到租户，直接 403 TENANT_CONTEXT_REQUIRED——
    这不是被测代码的问题，是测试线程自己没布置好上下文。"""
    from app.core.context import set_current_user, set_tenant

    set_tenant({"tenantId": str(TID)})
    set_current_user(ADMIN_USER)


def _ctx(student_no=None):
    from app.core.context import set_current_user, set_tenant

    set_tenant({"tenantId": str(TID)})
    payload = {"userId": "1", "tenantId": str(TID), "realName": "学生甲",
               "userType": "STUDENT", "currentRoleCode": "STUDENT",
               "activeContextId": "ctx"}
    if student_no:
        payload["studentNo"] = student_no
    set_current_user(payload)


def _session():
    from app.db.session import get_sessionmaker

    return get_sessionmaker()()


def _seed(db, *, batch_status="RUNNING", record_status="ONBOARD"):
    """一个批次 + 一条实习记录 + 一个学生档案，六个用例共用这个最小骨架。"""
    from app.models import InternshipBatch, InternshipRecord, StudentProfile

    batch = InternshipBatch(tenant_id=TID, batch_name="V93批次二测试批次",
                            batch_no=f"IXB2-{uuid.uuid4().hex[:8]}", status=batch_status)
    db.add(batch)
    db.flush()
    student_no = f"IXB2{uuid.uuid4().hex[:8]}"
    profile = StudentProfile(tenant_id=TID, student_no=student_no, real_name="批次二甲",
                             grade="2024", student_status="NORMAL", status="ACTIVE")
    db.add(profile)
    db.flush()
    record = InternshipRecord(tenant_id=TID, student_id=profile.id, batch_id=batch.id,
                             status=record_status)
    db.add(record)
    db.flush()
    return {"batch": batch.id, "internship": record.id, "student": profile.id,
            "studentNo": student_no}


def _seed_evidence_file(db) -> str:
    """建一条真实可绑定的依据文件，返回文件 ID。

    合规豁免的依据文件有三道硬前置（都在 file_business_binding_service 里）：
    1. 文件真实存在且未删除；
    2. status ∈ {AVAILABLE, STORED} 且 scan_status ∈ {CLEAN, NOT_REQUIRED}（安全扫描通过）；
    3. 必须是「本人上传的临时文件」——biz_type=TEMP_PRIVATE、biz_id 为空、visibility=PRIVATE，
       且 owner_user_id 等于当前操作人；否则走「历史文件接管」分支被拒。

    这些都是生产设计上的正确约束（防止把别人的文件改绑到自己的业务对象上），
    测试要照着满足，不能绕过。
    """
    from app.models.file import FileObject

    row = FileObject(tenant_id=TID, file_key=f"test/evidence/{uuid.uuid4().hex}.pdf",
                     file_name="豁免依据材料.pdf", status="AVAILABLE", scan_status="CLEAN",
                     biz_type="TEMP_PRIVATE", biz_id=None, visibility="PRIVATE",
                     owner_user_id=ADMIN_USER["userId"])
    db.add(row)
    db.flush()
    return str(row.id)


def _run_pair(fn):
    """两线程 barrier 同步起跑（跟上一批同款），返回 (ok, failed)。

    failed 项是 (seq, http_status, detail)；bare Exception 记 500——未接住的异常正是
    要抓的东西，不能被 except AppException 悄悄放过。
    """
    from app.core.exceptions import AppException

    ok, failed = [], []
    lock = threading.Lock()
    barrier = threading.Barrier(2)

    def _run(seq):
        try:
            barrier.wait(timeout=30)
            fn(seq)
            with lock:
                ok.append(seq)
        except AppException as exc:
            with lock:
                failed.append((seq, exc.http_status, exc.code))
        except Exception as exc:  # noqa: BLE001
            with lock:
                failed.append((seq, 500, repr(exc)[:200]))

    threads = [threading.Thread(target=_run, args=(i,)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=90)
    return ok, failed


# ═══════════════════════ 0. 串行基线（先证明种子是真的）═══════════════════════
#
# 上一批的模板每个实体都先跑一条串行用例，我第一版漏了，结果四条并发用例红成一片，
# 其中两条根本不是并发问题：一条是我没传依据文件（测的是我的用例），另一条是生产代码
# 本身就 100% 抛 TypeError。没有串行基线就分不清「并发挡不住」和「这功能压根跑不通」。

def test_serial_change_apply_lands_one_row(db_mode):
    """串行提交一次变更申请必须成功落库。"""
    from app.models import InternshipChangeRequest, InternshipRecord, StudentProfile
    from app.modules.internship.services import internship_change_service as svc

    db = _session()
    ids = _seed(db)
    db.commit()
    rec = db.get(InternshipRecord, ids["internship"])
    stu = db.get(StudentProfile, ids["student"])
    db.close()

    _ctx(ids["studentNo"])
    svc.student_apply(rec, stu, {
        "changeType": "WITHDRAW_POST", "reason": "企业提前终止合作，申请退岗以便重新分配。"})

    db = _session()
    try:
        rows = db.query(InternshipChangeRequest).filter(
            InternshipChangeRequest.tenant_id == TID,
            InternshipChangeRequest.internship_id == ids["internship"],
            InternshipChangeRequest.is_deleted.is_(False)).all()
    finally:
        db.close()
    assert len(rows) == 1


def test_serial_intention_create_lands_one_row(db_mode):
    """串行创建一次意向必须成功落库。"""
    from app.models import InternshipIntention
    from app.modules.internship.services import internship_match_service as svc

    db = _session()
    ids = _seed(db)
    db.commit()
    db.close()

    _ctx(ids["studentNo"])
    svc.create_intention(SimpleNamespace(
        recordId=str(ids["internship"]), preferredCity="长沙", preferredIndustry="制造业",
        preferredCompanyId=None, preferredPositionId=None, intentionNote="希望就近实习"),
        self_service=True)

    db = _session()
    try:
        rows = db.query(InternshipIntention).filter(
            InternshipIntention.tenant_id == TID,
            InternshipIntention.record_id == ids["internship"],
            InternshipIntention.is_deleted.is_(False)).all()
    finally:
        db.close()
    assert len(rows) == 1


def test_serial_exemption_grant_lands_one_row(db_mode):
    """串行申请一次豁免必须成功落库（依据文件是硬前置，见 evidence_authority_guard）。"""
    from app.models import InternshipComplianceExemption
    from app.modules.internship.services import internship_compliance_service as svc

    db = _session()
    ids = _seed(db)
    file_id = _seed_evidence_file(db)
    db.commit()
    db.close()

    _admin_ctx()
    svc.grant_exemption({
        "internshipId": str(ids["internship"]), "checkCode": "SAFETY_COURSE",
        "reason": "该企业已有等效安全培训记录，申请豁免重复学习。",
        "validUntil": "2099-01-01T00:00:00",
        "evidenceFileIds": [file_id],
    }, user=ADMIN_USER)

    db = _session()
    try:
        rows = db.query(InternshipComplianceExemption).filter(
            InternshipComplianceExemption.tenant_id == TID,
            InternshipComplianceExemption.internship_id == ids["internship"],
            InternshipComplianceExemption.is_deleted.is_(False)).all()
    finally:
        db.close()
    assert len(rows) == 1


def test_serial_consent_create_pending_lands_one_row(db_mode):
    """串行创建一次知情确认任务必须成功落库。"""
    from app.models import InternshipConsent
    from app.modules.internship.services import internship_consent_service as svc

    db = _session()
    ids = _seed(db)
    db.commit()
    db.close()

    _admin_ctx()
    svc.create_pending({
        "internshipId": str(ids["internship"]), "consentType": "STUDENT",
        "contentSnapshot": "岗位实习安全须知正文……", "contentVersion": "v1",
    }, user=ADMIN_USER)

    db = _session()
    try:
        rows = db.query(InternshipConsent).filter(
            InternshipConsent.tenant_id == TID,
            InternshipConsent.internship_id == ids["internship"],
            InternshipConsent.is_deleted.is_(False)).all()
    finally:
        db.close()
    assert len(rows) == 1


def test_serial_special_filing_create_lands_one_row(db_mode):
    """串行创建一次特殊备案必须成功落库。

    **这条是本批次挖出的真 bug**：`create()` 给 `InternshipSpecialFiling` 传了
    `requested_by_name` / `requested_by_user_id`，但这两个字段在 ORM 模型和真实表里
    **都不存在**（已用 information_schema 核对 t_internship_special_filing 的 33 列）。
    因此 `POST /internship/filings` 是 100% TypeError → 500，跟并发无关。

    这个 bug 会自我掩盖：创建永远失败 → 表里永远 0 行 → 另外两处读取
    （`review()` 的「申请人不能自审」守卫、合规工作台的 requestedByName 列）
    永远轮不到执行，也就一直没人发现。
    """
    from app.models import InternshipSpecialFiling
    from app.modules.internship.services import internship_special_filing_service as svc

    db = _session()
    ids = _seed(db)
    db.commit()
    db.close()

    _admin_ctx()
    svc.create({
        "internshipId": str(ids["internship"]), "filingType": "OTHER",
        "triggerReason": "企业临时调整岗位安排，需补充备案说明情况。",
        "fileIds": ["f-evidence-1"],
    }, user=ADMIN_USER)

    db = _session()
    try:
        rows = db.query(InternshipSpecialFiling).filter(
            InternshipSpecialFiling.tenant_id == TID,
            InternshipSpecialFiling.internship_id == ids["internship"],
            InternshipSpecialFiling.is_deleted.is_(False)).all()
    finally:
        db.close()
    assert len(rows) == 1


#: 竞态用例的重复轮数。首次创建竞态是**间歇性**的：实测里变更申请和意向都出现过
#: 「某一轮侥幸只落一条」。只跑一轮的race测试会变成 flaky——现在偶尔假绿，
#: 将来真修好了也无法可靠证明。每轮用独立种子，只要任意一轮落 2 条即判定竞态成立。
RACE_ROUNDS = 5


def _race_rounds(seed_fn, action_fn, count_fn, rounds: int = RACE_ROUNDS):
    """跑 N 轮「两线程同时首次创建」，返回 (每轮落库条数, 500 清单)。

    这里**不做断言**，两个事实分开交回调用方：某一轮抛 500 时如果直接断言中断，
    后面几轮的落库条数就采集不到了，一个问题会把另一个问题盖掉。

    :param seed_fn: () -> ids，每轮建一套全新种子（不能复用，否则第二轮撞的是第一轮的行）
    :param action_fn: (ids, seq) -> None，单个线程要执行的写操作
    :param count_fn: (ids) -> int，本轮实际落库条数
    """
    observed, crashes = [], []
    for round_no in range(rounds):
        ids = seed_fn()
        _ok, failed = _run_pair(lambda seq, _ids=ids: action_fn(_ids, seq))
        for seq, status, detail in failed:
            if status == 500:
                crashes.append((round_no, seq, detail))
        observed.append(count_fn(ids))
    return observed, crashes


# ═══════════════════════ 1. 变更申请（高危，静态确认无锁）═══════════════════════

def test_concurrent_change_apply_first_create(db_mode):
    """并发提交变更申请：只能落一条 PENDING，输家不许是 500。

    `student_apply()` 是「查有没有 PENDING → 没有就插入」，中间完全没有 FOR UPDATE，
    也没有任何 DB 唯一约束兜底——这是与请假/补卡完全相同的漏洞形状。
    """
    from app.models import InternshipChangeRequest, InternshipRecord, StudentProfile
    from app.modules.internship.services import internship_change_service as svc

    body = {"changeType": "WITHDRAW_POST", "reason": "企业提前终止合作，申请退岗以便重新分配。"}

    def _seed_one():
        db = _session()
        ids = _seed(db)
        db.commit()
        ids["rec"] = db.get(InternshipRecord, ids["internship"])
        ids["stu"] = db.get(StudentProfile, ids["student"])
        db.close()
        return ids

    def _action(ids, seq):
        _ctx(ids["studentNo"])
        svc.student_apply(ids["rec"], ids["stu"], dict(body))

    def _count(ids):
        db = _session()
        try:
            return db.query(InternshipChangeRequest).filter(
                InternshipChangeRequest.tenant_id == TID,
                InternshipChangeRequest.internship_id == ids["internship"],
                InternshipChangeRequest.is_deleted.is_(False)).count()
        finally:
            db.close()

    observed, crashes = _race_rounds(_seed_one, _action, _count)
    assert not crashes, f"变更申请并发输家拿到 500 而不是业务冲突：{crashes}"
    assert all(n == 1 for n in observed), (
        f"同一实习记录并发提交变更申请，{len(observed)} 轮各自落库条数={observed}"
        f"（出现 2 即竞态成立：两个请求都查到「没有待审核申请」，各插一条；"
        f"教师队列里会出现同一学生的两条申请，批了一条另一条还挂着）")


# ═══════════════════════ 2. 意向（高危，静态确认无锁）═══════════════════════

def test_concurrent_intention_create_first_create(db_mode):
    """并发创建实习意向：只能落一条进行中（DRAFT/SUBMITTED）意向。

    `create_intention()` 同样是「查有没有 DRAFT/SUBMITTED → 没有就插入」，无锁无约束。
    """
    from app.models import InternshipIntention
    from app.modules.internship.services import internship_match_service as svc

    def _seed_one():
        db = _session()
        ids = _seed(db)
        db.commit()
        db.close()
        return ids

    def _action(ids, seq):
        _ctx(ids["studentNo"])
        svc.create_intention(SimpleNamespace(
            recordId=str(ids["internship"]), preferredCity="长沙", preferredIndustry="制造业",
            preferredCompanyId=None, preferredPositionId=None, intentionNote="希望就近实习"),
            self_service=True)

    def _count(ids):
        db = _session()
        try:
            return db.query(InternshipIntention).filter(
                InternshipIntention.tenant_id == TID,
                InternshipIntention.record_id == ids["internship"],
                InternshipIntention.status.in_(("DRAFT", "SUBMITTED")),
                InternshipIntention.is_deleted.is_(False)).count()
        finally:
            db.close()

    observed, crashes = _race_rounds(_seed_one, _action, _count)
    assert not crashes, f"意向并发输家拿到 500 而不是业务冲突：{crashes}"
    assert all(n == 1 for n in observed), (
        f"同一实习记录并发创建意向，{len(observed)} 轮各自落库条数={observed}"
        f"（出现 2 即竞态成立：两个请求都查到「没有进行中意向」，各插一条）")


# ═══════════════════════ 3. 免修/豁免（最高危，连查重都没有）═══════════════════════

def test_concurrent_exemption_grant_first_create(db_mode):
    """并发申请合规豁免：`grant_exemption()` 全程没有查重，也没有锁和唯一约束。

    与前两个不同，这里连「先查有没有」的代码都没写——并发只是让重复更快出现。
    本用例钉死当前重复数量，作为修复前后的量化对比基线。
    """
    from app.models import InternshipComplianceExemption
    from app.modules.internship.services import internship_compliance_service as svc

    def _seed_one():
        db = _session()
        ids = _seed(db)
        # 一个文件只能绑一个业务对象，两个线程必须各带各的依据文件
        # （对应现实里两个管理员各自上传材料），否则测的是文件占用而不是并发查重。
        ids["files"] = [_seed_evidence_file(db) for _ in range(2)]
        db.commit()
        db.close()
        return ids

    def _action(ids, seq):
        _admin_ctx()
        svc.grant_exemption({
            "internshipId": str(ids["internship"]), "checkCode": "SAFETY_COURSE",
            "reason": "该企业已有等效安全培训记录，申请豁免重复学习。",
            "validUntil": "2099-01-01T00:00:00",
            "evidenceFileIds": [ids["files"][seq]],
        }, user=ADMIN_USER)

    def _count(ids):
        db = _session()
        try:
            return db.query(InternshipComplianceExemption).filter(
                InternshipComplianceExemption.tenant_id == TID,
                InternshipComplianceExemption.internship_id == ids["internship"],
                InternshipComplianceExemption.check_code == "SAFETY_COURSE",
                InternshipComplianceExemption.is_deleted.is_(False)).count()
        finally:
            db.close()

    observed, crashes = _race_rounds(_seed_one, _action, _count)
    # 豁免链路会绑定依据文件（bind_file_to_business 对 FileObject 加行锁），
    # 两个线程的加锁顺序不同会撞出 MySQL 死锁(1213)，而全仓没有任何死锁重试/转译，
    # 于是直接冒成 500。落库条数与死锁是两个独立缺口，都要报出来。
    assert not crashes, (
        f"豁免并发输家拿到 500（含 MySQL 死锁 1213）而不是业务冲突：{crashes}")
    assert all(n == 1 for n in observed), (
        f"同一实习记录 + 同一检查项并发申请豁免，{len(observed)} 轮各自落库条数={observed}"
        f"（grant_exemption 无查重、无锁、无唯一约束，这是真实缺口，非测试误报）")


# ═══════════════ 4. 知情同意（有 FOR UPDATE，但索引缺 status，未知）═══════════════

def test_concurrent_consent_create_pending_first_create(db_mode):
    """两次并发创建学生知情确认任务：`create_pending()` 对 PENDING/VALID 行加了 FOR UPDATE，
    但索引 `ix_ix_consent_intern` 只到 (tenant_id, internship_id, consent_type, is_deleted)，
    不含 status——间隙锁到底挡不挡得住「首次创建、目前一条 PENDING 都没有」这个窗口，
    必须实测，不能靠"有 FOR UPDATE"四个字就认定安全。
    """
    from app.models import InternshipConsent
    from app.modules.internship.services import internship_consent_service as svc

    db = _session()
    ids = _seed(db)
    db.commit()
    db.close()

    def _do(seq):
        _admin_ctx()
        svc.create_pending({
            "internshipId": str(ids["internship"]), "consentType": "STUDENT",
            "contentSnapshot": "岗位实习安全须知正文……", "contentVersion": "v1",
        }, user=ADMIN_USER)

    ok, failed = _run_pair(_do)

    db = _session()
    try:
        rows = db.query(InternshipConsent).filter(
            InternshipConsent.tenant_id == TID,
            InternshipConsent.internship_id == ids["internship"],
            InternshipConsent.consent_type == "STUDENT",
            InternshipConsent.status.in_(("PENDING", "VALID")),
            InternshipConsent.is_deleted.is_(False)).all()
    finally:
        db.close()

    assert len(rows) == 1, (
        f"同一实习记录并发创建知情确认任务，落了 {len(rows)} 条进行中记录："
        f"成功={ok} 失败={failed}（说明间隙锁没有挡住，需要补 DB 唯一约束）")
    for seq, status, detail in failed:
        assert status != 500, f"知情同意并发输家拿到 500：seq={seq} {detail}"


# ═══════════════ 5. 特殊备案（有 FOR UPDATE，索引更松，未知）═══════════════

def test_concurrent_special_filing_create_first_create(db_mode):
    """两次并发创建同类型特殊备案：索引 `ix_ix_filing_intern` 只到
    (tenant_id, internship_id, is_deleted)，连 filing_type 都不在索引里，
    比知情同意的间隙锁覆盖面更窄，最需要实测验证。
    """
    from app.models import InternshipSpecialFiling
    from app.modules.internship.services import internship_special_filing_service as svc

    db = _session()
    ids = _seed(db)
    db.commit()
    db.close()

    def _do(seq):
        _admin_ctx()
        svc.create({
            "internshipId": str(ids["internship"]), "filingType": "OTHER",
            "triggerReason": "企业临时调整岗位安排，需补充备案说明情况。",
            "fileIds": ["f-evidence-1"],
        }, user=ADMIN_USER)

    ok, failed = _run_pair(_do)

    db = _session()
    try:
        rows = db.query(InternshipSpecialFiling).filter(
            InternshipSpecialFiling.tenant_id == TID,
            InternshipSpecialFiling.internship_id == ids["internship"],
            InternshipSpecialFiling.filing_type == "OTHER",
            InternshipSpecialFiling.status.in_(
                ("DRAFT", "PENDING_COLLEGE", "PENDING_SCHOOL", "APPROVED")),
            InternshipSpecialFiling.is_deleted.is_(False)).all()
    finally:
        db.close()

    assert len(rows) == 1, (
        f"同一实习记录并发创建同类型特殊备案，落了 {len(rows)} 条有效/办理中记录："
        f"成功={ok} 失败={failed}（说明间隙锁没有挡住，需要补 DB 唯一约束）")
    for seq, status, detail in failed:
        assert status != 500, f"特殊备案并发输家拿到 500：seq={seq} {detail}"


# ═══════════════ 6. 安全课程完成（FOR UPDATE + DB 唯一约束，回归锁）═══════════════

@pytest.fixture()
def safety_course(db_mode):
    """给安全课程完成用例单独建一门课，独立于其它五个用例共用的 _seed。"""
    from app.modules.internship.services import internship_safety_service as svc

    db = _session()
    ids = _seed(db)
    db.commit()
    db.close()
    _admin_ctx()
    course = svc.create_course({
        "batchId": str(ids["batch"]), "title": "岗前安全教育", "courseVersion": "v1",
        "contentSnapshot": "安全操作规程正文……",
    }, user=ADMIN_USER)
    ids["course"] = course["id"]
    return ids


def test_concurrent_safety_completion_start_first_create(safety_course):
    """两次并发「开始学习」同一门课：`uk_ix_safety_completion` 唯一约束 + FOR UPDATE 双重兜底，
    预期就是这条一直是绿的——留作回归锁，防止以后有人把约束或锁悄悄删掉。
    """
    from app.models import InternshipSafetyCompletion
    from app.modules.internship.services import internship_safety_service as svc

    ids = safety_course

    def _do(seq):
        _ctx(ids["studentNo"])
        svc.start_my_course(ids["course"], {"studentNo": ids["studentNo"],
                                            "userType": "STUDENT", "userId": "1"})

    ok, failed = _run_pair(_do)

    db = _session()
    try:
        rows = db.query(InternshipSafetyCompletion).filter(
            InternshipSafetyCompletion.tenant_id == TID,
            InternshipSafetyCompletion.internship_id == ids["internship"],
            InternshipSafetyCompletion.course_id == int(ids["course"]),
            InternshipSafetyCompletion.is_deleted.is_(False)).all()
    finally:
        db.close()

    assert len(rows) == 1, (
        f"同一学生并发开始同一门安全课，落了 {len(rows)} 条完成记录：成功={ok} 失败={failed}")
    for seq, status, detail in failed:
        assert status != 500, f"安全课程并发输家拿到 500：seq={seq} {detail}"
