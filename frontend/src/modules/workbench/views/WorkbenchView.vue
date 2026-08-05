<template>
  <div class="wb-v2">
    <AppPageGuide guide-key="workbench.first-login" />

    <div class="wb-v2__layout">
      <main class="wb-v2__main">
        <section class="wb-v2__hero">
          <div class="wb-v2__hero-copy">
            <span class="wb-v2__eyebrow">{{ recipe.label }}</span>
            <h1>{{ greeting }}，{{ displayName }} <span aria-hidden="true">👋</span></h1>
            <p class="wb-v2__headline" :class="{ 'is-risk': hasOverdue && !error && !loading }">
              <span v-if="loading">正在读取你的今日工作安排…</span>
              <span v-else-if="error">工作台数据暂时未能加载</span>
              <span v-else>{{ headline }}</span>
            </p>
            <div class="wb-v2__hero-meta">
              <span>
                <svg viewBox="0 0 24 24">
                  <path
                    d="M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM3 21v-2a6 6 0 0 1 12 0v2M17 8h4M19 6v4"
                  />
                </svg>
                当前身份：{{ recipe.label.replace('工作台', '') || '教职工' }}
              </span>
              <span v-if="scopeLabel">
                <svg viewBox="0 0 24 24">
                  <path d="M12 3 4 6v5c0 5 3.5 8.5 8 10 4.5-1.5 8-5 8-10V6l-8-3Z" />
                </svg>
                数据范围：{{ scopeLabel }}
              </span>
            </div>
            <div class="wb-v2__hero-actions">
              <button type="button" class="is-light" :disabled="loading" @click="load">
                <svg viewBox="0 0 24 24"><path d="M20 12a8 8 0 1 1-2.3-5.7M20 4v6h-6" /></svg>
                刷新
              </button>
              <button type="button" @click="go('/admin/approval/todos?status=PENDING')">
                查看全部待办 <span>→</span>
              </button>
            </div>
          </div>
          <div class="wb-v2__hero-art" aria-hidden="true">
            <span class="wb-v2__glass wb-v2__glass--one" />
            <span class="wb-v2__glass wb-v2__glass--two" />
            <span class="wb-v2__glass wb-v2__glass--three">
              <svg viewBox="0 0 64 64">
                <path d="M13 47V25l19-10 19 10v22L32 57 13 47Z" />
                <path d="m13 25 19 11 19-11M32 36v21" />
              </svg>
            </span>
            <i v-for="n in 8" :key="n" :class="'is-spark-' + n" />
          </div>
        </section>

        <div v-if="error" class="wb-v2__error" role="alert">
          <div>
            <strong>无法加载工作台数据</strong><span>{{ error }}</span>
          </div>
          <button type="button" @click="load">重新加载</button>
        </div>

        <template v-else>
          <section class="wb-v2__action-grid" aria-label="待办指标">
            <button
              v-for="c in visibleSummaryCues"
              :key="c.key"
              type="button"
              class="wb-v2__action-card"
              :class="'is-' + c.accent"
              @click="onDrill(c)"
            >
              <span class="wb-v2__metric-icon">
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.8"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <path v-for="(d, index) in iconPaths(c.key)" :key="index" :d="d" />
                </svg>
              </span>
              <span class="wb-v2__action-copy">
                <small>{{ c.title }}</small>
                <strong>{{ loading ? '—' : valueOf(c.source) }}</strong>
                <em>{{ cueHint(c) }}</em>
              </span>
              <span class="wb-v2__action-arrow">›</span>
            </button>
          </section>

          <section v-if="scopeCards.length" class="wb-v2__panel wb-v2__scope-panel">
            <header class="wb-v2__section-head">
              <div>
                <h2>范围内指标</h2>
                <p v-if="scopeLabel">{{ scopeLabel }} · 实时业务概览</p>
              </div>
              <button
                type="button"
                class="wb-v2__settings"
                title="编辑工作台布局"
                @click="editing = !editing"
              >
                <svg viewBox="0 0 24 24">
                  <path d="M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z" />
                  <path
                    d="M19.4 15a1.8 1.8 0 0 0 .4 2l.1.1-2.8 2.8-.1-.1a1.8 1.8 0 0 0-2-.4 1.8 1.8 0 0 0-1.1 1.7v.2h-4v-.2A1.8 1.8 0 0 0 8.8 19a1.8 1.8 0 0 0-2 .4l-.1.1-2.8-2.8.1-.1a1.8 1.8 0 0 0 .4-2A1.8 1.8 0 0 0 2.7 13h-.2V9h.2a1.8 1.8 0 0 0 1.7-1.1 1.8 1.8 0 0 0-.4-2l-.1-.1L6.7 3l.1.1a1.8 1.8 0 0 0 2 .4A1.8 1.8 0 0 0 9.9 2h4a1.8 1.8 0 0 0 1.1 1.5 1.8 1.8 0 0 0 2-.4l.1-.1 2.8 2.8-.1.1a1.8 1.8 0 0 0-.4 2A1.8 1.8 0 0 0 21.1 9h.2v4h-.2a1.8 1.8 0 0 0-1.7 2Z"
                  />
                </svg>
              </button>
            </header>
            <div class="wb-v2__stat-grid">
              <button
                v-for="(c, index) in scopeCards"
                :key="c.key"
                type="button"
                class="wb-v2__stat-card"
                :class="'is-tone-' + (index % 4)"
                @click="onDrill(c)"
              >
                <span class="wb-v2__stat-icon">
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="1.8"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  >
                    <path v-for="(d, iconIndex) in iconPaths(c.key)" :key="iconIndex" :d="d" />
                  </svg>
                </span>
                <span>
                  <small>{{ c.title }}</small>
                  <strong>{{ valueOf(c.source) }}</strong>
                  <em>{{ statHint(c) }}</em>
                </span>
              </button>
            </div>
            <div v-if="visibleTypeCues.length" class="wb-v2__type-strip">
              <span>业务待办</span>
              <button
                v-for="c in visibleTypeCues.slice(0, 5)"
                :key="c.key"
                type="button"
                @click="onDrill(c)"
              >
                {{ c.title }} <strong>{{ valueOf(c.source) }}</strong>
              </button>
            </div>
          </section>

          <section v-if="editing" class="wb-v2__panel wb-v2__editor">
            <header class="wb-v2__section-head">
              <div>
                <h2>编辑工作台</h2>
                <p>偏好仅影响你本人，不改变权限与数据范围</p>
              </div>
              <button type="button" class="wb-v2__text-btn" @click="restoreDefaults">
                恢复默认
              </button>
            </header>
            <div class="wb-v2__edit-grid">
              <div>
                <h3>待办指标显隐与排序</h3>
                <div v-for="(c, idx) in editSummaryList" :key="c.key" class="wb-v2__edit-row">
                  <label
                    ><input
                      type="checkbox"
                      :checked="!tileHidden.has(c.key)"
                      @change="toggleTile(c.key, $event.target.checked)"
                    />{{ c.title }}</label
                  >
                  <span
                    ><button type="button" :disabled="idx === 0" @click="moveTile(c.key, -1)">
                      上移</button
                    ><button
                      type="button"
                      :disabled="idx === editSummaryList.length - 1"
                      @click="moveTile(c.key, 1)"
                    >
                      下移
                    </button></span
                  >
                </div>
              </div>
              <div>
                <h3>我的常用</h3>
                <label v-for="l in recipe.quickLinks" :key="l.to" class="wb-v2__edit-row">
                  <span
                    ><input
                      type="checkbox"
                      :checked="favSet.has(l.to)"
                      @change="toggleFav(l.to, $event.target.checked)"
                    />{{ l.label }}</span
                  >
                </label>
              </div>
            </div>
          </section>

          <div class="wb-v2__lower-grid">
            <section class="wb-v2__panel wb-v2__todos">
              <header class="wb-v2__section-head">
                <div>
                  <h2>
                    最近待办 <b v-if="todos.length">{{ todos.length }}</b>
                  </h2>
                  <p>优先展示逾期和即将到期事项</p>
                </div>
                <button
                  type="button"
                  class="wb-v2__text-btn"
                  @click="go('/admin/approval/todos?status=PENDING')"
                >
                  查看全部待办 →
                </button>
              </header>
              <p v-if="loading" class="wb-v2__empty">正在加载待办…</p>
              <p v-else-if="!recentTodos.length" class="wb-v2__empty is-success">
                今日无待办，一切正常
              </p>
              <ul v-else>
                <li
                  v-for="t in recentTodos"
                  :key="t.todoId"
                  tabindex="0"
                  @click="openTodo(t)"
                  @keydown.enter="openTodo(t)"
                >
                  <span class="wb-v2__todo-code" :class="priorityClass(t.priority)">{{
                    todoCode(t)
                  }}</span>
                  <span class="wb-v2__todo-main"
                    ><strong>{{ t.title }}</strong
                    ><small>{{ todoMeta(t) }}</small></span
                  >
                  <span
                    v-if="t.dueAt"
                    class="wb-v2__todo-due"
                    :class="{ 'is-over': isOverdue(t), 'is-near': isNearDeadline(t) }"
                    >{{ dueLabel(t) }}</span
                  >
                  <span class="wb-v2__todo-arrow">›</span>
                </li>
              </ul>
            </section>

            <section class="wb-v2__panel wb-v2__favorites">
              <header class="wb-v2__section-head">
                <div>
                  <h2>我的常用</h2>
                  <p>你的高频业务入口</p>
                </div>
                <button type="button" class="wb-v2__text-btn" @click="editing = !editing">
                  编辑
                </button>
              </header>
              <div class="wb-v2__favorite-grid">
                <button
                  v-for="(l, index) in displayLinks.slice(0, 6)"
                  :key="l.to"
                  type="button"
                  @click="go(l.to)"
                >
                  <span :class="'is-tone-' + (index % 4)">
                    <svg
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="1.8"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                    >
                      <path
                        v-for="(d, iconIndex) in quickIconPaths(index)"
                        :key="iconIndex"
                        :d="d"
                      />
                    </svg>
                  </span>
                  <strong>{{ l.label }}</strong>
                  <small>快速进入业务办理</small>
                </button>
                <button type="button" @click="goMessages">
                  <span class="is-tone-3">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                      <path d="M4 5h16v12H8l-4 4zM8 9h8M8 13h5" />
                    </svg>
                  </span>
                  <strong>消息中心</strong>
                  <small>{{ unread ? `${unread} 条未读消息` : '系统消息与通知' }}</small>
                </button>
              </div>
            </section>
          </div>
        </template>
      </main>

      <aside class="wb-v2__context">
        <section class="wb-v2__panel wb-v2__rhythm">
          <header class="wb-v2__section-head">
            <div>
              <h2>{{ recipe.showSchedule ? '今日节奏' : '待办节奏' }}</h2>
              <p>{{ todayLabel }}</p>
            </div>
            <button
              v-if="recipe.showSchedule"
              type="button"
              class="wb-v2__text-btn"
              @click="go(scheduleLink)"
            >
              完整日程
            </button>
          </header>
          <p v-if="scheduleLoading" class="wb-v2__empty">日程加载中…</p>
          <p v-else-if="!contextItems.length" class="wb-v2__empty is-success">今天暂无安排</p>
          <ol v-else>
            <li v-for="(item, index) in contextItems" :key="item.key">
              <span class="wb-v2__time">{{ item.time }}</span>
              <i :class="{ 'is-first': index === 0 }" />
              <span
                ><strong>{{ item.title }}</strong
                ><small>{{ item.meta }}</small></span
              >
            </li>
          </ol>
        </section>

        <section class="wb-v2__panel wb-v2__risk">
          <header class="wb-v2__section-head">
            <div>
              <h2>风险提醒</h2>
              <p>按当前数据范围汇总</p>
            </div>
          </header>
          <button type="button" :class="{ 'is-safe': !riskCount }" @click="go(riskPath)">
            <span class="wb-v2__risk-icon">!</span>
            <span>
              <strong v-if="riskCount">有 {{ riskCount }} 条风险需要关注</strong>
              <strong v-else>当前暂无高风险事项</strong>
              <small>{{ riskCount ? '建议优先进入台账处理' : '业务运行状态正常' }}</small>
            </span>
          </button>
          <button
            v-if="riskCount"
            type="button"
            class="wb-v2__text-btn wb-v2__risk-more"
            @click="go(riskPath)"
          >
            查看全部风险 →
          </button>
        </section>

        <section class="wb-v2__panel wb-v2__help">
          <header class="wb-v2__section-head">
            <div>
              <h2>本页帮助</h2>
              <p>常用操作说明</p>
            </div>
          </header>
          <button type="button" @click="go('/admin/help?topic=doc-workbench')">
            <span>丰</span
            ><span><strong>如何处理工作台待办？</strong><small>2 分钟快速了解流程</small></span>
          </button>
          <button type="button" @click="go('/admin/help?topic=doc-roles-scope')">
            <span>盾</span
            ><span><strong>角色与数据范围</strong><small>了解当前可见数据口径</small></span>
          </button>
          <button type="button" @click="go('/admin/help?topic=doc-global-search')">
            <span>搜</span
            ><span><strong>全局搜索使用指南</strong><small>快速定位学生和功能</small></span>
          </button>
          <button type="button" class="wb-v2__text-btn wb-v2__help-more" @click="go('/admin/help')">
            查看帮助中心 →
          </button>
        </section>

        <section class="wb-v2__panel wb-v2__quick">
          <header class="wb-v2__section-head">
            <div>
              <h2>快捷操作</h2>
              <p>来自你的角色配方</p>
            </div>
          </header>
          <div>
            <button
              v-for="(l, index) in displayLinks.slice(0, 4)"
              :key="l.to"
              type="button"
              @click="go(l.to)"
            >
              <span :class="'is-tone-' + (index % 4)">{{ quickGlyph(index) }}</span
              >{{ l.label }}
            </button>
          </div>
        </section>
      </aside>
    </div>
  </div>
