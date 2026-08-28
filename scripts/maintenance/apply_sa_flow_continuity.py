from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one anchor, got {count}: {old[:120]!r}")
    write(path, text.replace(old, new, 1))


def regex_once(path: str, pattern: str, repl: str) -> None:
    text = read(path)
    new, count = re.subn(pattern, repl, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"{path}: regex anchor count={count}: {pattern[:120]!r}")
    write(path, new)


def append_once(path: str, marker: str, content: str) -> None:
    text = read(path)
    if marker in text:
        return
    write(path, text.rstrip() + "\n\n" + content.strip() + "\n")


def p1_01() -> list[str]:
    changed: list[str] = []

    # 1) Authoritative todo route contract: correct business workspaces + true PC list-focus.
    path = "backend/app/services/todo_route_registry.py"
    for old, new in (
        ('"LEAVE_OVERDUE": ("todo-route:student-affairs-leave-ledger", "/admin/student-affairs/leave/ledger", {"status": "OVERDUE"}),',
         '"LEAVE_OVERDUE": ("todo-route:student-affairs-leave-followup", "/admin/student-affairs/leave/followup", {"status": "OVERDUE"}),'),
        ('"LEAVE_CANCEL": ("todo-route:student-affairs-leave-queue", "/admin/student-affairs/leave", {"status": "CANCEL_PENDING"}),',
         '"LEAVE_CANCEL": ("todo-route:student-affairs-leave-followup", "/admin/student-affairs/leave/followup", {"status": "WAIT_CANCEL_LEAVE"}),'),
        ('"LEAVE_EXTENSION": ("todo-route:student-affairs-leave-followup", "/admin/student-affairs/leave/followup", {"status": "PENDING"}),',
         '"LEAVE_EXTENSION": ("todo-route:student-affairs-leave-followup", "/admin/student-affairs/leave/followup", {"status": "EXTENSION_REVIEW"}),'),
    ):
        replace_once(path, old, new)
    replace_once(
        path,
        '# 学生小程序当前真实业务页。query.recordId 用于页面 focus。',
        '''# PC 列表页已实现 recordId -> detail-first -> 对象聚焦的业务类型。\n# exact=True 的证据由 frontend/tests/student-affairs-todo-pc-focus.contract.test.mjs 逐页约束；\n# 不允许只改本表、页面不消费 recordId。\n_PC_LIST_FOCUS = frozenset({\n    "LEAVE_APPROVAL", "LEAVE_OVERDUE", "LEAVE_CANCEL", "LEAVE_EXTENSION",\n    "AID_APPROVAL", "AID_ADJUST", "FUNDING_APPROVAL",\n    "DISCIPLINE_APPROVAL", "DISCIPLINE_REMOVE",\n})\n\n# 学生小程序当前真实业务页。query.recordId 用于页面 focus。'''
    )
    replace_once(
        path,
        '''        if fallback:\n            route_name, path, query = fallback\n            return {\n                "routeName": route_name,\n                "routeParams": {"recordId": rid},\n                "query": {**query, "recordId": rid},\n                "path": path,\n                "focusMode": FOCUS_NONE,\n                "exact": False,\n            }''',
        '''        if fallback:\n            route_name, path, query = fallback\n            focus_mode = FOCUS_LIST_FOCUS if type_code in _PC_LIST_FOCUS else FOCUS_NONE\n            return {\n                "routeName": route_name,\n                "routeParams": {"recordId": rid},\n                "query": {**query, "recordId": rid},\n                "path": path,\n                "focusMode": focus_mode,\n                # PC 的 LIST_FOCUS 由对应页面合同测试证明；这里不复用 Mini 端页面白名单。\n                "exact": focus_mode == FOCUS_LIST_FOCUS,\n            }'''
    )
    replace_once(
        path,
        '"pcList": {key: {"routeName": value[0], "path": value[1]} for key, value in _PC_LIST.items()},',
        '''"pcList": {\n            key: {\n                "routeName": value[0], "path": value[1],\n                "focusMode": FOCUS_LIST_FOCUS if key in _PC_LIST_FOCUS else FOCUS_NONE,\n                "exact": key in _PC_LIST_FOCUS,\n            }\n            for key, value in _PC_LIST.items()\n        },'''
    )
    changed.append(path)

    # 2) Leave approval: detail-first, no current-page find fallback.
    path = "frontend/src/modules/studentAffairs/views/leave/LeaveApprovalWorkbenchView.vue"
    replace_once(path, '      />\n      <div class="bar">', '      />\n      <AppInlineAlert v-if="focusNotice" type="warning" :description="focusNotice" />\n      <div class="bar">')
    replace_once(path, 'AppSearchBox, AppGlobalState, AppPagination', 'AppSearchBox, AppGlobalState, AppPagination, AppInlineAlert')
    replace_once(path, 'AppDescriptionList, AppAuditTrail, AppSearchBox, AppGlobalState, AppPagination\n  },', 'AppDescriptionList, AppAuditTrail, AppSearchBox, AppGlobalState, AppPagination, AppInlineAlert\n  },')
    replace_once(path, "      keyword: '',\n      pagination:", "      keyword: '', focusNotice: '',\n      pagination:")
    replace_once(path, '  created() { this.load() },\n  methods: {', '''  created() { this.initRouteFocus() },\n  watch: {\n    '$route.query.recordId'(value, previous) {\n      if (String(value || '') !== String(previous || '')) this.initRouteFocus()\n    }\n  },\n  methods: {\n    async initRouteFocus() {\n      const recordId = String(this.$route.query?.recordId || '').trim()\n      this.focusNotice = ''\n      if (!recordId) {\n        this.selectedId = ''\n        this.detail = { loading: false, error: '', data: null }\n        await this.load()\n        return\n      }\n      await this.focusRecordFromRoute(recordId)\n    },\n    async focusRecordFromRoute(recordId) {\n      this.loading = true\n      this.error = ''\n      const res = await leaveApi.detail(recordId)\n      if (res.code !== 0 || !res.data) {\n        this.loading = false\n        this.rows = []; this.total = 0; this.selectedId = ''\n        this.detail = { loading: false, error: '', data: null }\n        this.error = res.message || '该请假记录不存在、已不可见或不在当前数据范围内'\n        return\n      }\n      const detail = res.data\n      this.selectedId = String(recordId)\n      this.detail = { loading: false, error: '', data: detail }\n      if (!['COUNSELOR_REVIEW', 'COLLEGE_REVIEW', 'STUDENT_AFFAIRS_REVIEW'].includes(detail.affairsStatus)) {\n        this.focusNotice = `该待办状态已变化：当前为${detail.affairsStatusLabel || detail.affairsStatus || '未知状态'}，已按最新事实展示，旧待办动作不可继续执行。`\n      }\n      await this.load()\n    },''')
    changed.append(path)

    # 3) Leave follow-up: exact status + detail-first record focus.
    path = "frontend/src/modules/studentAffairs/views/leave/LeaveExtensionCancelView.vue"
    replace_once(path, '<div class="mp-stack">\n      <div class="bar">', '<div class="mp-stack">\n      <AppInlineAlert v-if="focusNotice" type="warning" :description="focusNotice" />\n      <div class="bar">')
    replace_once(path, "      keyword: '', statusFilter: '', statusOptions: STATUS_OPTIONS,", "      keyword: '', statusFilter: '', statusOptions: STATUS_OPTIONS, focusNotice: '',")
    replace_once(path, '  created() {\n    if (this.$route.query.status) this.statusFilter = String(this.$route.query.status)\n    this.load()\n  },\n  methods: {', '''  created() { this.initRouteFocus() },\n  watch: {\n    '$route.query'(value, previous) {\n      const nextId = String(value?.recordId || '')\n      const prevId = String(previous?.recordId || '')\n      if (nextId !== prevId || String(value?.status || '') !== String(previous?.status || '')) this.initRouteFocus()\n    }\n  },\n  methods: {\n    async initRouteFocus() {\n      const valid = new Set(['EXTENSION_REVIEW', 'WAIT_CANCEL_LEAVE', 'OVERDUE', 'APPROVED'])\n      const requested = String(this.$route.query?.status || '').trim()\n      this.statusFilter = valid.has(requested) ? requested : ''\n      this.focusNotice = ''\n      const recordId = String(this.$route.query?.recordId || '').trim()\n      if (!recordId) {\n        this.selectedId = ''\n        this.detail = { loading: false, error: '', data: null }\n        await this.load()\n        return\n      }\n      await this.focusRecordFromRoute(recordId, valid)\n    },\n    async focusRecordFromRoute(recordId, validStatuses = new Set(['EXTENSION_REVIEW', 'WAIT_CANCEL_LEAVE', 'OVERDUE', 'APPROVED'])) {\n      this.loading = true; this.error = ''\n      const res = await leaveApi.detail(recordId)\n      if (res.code !== 0 || !res.data) {\n        this.loading = false; this.rows = []; this.total = 0; this.selectedId = ''\n        this.detail = { loading: false, error: '', data: null }\n        this.error = res.message || '该请假后续记录不存在、已不可见或不在当前数据范围内'\n        return\n      }\n      const detail = res.data\n      const actual = String(detail.affairsStatus || '')\n      if (validStatuses.has(actual)) this.statusFilter = actual\n      else this.focusNotice = `该待办状态已变化：当前为${detail.affairsStatusLabel || actual || '未知状态'}，仅展示最新事实。`\n      this.selectedId = String(recordId)\n      this.detail = { loading: false, error: '', data: detail }\n      await this.load()\n    },''')
    changed.append(path)

    # 4) Aid workbench: record first -> authoritative batch -> list.
    path = "frontend/src/modules/studentAffairs/views/AidWorkbenchView.vue"
    replace_once(path, '    />\n    <!-- 批次上下文 -->', '    />\n    <p v-if="focusNotice" class="ad-focus-note">{{ focusNotice }}</p>\n    <!-- 批次上下文 -->')
    replace_once(path, "      routeIntentConsumed: false,\n      statusMatch: null,", "      routeIntentConsumed: false, focusRecordId: '', focusNotice: '',\n      statusMatch: null,")
    replace_once(path, '''  created() {\n    this.applyRouteFilters()\n    this.loadBatches()\n  },\n  watch: {\n    '$route.query'() { this.applyRouteFilters(); this.pagination.page = 1; if (this.batchId) this.loadApplications() }\n  },\n  methods: {''', '''  created() { this.initRouteFocus() },\n  watch: {\n    '$route.query'(value, previous) {\n      const nextId = String(value?.recordId || '')\n      const prevId = String(previous?.recordId || '')\n      if (nextId !== prevId) { this.initRouteFocus(); return }\n      this.applyRouteFilters(); this.pagination.page = 1; if (this.batchId) this.loadApplications()\n    }\n  },\n  methods: {\n    async initRouteFocus() {\n      this.applyRouteFilters()\n      const recordId = String(this.$route.query?.recordId || '').trim()\n      this.focusRecordId = recordId\n      this.focusNotice = ''\n      this.listError = ''\n      if (!recordId) {\n        this.selected = null; this.batchId = ''\n        await this.loadBatches()\n        return\n      }\n      const res = await studentAffairsApi.getAidDetail(recordId)\n      if (res.code !== 0 || !res.data) {\n        this.selected = null; this.batchId = ''; this.batches = []; this.list = []; this.pagination.total = 0\n        this.listError = res.message || '该困难认定申请不存在、已不可见或不在当前数据范围内'\n        return\n      }\n      this.selected = res.data\n      this.batchId = String(res.data.batchId || '')\n      if (!this.batchId) { this.listError = '该申请缺少真实批次上下文，无法安全定位'; return }\n      if (this.statusMatch?.length && !this.statusMatch.includes(res.data.status)) {\n        this.focusNotice = `该待办状态已变化：当前为${res.data.statusLabel || res.data.status || '未知状态'}，已按最新事实展示。`\n      }\n      await this.loadBatches()\n    },''')
    regex_once(path, r'''    async loadBatches\(\) \{.*?\n    \},\n    onBatchChange\(\) \{''', '''    async loadBatches() {\n      const res = await studentAffairsApi.getAidBatches({ page: 1, pageSize: 100 })\n      if (res.code === 0 && res.data) {\n        this.batches = res.data.items || []\n        if (this.batchId) {\n          const visible = this.batches.some((batch) => String(batch.batchId) === String(this.batchId))\n          if (!visible) {\n            this.listError = '该申请所属认定批次当前不可见，已停止自动回退到其他批次'\n            this.list = []; this.pagination.total = 0\n            return\n          }\n          await this.loadApplications()\n        } else if (this.batches.length) {\n          const candidate = this.batches.find((batch) => batch.status === 'OPEN') || this.batches[0]\n          this.batchId = candidate.batchId\n          await this.loadApplications()\n        }\n        this.consumeRouteIntent()\n      } else {\n        this.listError = res.message || '批次加载失败'\n      }\n    },\n    onBatchChange() {''')
    replace_once(path, '.ad-batchbar {', '.ad-focus-note { margin: 0 0 var(--space-3); padding: var(--space-2) var(--space-3); border: 1px solid var(--warning-200, #fde68a); border-radius: var(--radius-md); background: var(--warning-50, #fffbeb); color: var(--warning-800, #92400e); font-size: var(--font-size-sm); }\n.ad-batchbar {')
    changed.append(path)

    # 5) Funding workbench: detail first -> batch -> project. No generic resolver.
    path = "frontend/src/modules/studentAffairs/views/FundingWorkbenchView.vue"
    replace_once(path, '    />\n    <div class="fd-ctxbar">', '    />\n    <p v-if="focusNotice" class="fd-focus-note">{{ focusNotice }}</p>\n    <div class="fd-ctxbar">')
    replace_once(path, "      routeIntentConsumed: false,\n      statusMatch: null,", "      routeIntentConsumed: false, focusRecordId: '', focusNotice: '',\n      statusMatch: null,")
    replace_once(path, '''  created() {\n    this.applyRouteFilters()\n    this.loadProjects()\n  },\n  watch: {\n    '$route.query'() { this.applyRouteFilters(); this.pagination.page = 1; if (this.batchId) this.loadApplications() }\n  },\n  methods: {''', '''  created() { this.initRouteFocus() },\n  watch: {\n    '$route.query'(value, previous) {\n      const nextId = String(value?.recordId || '')\n      const prevId = String(previous?.recordId || '')\n      if (nextId !== prevId) { this.initRouteFocus(); return }\n      this.applyRouteFilters(); this.pagination.page = 1; if (this.batchId) this.loadApplications()\n    }\n  },\n  methods: {\n    async initRouteFocus() {\n      this.applyRouteFilters()\n      const recordId = String(this.$route.query?.recordId || '').trim()\n      this.focusRecordId = recordId\n      this.focusNotice = ''\n      this.listError = ''\n      if (!recordId) {\n        this.selected = null; this.projectId = ''; this.batchId = ''\n        await this.loadProjects()\n        return\n      }\n      const res = await studentAffairsApi.getFundingDetail(recordId)\n      if (res.code !== 0 || !res.data) {\n        this.selected = null; this.projectId = ''; this.batchId = ''; this.projects = []; this.batches = []; this.list = []; this.pagination.total = 0\n        this.listError = res.message || '该资助申请不存在、已不可见或不在当前数据范围内'\n        return\n      }\n      this.selected = res.data\n      this.batchId = String(res.data.batchId || '')\n      if (!this.batchId) { this.listError = '该资助申请缺少真实批次上下文，无法安全定位'; return }\n      if (this.statusMatch?.length && !this.statusMatch.includes(res.data.status)) {\n        this.focusNotice = `该待办状态已变化：当前为${res.data.statusLabel || res.data.status || '未知状态'}，已按最新事实展示。`\n      }\n      await this.loadProjects()\n    },''')
    regex_once(path, r'''    async loadProjects\(\) \{.*?\n    \},\n    async loadBatches\(\) \{''', '''    async loadProjects() {\n      const res = await studentAffairsApi.getFundingProjects({ page: 1, pageSize: 100 })\n      if (res.code !== 0 || !res.data) {\n        this.listError = res.message || '项目加载失败'\n        return\n      }\n      this.projects = res.data.items || []\n      await this.loadBatches()\n      if (this.batchId) {\n        const batch = this.batches.find((item) => String(item.batchId) === String(this.batchId))\n        if (!batch) {\n          this.listError = '该资助申请所属批次当前不可见，已停止自动回退到其他批次'\n          this.list = []; this.pagination.total = 0\n          return\n        }\n        const projectId = String(batch.projectId || '')\n        if (!projectId || !this.projects.some((item) => String(item.projectId) === projectId)) {\n          this.listError = '该资助批次所属项目当前不可见，已停止自动回退到其他项目'\n          this.list = []; this.pagination.total = 0\n          return\n        }\n        this.projectId = projectId\n        await this.loadApplications()\n        this.consumeRouteIntent()\n        return\n      }\n      if (!this.projectId && this.projects.length) {\n        this.projectId = this.projects[0].projectId\n        this.autoPickBatch()\n      }\n    },\n    async loadBatches() {''')
    replace_once(path, '.fd-ctxbar {', '.fd-focus-note { margin: 0 0 var(--space-3); padding: var(--space-2) var(--space-3); border: 1px solid var(--warning-200, #fde68a); border-radius: var(--radius-md); background: var(--warning-50, #fffbeb); color: var(--warning-800, #92400e); font-size: var(--font-size-sm); }\n.fd-ctxbar {')
    changed.append(path)

    # 6) Discipline workbench: exact case detail; preserve detail-only fields after list refresh.
    path = "frontend/src/modules/studentAffairs/views/DisciplineWorkbenchView.vue"
    replace_once(path, '    />\n    <div v-if="studentFilterLabel"', '    />\n    <p v-if="focusNotice" class="dp-focus-note">{{ focusNotice }}</p>\n    <div v-if="studentFilterLabel"')
    replace_once(path, "      studentFilter: { studentId: '', studentNo: '', studentName: '' },\n      statusMatch: null,", "      studentFilter: { studentId: '', studentNo: '', studentName: '' }, focusRecordId: '', focusNotice: '',\n      statusMatch: null,")
    replace_once(path, '''  created() {\n    this.applyRouteFilters()\n    this.loadList()\n  },\n  watch: {\n    '$route.query'() { this.applyRouteFilters(); this.pagination.page = 1; this.loadList() },\n    typeFilter() { this.pagination.page = 1; this.loadList() }\n  },\n  methods: {''', '''  created() { this.initRouteFocus() },\n  watch: {\n    '$route.query'(value, previous) {\n      const nextId = String(value?.recordId || '')\n      const prevId = String(previous?.recordId || '')\n      if (nextId !== prevId) { this.initRouteFocus(); return }\n      this.applyRouteFilters(); this.pagination.page = 1; this.loadList()\n    },\n    typeFilter() { this.pagination.page = 1; this.loadList() }\n  },\n  methods: {\n    async initRouteFocus() {\n      this.applyRouteFilters()\n      const recordId = String(this.$route.query?.recordId || '').trim()\n      this.focusRecordId = recordId\n      this.focusNotice = ''\n      this.listError = ''\n      if (!recordId) { this.selected = null; await this.loadList(); return }\n      const res = await studentAffairsApi.getDisciplineDetail(recordId)\n      if (res.code !== 0 || !res.data) {\n        this.selected = null; this.list = []; this.pagination.total = 0\n        this.listError = res.message || '该处分记录不存在、已不可见或不在当前数据范围内'\n        return\n      }\n      this.selected = res.data\n      if (this.statusMatch?.length && !this.statusMatch.includes(res.data.status)) {\n        this.focusNotice = `该待办状态已变化：当前为${res.data.statusLabel || res.data.status || '未知状态'}，已按最新事实展示。`\n      }\n      await this.loadList()\n    },''')
    replace_once(path, '          if (hit) this.selected = hit', '          if (hit) this.selected = { ...this.selected, ...hit }')
    replace_once(path, '''    select(it) {\n      this.selected = it\n    },''', '''    async select(it) {\n      this.selected = it\n      await this.reloadDetail()\n    },''')
    replace_once(path, '.dp-student-filter {', '.dp-focus-note { margin: 0 0 var(--space-3); padding: var(--space-2) var(--space-3); border: 1px solid var(--warning-200, #fde68a); border-radius: var(--radius-md); background: var(--warning-50, #fffbeb); color: var(--warning-800, #92400e); font-size: var(--font-size-sm); }\n.dp-student-filter {')
    changed.append(path)

    # 7) Backend route contract regression.
    path = "backend/tests/test_affairs_todo_drilldown.py"
    append_once(path, "test_pc_affairs_todo_routes_are_record_exact", '''\ndef test_pc_affairs_todo_routes_are_record_exact():\n    from app.services.todo_route_registry import resolve_todo_route\n\n    expected = {\n        "LEAVE_CANCEL": ("/admin/student-affairs/leave/followup", "WAIT_CANCEL_LEAVE"),\n        "LEAVE_EXTENSION": ("/admin/student-affairs/leave/followup", "EXTENSION_REVIEW"),\n        "LEAVE_OVERDUE": ("/admin/student-affairs/leave/followup", "OVERDUE"),\n        "LEAVE_APPROVAL": ("/admin/student-affairs/leave", "PENDING"),\n        "AID_APPROVAL": ("/admin/student-affairs/aid", "PENDING"),\n        "FUNDING_APPROVAL": ("/admin/student-affairs/funding", "PENDING"),\n        "DISCIPLINE_APPROVAL": ("/admin/student-affairs/discipline", "PENDING"),\n    }\n    for todo_type, (path_value, status) in expected.items():\n        target = resolve_todo_route(todo_type, 99123, client="pc")\n        assert target is not None\n        assert target["path"] == path_value\n        assert target["query"]["status"] == status\n        assert target["query"]["recordId"] == "99123"\n        assert target["focusMode"] == "LIST_FOCUS"\n        assert target["exact"] is True\n''')
    changed.append(path)

    # 8) Frontend source contract: exact means real detail-first consumer exists.
    path = "frontend/tests/student-affairs-todo-pc-focus.contract.test.mjs"
    write(path, '''import test from 'node:test'\nimport assert from 'node:assert/strict'\nimport fs from 'node:fs'\n\nconst read = (p) => fs.readFileSync(new URL(`../${p}`, import.meta.url), 'utf8')\n\nconst cases = [\n  ['src/modules/studentAffairs/views/leave/LeaveApprovalWorkbenchView.vue', 'focusRecordFromRoute', 'leaveApi.detail(recordId)'],\n  ['src/modules/studentAffairs/views/leave/LeaveExtensionCancelView.vue', 'focusRecordFromRoute', 'leaveApi.detail(recordId)'],\n  ['src/modules/studentAffairs/views/AidWorkbenchView.vue', 'initRouteFocus', 'studentAffairsApi.getAidDetail(recordId)'],\n  ['src/modules/studentAffairs/views/FundingWorkbenchView.vue', 'initRouteFocus', 'studentAffairsApi.getFundingDetail(recordId)'],\n  ['src/modules/studentAffairs/views/DisciplineWorkbenchView.vue', 'initRouteFocus', 'studentAffairsApi.getDisciplineDetail(recordId)'],\n]\n\ntest('PC 学工待办 exact 落点必须真实消费 recordId 并先查 detail', () => {\n  for (const [file, focusFn, detailCall] of cases) {\n    const src = read(file)\n    assert.match(src, /\\$route\\.query\\?\\.recordId|\\$route\\.query\\.recordId/, `${file} 必须消费 recordId`)\n    assert.ok(src.includes(focusFn), `${file} 缺少对象聚焦函数`)\n    assert.ok(src.includes(detailCall), `${file} 必须先调用既有详情 API`)\n  }\n})\n\ntest('困难认定与奖助不能用默认首批次/首项目覆盖 recordId 真值', () => {\n  const aid = read('src/modules/studentAffairs/views/AidWorkbenchView.vue')\n  assert.ok(aid.includes("this.batchId = String(res.data.batchId || '')"))\n  assert.ok(aid.includes('已停止自动回退到其他批次'))\n\n  const funding = read('src/modules/studentAffairs/views/FundingWorkbenchView.vue')\n  assert.ok(funding.includes("this.batchId = String(res.data.batchId || '')"))\n  assert.ok(funding.includes("const projectId = String(batch.projectId || '')"))\n  assert.ok(funding.includes('已停止自动回退到其他项目'))\n})\n\ntest('销假/续假/逾期待办使用动作真实状态，不接受 PENDING 混用', () => {\n  const follow = read('src/modules/studentAffairs/views/leave/LeaveExtensionCancelView.vue')\n  for (const status of ['EXTENSION_REVIEW', 'WAIT_CANCEL_LEAVE', 'OVERDUE']) assert.ok(follow.includes(status))\n  assert.match(follow, /valid = new Set\\(\\['EXTENSION_REVIEW', 'WAIT_CANCEL_LEAVE', 'OVERDUE', 'APPROVED'\\]\\)/)\n})\n''')
    changed.append(path)

    return changed


def main() -> None:
    ticket = (sys.argv[1] if len(sys.argv) > 1 else "").strip().upper()
    if ticket != "P1-01":
        raise SystemExit(f"temporary runner currently implements P1-01 only, got {ticket!r}")
    changed = p1_01()
    files_path = ROOT / ".sa-flow-changed-files"
    files_path.write_text("\n".join(changed) + "\n", encoding="utf-8")
    (ROOT / ".sa-flow-commit-message").write_text(
        "fix(student-affairs): make todo routes record-exact\n", encoding="utf-8"
    )
    print("P1-01 patched files:")
    print("\n".join(changed))


if __name__ == "__main__":
    main()
