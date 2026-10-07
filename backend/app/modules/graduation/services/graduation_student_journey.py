"""学生毕业设计「办理进度 + 当前要做」统一派生（学生 PC 与小程序共用）。

此前小程序按 stage 写死主任务、学生 PC 在前端按记录自行计算，两端经常给出不同的“当前要做”。
这里只做纯函数派生：输入为各环节学生本人视图（与 /mobile/graduation/* 返回一致），
输出 8 个有序步骤及唯一的当前步骤。不访问数据库、不改变任何状态，便于单测。

步骤 state：
- done     已完成
- todo     需要学生本人操作（会带 actionLabel）
- waiting  已提交/等待学校或导师处理
- blocked  出现问题需要学生联系导师/学校（如中期不通过）
- locked   前置环节未完成，尚未开始
"""
from __future__ import annotations

from typing import Any

STEP_TITLES = [
    ("topic", "选题"),
    ("taskbook", "任务书确认"),
    ("proposal", "开题报告"),
    ("guidance", "过程指导"),
    ("midterm", "中期检查"),
    ("final", "论文提交"),
    ("defense", "答辩"),
    ("grade", "成绩与归档"),
]

_TONE = {"done": "success", "todo": "primary", "waiting": "warning", "blocked": "danger", "locked": "default"}


