"""演示沙箱 · 一所 20K 职业院校的专业化数据蓝图。

这不是“为了让页面不空”的平均造数，而是给 sandbox-school 固化一套可审计、可重复、
与 2026-08 售前演示时点一致的职业院校数据规模合同。

原则：
- 20,000 = 当前学校学生规模，不等于 20,000 并发；
- 年级、学院、专业、班级、师生比先自洽，再允许业务域造数；
- 热门专业多班、长尾专业少班，禁止 32 个专业完全等规模这种“压测型假学校”；
- 2026-08-13：2026 级处于迎新/报到准备，2025 级升二年级，2024 级进入三年级/岗位实习；
- 所有姓名/手机号/业务内容均为确定性虚构数据，不复制任何真实学校或真实个人数据；
- 业务域不得使用 DEMO-xxx、演示数据-xxx、9 亿 marker 关系 ID 等 generic 填空方式。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

PROFILE_CODE = "SALES_REAL_SCHOOL_20K_202608"
PROFILE_VERSION = 2
REFERENCE_DATE = "2026-08-13"

# 三届在校/准在校学生合计恰好 20,000。
GRADE_STUDENT_COUNTS: dict[str, int] = {
    "2024": 6400,
    "2025": 6600,
    "2026": 7000,
}

EXPECTED_CLASS_COUNT = 384
EXPECTED_MAJOR_COUNT = 32
EXPECTED_COLLEGE_COUNT = 8
EXPECTED_STUDENT_COUNT = 20_000
EXPECTED_CLASSES_PER_GRADE = 128

# 一所 2 万人职业院校的后台身份规模：教学、辅导员、教务、学工、实习与毕设角色都有真实选择器背景。
# 96 名辅导员对应 384 个行政班，平均 4 班/人、约 208 名学生/人；比原先 192 人更接近日常院校配置。
STAFF_ACCOUNT_COUNTS: dict[str, int] = {
    "ACADEMIC_TEACHER": 912,
    "COUNSELOR": 96,
    "ACADEMIC_ADMIN": 48,
    "STUDENT_AFFAIRS_ADMIN": 32,
    "INTERN_MENTOR": 96,
    "GD_MENTOR": 96,
}
EXPECTED_STAFF_ACCOUNT_COUNT = sum(STAFF_ACCOUNT_COUNTS.values())

# 8 个二级学院、32 个常见高职专业。学校与人员均为虚构。
COLLEGE_MAJOR_BLUEPRINT: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("C01", "信息工程学院", (
        "软件技术", "大数据技术", "计算机网络技术", "人工智能技术应用",
    )),
    ("C02", "智能制造学院", (
        "机电一体化技术", "工业机器人技术", "数控技术", "电气自动化技术",
    )),
    ("C03", "汽车工程学院", (
        "新能源汽车技术", "汽车检测与维修技术", "智能网联汽车技术", "汽车制造与试验技术",
    )),
    ("C04", "经济管理学院", (
        "电子商务", "大数据与会计", "市场营销", "现代物流管理",
    )),
    ("C05", "文化旅游学院", (
        "旅游管理", "酒店管理与数字化运营", "烹饪工艺与营养", "空中乘务",
    )),
    ("C06", "建筑工程学院", (
        "建筑工程技术", "工程造价", "建筑室内设计", "建设工程管理",
    )),
    ("C07", "医药健康学院", (
        "护理", "康复治疗技术", "婴幼儿托育服务与管理", "健康管理",
    )),
    ("C08", "艺术设计学院", (
        "数字媒体艺术设计", "广告艺术设计", "动漫设计", "视觉传达设计",
    )),
)

# 每个专业“每届”行政班数。合计 128 班/届，三届即 384 班。
# 规模刻意不均匀：软件、护理、新能源、电商等热门专业班数更多；空乘、健康管理、视觉传达等较小。
MAJOR_CLASS_COUNTS_PER_GRADE: dict[str, int] = {
    "C01M01": 6, "C01M02": 5, "C01M03": 4, "C01M04": 4,   # 信息 19
    "C02M01": 5, "C02M02": 4, "C02M03": 4, "C02M04": 4,   # 制造 17
    "C03M01": 5, "C03M02": 4, "C03M03": 4, "C03M04": 3,   # 汽车 16
    "C04M01": 5, "C04M02": 5, "C04M03": 4, "C04M04": 4,   # 经管 18
    "C05M01": 3, "C05M02": 3, "C05M03": 4, "C05M04": 3,   # 文旅 13
    "C06M01": 4, "C06M02": 4, "C06M03": 4, "C06M04": 3,   # 建筑 15
    "C07M01": 8, "C07M02": 4, "C07M03": 3, "C07M04": 3,   # 医药 18
    "C08M01": 4, "C08M02": 3, "C08M03": 3, "C08M04": 2,   # 艺设 12
}

SURNAMES = (
    "王", "李", "张", "刘", "陈", "杨", "黄", "赵", "周", "吴",
    "徐", "孙", "胡", "朱", "高", "林", "何", "郭", "马", "罗",
    "梁", "宋", "郑", "谢", "韩", "唐", "冯", "于", "董", "萧",
)
GIVEN_NAMES = (
    "子涵", "浩然", "雨桐", "宇轩", "欣怡", "梓轩", "诗涵", "嘉豪", "思雨", "俊杰",
    "可欣", "天佑", "若溪", "泽宇", "佳宁", "明轩", "语彤", "启航", "晨曦", "睿哲",
    "安然", "景行", "清妍", "博文", "雅琪", "一诺", "致远", "星辰", "书瑶", "予安",
)


@dataclass(frozen=True)
class ClassSpec:
    grade: str
    college_code: str
    college_name: str
    major_code: str
    major_name: str
    class_index: int
    class_code: str
    class_name: str
    capacity: int
    target_students: int
    graduate_year: str


def _major_specs() -> Iterable[tuple[str, str, str, str]]:
    for college_code, college_name, majors in COLLEGE_MAJOR_BLUEPRINT:
        for major_index, major_name in enumerate(majors, 1):
            yield college_code, college_name, f"{college_code}M{major_index:02d}", major_name


def _grade_class_sizes(grade: str) -> list[int]:
    """把该届学生均匀分到 128 个行政班；专业规模差异由班级数体现，班额差值最多 1 人。"""
    total = GRADE_STUDENT_COUNTS[grade]
    base, remainder = divmod(total, EXPECTED_CLASSES_PER_GRADE)
    return [base + (1 if i < remainder else 0) for i in range(EXPECTED_CLASSES_PER_GRADE)]


def iter_class_specs() -> Iterable[ClassSpec]:
    for grade in ("2024", "2025", "2026"):
        sizes = _grade_class_sizes(grade)
        class_seq = 0
        for college_code, college_name, major_code, major_name in _major_specs():
            class_count = MAJOR_CLASS_COUNTS_PER_GRADE[major_code]
            for class_index in range(1, class_count + 1):
                class_code = f"{grade}-{major_code}-{class_index:02d}"
                class_name = f"{major_name}{grade[-2:]}{class_index:02d}班"
                target = sizes[class_seq]
                class_seq += 1
                yield ClassSpec(
                    grade=grade,
                    college_code=college_code,
                    college_name=college_name,
                    major_code=major_code,
                    major_name=major_name,
                    class_index=class_index,
                    class_code=class_code,
                    class_name=class_name,
                    capacity=max(60, target + 5),
                    target_students=target,
                    graduate_year=str(int(grade) + 3),
                )
        assert class_seq == EXPECTED_CLASSES_PER_GRADE


def student_no(grade: str, seq: int) -> str:
    return f"{grade}S{seq:04d}"


def person_name(seq: int) -> str:
    surname = SURNAMES[(seq - 1) % len(SURNAMES)]
    given = GIVEN_NAMES[((seq - 1) // len(SURNAMES)) % len(GIVEN_NAMES)]
    return surname + given


def student_name(grade: str, seq: int) -> str:
    # 三条固定销售故事线：student2 仍绑定李体验；另外两位用于学工/实习深度演示。
    if grade == "2026" and seq == 1:
        return "李体验"
    if grade == "2025" and seq == 1:
        return "陈思雨"
    if grade == "2024" and seq == 1:
        return "周启航"
    return person_name((int(grade) - 2023) * 10_000 + seq)


def lifecycle_stage(grade: str, seq: int) -> str:
    """2026-08-13 时点的主档生命周期分布。"""
    if grade == "2024":
        # 三年制高职进入三年级；5,600 人已进入岗位实习，800 人仍在校做实习准备/补修。
        return "INTERN" if seq <= 5600 else "ENROLLED"
    if grade == "2025":
        return "ENROLLED"
    # 2026 级尚未正式开学：30% 已录取待处理，45% 预报到核验，25% 已完成预报到待注册。
    if seq <= 2100:
        return "ADMITTED"
    if seq <= 5250:
        return "PRE_STUDENT_VERIFIED"
    return "REGISTERED_PENDING_ENROLLMENT"


def _classes_by_college_per_grade() -> dict[str, int]:
    out: dict[str, int] = {}
    for college_code, _college_name, majors in COLLEGE_MAJOR_BLUEPRINT:
        out[college_code] = sum(
            MAJOR_CLASS_COUNTS_PER_GRADE[f"{college_code}M{index:02d}"]
            for index, _major in enumerate(majors, 1)
        )
    return out


def blueprint_summary() -> dict:
    classes = list(iter_class_specs())
    students_by_college: dict[str, int] = {}
    for college_code, _college_name, _majors in COLLEGE_MAJOR_BLUEPRINT:
        students_by_college[college_code] = sum(
            item.target_students for item in classes if item.college_code == college_code
        )
    return {
        "profile": PROFILE_CODE,
        "version": PROFILE_VERSION,
        "referenceDate": REFERENCE_DATE,
        "students": sum(GRADE_STUDENT_COUNTS.values()),
        "studentsByGrade": dict(GRADE_STUDENT_COUNTS),
        "studentsByCollege": students_by_college,
        "staffAccounts": EXPECTED_STAFF_ACCOUNT_COUNT,
        "staffByRole": dict(STAFF_ACCOUNT_COUNTS),
        "colleges": len(COLLEGE_MAJOR_BLUEPRINT),
        "majors": sum(len(x[2]) for x in COLLEGE_MAJOR_BLUEPRINT),
        "classes": len(classes),
        "classesPerGrade": EXPECTED_CLASSES_PER_GRADE,
        "classesByCollegePerGrade": _classes_by_college_per_grade(),
        "classesByMajorPerGrade": dict(MAJOR_CLASS_COUNTS_PER_GRADE),
        "classSizeMin": min(x.target_students for x in classes),
        "classSizeMax": max(x.target_students for x in classes),
        "classSizeAverage": round(EXPECTED_STUDENT_COUNT / len(classes), 2),
    }


def assert_blueprint() -> None:
    classes = list(iter_class_specs())
    assert len(COLLEGE_MAJOR_BLUEPRINT) == EXPECTED_COLLEGE_COUNT
    assert sum(len(x[2]) for x in COLLEGE_MAJOR_BLUEPRINT) == EXPECTED_MAJOR_COUNT
    assert len(MAJOR_CLASS_COUNTS_PER_GRADE) == EXPECTED_MAJOR_COUNT
    assert sum(MAJOR_CLASS_COUNTS_PER_GRADE.values()) == EXPECTED_CLASSES_PER_GRADE
    assert len(classes) == EXPECTED_CLASS_COUNT
    assert sum(x.target_students for x in classes) == EXPECTED_STUDENT_COUNT
    assert STAFF_ACCOUNT_COUNTS["COUNSELOR"] * 4 == EXPECTED_CLASS_COUNT
    for grade, expected in GRADE_STUDENT_COUNTS.items():
        grade_classes = [x for x in classes if x.grade == grade]
        assert len(grade_classes) == EXPECTED_CLASSES_PER_GRADE
        actual = sum(x.target_students for x in grade_classes)
        assert actual == expected, (grade, actual, expected)
    assert min(x.target_students for x in classes) >= 50
    assert max(x.target_students for x in classes) <= 55
    assert min(MAJOR_CLASS_COUNTS_PER_GRADE.values()) >= 2
    assert max(MAJOR_CLASS_COUNTS_PER_GRADE.values()) <= 8


assert_blueprint()
