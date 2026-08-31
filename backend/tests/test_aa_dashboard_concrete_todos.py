"""V8.1 教务首页具体待办纯合同测试（不依赖共享 MySQL DDL）。"""


def test_concrete_todos_keep_counts_and_exact_business_targets():
    from app.modules.academic_affairs.services.academic_affairs_service import _todos

    grade = {
        "counts": {"SUBMITTED": 1, "RETURNED": 1},
        "reviewTasks": [{
            "gradeTaskId": "701", "courseName": "数据库原理", "className": "软件2601",
            "teacherKey": "T-01", "status": "SUBMITTED", "deadline": "2026-09-03",
            "recentChange": "2026-08-31T08:00:00 · 学院审核中",
        }],
        "pendingTasks": [{
            "gradeTaskId": "702", "courseName": "Web 开发", "className": "软件2601",
            "teacherKey": "T-02", "status": "RETURNED", "statusLabel": "已退回",
            "enteredCount": 30, "rosterCount": 32, "deadline": "2026-09-02",
            "recentChange": "2026-08-31T09:00:00 · 已退回",
        }],
    }
    status = {"count": 1, "items": [{
        "changeId": "801", "studentName": "张同学", "changeType": "SUSPEND",
        "changeTypeLabel": "休学", "currentNode": "COLLEGE_REVIEW", "deadline": "",
        "recentChange": "2026-08-31T10:00:00 · 流转至 COLLEGE_REVIEW",
        "exactRoute": "/admin/academic-affairs/status-changes/801",
    }]}
    warnings = {"count": 1, "items": [{
        "warningId": "901", "studentName": "李同学", "level": "HIGH", "reason": "连续两门不及格",
        "owner": "王辅导员", "deadline": "2026-09-05", "recentChange": "2026-08-31T11:00:00 · 待处置",
        "exactRoute": "/admin/academic-affairs/warnings/console?tab=followup&warningId=901",
    }]}
    graduation = {"count": 1, "items": [{
        "resultId": "1001", "studentName": "赵同学", "batchName": "2026届毕业审核",
        "status": "SYSTEM_ABNORMAL", "deadline": "", "recentChange": "2026-08-31T12:00:00 · SYSTEM_ABNORMAL",
        "exactRoute": "/admin/academic-affairs/graduation/audit-console?tab=reason&batchId=11&resultId=1001",
    }]}

    groups = {item["key"]: item for item in _todos(grade, status, warnings, graduation)}

    assert groups["gradeReview"]["count"] == 1
    assert groups["gradeLagging"]["count"] == 1
    assert groups["statusChangeReview"]["count"] == 1
    assert groups["warningHandle"]["count"] == 1
    assert groups["graduationReview"]["count"] == 1
    required = {"businessId", "entityType", "title", "reason", "ownerRole", "deadline",
                "recentChange", "primaryAction", "nextStep", "exactRoute"}
    for group in groups.values():
        assert group["items"], group["key"]
        assert required.issubset(group["items"][0])
    assert groups["gradeReview"]["items"][0]["exactRoute"].endswith("taskId=701")
    assert groups["gradeLagging"]["items"][0]["exactRoute"].endswith("taskId=702")
    assert groups["warningHandle"]["items"][0]["ownerRole"] == "王辅导员"
