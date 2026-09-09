<template>
  <div class="wb-focus" :aria-busy="loading">
    <AppPageGuide guide-key="workbench.first-login" :auto-open="false" />
    <header class="wb-heading">
      <h1>我的工作台</h1>
      <div class="wb-tools">
        <button type="button" :disabled="loading" @click="load">
          {{ loading ? '刷新中…' : '刷新' }}
        </button>
        <button
          type="button"
          :aria-expanded="editing"
          aria-controls="workbench-editor"
          @click="toggleEditing"
        >
          {{ editing ? '完成设置' : '自定义' }}
        </button>
        <button type="button" @click="go('/admin/help?topic=doc-workbench')">帮助</button>
      </div>
    </header>

    <section v-if="showStudentAffairs && (todoTotal || error)" class="wb-tasks wb-panel" aria-label="学工业务待办">
      <header class="wb-section-head"><h2>待我办理 <small>{{ loading ? '—' : todoTotal }}</small></h2><button class="wb-link" type="button" @click="showBusinessQueue">办理队列</button></header>
      <p v-if="error" class="wb-error" role="alert">{{ error }}</p>
      <ul v-else class="wb-task-list">
        <li v-for="todo in todos.slice(0, 5)" :key="todo.todoId"><div class="wb-task-title"><strong>{{ todo.title }}</strong><small>{{ todoMeta(todo) }}</small></div><span class="wb-deadline">{{ todo.dueAt ? dueLabel(todo) : '未设时限' }}</span><button type="button" class="wb-handle" :disabled="!todo.typedRouteTarget" @click="openTodo(todo)">去办理</button></li>
      </ul>
    </section>

    <StudentAffairsPriorityPanel
      v-if="showStudentAffairs"
      ref="priorityPanel"
      :ctx="ctx"
      :pending="loading || error ? null : summary.pending"
    />
    <details :open="!showStudentAffairs" class="wb-personal-details">
      <summary v-if="showStudentAffairs">我的待办与个人设置</summary>
      <div v-if="error" class="wb-error" role="alert">
        <strong>待办加载失败</strong><span>{{ error }}</span>
        <button type="button" :disabled="loading" @click="load">重试</button>
      </div>
      <template v-else>
        <section v-if="visibleSummaryCues.length" class="wb-summary" aria-label="待办汇总">
          <button
            v-for="c in visibleSummaryCues"
            :key="c.key"
            type="button"
            :disabled="loading"
            :class="['is-' + c.accent, { 'has-value': valueOf(c.source) > 0 }]"
            @click="onDrill(c)"
          >
            <span>{{ c.title }}</span
            ><strong>{{ loading ? '—' : valueOf(c.source) }}</strong>
          </button>
        </section>

        <section class="wb-tasks wb-panel" aria-label="待处理事项">
          <header class="wb-section-head">
            <div class="wb-task-tabs" role="group" aria-label="事项类型">
              <button
                id="approval-tab"
                type="button"
                :aria-pressed="taskSource === 'approval'"
                aria-controls="workbench-task-panel"
                @click="taskSource = 'approval'"
              >
                待我审批 <b>{{ loading ? '—' : summary.pending }}</b>
              </button>
              <button
                id="business-tab"
                type="button"
                :aria-pressed="taskSource === 'business'"
                aria-controls="workbench-task-panel"
                @click="taskSource = 'business'"
              >
                业务待办 <b>{{ loading ? '—' : todoTotal }}</b>
              </button>
            </div>
            <button type="button" class="wb-link" @click="go('/admin/approval/todos')">
              全部待办
            </button>
          </header>
          <div
            v-if="taskSource === 'business' && visibleTypeCues.length"
            class="wb-types"
            aria-label="按业务查看待办"
          >
            <button v-for="c in visibleTypeCues" :key="c.key" type="button" @click="onDrill(c)">
              {{ c.title }} <b>{{ valueOf(c.source) }}</b>
            </button>
          </div>
          <div
            id="workbench-task-panel"
            role="region"
            :aria-labelledby="taskSource === 'approval' ? 'approval-tab' : 'business-tab'"
          >
            <p v-if="loading" class="wb-empty" role="status">正在加载待办…</p>
            <p
              v-else-if="taskSource === 'approval' && approvalsError"
              class="wb-empty wb-error-text"
              role="alert"
            >
              {{ approvalsError }}
            </p>
            <p v-else-if="!recentTodos.length" class="wb-empty">
              {{ currentTaskTotal ? '暂无预览事项，请进入对应业务查看。' : '暂无待处理事项' }}
            </p>
            <template v-else>
              <div class="wb-table-head" aria-hidden="true">
                <span>事项 / 来源</span><span>办理时限</span><span>操作</span>
              </div>
              <ul class="wb-task-list">
                <li v-for="t in recentTodos" :key="t.todoId">
                  <div class="wb-task-title">
                    <strong>{{ t.title }}</strong
                    ><small>{{ todoMeta(t) }}</small>
                  </div>
                  <span
                    class="wb-deadline"
                    :class="{ 'is-over': isOverdue(t), 'is-near': isNearDeadline(t) }"
                    >{{ t.dueAt ? dueLabel(t) : '未设时限' }}</span
                  >
                  <button
                    type="button"
                    class="wb-handle"
                    :disabled="!t.typedRouteTarget"
                    :title="t.typedRouteTarget ? t.title : '暂未开通直达入口，请前往对应业务模块'"
                    @click="openTodo(t)"
                  >
                    {{
                      !t.typedRouteTarget
                        ? '暂无直达'
                        : t.focusMode === 'DETAIL'
                          ? '去处理'
                          : '进入业务'
                    }}
                  </button>
                </li>
              </ul>
              <footer class="wb-list-footer">
                已展示 {{ recentTodos.length }} 项<button
                  v-if="taskSource === 'approval' && currentTaskTotal > recentTodos.length"
                  type="button"
                  class="wb-link"
                  @click="go('/admin/approval/todos')"
                >
                  查看其余待办
                </button>
                <button v-if="taskSource === 'business' && todos.length < todoTotal" type="button" class="wb-link" :disabled="businessMoreBusy" @click="loadMoreBusiness">{{ businessMoreBusy ? '加载中…' : '加载更多' }}</button>
                <span v-if="taskSource === 'business' && businessMoreError" role="alert">{{ businessMoreError }}</span>
              </footer>
            </template>
          </div>
        </section>

        <div v-if="riskItems.length" class="wb-alerts" aria-label="需要关注">
          <button v-for="item in riskItems" :key="item.key" type="button" @click="go(item.path)">
            {{ item.text }}<span>查看</span>
          </button>
        </div>

        <section class="wb-shortcuts" aria-label="个人常用入口">
          <span>常用</span>
          <button v-for="l in displayLinks" :key="l.to" type="button" @click="go(l.to)">
            {{ l.label }}
          </button>
          <button type="button" @click="goMessages">
            消息<span v-if="unread" class="wb-badge">{{ unread }}</span>
          </button>
        </section>

        <section v-if="recipe.showSchedule" class="wb-panel wb-schedule">
          <header class="wb-section-head">
            <h2>
              今日课程 <small>{{ todayLabel }}</small>
            </h2>
            <button type="button" class="wb-link" @click="go(scheduleLink)">查看课表</button>
          </header>
          <p v-if="scheduleLoading" class="wb-empty">课表加载中…</p>
          <p v-else-if="scheduleError" class="wb-empty wb-error-text">课表暂不可用，请稍后刷新</p>
          <p v-else-if="!scheduleItems.length" class="wb-empty">今日无课程安排</p>
          <ol v-else>
            <li v-for="item in contextItems" :key="item.key">
              <time>{{ item.time }}</time
              ><strong>{{ item.title }}</strong
              ><span>{{ item.meta }}</span>
            </li>
          </ol>
        </section>

        <details v-if="scopeCards.length" class="wb-scope">
          <summary>业务概况<span v-if="statsError">统计暂不可用</span></summary>
          <div>
            <button v-for="c in scopeCards" :key="c.key" type="button" @click="onDrill(c)">
              <span>{{ c.title }}</span
              ><strong>{{
                loading || valueOf(c.source) === null ? '—' : valueOf(c.source)
              }}</strong>
            </button>
          </div>
        </details>
      </template>

      <section v-if="editing" id="workbench-editor" class="wb-panel wb-editor">
        <header class="wb-section-head">
          <h2>自定义工作台</h2>
          <button type="button" class="wb-link" @click="restoreDefaults">恢复默认</button>
        </header>
        <div class="wb-edit-grid">
          <fieldset>
            <legend>汇总显隐与排序</legend>
            <div v-for="(c, idx) in editSummaryList" :key="c.key" class="wb-edit-row">
              <label
                ><input
                  type="checkbox"
                  :checked="!tileHidden.has(c.key)"
                  @change="toggleTile(c.key, $event.target.checked)"
                />{{ c.title }}</label
              >
              <span
                ><button
                  type="button"
                  :disabled="idx === 0"
                  :aria-label="'上移' + c.title"
                  @click="moveTile(c.key, -1)"
                >
                  上移</button
                ><button
                  type="button"
                  :disabled="idx === editSummaryList.length - 1"
                  :aria-label="'下移' + c.title"
                  @click="moveTile(c.key, 1)"
                >
                  下移
                </button></span
              >
            </div>
          </fieldset>
          <fieldset>
            <legend>常用入口</legend>
            <label v-for="l in recipe.quickLinks" :key="l.to" class="wb-edit-row"
              ><span
                ><input
                  type="checkbox"
                  :checked="favSet.has(l.to)"
                  @change="toggleFav(l.to, $event.target.checked)"
                />{{ l.label }}</span
              ></label
            >
          </fieldset>
        </div>
      </section>
    </details>
  </div>
