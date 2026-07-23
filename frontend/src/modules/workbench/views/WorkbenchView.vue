<template>
  <div class="wb">
    <AppPageGuide guide-key="workbench.first-login" />

    <section class="wb__hero">
      <div class="wb__hero-main">
        <h1 class="wb__hi">你好，{{ displayName }}</h1>
        <p class="wb__headline" :class="{ 'is-risk': hasOverdue && !error && !loading }">
          <span v-if="loading">正在读取你的待办…</span>
          <span v-else-if="error">待办读取失败</span>
          <span v-else>{{ headline }}</span>
        </p>
        <p v-if="!loading && !error && scopeLabel" class="wb__scope">数据范围：{{ scopeLabel }}</p>
      </div>
      <div class="wb__hero-side">
        <span class="wb__role">{{ recipe.label }}</span>
        <button class="wb__refresh" type="button" :disabled="loading" @click="editing = !editing">
          {{ editing ? '完成' : '编辑布局' }}
        </button>
        <button class="wb__refresh" type="button" :disabled="loading" @click="load">刷新</button>
      </div>
    </section>

    <div v-if="error" class="wb__error" role="alert">
      <strong>无法加载工作台数据。</strong>
      <span>{{ error }}</span>
      <button class="wb__retry" type="button" @click="load">重试</button>
    </div>

    <template v-else>
      <section v-if="editing" class="wb__edit">
        <div class="wb__edit-head">
          <strong>编辑布局</strong>
          <span>只影响你本人看到的磁贴与常用入口，不改变权限。</span>
          <button type="button" class="wb__edit-reset" @click="restoreDefaults">恢复默认</button>
        </div>
        <div class="wb__edit-grid">
          <div>
            <h3 class="wb__edit-title">汇总磁贴（显隐 / 排序）</h3>
            <div v-for="(c, idx) in editSummaryList" :key="c.key" class="wb__edit-row wb__edit-row--sort">
              <label class="wb__edit-check">
                <input type="checkbox" :checked="!tileHidden.has(c.key)" @change="toggleTile(c.key, $event.target.checked)">
                <span>{{ c.title }}</span>
              </label>
              <span class="wb__edit-sort">
                <button type="button" :disabled="idx === 0" @click="moveTile(c.key, -1)">上移</button>
                <button type="button" :disabled="idx === editSummaryList.length - 1" @click="moveTile(c.key, 1)">下移</button>
              </span>
            </div>
          </div>
          <div>
            <h3 class="wb__edit-title">我的常用（收藏）</h3>
            <label v-for="l in recipe.quickLinks" :key="l.to" class="wb__edit-row">
              <input type="checkbox" :checked="favSet.has(l.to)" @change="toggleFav(l.to, $event.target.checked)">
              <span>{{ l.label }}</span>
            </label>
            <p class="wb__edit-hint">不勾选任何项时，显示角色默认入口。</p>
          </div>
        </div>
      </section>

      <section class="wb__block">
        <h2 class="wb__block-title">我的待办</h2>
        <div class="wb__cues">
          <AppMetricCard
            v-for="c in visibleSummaryCues"
            :key="c.key"
            :title="c.title"
            :value="loading ? 0 : valueOf(c.source)"
            :accent="c.accent"
            :loading="loading"
            drillable
            :drill-target="c.to"
            @drill="onDrill(c)"
          />
        </div>
      </section>

      <section v-if="!loading && visibleStatsCues.length" class="wb__block">
        <h2 class="wb__block-title">范围内指标</h2>
        <div class="wb__cues">
          <AppMetricCard
            v-for="c in visibleStatsCues"
            :key="c.key"
            :title="c.title"
            :value="valueOf(c.source)"
            :accent="c.accent"
            drillable
            :drill-target="c.to"
            @drill="onDrill(c)"
          />
        </div>
      </section>

      <section v-if="!loading && visibleTypeCues.length" class="wb__block">
        <h2 class="wb__block-title">按类型</h2>
        <div class="wb__cues">
          <AppMetricCard
            v-for="c in visibleTypeCues"
            :key="c.key"
            :title="c.title"
            :value="valueOf(c.source)"
            :accent="c.accent"
            drillable
            :drill-target="c.to"
            @drill="onDrill(c)"
          />
        </div>
      </section>

      <section class="wb__block wb__split">
        <div class="wb__list">
          <h2 class="wb__block-title">
            最近待办
            <button class="wb__more" type="button" @click="go('/admin/approval/todos')">全部 →</button>
          </h2>

          <p v-if="loading" class="wb__muted">加载中…</p>
          <p v-else-if="!todos.length" class="wb__empty">今日无待办，一切正常</p>
          <ul v-else class="wb__items">
            <li
              v-for="t in todos"
              :key="t.todoId"
              class="wb__item"
              role="button"
              tabindex="0"
              @click="openTodo(t)"
              @keydown.enter="openTodo(t)"
            >
              <span class="wb__dot" :class="priorityClass(t.priority)" />
              <span class="wb__item-title">{{ t.title }}</span>
              <span
                v-if="t.dueAt"
                class="wb__due"
                :class="{ 'is-over': isOverdue(t), 'is-near': isNearDeadline(t) }"
              >
                {{ dueLabel(t) }}
              </span>
            </li>
          </ul>
        </div>

        <div class="wb__side">
          <h2 class="wb__block-title">我的常用</h2>
          <button
            v-for="l in displayLinks"
            :key="l.to"
            class="wb__link"
            type="button"
            @click="go(l.to)"
          >{{ l.label }}</button>
          <div v-if="!loading && unread > 0" class="wb__msg" title="消息中心页面待建设，此处仅展示未读数">
            未读消息 <strong>{{ unread }}</strong>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<script>
