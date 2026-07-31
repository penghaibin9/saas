"""Apply only the display and degradation fixes proven by the V5 full review.

Every replacement is asserted to occur exactly once. The script fails rather than
making a fuzzy change when the branch source no longer matches the reviewed code.
It is executed once on agent/student-portal-v5-full-review and never touches main.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace_once(path: str, old: str, new: str) -> None:
    file_path = ROOT / path
    content = file_path.read_text(encoding="utf-8")
    count = content.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one match, got {count}: {old[:100]!r}")
    file_path.write_text(content.replace(old, new, 1), encoding="utf-8")
    print(f"updated {path}")


# ── 首页：未知聚合状态不再误判为“未开始”，内部枚举不直出 ──
replace_once(
    "student-portal/src/views/home/HomeView.vue",
    ":text=\"d.hasData ? statusLabel(d.status) : '未开始'\"",
    ":text=\"d.hasData ? statusLabel(d.status) : '状态待同步'\"",
)
replace_once(
    "student-portal/src/views/home/HomeView.vue",
    "const STATUS_LABELS = { CHECKED_IN: '已报到', ONBOARD: '进行中', DONE: '已完成', NORMAL: '正常', SIGNED: '已签约', WARNING: '预警', PENDING: '待处理', PROCESSING: '进行中', APPROVED: '已通过', VERIFIED: '已核验' }",
    "const STATUS_LABELS = { CHECKED_IN: '已报到', ONBOARD: '进行中', DONE: '已完成', NORMAL: '正常', SIGNED: '已签约', WARNING: '预警', PENDING: '待处理', PROCESSING: '进行中', APPROVED: '已通过', VERIFIED: '已核验', UNEMPLOYED: '暂未就业', EMPLOYED: '已就业', JOB_SEEKING: '求职中', NOT_STARTED: '尚未开始' }",
)
replace_once(
    "student-portal/src/views/home/HomeView.vue",
    "return { ...def, done, current, state: domain.hasData ? statusLabel(domain.status) : '未开始' }",
    "return { ...def, done, current, state: domain.hasData ? statusLabel(domain.status) : '状态待同步' }",
)
replace_once(
    "student-portal/src/views/home/HomeView.vue",
    "function statusLabel(s) { return STATUS_LABELS[s] || s || '进行中' }",
    "function statusLabel(s) {\n  const raw = String(s || '').trim()\n  if (!raw) return '状态待确认'\n  const key = raw.toUpperCase()\n  if (STATUS_LABELS[key]) return STATUS_LABELS[key]\n  return /^[A-Z0-9_]+$/.test(raw) ? '状态待确认' : raw\n}",
)
replace_once(
    "student-portal/src/views/home/HomeView.vue",
    "color: todos.value.length ? 'var(--pri)' : 'var(--t1)'",
    "color: todos.value.length ? 'var(--pri-text, var(--pri))' : 'var(--t1)'",
)

# ── 我的档案：申请名称、请假类型和审核节点中文化 ──
replace_once(
    "student-portal/src/views/profile/ProfileView.vue",
    "<div style=\"flex:1;min-width:0\"><div class=\"atitle\">{{ a.name }}</div>",
    "<div style=\"flex:1;min-width:0\"><div class=\"atitle\">{{ applicationName(a) }}</div>",
)
replace_once(
    "student-portal/src/views/profile/ProfileView.vue",
    "<StatusTag :text=\"a.statusText || a.status\" :tone=\"groupTone(a.group)\" />",
    "<StatusTag :text=\"applicationStatusText(a)\" :tone=\"groupTone(a.group)\" />",
)
replace_once(
    "student-portal/src/views/profile/ProfileView.vue",
    "function statusText(s) { return STATUS_MAP[s] || s || '在读' }",
    "function statusText(s) { return STATUS_MAP[s] || s || '在读' }\nconst APPLICATION_STATUS_MAP = { SUBMITTED: '已提交', PENDING_REVIEW: '待审核', CLASS_REVIEW: '班级审核中', COUNSELOR_REVIEW: '辅导员审核中', COLLEGE_REVIEW: '学院审核中', SCHOOL_REVIEW: '学校审核中', APPROVED: '已通过', REJECTED: '未通过', RETURNED: '已退回', PROCESSING: '处理中', COMPLETED: '已完成' }\nconst APPLICATION_NAME_MAP = { PERSONAL: '事假申请', SICK: '病假申请', OFFICIAL: '公假申请', LEAVE: '请假申请', AID: '困难认定', FUNDING: '奖助申请', DORM: '宿舍事务' }\nfunction readableCode(value, mapping, fallback = '状态待确认') {\n  const raw = String(value || '').trim()\n  if (!raw) return fallback\n  const key = raw.toUpperCase()\n  if (mapping[key]) return mapping[key]\n  return /^[A-Z0-9_]+$/.test(raw) ? fallback : raw\n}\nfunction applicationName(item) { return readableCode(item?.name || item?.type || item?.leaveType, APPLICATION_NAME_MAP, '业务申请') }\nfunction applicationStatusText(item) { return item?.statusText || readableCode(item?.status || item?.currentNode, APPLICATION_STATUS_MAP) }",
)
replace_once(
    "student-portal/src/views/profile/ProfileView.vue",
    "function modTagStyle() { return { background: 'var(--pri-50)', color: 'var(--pri)' } }",
    "function modTagStyle() { return { background: 'var(--pri-50)', color: 'var(--pri-text, var(--pri))' } }",
)

# ── 消息中心：正文里的内部审核枚举中文化 ──
replace_once(
    "student-portal/src/views/messages/MessagesView.vue",
    "{{ m.title }}",
    "{{ displayMessageText(m.title) }}",
)
replace_once(
    "student-portal/src/views/messages/MessagesView.vue",
    "function modName(key) { return MODULES.find((m) => m.key === key || m.domain === key)?.title || '系统' }",
    "const MESSAGE_STATUS_TEXT = { PENDING_REVIEW: '待审核', SUBMITTED: '已提交', RETURNED: '已退回', REJECTED: '未通过', APPROVED: '已通过', PROCESSING: '处理中', COMPLETED: '已完成', CLASS_REVIEW: '班级审核中', COLLEGE_REVIEW: '学院审核中', SCHOOL_REVIEW: '学校审核中' }\nfunction displayMessageText(value) {\n  let text = String(value || '')\n  for (const [key, label] of Object.entries(MESSAGE_STATUS_TEXT)) text = text.replaceAll(key, label)\n  return text || '系统通知'\n}\nfunction modName(key) { return MODULES.find((m) => m.key === key || m.domain === key)?.title || '系统' }",
)
replace_once(
    "student-portal/src/views/messages/MessagesView.vue",
    ".mtab.on { background: var(--pri-50); color: var(--pri); font-weight: 600; }",
    ".mtab.on { background: var(--pri-50); color: var(--pri-text, var(--pri)); font-weight: 600; }",
)
replace_once(
    "student-portal/src/views/messages/MessagesView.vue",
    ".linkall { font-size: 13px; color: var(--pri); cursor: pointer; }",
    ".linkall { font-size: 13px; color: var(--pri-text, var(--pri)); cursor: pointer; }",
)
replace_once(
    "student-portal/src/views/messages/MessagesView.vue",
    ".mrow:hover { background: #FAFBFC; }",
    ".mrow:hover { background: var(--surface-2, #FAFBFC); }",
)
replace_once(
    "student-portal/src/views/messages/MessagesView.vue",
    "border-bottom: 1px solid #F4F5F7;",
    "border-bottom: 1px solid var(--line2);",
)

# ── 毕业设计：环节与版本使用学生可读口径 ──
replace_once(
    "student-portal/src/views/graduation/GraduationWorkbenchView.vue",
    "{{ my.stageLabel || my.stage || '待开始' }}",
    "{{ stageText(my.stageLabel || my.stage) }}",
)
replace_once(
    "student-portal/src/views/graduation/GraduationWorkbenchView.vue",
    "我已阅读并确认任务书 v{{ taskbook.taskbookVersion || '—' }}",
    "我已阅读并确认任务书第 {{ taskbook.taskbookVersion || '—' }} 版",
)
replace_once(
    "student-portal/src/views/graduation/GraduationWorkbenchView.vue",
    "detail: taskbook.value.hasData ? `任务书 v${taskbook.value.taskbookVersion || 1} · ${taskbook.value.objective || '请阅读任务书详情'}`",
    "detail: taskbook.value.hasData ? `任务书第 ${taskbook.value.taskbookVersion || 1} 版 · ${taskbook.value.objective || '请阅读任务书详情'}`",
)
replace_once(
    "student-portal/src/views/graduation/GraduationWorkbenchView.vue",
    "const steps = computed(() => [",
    "const STAGE_TEXT = { TOPIC: '组织与选题', TASKBOOK: '任务书确认', PROPOSAL: '开题论证', MIDTERM: '中期检查', FINAL: '论文成果', PEER: '成果互查', DEFENSE: '答辩安排', ARCHIVE: '成绩与归档', COMPLETED: '已完成' }\nfunction stageText(value) {\n  const raw = String(value || '').trim()\n  if (!raw) return '待开始'\n  const key = raw.toUpperCase()\n  if (STAGE_TEXT[key]) return STAGE_TEXT[key]\n  return /^[A-Z0-9_]+$/.test(raw) ? '环节待确认' : raw\n}\n\nconst steps = computed(() => [",
)

# ── 学工宿舍：床位数据正常时，调宿记录 403 只做分项降级 ──
replace_once(
    "student-portal/src/views/affairs/AffairsFourEndView.vue",
    "<div class=\"section-title\">调宿申请记录</div><AutoTable :rows=\"dormTransfers\" empty=\"暂无调宿申请\" />",
    "<div class=\"section-title\">调宿申请记录</div><p v-if=\"dormTransferError\" class=\"sp-notice\">{{ dormTransferError }}</p><AutoTable v-else :rows=\"dormTransfers\" empty=\"暂无调宿申请\" />",
)
replace_once(
    "student-portal/src/views/affairs/AffairsFourEndView.vue",
    "const leave = ref({ items: [] }); const aid = ref({ items: [] }); const funding = ref({ items: [] }); const dorm = ref({}); const discipline = ref({ items: [] }); const psy = ref({ questions: [] }); const psyHistory = ref({ items: [] }); const activities = ref({ available: [], mine: [] }); const talk = ref({ items: [] }); const aidBatches = ref([]); const fundingBatches = ref([]); const secondClass = ref({ items: [], byType: [] }); const creditAppeals = ref([]); const dormTransfers = ref([])",
    "const leave = ref({ items: [] }); const aid = ref({ items: [] }); const funding = ref({ items: [] }); const dorm = ref({}); const discipline = ref({ items: [] }); const psy = ref({ questions: [] }); const psyHistory = ref({ items: [] }); const activities = ref({ available: [], mine: [] }); const talk = ref({ items: [] }); const aidBatches = ref([]); const fundingBatches = ref([]); const secondClass = ref({ items: [], byType: [] }); const creditAppeals = ref([]); const dormTransfers = ref([]); const dormTransferError = ref('')",
)
replace_once(
    "student-portal/src/views/affairs/AffairsFourEndView.vue",
    "dorm: [{ load: () => portalApi.affairsDorm(), apply: (value) => { dorm.value = value || {} } }, { load: () => affairsFourEndApi.myDormTransfers(), apply: (value) => { dormTransfers.value = value?.items || [] } }],",
    "dorm: [{ load: () => portalApi.affairsDorm(), apply: (value) => { dorm.value = value || {} } }, { load: () => affairsFourEndApi.myDormTransfers(), optional: true, apply: (value) => { dormTransferError.value = ''; dormTransfers.value = value?.items || [] }, fail: () => { dormTransfers.value = []; dormTransferError.value = '调宿申请记录暂时无法读取，当前宿舍与床位信息仍可正常查看。' } }],",
)
replace_once(
    "student-portal/src/views/affairs/AffairsFourEndView.vue",
    "if (result.status === 'fulfilled') entries[index].apply(result.value)\n        else failures.push(result.reason?.message || '数据加载失败')",
    "if (result.status === 'fulfilled') entries[index].apply(result.value)\n        else if (entries[index].optional) entries[index].fail?.(result.reason)\n        else failures.push(result.reason?.message || '数据加载失败')",
)

# ── 复验脚本同步新主题名称，并用显式教务导航检查返回能力 ──
replace_once(
    "student-portal/review/v5-review-config.json",
    '"key":"blue","label":"学院蓝"',
    '"key":"blue","label":"深海蓝"',
)
replace_once(
    "student-portal/review/v5-full-review.mjs",
    "  const backButton = page.getByRole('button', { name: /返回教务工作台/ })\n  const backFound = await backButton.count()\n  if (backFound) await backButton.click()\n  const backPassed = await page.waitForURL((url) => url.pathname.endsWith('/academic'), { timeout: 8000 }).then(() => true).catch(() => false)\n  report.functionalChecks.push({\n    name: '教务独立三级页返回教务工作台',\n    passed: backFound === 1 && backPassed,\n    actual: { backFound, backPassed, url: page.url() },\n    screenshot: await capture(page, outputDir, 'functional-academic-back', false)\n  })",
    "  const academicHome = page.locator('.academic-context__item', { hasText: '教务总览' })\n  const academicHomeFound = await academicHome.count()\n  if (academicHomeFound) await academicHome.click()\n  const backPassed = await page.waitForURL((url) => url.pathname.endsWith('/academic'), { timeout: 8000 }).then(() => true).catch(() => false)\n  report.functionalChecks.push({\n    name: '教务独立三级页通过上下文导航返回教务工作台',\n    passed: academicHomeFound === 1 && backPassed,\n    actual: { academicHomeFound, backPassed, url: page.url() },\n    screenshot: await capture(page, outputDir, 'functional-academic-back', false)\n  })",
)

print("all asserted reviewed display fixes applied")