</template>

<script>
/**
 * WorkbenchView —— 角色化工作台（对标 Dynamics 365 Role Center）。
 * 角色以后端 /todos/summary.role 为准；P7 偏好只改布局，不改权限。
 */
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
  components: { AppPageGuide },
  props: {
    displayName: { type: String, default: '老师' }
  },
  data() {
    return {
      loading: true,
      error: '',
      role: '',
      summary: { ...EMPTY_SUMMARY },
      stats: { ...EMPTY_STATS },
      byType: {},
      todos: [],
      unread: 0,
      editing: false,
      tilePref: { order: [], hidden: [] },
      favPaths: [],
      scheduleItems: [],
      scheduleLoading: false
    }
  },
  computed: {
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
    headline() {
      try {
        return this.recipe.headline({
          summary: this.summary,
          byType: this.byType,
          stats: this.stats
        })
      } catch {
        return ''
      }
    },
    hasOverdue() {
      return (this.summary.overdue || 0) > 0
    },
    scopeLabel() {
      return this.stats.scopeLabel || ''
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
    greeting() {
      const hour = new Date().getHours()
      if (hour < 11) return '上午好'
      if (hour < 14) return '中午好'
      if (hour < 18) return '下午好'
      return '晚上好'
    },
    todayLabel() {
      return new Intl.DateTimeFormat('zh-CN', {
        month: 'long',
        day: 'numeric',
        weekday: 'short'
      }).format(new Date())
    },
    scopeCards() {
      const source = [...this.visibleStatsCues]
      if (!source.length) source.push(...this.visibleTypeCues)
      if (!source.some((c) => c.key === 'messages')) {
        source.push({
          key: 'messages',
          title: '未读消息',
          source: 'message.unread',
          accent: 'primary',
          to: '/admin/messages/inbox'
        })
      }
      return source.slice(0, 4)
    },
    recentTodos() {
      return this.todos.slice(0, 5)
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
    riskCount() {
      return Number(this.summary.overdue || this.stats.academicWarning || 0)
    },
    riskPath() {
      return this.summary.overdue
        ? '/admin/approval/todos?urgency=OVERDUE'
        : '/admin/academic-affairs/warnings?status=OPEN'
    }
  },
  created() {
    this.load()
  },
  methods: {
    async load() {
      this.loading = true
      this.error = ''
      try {
        const needStats = true
        const reqs = [fetchTodoSummary(), fetchTodoCount(), fetchTodoList(), fetchMessageCount()]
        if (needStats) reqs.push(fetchSchoolStats())
        const [summary, count, list, msg, schoolStats] = await Promise.all(reqs)
        this.role = summary.role || ''
        this.summary = {
          pending: Number(summary.pending) || 0,
          overdue: Number(summary.overdue) || 0,
          nearDeadline: Number(summary.nearDeadline) || 0,
          doneToday: Number(summary.doneToday) || 0
        }
        this.byType = count.byType && typeof count.byType === 'object' ? { ...count.byType } : {}
        this.todos = Array.isArray(list.items) ? list.items : []
        this.unread = Number(msg.unread) || 0
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
        }
        await this.loadPrefsQuiet()
        if (this.recipe.showSchedule) await this.loadScheduleQuiet()
      } catch (e) {
        this.role = ''
        this.summary = { ...EMPTY_SUMMARY }
        this.stats = { ...EMPTY_STATS }
        this.byType = {}
        this.todos = []
        this.unread = 0
        this.scheduleItems = []
        this.error = (e && e.message) || '请求失败'
      } finally {
        this.loading = false
      }
    },
    async loadScheduleQuiet() {
      this.scheduleLoading = true
      try {
        const u = currentUserFromToken() || {}
        const key = String(u.loginName || u.userId || '').trim()
        const res = await fetchMyScheduleToday(key)
        this.scheduleItems = Array.isArray(res.items) ? res.items : []
      } catch {
        this.scheduleItems = []
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
      if (ns === 'stats') return this.stats[key] || 0
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
      const type = t && t.todoType
      const path =
        (type && TODO_TYPE_ROUTES[type]) ||
        (type
          ? `/admin/approval/todos?todoType=${encodeURIComponent(type)}&status=PENDING`
          : '/admin/approval/todos?status=PENDING')
      this.trackClick(type || 'todo', path)
      this.go(path)
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
    cueHint(c) {
      const hints = {
        pending: '较昨日新增事项',
        overdue: this.summary.overdue ? '请尽快处理' : '暂无逾期事项',
        nearDeadline: this.summary.nearDeadline ? '请留意截止时间' : '暂无临期事项',
        doneToday: '今日办理进度'
      }
      return hints[c.key] || '点击查看明细'
    },
    statHint(c) {
      const value = this.valueOf(c.source)
      if (c.key === 'messages') return value ? '等待你查看' : '暂无未读消息'
      return value ? '点击查看业务明细' : '当前暂无数据'
    },
    iconPaths(key) {
      const icons = {
        pending: ['M7 4h10', 'M7 4v3h10V4', 'M5 6h14v15H5z', 'm8 11 2 2 4-4'],
        overdue: ['M7 3h10M7 21h10', 'M8 3v5l4 4-4 4v5M16 3v5l-4 4 4 4v5'],
        nearDeadline: ['M12 7v5l3 2', 'M21 12a9 9 0 1 1-3-6.7'],
        doneToday: ['M22 11.1V12a10 10 0 1 1-5.9-9.1', 'm9 11 3 3L22 4'],
        studentTotal: [
          'M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z',
          'M2 21v-2a7 7 0 0 1 14 0v2',
          'M17 8h5M19.5 5.5v5'
        ],
        pendingApproval: ['M6 3h12v18H6z', 'M9 8h6M9 12h6M9 16h4'],
        academicWarning: ['M12 3 2 21h20L12 3Z', 'M12 9v5M12 18h.01'],
        orientationPending: ['M4 5h16v16H4zM8 3v4M16 3v4M4 10h16', 'm9 15 2 2 4-4'],
        unemployed: ['M4 7h16v13H4z', 'M9 7V4h6v3', 'M8 12h8'],
        messages: ['M4 5h16v12H8l-4 4z', 'M8 9h8M8 13h5']
      }
      return icons[key] || ['M4 19V9M10 19V5M16 19v-7M22 19H2']
    },
    quickIconPaths(index) {
      const icons = [
        ['M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z', 'M2 21v-2a7 7 0 0 1 14 0v2', 'M17 8h5'],
        ['M12 3 4 7v5c0 5 3 8 8 10 5-2 8-5 8-10V7l-8-4Z', 'm9 12 2 2 4-4'],
        ['M4 5h16v12H8l-4 4z', 'M8 9h8M8 13h5'],
        ['M4 20V10M10 20V4M16 20v-8M22 20H2']
      ]
      return icons[index % icons.length]
    },
    quickGlyph(index) {
      return ['➤', '◆', '●', '▣'][index % 4]
    },
    todoCode(t) {
      const title = String(t.title || '办').trim()
      return title.charAt(0)
    },
    todoMeta(t) {
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
.wb-v2 {
  --wb-blue: #145ef4;
  --wb-blue-deep: #053dce;
  --wb-navy: #10254d;
  --wb-text: #17294e;
  --wb-muted: #7585a4;
  --wb-line: #e3eaf6;
  --wb-card: rgba(255, 255, 255, 0.96);
  min-width: 0;
  color: var(--wb-text);
}

.wb-v2 button {
  font: inherit;
}
.wb-v2 svg {
  width: 1em;
  height: 1em;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.wb-v2__layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 286px;
  gap: 16px;
  align-items: start;
}
.wb-v2__main,
.wb-v2__context {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 12px;
}
.wb-v2__panel {
  border: 1px solid var(--wb-line);
  border-radius: 12px;
  background: var(--wb-card);
  box-shadow: 0 6px 22px rgba(28, 69, 142, 0.045);
}

.wb-v2__hero {
  position: relative;
  min-height: 236px;
  overflow: hidden;
  border-radius: 13px;
  padding: 28px 31px;
  color: #fff;
  background: linear-gradient(122deg, #0750dd 0%, #116df6 54%, #237cff 100%);
  box-shadow: 0 16px 34px -18px rgba(10, 83, 222, 0.72);
}
.wb-v2__hero::before,
.wb-v2__hero::after {
  content: '';
  position: absolute;
  pointer-events: none;
}
.wb-v2__hero::before {
  inset: 0;
  opacity: 0.38;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.08) 1px, transparent 1px);
  background-size: 42px 42px;
  mask-image: linear-gradient(90deg, transparent 38%, #000);
}
.wb-v2__hero::after {
  width: 520px;
  height: 520px;
  right: -95px;
  top: -315px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 50%;
  box-shadow:
    0 0 0 70px rgba(255, 255, 255, 0.025),
    0 0 0 145px rgba(255, 255, 255, 0.02);
}
.wb-v2__hero-copy {
  position: relative;
  z-index: 3;
  max-width: 66%;
}
.wb-v2__eyebrow {
  display: inline-block;
  margin-bottom: 9px;
  font-size: 12px;
  font-weight: 650;
  letter-spacing: 0.06em;
  color: rgba(255, 255, 255, 0.7);
}
.wb-v2__hero h1 {
  margin: 0 0 10px;
  font-size: clamp(25px, 2vw, 34px);
  line-height: 1.25;
  letter-spacing: -0.025em;
}
.wb-v2__headline {
  margin: 0;
  font-size: 16px;
  color: rgba(255, 255, 255, 0.9);
}
.wb-v2__headline.is-risk {
  color: #fff2be;
  font-weight: 650;
}
.wb-v2__hero-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 18px;
  margin-top: 15px;
  color: rgba(255, 255, 255, 0.72);
  font-size: 12px;
}
.wb-v2__hero-meta span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.wb-v2__hero-meta svg {
  font-size: 14px;
  stroke-width: 1.8;
}
.wb-v2__hero-actions {
  display: flex;
  gap: 10px;
  margin-top: 23px;
}
.wb-v2__hero-actions button {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 38px;
  padding: 0 18px;
  border: 1px solid rgba(255, 255, 255, 0.68);
  border-radius: 8px;
  background: #fff;
  color: var(--wb-blue);
  font-weight: 650;
  cursor: pointer;
  box-shadow: 0 8px 20px rgba(0, 37, 123, 0.16);
}
.wb-v2__hero-actions button.is-light {
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
  border-color: rgba(255, 255, 255, 0.55);
  box-shadow: none;
}
.wb-v2__hero-actions button:hover {
  transform: translateY(-1px);
}
.wb-v2__hero-art {
  position: absolute;
  z-index: 2;
  right: 3%;
  top: 0;
  width: 42%;
  height: 100%;
  perspective: 900px;
}
.wb-v2__glass {
  position: absolute;
  display: block;
  border: 1px solid rgba(255, 255, 255, 0.34);
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.27), rgba(255, 255, 255, 0.04));
  box-shadow:
    inset 0 0 24px rgba(255, 255, 255, 0.1),
    0 28px 50px rgba(0, 33, 140, 0.28);
  backdrop-filter: blur(3px);
  transform: rotateX(58deg) rotateZ(-27deg);
}
.wb-v2__glass--one {
  width: 210px;
  height: 150px;
  right: 0;
  top: 31px;
}
.wb-v2__glass--two {
  width: 178px;
  height: 112px;
  right: 130px;
  top: 92px;
}
.wb-v2__glass--three {
  width: 90px;
  height: 72px;
  right: 116px;
  top: 70px;
  transform: rotate(-4deg);
  border-radius: 8px;
}
.wb-v2__glass--three svg {
  width: 52px;
  height: 52px;
  margin: 10px 19px;
  color: rgba(255, 255, 255, 0.76);
}
.wb-v2__hero-art i {
  position: absolute;
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: #fff;
  box-shadow: 0 0 9px 2px #fff;
}
.wb-v2__hero-art .is-spark-1 {
  top: 23%;
  left: 18%;
}
.wb-v2__hero-art .is-spark-2 {
  top: 61%;
  left: 8%;
}
.wb-v2__hero-art .is-spark-3 {
  top: 33%;
  right: 10%;
}
.wb-v2__hero-art .is-spark-4 {
  top: 71%;
  right: 18%;
}
.wb-v2__hero-art .is-spark-5 {
  top: 81%;
  left: 47%;
}
.wb-v2__hero-art .is-spark-6 {
  top: 16%;
  right: 37%;
}
.wb-v2__hero-art .is-spark-7 {
  top: 49%;
  left: 35%;
}
.wb-v2__hero-art .is-spark-8 {
  top: 10%;
  left: 4%;
}

.wb-v2__error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 16px;
  border: 1px solid #f4c5c9;
  border-radius: 10px;
  background: #fff4f5;
  color: #ba2935;
}
.wb-v2__error div {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.wb-v2__error span {
  font-size: 12px;
}
.wb-v2__error button {
  border: 0;
  border-radius: 7px;
  padding: 7px 12px;
  background: #d93645;
  color: #fff;
  cursor: pointer;
}

.wb-v2__action-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}
.wb-v2__action-card {
  display: grid;
  grid-template-columns: 48px minmax(0, 1fr) 24px;
  align-items: center;
  gap: 10px;
  min-height: 116px;
  padding: 16px;
  border: 1px solid var(--wb-line);
  border-radius: 11px;
  background: var(--wb-card);
  text-align: left;
  color: var(--wb-text);
  cursor: pointer;
  box-shadow: 0 6px 18px rgba(29, 69, 143, 0.035);
  transition: 0.16s ease;
}
.wb-v2__action-card:hover {
  border-color: #bad0fb;
  transform: translateY(-2px);
  box-shadow: 0 12px 24px rgba(35, 91, 195, 0.09);
}
.wb-v2__metric-icon {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: #e9f0ff;
  color: #356ff5;
}
.wb-v2__metric-icon svg {
  width: 22px;
  height: 22px;
}
.wb-v2__action-card.is-risk .wb-v2__metric-icon {
  color: #ee4855;
  background: #ffebed;
}
.wb-v2__action-card.is-warning .wb-v2__metric-icon {
  color: #ee9817;
  background: #fff2df;
}
.wb-v2__action-card.is-success .wb-v2__metric-icon {
  color: #34ad69;
  background: #e6f8ed;
}
.wb-v2__action-copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
}
.wb-v2__action-copy small {
  font-size: 13px;
  color: #3c4d70;
}
.wb-v2__action-copy strong {
  margin: 2px 0;
  font-size: 25px;
  line-height: 1.15;
  color: #10254d;
}
.wb-v2__action-copy em {
  overflow: hidden;
  color: #99a5bb;
  font-size: 11px;
  font-style: normal;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.wb-v2__action-arrow {
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  border: 1px solid var(--wb-line);
  border-radius: 50%;
  color: #8191ad;
  font-size: 20px;
}

.wb-v2__section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px 10px;
}
.wb-v2__section-head h2 {
  margin: 0;
  color: var(--wb-navy);
  font-size: 15px;
}
.wb-v2__section-head h2 b {
  display: inline-grid;
  min-width: 19px;
  height: 19px;
  place-items: center;
  margin-left: 4px;
  border-radius: 10px;
  background: #edf3ff;
  color: var(--wb-blue);
  font-size: 10px;
}
.wb-v2__section-head p {
  margin: 3px 0 0;
  color: var(--wb-muted);
  font-size: 11px;
}
.wb-v2__settings {
  display: grid;
  width: 29px;
  height: 29px;
  place-items: center;
  border: 0;
  background: transparent;
  color: #8594b1;
  cursor: pointer;
}
.wb-v2__settings svg {
  width: 17px;
  height: 17px;
}
.wb-v2__text-btn {
  padding: 4px 0;
  border: 0;
  background: transparent;
  color: var(--wb-blue);
  font-size: 11px;
  cursor: pointer;
}