</template>

<script>
/**
 * WorkbenchView —— 角色化工作台（对标 Dynamics 365 Role Center）。
 * 角色以后端 /todos/summary.role 为准；P7 偏好只改布局，不改权限。
 */
import StudentAffairsPriorityPanel from '../components/StudentAffairsPriorityPanel.vue'
import { matchPermission } from '@/config/navPlan'
import { approvalApi } from '@/modules/approval/api/approval.api'
import AppPageGuide from '@/components/common/experience/AppPageGuide.vue'
import {
  fetchMessageCount,
  fetchMyScheduleToday,
  fetchSchoolStats,
  fetchTodoCount,
  fetchTodoList,
  fetchTodoSummary,
  trackWorkbenchEvent
} from '../api/workbench.api'
import {
  applyFavoriteLinks,
  applyTilePrefs,
  favoritesPrefKey,
  loadPrefs,
  parseJsonPref,
  savePref,
  tilesPrefKey
} from '../api/workbenchPrefs'
import { resolveRecipe, TODO_TYPE_ROUTES } from '../config/workbenchRecipes'
import { currentUserFromToken } from '@/services/http/client'

const EMPTY_SUMMARY = Object.freeze({
  pending: 0,
  overdue: 0,
  nearDeadline: 0,
  doneToday: 0
})

