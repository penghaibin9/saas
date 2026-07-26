"""把旧业务域的学生台账接回学籍主档（学生主档统一整改 阶段 D 第二部分）。

四张历史台账（在校服务 / 旧学业 / 就业 / 迎新候选人）里有大量 student_id 为空的行，
它们和 t_student_profile 之间只靠「学号一样」这条口头约定。本脚本按同租户学号唯一匹配
把 student_id 补上，之后学籍改了名字，这些台账会自动跟着变（见 student_projection_sync）。

安全口径：
- **默认只体检不写库**。要真正写入必须显式加 --apply。
- 只认「同租户 + 学号在主档里唯一命中 + 台账里该学号也唯一」的行；一对多、多对一一律不碰，
  进 ambiguous 报告让人工看。姓名相似不作为匹配依据（同名太常见，错绑比不绑更难收拾）。
- 已有 student_id 的行只做校验（是否指向本租户存在的档案），不覆盖。
- 幂等：重复执行第二次起 matched=0，不会二次写入。

用法：

    python -m scripts.backfill_shadow_student_ids                 # 全租户体检
    python -m scripts.backfill_shadow_student_ids --tenant 100..1 # 指定租户
    python -m scripts.backfill_shadow_student_ids --apply         # 确认后写入
    python -m scripts.backfill_shadow_student_ids --apply --domain campus-service
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Windows 控制台默认 GBK，中文报告会变乱码，这里强制 UTF-8 输出
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):  # 非 tty/旧解释器
    pass

from sqlalchemy import select  # noqa: E402

from app.db.session import get_sessionmaker  # noqa: E402
from app.models import (AcademicStudent, CsServiceStudent, EmpStudent, OrientationStudent,  # noqa: E402
                        StudentProfile)

# 域 → (模型, 台账里的学号列名, 展示名)
DOMAINS = {
    "campus-service": (CsServiceStudent, "student_no", "在校服务台账"),
    "academic": (AcademicStudent, "student_no", "旧学业台账"),
    "employment": (EmpStudent, "student_no", "就业台账"),
    # 迎新用录取编号，不是学号；很多候选人根本还没有学籍，匹配不上是正常的
    "orientation": (OrientationStudent, "admission_no", "迎新候选人"),
}

BUCKETS = ("matched", "already_bound", "unmatched", "ambiguous", "cross_tenant",
           "student_no_conflict", "no_key")


def _profiles_by_no(db, tenant_id: int) -> tuple[dict, set]:
    """{学号: 主档id} + 学号重复集合。重复学号一律不参与自动匹配。"""
    rows = db.execute(select(StudentProfile.student_no, StudentProfile.id).where(
        StudentProfile.tenant_id == int(tenant_id),
        StudentProfile.is_deleted.is_(False),
        StudentProfile.student_no.is_not(None))).all()
    seen, dup = {}, set()
    for no, pid in rows:
        key = str(no).strip()
        if not key:
            continue
        if key in seen:
            dup.add(key)
        seen[key] = int(pid)
    for k in dup:
        seen.pop(k, None)
    return seen, dup


def scan_domain(db, domain: str, tenant_id: int, apply: bool) -> dict:
    model, key_col, label = DOMAINS[domain]
    counts = {b: 0 for b in BUCKETS}
    details = defaultdict(list)

    by_no, dup_no = _profiles_by_no(db, tenant_id)
    rows = db.scalars(select(model).where(
        model.tenant_id == int(tenant_id), model.is_deleted.is_(False))).all()

    # 台账内部同一学号出现多行，也不能自动绑（绑哪一行都可能错）
    local_count = defaultdict(int)
    for r in rows:
        k = str(getattr(r, key_col, None) or "").strip()
        if k:
            local_count[k] += 1

    for r in rows:
        key = str(getattr(r, key_col, None) or "").strip()
        bound = getattr(r, "student_id", None)

        if bound:
            p = db.get(StudentProfile, int(bound))
            if p is None or p.is_deleted or int(p.tenant_id) != int(tenant_id):
                counts["cross_tenant"] += 1
                details["cross_tenant"].append(
                    {"rowId": int(r.id), "key": key, "boundStudentId": int(bound),
                     "why": "指向的学籍档案不存在/已删除/不属于本租户"})
            else:
                counts["already_bound"] += 1
            continue

        if not key:
            counts["no_key"] += 1
            details["no_key"].append({"rowId": int(r.id), "name": getattr(r, "name", "")})
            continue

        if key in dup_no:
            counts["student_no_conflict"] += 1
            details["student_no_conflict"].append(
                {"rowId": int(r.id), "key": key, "why": "学籍档案里该学号有多条，需先清理主档"})
            continue

        if local_count.get(key, 0) > 1:
            counts["ambiguous"] += 1
            details["ambiguous"].append(
                {"rowId": int(r.id), "key": key,
                 "why": f"本台账内同一{'录取编号' if domain == 'orientation' else '学号'}有 {local_count[key]} 行"})
            continue

        pid = by_no.get(key)
        if not pid:
            counts["unmatched"] += 1
            details["unmatched"].append({"rowId": int(r.id), "key": key,
                                         "name": getattr(r, "name", "")})
            continue

        counts["matched"] += 1
        details["matched"].append({"rowId": int(r.id), "key": key, "studentId": pid})
        if apply:
            r.student_id = pid
            r.version = int(getattr(r, "version", 0) or 0) + 1

    return {"domain": domain, "label": label, "counts": counts, "details": details}


def _tenant_ids(db, only: int | None) -> list[int]:
    if only:
        return [int(only)]
    ids = set()
    for model, _, _ in DOMAINS.values():
        ids.update(int(t) for t in db.scalars(select(model.tenant_id).distinct()).all() if t)
    return sorted(ids)


def main() -> int:
    ap = argparse.ArgumentParser(description="回填旧业务域台账的 student_id")
    ap.add_argument("--apply", action="store_true", help="真正写库（不加则只体检）")
    ap.add_argument("--tenant", type=int, default=None, help="只处理指定租户")
    ap.add_argument("--domain", choices=sorted(DOMAINS), default=None, help="只处理指定域")
    ap.add_argument("--show", type=int, default=10, help="每类明细最多打印几条")
    args = ap.parse_args()

    domains = [args.domain] if args.domain else list(DOMAINS)
    session = get_sessionmaker()
    db = session()
    total = {b: 0 for b in BUCKETS}
    try:
        tenants = _tenant_ids(db, args.tenant)
        if not tenants:
            print("没有找到任何业务台账数据，无需回填。")
            return 0
        print(f"模式：{'写入' if args.apply else '体检（不写库）'}；租户：{tenants}\n")
        for tid in tenants:
            print(f"── 租户 {tid} " + "─" * 40)
            for d in domains:
                res = scan_domain(db, d, tid, args.apply)
                c = res["counts"]
                for b in BUCKETS:
                    total[b] += c[b]
                print(f"  {res['label']:<12} " + "  ".join(f"{b}={c[b]}" for b in BUCKETS if c[b]))
                for b in ("cross_tenant", "student_no_conflict", "ambiguous", "unmatched", "no_key"):
                    for item in res["details"][b][:args.show]:
                        print(f"      [{b}] {item}")
                    extra = len(res["details"][b]) - args.show
                    if extra > 0:
                        print(f"      [{b}] …另有 {extra} 条")
        if args.apply:
            db.commit()
            print("\n已提交写入。")
        else:
            db.rollback()
            print("\n体检模式，未写入任何数据。确认无误后加 --apply 重跑。")
        print("合计：" + "  ".join(f"{b}={total[b]}" for b in BUCKETS))
        # 需要人工处理的类别不为 0 时用非零退出码，便于运维脚本发现
        return 1 if (total["cross_tenant"] or total["student_no_conflict"]) else 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
