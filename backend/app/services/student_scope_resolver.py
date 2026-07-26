"""按组织范围选学生（学生主档统一整改 阶段 E：批次选人的公共内核）。

要替掉的老做法：每开一个实习批次/毕设批次，教学秘书就导一次 Excel 名单。
同一批人被反复录入、录错、录漏，学生转班后名单也不会跟着变。

本模块提供「一条规则 → 一份学生名单」的统一解析：

    规则 = 包含（学院 / 专业 / 班级 / 年级 / 指定学生）
         - 排除（学院 / 专业 / 班级 / 指定学生）
         ∩ 学籍状态过滤
         ∩ 调用者的数据范围

规则本身只描述"要哪些人"，不含任何业务语义，所以实习、毕设、评奖、体检都能复用。
业务侧的"能不能参加"（学分、欠费、已在别的批次等）由各域的资格校验另行叠加，
本模块不猜业务规则——猜错会把不该进的人放进正式名单。

前端不要另造选择器——公共组件已齐，选人页直接用（CLAUDE.md §6.3）：

- `AppOrgCascader`（学院→专业→班级三级联动，components/common/picker）
- `AppCollegePicker` / `AppMajorPicker` / `AppClassPicker` / `AppStudentPicker`
  （entityPickers.js，均支持 multiple + 远程搜索 + 数据范围提示）

本模块的规则字段就是按这些组件的产出对齐的：组件吐 id，规则收 `collegeIds`/`majorIds`/
`classIds`/`studentIds`，排除项同名加 `exclude` 前缀，前后端不需要再做一层字段映射。

已知两处缺口（建到选人页时要先补，且应补在公共层而不是页面里）：

1. 喂数据的 adapter 只有教务有（`academicAffairsPickerAdapters` 里的
   `orgCascade/college/major/class`）；学工与实习/毕设的 adapter 集合里没有这几个 key，
   直接把组件放进实习页会是空下拉。
2. 现有两个组织树接口的权限都不匹配选人场景：`/system/org-tree` 要
   `systemAdmin.org.view`，教务的 `/orgs/tree` 要教务权限，而选人的是实习管理员／学院管理员。
   需要一个按调用者数据范围返回的公共组织树端点，别让业务方各自复制一份。

另：年级没有现成组件，但年级是主档上的字符串枚举，用 `AppSelect` + 后端 distinct 即可，
不必为它新造 picker。

三条硬口径：

1. **数据范围先收敛再返回**。学院管理员即使把规则写成"全校"，也只会拿到本院学生；
   被裁掉多少人如实返回（outOfScopeCount），不静默吞掉。
2. **只认在籍在读**。默认排除已作废、已毕业、已离校的档案，避免把毕业生拉进新批次。
3. **结果去重**。同时选了"计算机学院"和"计算2401班"不会让同一个学生出现两次。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import or_, select

from app.core.exceptions import AppException

# 默认参与批次的生命周期阶段：在读 / 毕业年级 / 已在实习。
# 新生（ADMITTED 等）还没正式注册，毕业离校（GRADUATED/ALUMNI）已不在校，都不该被批量选中。
DEFAULT_STAGES = ("ENROLLED", "GRADUATING", "INTERN")

# 学生状态：只要正常在籍的。MERGED（重复档已合并）/RECYCLED（已回收）不参与。
DEFAULT_STUDENT_STATUSES = ("NORMAL",)

MAX_PREVIEW_ROWS = 2000


@dataclass
class ScopeRule:
    """结构化选人规则。全空 = 不选任何人（不是"选全部"，避免误操作一键全校）。"""

    college_ids: set[int] = field(default_factory=set)
    major_ids: set[int] = field(default_factory=set)
    class_ids: set[int] = field(default_factory=set)
    student_ids: set[int] = field(default_factory=set)
    grades: set[str] = field(default_factory=set)

    exclude_college_ids: set[int] = field(default_factory=set)
    exclude_major_ids: set[int] = field(default_factory=set)
    exclude_class_ids: set[int] = field(default_factory=set)
    exclude_student_ids: set[int] = field(default_factory=set)

    stages: tuple[str, ...] = DEFAULT_STAGES
    student_statuses: tuple[str, ...] = DEFAULT_STUDENT_STATUSES

    def is_empty(self) -> bool:
        return not (self.college_ids or self.major_ids or self.class_ids
                    or self.student_ids or self.grades)

    def to_dict(self) -> dict:
        """落库/回显用。集合转有序列表，保证同一规则的存储表示稳定可比。"""
        return {
            "collegeIds": sorted(self.college_ids),
            "majorIds": sorted(self.major_ids),
            "classIds": sorted(self.class_ids),
            "studentIds": sorted(self.student_ids),
            "grades": sorted(self.grades),
            "excludeCollegeIds": sorted(self.exclude_college_ids),
            "excludeMajorIds": sorted(self.exclude_major_ids),
            "excludeClassIds": sorted(self.exclude_class_ids),
            "excludeStudentIds": sorted(self.exclude_student_ids),
            "stages": list(self.stages),
            "studentStatuses": list(self.student_statuses),
        }


def _ids(raw, field_name: str) -> set[int]:
    out = set()
    for v in (raw or []):
        if v in (None, "", 0, "0"):
            continue
        try:
            out.add(int(v))
        except (TypeError, ValueError):
            raise AppException("VALIDATION_ERROR", f"{field_name} 含非法 id：{v!r}")
    return out


def _strs(raw) -> set[str]:
    return {str(v).strip() for v in (raw or []) if str(v or "").strip()}


def parse_rule(body: dict | None) -> ScopeRule:
    """把前端/数据库里的 JSON 规则转成 ScopeRule，非法 id 直接报错而不是忽略。

    忽略非法值会让"我明明选了 3 个班怎么只出 2 个班"变成无法排查的玄学问题。
    """
    b = body or {}
    # 排序后再转 tuple：_strs 返回集合，直接转会让同一份规则每次落库的顺序都不一样，
    # 「这个批次的选人规则改过没有」就无从比对（冻结前后对账要靠它）。
    stages = tuple(sorted(_strs(b.get("stages")))) or DEFAULT_STAGES
    statuses = tuple(sorted(_strs(b.get("studentStatuses")))) or DEFAULT_STUDENT_STATUSES
    return ScopeRule(
        college_ids=_ids(b.get("collegeIds"), "collegeIds"),
        major_ids=_ids(b.get("majorIds"), "majorIds"),
        class_ids=_ids(b.get("classIds"), "classIds"),
        student_ids=_ids(b.get("studentIds"), "studentIds"),
        grades=_strs(b.get("grades")),
        exclude_college_ids=_ids(b.get("excludeCollegeIds"), "excludeCollegeIds"),
        exclude_major_ids=_ids(b.get("excludeMajorIds"), "excludeMajorIds"),
        exclude_class_ids=_ids(b.get("excludeClassIds"), "excludeClassIds"),
        exclude_student_ids=_ids(b.get("excludeStudentIds"), "excludeStudentIds"),
        stages=stages, student_statuses=statuses)


@dataclass
class ScopeResolveResult:
    students: list = field(default_factory=list)        # StudentProfile 列表（已去重、已排序）
    matched_count: int = 0                              # 规则命中且在数据范围内的人数
    excluded_count: int = 0                             # 被排除项剔掉的人数
    out_of_scope_count: int = 0                         # 被调用者数据范围裁掉的人数
    truncated: bool = False                             # 是否超过预览上限被截断

    def summary(self) -> dict:
        return {"matchedCount": self.matched_count, "excludedCount": self.excluded_count,
                "outOfScopeCount": self.out_of_scope_count, "truncated": self.truncated}


def _scope_filter(user):
    """调用者的数据范围。返回 (class_ids, student_ids)，None 表示该维度不限。"""
    from app.core.affairs_security import student_directory_scope
    if user is None:
        return None, None      # 内部调用（脚本/定时任务）不做人身份收敛
    return student_directory_scope(user)


def resolve(db, tenant_id: int, rule: ScopeRule, *, user: dict | None = None,
            limit: int | None = MAX_PREVIEW_ROWS) -> ScopeResolveResult:
    """解析规则得到学生名单。

    user 传当前登录人时按其数据范围收敛（页面预览/冻结都必须传）；
    传 None 表示系统内部调用，不做人身份收敛（脚本、迁移、定时任务）。
    """
    from app.models import StudentProfile

    result = ScopeResolveResult()
    if rule.is_empty():
        return result       # 没选任何范围就是没选人，绝不退化成"全校"

    conds = [StudentProfile.tenant_id == int(tenant_id),
             StudentProfile.is_deleted.is_(False)]
    if rule.stages:
        conds.append(StudentProfile.current_stage.in_(list(rule.stages)))
    if rule.student_statuses:
        conds.append(StudentProfile.student_status.in_(list(rule.student_statuses)))

    # 包含项之间是"或"：选了整个学院，又单独点了外院某个学生，两边都要
    includes = []
    if rule.college_ids:
        includes.append(StudentProfile.college_id.in_(list(rule.college_ids)))
    if rule.major_ids:
        includes.append(StudentProfile.major_id.in_(list(rule.major_ids)))
    if rule.class_ids:
        includes.append(StudentProfile.class_id.in_(list(rule.class_ids)))
    if rule.student_ids:
        includes.append(StudentProfile.id.in_(list(rule.student_ids)))
    if rule.grades:
        includes.append(StudentProfile.grade.in_(list(rule.grades)))
    conds.append(or_(*includes))

    rows = db.scalars(select(StudentProfile).where(*conds)
                      .order_by(StudentProfile.class_id, StudentProfile.student_no)).all()

    # 排除项：按学院/专业/班级/学生逐条剔除
    kept = []
    for s in rows:
        if (s.id in rule.exclude_student_ids
                or (s.college_id and int(s.college_id) in rule.exclude_college_ids)
                or (s.major_id and int(s.major_id) in rule.exclude_major_ids)
                or (s.class_id and int(s.class_id) in rule.exclude_class_ids)):
            result.excluded_count += 1
            continue
        kept.append(s)

    # 数据范围收敛：放在排除之后，这样"被排除"和"没权限看"两个数字互不污染
    allow_classes, allow_students = _scope_filter(user)
    if allow_classes is not None or allow_students is not None:
        in_scope = []
        for s in kept:
            ok = ((allow_classes is not None and s.class_id
                   and int(s.class_id) in allow_classes)
                  or (allow_students is not None and int(s.id) in allow_students))
            if ok:
                in_scope.append(s)
            else:
                result.out_of_scope_count += 1
        kept = in_scope

    result.matched_count = len(kept)
    if limit and len(kept) > limit:
        result.truncated = True
        kept = kept[:limit]
    result.students = kept
    return result


def preview_rows(db, students, tenant_id: int) -> list[dict]:
    """把学生列表渲染成预览表格行。只出非敏感字段——选人页不需要手机号/身份证。"""
    from app.models.org import College, Major, SchoolClass

    cache: dict = {}

    def _name(model, oid):
        if not oid:
            return ""
        key = (model.__name__, int(oid))
        if key not in cache:
            row = db.get(model, oid)
            cache[key] = "" if row is None else (
                getattr(row, "college_name", None) or getattr(row, "major_name", None)
                or getattr(row, "class_name", None) or "")
        return cache[key]

    return [{
        "studentId": str(s.id),
        "studentNo": s.student_no or "",
        "name": s.real_name,
        "gender": s.gender or "",
        "grade": s.grade or "",
        "collegeName": _name(College, s.college_id),
        "majorName": _name(Major, s.major_id),
        "className": _name(SchoolClass, s.class_id),
        "currentStage": s.current_stage,
        "studentStatus": s.student_status,
    } for s in students]


def resolve_preview(db, tenant_id: int, body: dict | None, *, user: dict | None = None) -> dict:
    """接口层直接可用：规则 JSON → {rule, rows, summary}。"""
    rule = parse_rule(body)
    res = resolve(db, tenant_id, rule, user=user)
    return {"rule": rule.to_dict(), "rows": preview_rows(db, res.students, tenant_id),
            **res.summary()}