const EMPTY_STATS = Object.freeze({
  studentTotal: 0,
  pendingApproval: 0,
  academicWarning: 0,
  unemployed: 0,
  orientationPending: 0,
  scopeLabel: ''
})

export default {
  name: 'WorkbenchView',
  components: { AppPageGuide, StudentAffairsPriorityPanel },
  props: {
    ctx: { type: Object, default: null },
    displayName: { type: String, default: '老师' }
  },
  data() {
    return {
      loading: true,
      loadingRequest: false,
      error: '',
      statsError: false,
      role: '',
      summary: { ...EMPTY_SUMMARY },
      stats: { ...EMPTY_STATS },
      byType: {},
      todos: [],
      approvals: [],
      approvalsError: '',
      todoTotal: 0,
      taskSource: 'approval',
      businessPage: 1, businessEpoch: 0, businessMoreBusy: false, businessMoreError: '',
      unread: 0,
      editing: false,
      tilePref: { order: [], hidden: [] },
      favPaths: [],
      scheduleItems: [],
      scheduleLoading: false,
      scheduleError: false
    }
  },
  computed: {
    showStudentAffairs() {
      return matchPermission(this.ctx?.permissionPatterns || [], 'studentAffairs.dashboard.view')
    },
    recipe() {
      return resolveRecipe(this.role)
    },
    scheduleLink() {
      const u = currentUserFromToken() || {}
      const key = String(u.loginName || u.userId || '').trim()
      return key
        ? `/admin/academic-affairs/schedule/teacher/${encodeURIComponent(key)}`
        : '/admin/academic-affairs/schedule/teacher'
    },
    tileHidden() {
      return new Set(this.tilePref.hidden || [])
    },
    favSet() {
      return new Set(this.favPaths || [])
    },
    editSummaryList() {
      return applyTilePrefs(this.recipe.summaryCues, {
        order: this.tilePref.order || [],
        hidden: []
      })
    },
    visibleSummaryCues() {
      return applyTilePrefs(this.recipe.summaryCues, this.tilePref)
    },
    visibleStatsCues() {
      return (this.recipe.statsCues || []).filter((c) => !this.tileHidden.has(c.key))
    },
    visibleTypeCues() {
      return (this.recipe.typeCues || []).filter((c) => this.valueOf(c.source) > 0)
    },
    displayLinks() {
      const links = applyFavoriteLinks(this.recipe.quickLinks, this.favPaths)
      if (!this.favPaths.length) return links
      return links.filter((l) => l.favorited)
    },
    todayLabel() {
      return new Intl.DateTimeFormat('zh-CN', {
        month: 'long',
        day: 'numeric',
        weekday: 'short'
      }).format(new Date())
    },
    scopeCards() {
      const source = this.visibleStatsCues.filter((c) => c.key !== 'pendingApproval')
      if (!source.length) source.push(...this.visibleTypeCues)
      return source.slice(0, 4)
    },
    recentTodos() {
      if (this.taskSource === 'business') return this.todos
      return this.approvals.map((task) => ({
        todoId: task.taskId,
        title: task.title,
        todoTypeName: task.bizTypeLabel,
        sourceName: [task.applicantName, task.className]
          .filter((value) => value && value !== '—')
          .join(' · '),
        dueAt: task.deadline,
        typedRouteTarget: task.taskId
          ? '/admin/approval/todos/' + encodeURIComponent(task.taskId)
          : '',
        focusMode: 'DETAIL'
      }))
    },
    currentTaskTotal() {
      return this.taskSource === 'approval' ? this.summary.pending : this.todoTotal
    },
    contextItems() {
      if (this.recipe.showSchedule && this.scheduleItems.length) {
        return this.scheduleItems.slice(0, 4).map((s, index) => ({
          key: s.id || `schedule-${index}`,
          time: s.startTime || s.time || s.slotName || s.slotLabel || `${index + 1}`,
          title: this.scheduleTitle(s),
          meta: this.scheduleSlot(s)
        }))
      }
      return this.todos.slice(0, 4).map((t, index) => ({
        key: t.todoId || `todo-${index}`,
        time: t.dueAt ? this.fmtTime(t.dueAt) : '待办',
        title: t.title,
        meta: this.todoMeta(t)
      }))
    },
    // V3 施工手册 TP-W10：逾期待办与学业预警是两类不同风险，此前用 `||` 只取其一，
    // 同时存在时会丢掉一类真实风险数字。拆成两个独立条目，都展示、各自可下钻。
    riskItems() {
      const items = []
      const overdue = Number(this.summary.overdue || 0)
      if (overdue > 0) {
        items.push({
          key: 'overdue',
          count: overdue,
          text: `有 ${overdue} 项已逾期待办`,
          hint: '建议优先进入待办台账处理',
          path: '/admin/approval/todos?urgency=OVERDUE'
        })
      }
      const warning = Number(this.stats.academicWarning || 0)
      if (warning > 0) {
        items.push({
          key: 'academicWarning',
          count: warning,
          text: `有 ${warning} 项学业预警在办`,
          hint: '建议优先进入预警台账处理',
          path: TODO_TYPE_ROUTES.ACAD_WARNING_HANDLE
        })
      }
      return items
    }
  },
  created() {
    this.load()
  },
  methods: {
    showBusinessQueue() {
      this.taskSource = 'business'
      this.$el.querySelector('.wb-personal-details').open = true
      this.$nextTick(() => this.$el.querySelector('.wb-personal-details .wb-tasks').scrollIntoView({ block: 'start' }))
    },
    async loadMoreBusiness() {
      if (this.businessMoreBusy || this.loading || this.todos.length >= this.todoTotal) return
      const epoch = this.businessEpoch, page = this.businessPage + 1
      this.businessMoreBusy = true; this.businessMoreError = ''
      try {
        const result = await fetchTodoList({ page, pageSize: 8 })
        if (epoch !== this.businessEpoch) return
        if (!Array.isArray(result?.items)) throw new Error('待办列表暂不可用')
        this.todos = [...new Map([...this.todos, ...result.items].map(todo => [String(todo.todoId), todo])).values()]
        this.todoTotal = Number(result.total || 0); this.businessPage = page
      } catch (error) {
        if (epoch === this.businessEpoch) this.businessMoreError = error.message || '加载失败，请重试'
      } finally { if (epoch === this.businessEpoch) this.businessMoreBusy = false }
    },
    toggleEditing() {
      this.editing = !this.editing
      if (this.editing) this.$el.querySelector('.wb-personal-details').open = true
    },
    async load() {
      // V3 施工手册 TP-W08：核心待办/消息与非核心范围内统计（stats.workbench）
      // 分区加载，用 allSettled 而不是 all——以前统计接口一超时/500，
      // Promise.all 整体 reject，连正常返回的待办和消息也被 catch 块清空重置成
      // 假空态，让老师以为自己"今天没有待办"。
      this.$refs.priorityPanel?.load()
      if (this.loadingRequest) return
      this.businessEpoch++; this.businessPage = 1; this.businessMoreBusy = false; this.businessMoreError = ''
      this.loadingRequest = true
      this.loading = true
      this.error = ''
      this.statsError = false

      const [coreResult, statsResult, approvalResult] = await Promise.allSettled([
        Promise.all([fetchTodoSummary(), fetchTodoCount(), fetchTodoList(), fetchMessageCount()]),
        fetchSchoolStats(),
        approvalApi.getTodos({ page: 1, pageSize: 8 })
      ])

      this.approvalsError = ''
      if (approvalResult.status === 'fulfilled' && approvalResult.value.code === 0) {
        this.approvals = approvalResult.value.data.list || []
      } else {
        this.approvals = []
        this.approvalsError =
          approvalResult.status === 'rejected'
            ? approvalResult.reason?.message || '审批任务加载失败'
            : approvalResult.value.message || '审批任务加载失败'
      }

      if (coreResult.status === 'fulfilled') {
        const [summary, count, list, msg] = coreResult.value
        this.role = summary.role || ''
        this.summary = {
          pending: Number(summary.pending) || 0,
          overdue: Number(summary.overdue) || 0,
          nearDeadline: Number(summary.nearDeadline) || 0,
          doneToday: Number(summary.doneToday) || 0
        }
        this.byType = count.byType && typeof count.byType === 'object' ? { ...count.byType } : {}
        this.todos = Array.isArray(list.items) ? list.items : []
        this.todoTotal = Number(list.total) || 0
        this.unread = Number(msg.unread) || 0
      } else {
        this.role = ''
        this.summary = { ...EMPTY_SUMMARY }
        this.byType = {}
        this.todos = []
        this.todoTotal = 0
        this.unread = 0
        this.error = (coreResult.reason && coreResult.reason.message) || '请求失败'
      }

      const schoolStats = statsResult.status === 'fulfilled' ? statsResult.value : null
      if (schoolStats && typeof schoolStats === 'object') {
        this.stats = {
          studentTotal: Number(schoolStats.studentTotal) || 0,
          pendingApproval: Number(schoolStats.pendingApproval) || 0,
          academicWarning: Number(schoolStats.academicWarning) || 0,
          unemployed: Number(schoolStats.unemployed) || 0,
          orientationPending: Number(schoolStats.orientationPending) || 0,
          scopeLabel: schoolStats.scopeLabel || ''
        }
      } else {
        this.stats = { ...EMPTY_STATS }
        this.statsError = statsResult.status === 'rejected'
      }

      await this.loadPrefsQuiet()
      if (this.recipe.showSchedule) await this.loadScheduleQuiet()
      this.loading = false
      this.loadingRequest = false
    },
    async loadScheduleQuiet() {
      this.scheduleLoading = true
      this.scheduleError = false
      try {
        const u = currentUserFromToken() || {}
        const key = String(u.loginName || u.userId || '').trim()
        const res = await fetchMyScheduleToday(key)
        this.scheduleItems = Array.isArray(res.items) ? res.items : []
      } catch {
        // V3 施工手册 TP-W09：故障与"今天真的没课"是两种不同事实，不能都显示
        // "今天暂无安排"——教务接口故障时必须诚实报错，不能伪装成空。
        this.scheduleItems = []
        this.scheduleError = true
      } finally {
        this.scheduleLoading = false
      }
    },
    async loadPrefsQuiet() {
      try {
        const tk = tilesPrefKey(this.role)
        const fk = favoritesPrefKey(this.role)
        const items = await loadPrefs([tk, fk])
        this.tilePref = parseJsonPref(items[tk], { order: [], hidden: [] })
        this.favPaths = parseJsonPref(items[fk], [])
        if (!Array.isArray(this.favPaths)) this.favPaths = []
        if (!Array.isArray(this.tilePref.hidden)) this.tilePref.hidden = []
        if (!Array.isArray(this.tilePref.order)) this.tilePref.order = []
      } catch {
        // 偏好失败不影响待办数字
      }
    },
    async persistTiles() {
      try {
        await savePref(tilesPrefKey(this.role), this.tilePref)
      } catch {
        /* 忽略 */
      }
    },
    async persistFavs() {
      try {
        await savePref(favoritesPrefKey(this.role), this.favPaths)
      } catch {
        /* 忽略 */
      }
    },
    toggleTile(key, visible) {
      const hidden = new Set(this.tilePref.hidden || [])
      if (visible) hidden.delete(key)
      else hidden.add(key)
      this.tilePref = { ...this.tilePref, hidden: [...hidden] }
      this.persistTiles()
    },
    moveTile(key, delta) {
      const list = this.editSummaryList.map((c) => c.key)
      const i = list.indexOf(key)
      const j = i + delta
      if (i < 0 || j < 0 || j >= list.length) return
      const next = [...list]
      const tmp = next[i]
      next[i] = next[j]
      next[j] = tmp
      this.tilePref = { ...this.tilePref, order: next }
      this.persistTiles()
    },
    toggleFav(to, on) {
      const set = new Set(this.favPaths || [])
      if (on) set.add(to)
      else set.delete(to)
      this.favPaths = [...set]
      this.persistFavs()
    },
    async restoreDefaults() {
      this.tilePref = { order: [], hidden: [] }
      this.favPaths = []
      await Promise.all([this.persistTiles(), this.persistFavs()])
      this.editing = false
    },
    valueOf(source) {
      const [ns, key] = String(source || '').split('.')
      if (ns === 'summary') return this.summary[key] || 0
      if (ns === 'todoType') return this.byType[key] || 0
      // V3 施工手册 TP-W08：范围内统计（stats.workbench）故障时诚实返回 null（模板
      // 显示"—"），不能借 EMPTY_STATS 的兜底 0 冒充"范围内真的是 0"。
      if (ns === 'stats') return this.statsError ? null : this.stats[key] || 0
      if (ns === 'message') return this.unread || 0
      return 0
    },
    onDrill(c) {
      this.trackClick(c && c.key, c && c.to)
      this.go(c && c.to)
    },
    goMessages() {
      this.trackClick('messages', '/admin/messages/inbox')
      this.go('/admin/messages/inbox')
    },
    trackClick(key, path) {
      trackWorkbenchEvent('WORKBENCH_CLICK', {
        cueKey: key || '',
        path: path || '',
        role: this.role || ''
      }).catch(() => {
        /* 埋点失败不阻断导航 */
      })
    },
    go(path) {
      if (!path) return
      const full = String(path)
      if (this.$route.fullPath !== full) this.$router.push(full).catch(() => {})
    },
    openTodo(t) {
      // V3 施工手册 TP-W06：不再本地猜路由。服务端有 typedRouteTarget 就导航；
      // 没有就 fail-closed（禁用 + 提示原因），不再拿 TODO_TYPE_ROUTES 或拼
      // todoType/status 兜底——那两条路径都不保证真的存在对应能力，点了可能
      // 落进空壳或全量列表，误导成"已处理"。
      const type = t && t.todoType
      const typedTarget = String(t?.typedRouteTarget || '').trim()
      if (!typedTarget) {
        this.trackClick(type || 'todo', '')
        this.$message?.warning?.('该类待办暂未开通工作台直达入口，请前往对应业务模块处理')
        return
      }
      this.trackClick(type || 'todo', typedTarget)
      this.go(typedTarget)
    },
    scheduleTitle(s) {
      return [s.courseName || s.course || '课程', s.className || s.teachingClassName || '']
        .filter(Boolean)
        .join(' · ')
    },
    scheduleSlot(s) {
      const slot =
        s.slotName ||
        s.slotLabel ||
        (s.startSlot && s.endSlot ? `${s.startSlot}-${s.endSlot}节` : '')
      const room = s.classroom || s.roomName || ''
      return [slot, room].filter(Boolean).join(' · ')
    },
    priorityClass(priority) {
      const p = String(priority || 'NORMAL').toLowerCase()
      return `is-${p}`
    },
    isOverdue(t) {
      return !!t.dueAt && new Date(t.dueAt).getTime() < Date.now()
    },
    isNearDeadline(t) {
      if (!t.dueAt || this.isOverdue(t)) return false
      const due = new Date(t.dueAt).getTime()
      return due <= Date.now() + 24 * 60 * 60 * 1000
    },
    dueLabel(t) {
      if (this.isOverdue(t)) return '已逾期'
      if (this.isNearDeadline(t)) return '即将到期 ' + this.fmtDate(t.dueAt)
      return '截止 ' + this.fmtDate(t.dueAt)
    },
    fmtDate(v) {
      const d = new Date(v)
      if (Number.isNaN(d.getTime())) return ''
      return `${d.getMonth() + 1}月${d.getDate()}日`
    },
    fmtTime(v) {
      const d = new Date(v)
      if (Number.isNaN(d.getTime())) return '待办'
      return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
    },
    todoMeta(t) {
      if (['WORK_STUDY_REVIEW', 'WORK_STUDY_ONBOARD'].includes(t.todoType)) return `勤工助学 · 记录 ${t.recordId || t.bizId || '待核对'}`
      if (['STUDENT_LOAN_REVIEW', 'STUDENT_LOAN_CONFIRM'].includes(t.todoType)) return `助学贷款 · 记录 ${t.recordId || t.bizId || '待核对'}`
      if (['FEE_REDUCTION_REVIEW', 'FEE_REDUCTION_FULFILL'].includes(t.todoType)) return `减免临补 · 申请 ${t.recordId || t.bizId || '待核对'}`
      return [
        t.moduleName || t.bizTypeLabel || t.todoTypeName || t.todoType || '业务待办',
        t.assigneeName || t.sourceName || ''
      ]
        .filter(Boolean)
        .join(' · ')
    }
  }
}
</script>