.wb-v2__stat-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  padding: 0 14px 14px;
}
.wb-v2__stat-card {
  display: flex;
  align-items: center;
  gap: 11px;
  min-height: 92px;
  padding: 13px;
  border: 1px solid #e4eaf4;
  border-radius: 10px;
  background: #fff;
  color: var(--wb-text);
  text-align: left;
  cursor: pointer;
}
.wb-v2__stat-card:hover {
  border-color: #bcd2ff;
  background: #fbfdff;
}
.wb-v2__stat-icon,
.wb-v2__favorite-grid button > span {
  display: grid;
  width: 39px;
  height: 39px;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 50%;
  background: #e8f0ff;
  color: #2867ef;
}
.wb-v2__stat-icon svg,
.wb-v2__favorite-grid button > span svg {
  width: 20px;
  height: 20px;
}
.wb-v2__stat-card.is-tone-1 .wb-v2__stat-icon,
.is-tone-1 {
  color: #ec9d1f !important;
  background: #fff3df !important;
}
.wb-v2__stat-card.is-tone-2 .wb-v2__stat-icon,
.is-tone-2 {
  color: #36ad6c !important;
  background: #e9f8ef !important;
}
.wb-v2__stat-card.is-tone-3 .wb-v2__stat-icon,
.is-tone-3 {
  color: #7859e8 !important;
  background: #f0ebff !important;
}
.wb-v2__stat-card > span:last-child {
  display: flex;
  min-width: 0;
  flex-direction: column;
}
.wb-v2__stat-card small {
  color: #50607d;
  font-size: 11px;
}
.wb-v2__stat-card strong {
  margin: 2px 0;
  color: var(--wb-navy);
  font-size: 20px;
}
.wb-v2__stat-card em {
  color: #98a4b8;
  font-size: 10px;
  font-style: normal;
  white-space: nowrap;
}
.wb-v2__type-strip {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 7px;
  padding: 0 14px 13px;
}
.wb-v2__type-strip > span {
  color: var(--wb-muted);
  font-size: 11px;
}
.wb-v2__type-strip button {
  padding: 5px 9px;
  border: 1px solid #dfe7f4;
  border-radius: 15px;
  background: #f8faff;
  color: #5b6985;
  font-size: 10px;
  cursor: pointer;
}
.wb-v2__type-strip strong {
  color: var(--wb-blue);
}