def _d(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _step(key: str, state: str, status: str, detail: str = "", action: str = "",
          *, returned: bool = False, comment: str = "") -> dict:
    order = [k for k, _ in STEP_TITLES].index(key) + 1
    title = dict(STEP_TITLES)[key]
    tone = "danger" if returned else _TONE[state]
    return {
        "key": key, "order": order, "title": title, "state": state, "tone": tone,
        "statusText": status, "detail": detail, "comment": comment or "",
        "returned": bool(returned), "actionLabel": action if state == "todo" else "",
    }


def _topic_step(my: dict, round_: dict | None) -> dict:
    if my.get("hasTopic") or my.get("topicId"):
        advisor = my.get("advisorName") or ""
        return _step("topic", "done", "课题已确定",
                     f"{my.get('topicTitle') or ''}{('，指导教师 ' + advisor) if advisor else ''}")
    if round_:
        choices = round_.get("myChoices") or []
        if any(str(c.get("status") or "").upper() == "PENDING" for c in choices):
            return _step("topic", "waiting", "志愿已提交，等待确认",
                         "导师或管理员确认后课题即确定；确认前可以退选重填。")
        return _step("topic", "todo", "选题轮次已开放",
                     f"{round_.get('roundName') or '当前轮次'}：请从题目库选择志愿并提交。", "去选题")
    return _step("topic", "waiting", "等待学校开放选题", "学校开放选题轮次后，这里会提醒你去选题。")


def _taskbook_step(tb: dict, topic_done: bool) -> dict:
    status = str(tb.get("status") or "").upper()
    if status == "CONFIRMED":
        return _step("taskbook", "done", "已确认", f"任务书第 {tb.get('taskbookVersion') or 1} 版")
    if tb.get("hasData") and status in ("PENDING_CONFIRM", "CHANGE_PENDING"):
        detail = "导师修改了任务书，请重新阅读并确认。" if status == "CHANGE_PENDING" else "请阅读导师下达的任务书并确认。"
        return _step("taskbook", "todo", "待你确认", detail, "去确认任务书")
    if not topic_done:
        return _step("taskbook", "locked", "未开始", "课题确定后，导师会下达任务书。")
    return _step("taskbook", "waiting", "等待导师下达", tb.get("message") or "导师尚未下达任务书。")


def _proposal_step(pp: dict, tb_done: bool) -> dict:
    latest = _d(pp.get("latest"))
    status = str(latest.get("status") or "").upper()
    if status == "APPROVED":
        return _step("proposal", "done", "已通过", f"开题报告 {latest.get('version') or ''}".strip())
    if pp.get("canSubmit"):
        if status == "REJECTED":
            return _step("proposal", "todo", "被退回，需修改后重交", "请按导师意见修改后重新提交。",
                         "修改并重交开题报告", returned=True, comment=latest.get("reviewComment") or "")
        return _step("proposal", "todo", "待提交", "填写选题背景、研究方案并上传开题报告。", "去提交开题报告")
    if status == "PENDING_REVIEW":
        return _step("proposal", "waiting", "已提交，等待导师审阅", f"当前版本 {latest.get('version') or ''}".strip())
    if not tb_done:
        return _step("proposal", "locked", "未开始", "确认任务书后即可提交开题报告。")
    return _step("proposal", "waiting", "暂不能提交", pp.get("reason") or "请联系指导教师确认开题安排。")



def _guidance_step(my: dict, proposal_done: bool) -> dict:
    logs = my.get("guideLogs") or []
    if logs:
        return _step("guidance", "done", f"已有 {len(logs)} 条指导记录",
                     (logs[0].get("text") or "")[:60] if isinstance(logs[0], dict) else "")
    if not proposal_done:
        return _step("guidance", "locked", "未开始", "开题通过后进入过程指导。")
    # 过程指导由导师记录，学生无需在系统里操作，因此不会成为“当前要做”。
    return _step("guidance", "done", "进行中", "请按任务书计划主动与指导教师沟通，导师会记录指导情况。")


def _midterm_step(mt: dict, proposal_done: bool) -> dict:
    status = str(mt.get("status") or "").upper()
    if status in ("CHECKED_PASS", "RECTIFIED_PASS"):
        return _step("midterm", "done", "已通过", mt.get("checkComment") or "")
    if status == "RECTIFYING":
        deadline = mt.get("rectifyDeadline") or ""
        return _step("midterm", "todo", "需要整改",
                     f"请按导师意见提交整改说明{('，截止 ' + str(deadline)[:10]) if deadline else ''}。",
                     "去提交整改", returned=True, comment=mt.get("checkComment") or "")
    if status == "RECTIFY_SUBMITTED":
        return _step("midterm", "waiting", "整改已提交，等待复核")
    if status == "CHECKED_FAIL":
        return _step("midterm", "blocked", "中期检查未通过", "请尽快联系指导教师确认后续安排。",
                     comment=mt.get("checkComment") or "")
    if not proposal_done:
        return _step("midterm", "locked", "未开始", "开题通过后由导师进行中期检查。")
    return _step("midterm", "waiting", "等待导师检查", "导师完成中期检查后会在这里显示结论。")


def _final_step(fn: dict, midterm_done: bool) -> dict:
    items = fn.get("items") or []
    latest = _d(items[0]) if items else {}
    rejected_comment = (latest.get("reviewComment") or "") if str(latest.get("status") or "").upper() == "REJECTED" else ""
    if fn.get("finalApproved"):
        return _step("final", "done", "定稿已通过", f"查重 {latest.get('plagiarismRate') or '—'}")
    rejected = str(latest.get("status") or "").upper() == "REJECTED"
    if fn.get("canSubmitFinal"):
        return _step("final", "todo", "被退回，需重交定稿" if rejected else "初稿已通过，请提交定稿",
                     "上传论文定稿（PDF 或 Word）。", "去提交定稿", returned=rejected,
                     comment=rejected_comment)
    if fn.get("canSubmitDraft"):
        return _step("final", "todo", "被退回，需重交初稿" if rejected else "可以提交论文初稿",
                     "上传论文初稿（PDF 或 Word），手机和电脑都可以提交。", "去提交初稿", returned=rejected,
                     comment=rejected_comment)
    if items and str(latest.get("status") or "").upper() == "PENDING_REVIEW":
        return _step("final", "waiting", f"{latest.get('type') or '论文'}已提交，等待导师批阅")
    if not midterm_done:
        return _step("final", "locked", "未开始", "中期检查通过后即可提交论文。")
    return _step("final", "waiting", "暂不能提交", fn.get("hint") or "请联系指导教师。")


def _defense_step(df: dict, final_done: bool, grade_published: bool) -> dict:
    if grade_published:
        return _step("defense", "done", "答辩已完成")
    if df.get("published"):
        where = " · ".join(str(x) for x in (df.get("date"), df.get("location")) if x)
        return _step("defense", "waiting", "答辩安排已发布", where or "请按学校通知参加答辩。")
    if not final_done:
        return _step("defense", "locked", "未开始", "论文定稿通过后由学校安排答辩。")
    return _step("defense", "waiting", "等待学校安排答辩", df.get("message") or "")


def _grade_step(gr: dict, ar: dict) -> dict:
    if gr.get("published"):
        appeal = _d(gr.get("latestAppeal"))
        if str(appeal.get("status") or "").upper() == "PENDING":
            return _step("grade", "waiting", "成绩申诉复核中", appeal.get("reason") or "")
        filed = str(ar.get("status") or "").upper() == "FILED"
        return _step("grade", "done", "已归档" if filed else "成绩已发布",
                     f"综合成绩 {gr.get('totalScore') if gr.get('totalScore') is not None else '—'} 分"
                     f"{('（' + str(gr.get('gradeLevel')) + '）') if gr.get('gradeLevel') else ''}")
    return _step("grade", "locked", "未发布", "答辩结束后由学校统一发布成绩。")


_STAGE_RANK = {
    "TOPIC_SELECTING": 0, "TASKBOOK_CONFIRM": 1, "GUIDING": 2, "MIDTERM": 4,
    "FINAL_CHECK": 5, "DEFENSE": 6, "COMPLETED": 7, "ARCHIVED": 7,
}


# 读取失败的环节 → 对应步骤；archive 只影响“已归档/成绩已发布”文案，不单独标记。
_SECTION_STEP = {
    "round": "topic", "taskbook": "taskbook", "proposal": "proposal", "midterm": "midterm",
    "final": "final", "defense": "defense", "grade": "grade",
}


def _load_failed_step(key: str) -> dict:
    step = _step(key, "waiting", "暂时无法读取", "该环节数据读取失败，请稍后下拉刷新重试；如持续失败请联系学校管理员。")
    step["tone"] = "default"
    step["loadFailed"] = True
    return step


def build_journey(*, my: dict, round_: dict | None = None, taskbook: dict | None = None,
                  proposal: dict | None = None, midterm: dict | None = None, final: dict | None = None,
                  defense: dict | None = None, grade: dict | None = None, archive: dict | None = None,
                  failed=()) -> dict:
    """根据学生本人各环节视图派生有序步骤和唯一“当前要做”。

    failed：读取失败的环节名。对应步骤如实显示“暂时无法读取”，不能用空数据推出“等待/未开始”等假状态。
    """
    my, tb, pp, mt, fn, df, gr, ar = (_d(x) for x in (my, taskbook, proposal, midterm, final, defense, grade, archive))
    if not my.get("hasData"):
        return {"hasData": False, "steps": [], "current": None, "doneCount": 0, "total": len(STEP_TITLES),
                "message": my.get("message") or "你暂无毕业设计记录"}
    rank = _STAGE_RANK.get(str(my.get("stage") or "").upper(), 0)

    steps = [_topic_step(my, round_ if isinstance(round_, dict) else None)]
    steps.append(_taskbook_step(tb, steps[0]["state"] == "done" or rank >= 1))
    steps.append(_proposal_step(pp, steps[1]["state"] == "done" or rank >= 2))
    proposal_done = steps[2]["state"] == "done" or rank >= 4
    steps.append(_guidance_step(my, proposal_done))
    steps.append(_midterm_step(mt, proposal_done))
    midterm_done = steps[4]["state"] == "done" or rank >= 5
    steps.append(_final_step(fn, midterm_done))
    final_done = steps[5]["state"] == "done" or rank >= 6
    steps.append(_defense_step(df, final_done, bool(gr.get("published"))))
    steps.append(_grade_step(gr, ar))

    failed_steps = {_SECTION_STEP[name] for name in (failed or ()) if name in _SECTION_STEP}
    for index, step in enumerate(steps):
        if step["key"] in failed_steps and not (step["key"] == "topic" and step["state"] == "done"):
            steps[index] = _load_failed_step(step["key"])

    # 学校导入的历史档案可能已处于后续阶段但缺少前置记录：阶段已越过的环节不再显示为“等待/未开始”。
    for index, step in enumerate(steps):
        if index < rank and step["state"] in ("waiting", "locked"):
            steps[index] = _step(step["key"], "done", "已完成")

    current = (
        next((s for s in steps if s["state"] == "todo"), None)
        or next((s for s in steps if s["state"] == "blocked"), None)
        or next((s for s in steps if s["state"] == "waiting"), None)
        or steps[-1]
    )
    return {
        "hasData": True,
        "stage": my.get("stage") or "",
        "steps": steps,
        "current": current,
        "doneCount": sum(1 for s in steps if s["state"] == "done"),
        "total": len(steps),
    }
