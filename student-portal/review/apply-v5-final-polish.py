"""Apply the final, screenshot-proven Student Portal V5 polish fixes.

Every replacement must match exactly once. No fuzzy edits and no backend files.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace_once(path: str, old: str, new: str) -> None:
    file_path = ROOT / path
    content = file_path.read_text(encoding="utf-8")
    count = content.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, got {count}: {old[:120]!r}")
    file_path.write_text(content.replace(old, new, 1), encoding="utf-8")
    print(f"updated {path}")


# 首页消息速览仍可能包含后端内部状态词。
replace_once(
    "student-portal/src/views/home/HomeView.vue",
    "<div class=\"home-message__title\" :style=\"{ fontWeight: m.read ? 500 : 750 }\">{{ m.title }}</div>",
    "<div class=\"home-message__title\" :style=\"{ fontWeight: m.read ? 500 : 750 }\">{{ displayMessageText(m.title) }}</div>",
)
replace_once(
    "student-portal/src/views/home/HomeView.vue",
    "const STATUS_LABELS = { CHECKED_IN: '已报到', ONBOARD: '进行中', DONE: '已完成', NORMAL: '正常', SIGNED: '已签约', WARNING: '预警', PENDING: '待处理', PROCESSING: '进行中', APPROVED: '已通过', VERIFIED: '已核验', UNEMPLOYED: '暂未就业', EMPLOYED: '已就业', JOB_SEEKING: '求职中', NOT_STARTED: '尚未开始' }",
    "const MESSAGE_STATUS_TEXT = { PENDING_REVIEW: '待审核', SUBMITTED: '已提交', RETURNED: '已退回', REJECTED: '未通过', APPROVED: '已通过', PROCESSING: '处理中', COMPLETED: '已完成', CLASS_REVIEW: '班级审核中', COLLEGE_REVIEW: '学院审核中', SCHOOL_REVIEW: '学校审核中' }\nconst STATUS_LABELS = { CHECKED_IN: '已报到', ONBOARD: '进行中', DONE: '已完成', NORMAL: '正常', SIGNED: '已签约', WARNING: '预警', PENDING: '待处理', PROCESSING: '进行中', APPROVED: '已通过', VERIFIED: '已核验', UNEMPLOYED: '暂未就业', EMPLOYED: '已就业', JOB_SEEKING: '求职中', NOT_STARTED: '尚未开始' }",
)
replace_once(
    "student-portal/src/views/home/HomeView.vue",
    "function statusLabel(s) {\n  const raw = String(s || '').trim()",
    "function displayMessageText(value) {\n  let text = String(value || '')\n  for (const [key, label] of Object.entries(MESSAGE_STATUS_TEXT)) text = text.replaceAll(key, label)\n  return text || '系统通知'\n}\nfunction statusLabel(s) {\n  const raw = String(s || '').trim()",
)

# 毕设开题记录版本改为学生可读的“第 N 版”。
replace_once(
    "student-portal/src/views/graduation/GraduationWorkbenchView.vue",
    "detail: proposal.value.latest ? `当前版本 ${proposal.value.latest.version || '—'}` : (proposal.value.reason || '请在课题确认后提交开题报告。'),",
    "detail: proposal.value.latest ? `当前为第 ${proposal.value.latest.version || '—'} 版` : (proposal.value.reason || '请在课题确认后提交开题报告。'),",
)

# 弱文本略加深，满足白底常规正文对比度。
replace_once(
    "student-portal/src/App.vue",
    "'--t3': dark ? '#adb9cf' : '#65728a',\n    '--t4': dark ? '#91a0ba' : '#718097',",
    "'--t3': dark ? '#adb9cf' : '#58667d',\n    '--t4': dark ? '#91a0ba' : '#5f6d82',",
)

# 对比度工具：渐变背景不再错误回落到页面浅色底；可滚动宽表不记为越界。
replace_once(
    "student-portal/review/review-lib.mjs",
    "      const r = el.getBoundingClientRect()\n      const outsideViewport = r.left < -2 || r.right > vw + 2\n      return outsideViewport ? [{ cls: String(el.className || '').slice(0, 140), ...rect(el) }] : []",
    "      const r = el.getBoundingClientRect()\n      let parent = el.parentElement\n      let containedByScroller = false\n      while (parent) {\n        const parentStyle = getComputedStyle(parent)\n        if (['auto', 'scroll'].includes(parentStyle.overflowX) && parent.scrollWidth > parent.clientWidth + 4) {\n          containedByScroller = true\n          break\n        }\n        parent = parent.parentElement\n      }\n      const outsideViewport = r.left < -2 || r.right > vw + 2\n      return outsideViewport && !containedByScroller ? [{ cls: String(el.className || '').slice(0, 140), ...rect(el) }] : []",
)
replace_once(
    "student-portal/review/review-lib.mjs",
    "      while (current) {\n        const rgba = parseRgb(getComputedStyle(current).backgroundColor)\n        if (rgba && rgba[3] >= .92) return rgba\n        current = current.parentElement\n      }",
    "      while (current) {\n        const currentStyle = getComputedStyle(current)\n        if (currentStyle.backgroundImage && currentStyle.backgroundImage !== 'none') return null\n        const rgba = parseRgb(currentStyle.backgroundColor)\n        if (rgba && rgba[3] >= .92) return rgba\n        current = current.parentElement\n      }",
)

# 1024px 学业预警必须保留代表截图，便于人工确认滚动容器。
replace_once(
    "student-portal/review/v5-review-config.json",
    '"/academic/exam",\n    "/campus-service",',
    '"/academic/exam",\n    "/academic/warning",\n    "/campus-service",',
)

print("all asserted final V5 polish fixes applied")