.wb-v2__editor {
  padding-bottom: 14px;
}
.wb-v2__edit-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
  padding: 2px 16px;
}
.wb-v2__edit-grid h3 {
  margin: 0 0 6px;
  font-size: 12px;
}
.wb-v2__edit-row {
  display: flex;
  min-height: 32px;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  color: #52617d;
  font-size: 11px;
}
.wb-v2__edit-row label,
.wb-v2__edit-row > span {
  display: flex;
  align-items: center;
  gap: 6px;
}
.wb-v2__edit-row button {
  margin-left: 4px;
  padding: 3px 7px;
  border: 1px solid #dce5f3;
  border-radius: 5px;
  background: #fff;
  color: var(--wb-blue);
  font-size: 10px;
  cursor: pointer;
}

.wb-v2__lower-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.18fr) minmax(320px, 0.82fr);
  gap: 10px;
}
.wb-v2__todos ul {
  margin: 0;
  padding: 0 14px 12px;
  list-style: none;
}
.wb-v2__todos li {
  display: flex;
  min-height: 55px;
  align-items: center;
  gap: 10px;
  border-top: 1px solid #edf1f7;
  cursor: pointer;
}
.wb-v2__todos li:hover .wb-v2__todo-main strong {
  color: var(--wb-blue);
}
.wb-v2__todo-code {
  display: grid;
  width: 29px;
  height: 29px;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 8px;
  background: #edf3ff;
  color: #3472ef;
  font-size: 11px;
  font-weight: 700;
}
.wb-v2__todo-code.is-high {
  background: #ffebed;
  color: #e74450;
}
.wb-v2__todo-code.is-medium {
  background: #fff2df;
  color: #e89518;
}
.wb-v2__todo-main {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
}
.wb-v2__todo-main strong {
  overflow: hidden;
  color: #243759;
  font-size: 11px;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.wb-v2__todo-main small {
  overflow: hidden;
  margin-top: 3px;
  color: #929eb3;
  font-size: 9px;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.wb-v2__todo-due {
  color: #76849d;
  font-size: 9px;
  white-space: nowrap;
}
.wb-v2__todo-due.is-over {
  color: #e33b49;
  font-weight: 650;
}
.wb-v2__todo-due.is-near {
  color: #e98b12;
  font-weight: 650;
}
.wb-v2__todo-arrow {
  color: #8695af;
  font-size: 18px;
}
.wb-v2__favorite-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  padding: 0 14px 14px;
}
.wb-v2__favorite-grid button {
  display: grid;
  grid-template-columns: 36px minmax(0, 1fr);
  grid-template-rows: auto auto;
  column-gap: 8px;
  min-height: 63px;
  align-items: center;
  padding: 9px;
  border: 1px solid #e6ebf4;
  border-radius: 9px;
  background: #fbfcff;
  color: var(--wb-text);
  text-align: left;
  cursor: pointer;
}
.wb-v2__favorite-grid button:hover {
  border-color: #bfd3ff;
  background: #f8fbff;
}
.wb-v2__favorite-grid button > span {
  grid-row: 1 / 3;
  width: 34px;
  height: 34px;
}
.wb-v2__favorite-grid button strong {
  align-self: end;
  overflow: hidden;
  font-size: 10px;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.wb-v2__favorite-grid button small {
  align-self: start;
  overflow: hidden;
  color: #9aa5b8;
  font-size: 8px;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.wb-v2__context .wb-v2__panel {
  box-shadow: 0 6px 20px rgba(27, 65, 132, 0.035);
}
.wb-v2__rhythm ol {
  margin: 0;
  padding: 3px 15px 12px;
  list-style: none;
}
.wb-v2__rhythm li {
  display: grid;
  grid-template-columns: 39px 12px minmax(0, 1fr);
  gap: 8px;
  min-height: 59px;
  align-items: start;
}
.wb-v2__time {
  padding-top: 1px;
  color: var(--wb-blue);
  font-size: 10px;
  font-weight: 650;
}
.wb-v2__rhythm li i {
  position: relative;
  width: 7px;
  height: 7px;
  margin-top: 4px;
  border: 2px solid #fff;
  border-radius: 50%;
  background: #87a9f8;
  box-shadow: 0 0 0 1px #9db9f9;
}
.wb-v2__rhythm li i.is-first {
  background: var(--wb-blue);
}
.wb-v2__rhythm li:not(:last-child) i::after {
  content: '';
  position: absolute;
  top: 8px;
  left: 2px;
  width: 1px;
  height: 44px;
  background: #dce5f5;
}
.wb-v2__rhythm li > span:last-child {
  display: flex;
  min-width: 0;
  flex-direction: column;
}
.wb-v2__rhythm strong {
  overflow: hidden;
  color: #324461;
  font-size: 10px;
  line-height: 1.45;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.wb-v2__rhythm small {
  overflow: hidden;
  margin-top: 3px;
  color: #99a4b7;
  font-size: 8px;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.wb-v2__risk {
  padding-bottom: 11px;
}
.wb-v2__risk > button:not(.wb-v2__text-btn) {
  display: flex;
  width: calc(100% - 24px);
  align-items: center;
  gap: 10px;
  margin: 0 12px;
  padding: 11px;
  border: 1px solid #ffd2d5;
  border-radius: 9px;
  background: #fff1f2;
  color: #d93645;
  text-align: left;
  cursor: pointer;
}
.wb-v2__risk > button.is-safe {
  border-color: #ccebd8;
  background: #f0faf4;
  color: #2a9a5a;
}
.wb-v2__risk-icon {
  display: grid;
  width: 30px;
  height: 30px;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 50%;
  background: currentColor;
  color: #fff;
  font-weight: 800;
}
.wb-v2__risk button span:last-child {
  display: flex;
  flex-direction: column;
}
.wb-v2__risk strong {
  font-size: 10px;
}
.wb-v2__risk small {
  margin-top: 3px;
  color: #9d7b80;
  font-size: 8px;
}
.wb-v2__risk-more {
  margin: 8px 14px 0 auto;
  display: block;
}
.wb-v2__help {
  padding-bottom: 10px;
}
.wb-v2__help > button:not(.wb-v2__text-btn) {
  display: flex;
  width: calc(100% - 24px);
  align-items: center;
  gap: 9px;
  margin: 0 12px;
  padding: 8px 2px;
  border: 0;
  border-top: 1px solid #f0f3f8;
  background: transparent;
  color: #647696;
  text-align: left;
  cursor: pointer;
}
.wb-v2__help > button > span:first-child {
  display: grid;
  width: 25px;
  height: 25px;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 50%;
  background: #edf3ff;
  color: #3872ea;
  font-size: 9px;
}
.wb-v2__help > button > span:last-child {
  display: flex;
  min-width: 0;
  flex-direction: column;
}
.wb-v2__help strong {
  color: #344765;
  font-size: 9px;
}
.wb-v2__help small {
  margin-top: 2px;
  color: #9aa5b8;
  font-size: 8px;
}
.wb-v2__help-more {
  display: block;
  margin: 5px 14px 0 auto;
}
.wb-v2__quick {
  padding-bottom: 12px;
}
.wb-v2__quick > div:last-child {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 7px;
  padding: 0 12px;
}
.wb-v2__quick > div button {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 6px;
  min-height: 39px;
  padding: 6px;
  border: 1px solid #e6ebf4;
  border-radius: 8px;
  background: #fbfcff;
  color: #3f526f;
  font-size: 9px;
  cursor: pointer;
}
.wb-v2__quick > div button span {
  display: grid;
  width: 24px;
  height: 24px;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 7px;
  color: #2f6ff1;
  background: #eaf1ff;
  font-size: 9px;
}
.wb-v2__empty {
  margin: 0;
  padding: 25px 12px;
  color: #8794aa;
  font-size: 11px;
  text-align: center;
}
.wb-v2__empty.is-success {
  color: #3d9b66;
}

@media (max-width: 1480px) {
  .wb-v2__layout {
    grid-template-columns: minmax(0, 1fr) 260px;
  }
  .wb-v2__hero {
    min-height: 220px;
    padding: 25px;
  }
  .wb-v2__action-card {
    grid-template-columns: 42px minmax(0, 1fr) 20px;
    padding: 13px;
  }
  .wb-v2__metric-icon {
    width: 40px;
    height: 40px;
  }
  .wb-v2__lower-grid {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 1240px) {
  .wb-v2__layout {
    grid-template-columns: 1fr;
  }
  .wb-v2__context {
    display: grid;
    grid-template-columns: 1fr 1fr;
    align-items: stretch;
  }
  .wb-v2__action-grid,
  .wb-v2__stat-grid {
    grid-template-columns: 1fr 1fr;
  }
}
@media (max-width: 760px) {
  .wb-v2__hero-copy {
    max-width: 100%;
  }
  .wb-v2__hero-art {
    opacity: 0.35;
    width: 70%;
  }
  .wb-v2__action-grid,
  .wb-v2__stat-grid,
  .wb-v2__context,
  .wb-v2__edit-grid {
    grid-template-columns: 1fr;
  }
  .wb-v2__favorite-grid {
    grid-template-columns: 1fr;
  }
}
</style>