/**
 * WorkbenchView —— 角色化工作台（对标 Dynamics 365 Role Center）。
 * 角色以后端 /todos/summary.role 为准；P7 偏好只改布局，不改权限。
 */
import AppMetricCard from '@/components/common/AppMetricCard.vue'
import AppPageGuide from '@/components/common/experience/AppPageGuide.vue'
import {
  fetchMessageCount,
  fetchSchoolStats,
  fetchTodoCount,
  fetchTodoList,
  fetchTodoSummary
} from '../api/workbench.api'
import {
  applyFavoriteLinks,
  applyTilePrefs,
  bumpClickCount,
  clicksPrefKey,
  favoritesPrefKey,
  loadPrefs,
  parseJsonPref,
  savePref,
  tilesPrefKey
} from '../api/workbenchPrefs'
import { resolveRecipe, TODO_TYPE_ROUTES } from '../config/workbenchRecipes'

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
  components: { AppMetricCard, AppPageGuide },
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
      clickCounts: {}
    }
  },
  computed: {
    recipe() {
      return resolveRecipe(this.role)
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
      return applyTilePrefs(this.recipe.summaryCues, { order: this.tilePref.order || [], hidden: [] })
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
        const reqs = [
          fetchTodoSummary(),
          fetchTodoCount(),
          fetchTodoList(),
          fetchMessageCount()
        ]
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
      } catch (e) {
        this.role = ''
        this.summary = { ...EMPTY_SUMMARY }
        this.stats = { ...EMPTY_STATS }
        this.byType = {}
        this.todos = []
        this.unread = 0
        this.error = (e && e.message) || '请求失败'
      } finally {
        this.loading = false
      }
    },
    async loadPrefsQuiet() {
      try {
        const tk = tilesPrefKey(this.role)
        const fk = favoritesPrefKey(this.role)
        const ck = clicksPrefKey(this.role)
        const items = await loadPrefs([tk, fk, ck])
        this.tilePref = parseJsonPref(items[tk], { order: [], hidden: [] })
        this.favPaths = parseJsonPref(items[fk], [])
        this.clickCounts = parseJsonPref(items[ck], {})
        if (!Array.isArray(this.favPaths)) this.favPaths = []
        if (!Array.isArray(this.tilePref.hidden)) this.tilePref.hidden = []
        if (!Array.isArray(this.tilePref.order)) this.tilePref.order = []
        if (!this.clickCounts || typeof this.clickCounts !== 'object') this.clickCounts = {}
      } catch {
        // 偏好失败不影响待办数字
      }
    },
    async persistTiles() {
      try {
        await savePref(tilesPrefKey(this.role), this.tilePref)
      } catch { /* 忽略 */ }
    },
    async persistFavs() {
      try {
        await savePref(favoritesPrefKey(this.role), this.favPaths)
      } catch { /* 忽略 */ }
    },
    async persistClicks() {
      try {
        await savePref(clicksPrefKey(this.role), this.clickCounts)
      } catch { /* 忽略 */ }
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
      if (c && c.key) {
        this.clickCounts = bumpClickCount(this.clickCounts, c.key)
        this.persistClicks()
      }
      this.go(c && c.to)
    },
    go(path) {
      if (!path) return
      if (this.$route.path !== path) this.$router.push(path).catch(() => {})
    },
    openTodo(t) {
      this.go(TODO_TYPE_ROUTES[t && t.todoType] || '/admin/approval/todos')
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
    }
  }
}
</script>

<style scoped>
.wb { display: flex; flex-direction: column; gap: 18px; padding: 4px 2px 24px; }

