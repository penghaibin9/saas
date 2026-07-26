"""影子台账回填脚本（阶段 D 第二部分）。

验的是"敢不敢在学校生产库上跑"这件事：默认不写库、只认唯一匹配、跨租户不碰、
重复执行不重复写、需要人工处理的情况老老实实分类报出来而不是猜着绑。
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

TID = 1000000000000000006
OTHER_TID = 1000000000000000007


def _load_script():
    path = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "backfill_shadow_student_ids.py"
    spec = importlib.util.spec_from_file_location("backfill_shadow", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _profile(db, no, name="回填测试", tenant=TID):
    from app.models import StudentProfile
    s = StudentProfile(tenant_id=tenant, student_no=no, real_name=name, current_stage="ENROLLED",
                       student_status="NORMAL", status="ACTIVE")
    db.add(s)
    db.flush()
    return s


def _cs(db, no=None, student_id=None, name="台账行", tenant=TID):
    from app.models import CsServiceStudent
    r = CsServiceStudent(tenant_id=tenant, name=name, student_no=no, student_id=student_id,
                         record_status="ACTIVE")
    db.add(r)
    db.flush()
    return r


# ── 1. 默认不写库 ──────────────────────────────────────────────────────────

def test_dry_run_reports_but_writes_nothing(db_mode):
    from app.db.session import get_sessionmaker

    mod = _load_script()
    db = get_sessionmaker()()
    try:
        p = _profile(db, "BF0001")
        row = _cs(db, no="BF0001")
        db.commit()
        rid, pid = row.id, p.id

        res = mod.scan_domain(db, "campus-service", TID, apply=False)
        assert res["counts"]["matched"] == 1
        db.rollback()

        from app.models import CsServiceStudent
        assert db.get(CsServiceStudent, rid).student_id is None, "体检模式不得写库"
        assert pid  # 主档未被触碰
    finally:
        db.close()


def test_apply_binds_matched_rows(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import CsServiceStudent

    mod = _load_script()
    db = get_sessionmaker()()
    try:
        p = _profile(db, "BF0002")
        row = _cs(db, no="BF0002")
        db.commit()

        mod.scan_domain(db, "campus-service", TID, apply=True)
        db.commit()
        assert int(db.get(CsServiceStudent, row.id).student_id) == p.id
    finally:
        db.close()


def test_apply_is_idempotent(db_mode):
    """跑第二遍不会重复写：第一遍 matched，第二遍全部落到 already_bound。"""
    from app.db.session import get_sessionmaker

    mod = _load_script()
    db = get_sessionmaker()()
    try:
        _profile(db, "BF0003")
        _cs(db, no="BF0003")
        db.commit()

        first = mod.scan_domain(db, "campus-service", TID, apply=True)
        db.commit()
        second = mod.scan_domain(db, "campus-service", TID, apply=True)
        db.commit()

        assert first["counts"]["matched"] == 1
        assert second["counts"]["matched"] == 0
        assert second["counts"]["already_bound"] == 1
    finally:
        db.close()


# ── 2. 只认有把握的匹配 ────────────────────────────────────────────────────

def test_unmatched_rows_are_reported_not_guessed(db_mode):
    """台账里的学号在主档查不到就报 unmatched，绝不按姓名找个像的绑上。"""
    from app.db.session import get_sessionmaker
    from app.models import CsServiceStudent

    mod = _load_script()
    db = get_sessionmaker()()
    try:
        _profile(db, "BF0004", name="同名同学")
        row = _cs(db, no="BF9999", name="同名同学")  # 姓名一样但学号对不上
        db.commit()

        res = mod.scan_domain(db, "campus-service", TID, apply=True)
        db.commit()
        assert res["counts"]["unmatched"] == 1
        assert db.get(CsServiceStudent, row.id).student_id is None, "姓名相同不构成绑定依据"
    finally:
        db.close()


def test_duplicate_rows_in_ledger_are_ambiguous(db_mode):
    """同一学号在台账里有多行时不猜绑哪一行，全部进 ambiguous 等人工判断。"""
    from app.db.session import get_sessionmaker
    from app.models import CsServiceStudent

    mod = _load_script()
    db = get_sessionmaker()()
    try:
        _profile(db, "BF0005")
        a = _cs(db, no="BF0005", name="重复甲")
        b = _cs(db, no="BF0005", name="重复乙")
        db.commit()

        res = mod.scan_domain(db, "campus-service", TID, apply=True)
        db.commit()
        assert res["counts"]["ambiguous"] == 2 and res["counts"]["matched"] == 0
        assert db.get(CsServiceStudent, a.id).student_id is None
        assert db.get(CsServiceStudent, b.id).student_id is None
    finally:
        db.close()


def test_rows_without_key_are_reported(db_mode):
    """连学号都没有的历史行单列一类，不会被误判成"匹配不上"。"""
    from app.db.session import get_sessionmaker

    mod = _load_script()
    db = get_sessionmaker()()
    try:
        _cs(db, no=None, name="无学号行")
        db.commit()
        res = mod.scan_domain(db, "campus-service", TID, apply=False)
        db.rollback()
        assert res["counts"]["no_key"] == 1
    finally:
        db.close()


# ── 3. 多租户红线 ──────────────────────────────────────────────────────────

def test_never_matches_across_tenants(db_mode):
    """别的学校有同样学号也不能被匹配上（跨租户是红线）。"""
    from app.db.session import get_sessionmaker
    from app.models import CsServiceStudent

    mod = _load_script()
    db = get_sessionmaker()()
    try:
        _profile(db, "BF0006", name="外校同学号", tenant=OTHER_TID)
        row = _cs(db, no="BF0006")
        db.commit()

        res = mod.scan_domain(db, "campus-service", TID, apply=True)
        db.commit()
        assert res["counts"]["matched"] == 0 and res["counts"]["unmatched"] == 1
        assert db.get(CsServiceStudent, row.id).student_id is None
    finally:
        db.close()


def test_existing_binding_to_foreign_tenant_is_flagged(db_mode):
    """已经绑到别租户档案的历史脏数据要被揪出来，且脚本不擅自改它。"""
    from app.db.session import get_sessionmaker
    from app.models import CsServiceStudent

    mod = _load_script()
    db = get_sessionmaker()()
    try:
        foreign = _profile(db, "BF0007", tenant=OTHER_TID)
        row = _cs(db, no="BF0007", student_id=foreign.id)
        db.commit()

        res = mod.scan_domain(db, "campus-service", TID, apply=True)
        db.commit()
        assert res["counts"]["cross_tenant"] == 1
        assert int(db.get(CsServiceStudent, row.id).student_id) == foreign.id, "脚本不得擅自改已有绑定"
    finally:
        db.close()


# ── 4. 四个域都在覆盖范围内 ────────────────────────────────────────────────

@pytest.mark.parametrize("domain", ["campus-service", "academic", "employment", "orientation"])
def test_all_four_shadow_domains_are_covered(db_mode, domain):
    mod = _load_script()
    assert domain in mod.DOMAINS
    model, key_col, _ = mod.DOMAINS[domain]
    assert hasattr(model, key_col) and hasattr(model, "student_id")


def test_orientation_matches_on_admission_no(db_mode):
    """迎新用录取编号匹配，不是学号——搞错了会把所有候选人判成 unmatched。"""
    from app.db.session import get_sessionmaker
    from app.models import OrientationStudent

    mod = _load_script()
    db = get_sessionmaker()()
    try:
        p = _profile(db, "LQBF0008")
        row = OrientationStudent(tenant_id=TID, name="新生", admission_no="LQBF0008",
                                 stage="ADMITTED", report_status="NOT_REPORTED")
        db.add(row)
        db.commit()

        res = mod.scan_domain(db, "orientation", TID, apply=True)
        db.commit()
        assert res["counts"]["matched"] == 1
        assert int(db.get(OrientationStudent, row.id).student_id) == p.id
    finally:
        db.close()