<style scoped>
.wb-focus {
  color: var(--t1, #243650);
  min-width: 0;
  font-size: 14px;
}
.wb-focus button {
  font: inherit;
  cursor: pointer;
  color: inherit;
  border: 1px solid var(--line, #dde4ee);
  background: var(--surface, #fff);
  border-radius: 6px;
  padding: 6px 12px;
}
.wb-focus button:hover:not(:disabled) {
  color: var(--pri, #285dc0);
  background: var(--pri-50, #edf3fc);
}
.wb-focus button:focus-visible,
.wb-scope summary:focus-visible {
  outline: 2px solid var(--pri, #285dc0);
  outline-offset: 3px;
}
.wb-focus button:disabled {
  opacity: 0.55;
  cursor: default;
}
.wb-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin: 0 0 14px;
  min-height: 38px;
}
.wb-heading h1 {
  margin: 0;
  font-size: 22px;
  font-weight: 650;
}
.wb-tools {
  display: flex;
  gap: 6px;
}
.wb-tools button {
  background: transparent;
  border-color: transparent;
  color: var(--t3, #65758b);
}
.wb-summary {
  display: flex;
  flex-wrap: wrap;
  padding: 4px 0;
  margin-bottom: 16px;
  border-block: 1px solid var(--line, #dde4ee);
}
.wb-summary button {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 12px 20px;
  background: transparent;
  border: 0;
  border-radius: 0;
  min-width: 150px;
}
.wb-summary button + button {
  border-left: 1px solid var(--line, #dde4ee);
}
.wb-summary span {
  font-size: 13px;
  color: var(--t3, #65758b);
}
.wb-summary strong {
  font-size: 25px;
  font-weight: 650;
  font-variant-numeric: tabular-nums;
}
.wb-summary .is-primary strong {
  color: var(--pri, #285dc0);
}
.wb-summary .is-risk.has-value strong,
.wb-deadline.is-over {
  color: var(--danger, #c9444c);
}
.wb-summary .is-warning.has-value strong,
.wb-deadline.is-near {
  color: var(--warning, #a76816);
}
.wb-panel {
  border: 1px solid var(--line, #dde4ee);
  background: var(--surface, #fff);
  border-radius: 8px;
  overflow: hidden;
}
.wb-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 18px;
}
.wb-section-head h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 650;
}
.wb-focus .wb-link {
  border: 0;
  padding: 4px 0;
  background: transparent;
  color: var(--pri, #285dc0);
  font-size: 13px;
}
.wb-types {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 0 18px 12px;
}
.wb-types button {
  font-size: 12px;
  padding: 4px 9px;
  background: transparent;
}
.wb-types b {
  margin-left: 6px;
  color: var(--pri, #285dc0);
}
.wb-table-head,
.wb-task-list li {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 170px 100px;
  align-items: center;
  gap: 20px;
  padding: 12px 18px;
}
.wb-table-head {
  background: var(--surface-2, #f6f8fb);
  font-size: 12px;
  color: var(--t3, #65758b);
  padding-block: 9px;
  border-block: 1px solid var(--line, #dde4ee);
}
.wb-table-head span:last-child {
  text-align: right;
}
.wb-task-list {
  margin: 0;
  padding: 0;
  list-style: none;
}
.wb-task-list li {
  min-height: 70px;
  box-sizing: border-box;
  border-bottom: 1px solid var(--line, #dde4ee);
}
.wb-task-list li:last-child {
  border-bottom: 0;
}
.wb-task-list li:hover {
  background: var(--surface-2, #f6f8fb);
}
.wb-task-title {
  display: flex;
  flex-direction: column;
  gap: 5px;
  min-width: 0;
}
.wb-task-title strong {
  font-size: 14px;
  font-weight: 550;
  overflow-wrap: anywhere;
}
.wb-task-title small {
  color: var(--t3, #65758b);
  font-size: 12px;
  overflow-wrap: anywhere;
}
.wb-deadline {
  font-size: 13px;
  color: var(--t3, #65758b);
}
.wb-focus .wb-handle {
  justify-self: end;
  color: var(--pri, #285dc0);
  border-color: var(--line, #dde4ee);
  white-space: nowrap;
  font-size: 13px;
}
.wb-list-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 18px;
  border-top: 1px solid var(--line, #dde4ee);
  font-size: 12px;
  color: var(--t3, #65758b);
}
.wb-empty {
  padding: 32px 18px;
  margin: 0;
  font-size: 14px;
  color: var(--t3, #65758b);
  text-align: center;
}
.wb-alerts {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 12px;
}
.wb-alerts button {
  color: var(--danger, #c9444c);
  background: transparent;
  font-size: 13px;
  border: 0;
  padding: 4px 0;
}
.wb-alerts span {
  margin-left: 12px;
  text-decoration: underline;
}
.wb-shortcuts {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  padding: 16px 0;
}
.wb-shortcuts > span {
  color: var(--t3, #65758b);
  font-size: 13px;
  margin-right: 6px;
}
.wb-shortcuts button {
  background: transparent;
  font-size: 13px;
}
.wb-badge {
  padding-left: 8px;
  color: var(--pri, #285dc0);
  font-variant-numeric: tabular-nums;
}
.wb-schedule {
  margin-bottom: 12px;
}
.wb-schedule h2 small {
  font-size: 12px;
  font-weight: 400;
  color: var(--t3, #65758b);
  margin-left: 12px;
}
.wb-schedule ol {
  margin: 0;
  padding: 0 18px;
  list-style: none;
}
.wb-schedule li {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 12px 0;
  border-top: 1px solid var(--line, #dde4ee);
  flex-wrap: wrap;
}
.wb-schedule time {
  color: var(--pri, #285dc0);
}
.wb-schedule strong {
  font-size: 14px;
  font-weight: 500;
}
.wb-schedule li span {
  font-size: 13px;
  color: var(--t3, #65758b);
}
.wb-scope {
  border-top: 1px solid var(--line, #dde4ee);
  color: var(--t3, #65758b);
}
.wb-scope summary {
  cursor: pointer;
  font-size: 13px;
  padding: 12px 0;
}
.wb-scope summary span {
  margin-left: 16px;
}
.wb-scope > div {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding: 0 0 12px;
}
.wb-scope button {
  display: flex;
  gap: 18px;
  align-items: center;
  background: transparent;
  font-size: 13px;
}
.wb-scope strong {
  color: var(--t1, #243650);
  font-size: 18px;
}
.wb-editor {
  margin-top: 14px;
}
.wb-edit-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
  padding: 8px 18px 16px;
}
.wb-edit-grid fieldset {
  border: 0;
  margin: 0;
  padding: 0;
  min-width: 0;
}
.wb-edit-grid legend {
  color: var(--t3, #65758b);
  margin-bottom: 8px;
  font-size: 13px;
}
.wb-edit-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 5px 0;
  font-size: 13px;
}
.wb-edit-row label,
.wb-edit-row > span {
  display: flex;
  align-items: center;
  gap: 8px;
}
.wb-edit-row button {
  font-size: 12px;
  padding: 3px 7px;
}
.wb-edit-row input {
  accent-color: var(--pri, #285dc0);
}
.wb-error {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 16px;
  padding: 18px;
  background: var(--surface, #fff);
  border: 1px solid var(--line, #dde4ee);
  border-radius: 8px;
}
.wb-error,
.wb-error-text {
  color: var(--danger, #c9444c);
}
@media (max-width: 900px) {
  .wb-summary button {
    min-width: 40%;
  }
  .wb-summary button:nth-child(3) {
    border-left: 0;
  }
  .wb-table-head,
  .wb-task-list li {
    grid-template-columns: minmax(0, 1fr) 120px 85px;
    gap: 12px;
  }
}
@media (max-width: 600px) {
  .wb-heading {
    flex-wrap: wrap;
  }
  .wb-heading h1 {
    font-size: 20px;
  }
  .wb-edit-grid {
    grid-template-columns: 1fr;
  }
  .wb-table-head {
    display: none;
  }
  .wb-task-list li {
    grid-template-columns: minmax(0, 1fr) auto;
  }
  .wb-task-title {
    grid-column: 1/-1;
  }
  .wb-summary button {
    padding: 10px;
    gap: 8px;
  }
  .wb-summary strong {
    font-size: 22px;
  }
}
.wb-task-tabs {
  display: flex;
  gap: 20px;
}
.wb-focus .wb-task-tabs button {
  border: 0;
  border-radius: 0;
  padding: 5px 0;
  background: transparent;
  color: var(--t3, #65758b);
  border-bottom: 2px solid transparent;
}
.wb-focus .wb-task-tabs button[aria-selected='true'] {
  color: var(--pri, #285dc0);
  border-bottom-color: var(--pri, #285dc0);
  font-weight: 600;
}
.wb-task-tabs b {
  margin-left: 6px;
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}
.wb-personal-details {
  margin-top: 14px;
}
.wb-personal-details > summary {
  color: var(--t3, #65758b);
  font-size: 13px;
  padding: 10px 0;
  cursor: pointer;
}
.wb-personal-details[open] > summary {
  margin-bottom: 12px;
}
</style>