.wb__hero {
  display: flex; align-items: flex-start; justify-content: space-between; gap: 16px;
  padding: 20px 22px; border-radius: 14px; color: #fff;
  background: linear-gradient(120deg, #1f3f78 0%, #2f6ab5 60%, #3f86c9 100%);
}
.wb__hi { margin: 0 0 6px; font-size: 20px; font-weight: 700; }
.wb__headline { margin: 0; font-size: 15px; opacity: .92; }
.wb__headline.is-risk { font-weight: 700; opacity: 1; }
.wb__scope { margin: 8px 0 0; font-size: 12px; opacity: .78; }
.wb__hero-side { display: flex; align-items: center; gap: 10px; flex-shrink: 0; flex-wrap: wrap; }
.wb__role {
  font-size: 13px; padding: 4px 10px; border-radius: 999px;
  background: rgba(255,255,255,.18);
}
.wb__refresh {
  font-size: 13px; padding: 4px 12px; border-radius: 8px; cursor: pointer;
  color: #fff; background: rgba(255,255,255,.16); border: 1px solid rgba(255,255,255,.3);
}
.wb__refresh:disabled { opacity: .5; cursor: default; }

.wb__error {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  padding: 14px 16px;
  border: 1px solid #f0c2c2; background: #fdf3f3; color: #a33; border-radius: 10px;
}
.wb__retry {
  margin-left: auto; padding: 4px 12px; border-radius: 8px; cursor: pointer;
  border: 1px solid #d99; background: #fff; color: #a33;
}

.wb__edit {
  padding: 14px 16px; border-radius: 12px; background: #f7fafc; border: 1px solid #e3ebf3;
}
.wb__edit-head {
  display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin-bottom: 12px;
  font-size: 13px; color: #5a6b7d;
}
.wb__edit-head strong { color: #1f2d3d; font-size: 14px; }
.wb__edit-reset {
  margin-left: auto; font-size: 13px; cursor: pointer; color: #2f6ab5;
  background: none; border: none; font-family: inherit;
}
.wb__edit-grid { display: grid; gap: 16px; grid-template-columns: 1fr 1fr; }
@media (max-width: 700px) { .wb__edit-grid { grid-template-columns: 1fr; } }
.wb__edit-title { margin: 0 0 8px; font-size: 13px; color: #1f2d3d; }
.wb__edit-row {
  display: flex; align-items: center; gap: 8px; padding: 6px 0; font-size: 14px; color: #22303f;
}
.wb__edit-row--sort { justify-content: space-between; }
.wb__edit-check { display: flex; align-items: center; gap: 8px; }
.wb__edit-sort { display: flex; gap: 6px; }
.wb__edit-sort button {
  font-size: 12px; padding: 2px 8px; cursor: pointer; border-radius: 6px;
  border: 1px solid #c9d6e4; background: #fff; color: #2f6ab5; font-family: inherit;
}
.wb__edit-sort button:disabled { opacity: .4; cursor: default; }
.wb__edit-hint { margin: 8px 0 0; font-size: 12px; color: #8a97a5; }

.wb__block { display: flex; flex-direction: column; gap: 10px; }
.wb__block-title {
  display: flex; align-items: center; justify-content: space-between;
  margin: 0; font-size: 15px; font-weight: 600; color: #1f2d3d;
}
.wb__more {
  font-size: 13px; font-weight: 400; color: #2f6ab5;
  background: none; border: none; cursor: pointer; padding: 0;
  font-family: inherit;
}
.wb__cues { display: grid; gap: 12px; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); }

.wb__split { display: grid; gap: 16px; grid-template-columns: minmax(0, 2fr) minmax(220px, 1fr); }
@media (max-width: 900px) { .wb__split { grid-template-columns: 1fr; } }

.wb__items { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 2px; }
.wb__item {
  display: flex; align-items: center; gap: 10px; padding: 11px 12px; cursor: pointer;
  border-radius: 10px; background: #fff; border: 1px solid #edf1f5;
}
.wb__item:hover { border-color: #cfe0f2; background: #f8fbff; }
.wb__dot { width: 8px; height: 8px; border-radius: 50%; background: #9bb4cc; flex-shrink: 0; }
.wb__dot.is-high { background: #e05b5b; }
.wb__dot.is-medium { background: #e0a05b; }
.wb__item-title { flex: 1; font-size: 14px; color: #22303f; min-width: 0; }
.wb__due { font-size: 12px; color: #7a8a9a; flex-shrink: 0; }
.wb__due.is-over { color: #e05b5b; font-weight: 600; }
.wb__due.is-near { color: #c47a12; font-weight: 600; }

.wb__side { display: flex; flex-direction: column; gap: 8px; }
.wb__link {
  padding: 10px 12px; border-radius: 10px; font-size: 14px; color: #22303f;
  background: #fff; border: 1px solid #edf1f5; text-decoration: none; cursor: pointer;
  text-align: left; font-family: inherit;
}
.wb__link:hover { border-color: #cfe0f2; background: #f8fbff; }
.wb__msg {
  margin-top: 4px; padding: 10px 12px; border-radius: 10px;
  font-size: 14px; color: #8a5a00; background: #fff8e8; border: 1px solid #f0e0bb;
}
.wb__empty { margin: 0; padding: 22px 0; text-align: center; color: #5a9367; font-size: 14px; }
.wb__muted { margin: 0; padding: 18px 0; text-align: center; color: #8a97a5; font-size: 13px; }
</style>
