<template>
  <div class="wb">
    <!-- 第 1 行：先给结论（对标 Role Center 的 Headline） -->
    <section class="wb__hero">
      <div class="wb__hero-main">
        <h1 class="wb__hi">你好，{{ displayName }}</h1>
        <p class="wb__headline" :class="{ 'is-risk': hasOverdue && !error && !loading }">
          <span v-if="loading">正在读取你的待办…</span>
          <span v-else-if="error">待办读取失败</span>
          <span v-else>{{ headline }}</span>
        </p>
      </div>
      <div class="wb__hero-side">
        <span class="wb__role">{{ recipe.label }}</span>
        <button class="wb__refresh" type="button" :disabled="loading" @click="load">刷新</button>
      </div>
    </section>

    <!-- 读取失败：如实报错，不用占位数字冒充 -->
    <div v-if="error" class="wb__error" role="alert">
      <strong>无法加载工作台数据。</strong>
      <span>{{ error }}</span>
      <button class="wb__retry" type="button" @click="load">重试</button>
    </div>

    <template v-else>
      <!-- 第 2 行：汇总磁贴（可点击下钻） -->
      <section class="wb__block">
        <h2 class="wb__block-title">我的待办</h2>
        <div class="wb__cues">
          <AppMetricCard
            v-for="c in recipe.summaryCues"
            :key="c.key"
            :title="c.title"
            :value="loading ? 0 : valueOf(c.source)"
            :accent="c.accent"
            :loading="loading"
            drillable
            :drill-target="c.to"
            @drill="go"
          />
        </div>
      </section>

      <!-- 第 3 行：分类磁贴（该角色的业务队列；为 0 的类型不占版面） -->
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
            @drill="go"
          />
        </div>
      </section>

      <!-- 第 4 行：明细 + 快捷入口 -->
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
              <span v-if="t.dueAt" class="wb__due" :class="{ 'is-over': isOverdue(t) }">
                {{ isOverdue(t) ? '已逾期' : '截止 ' + fmtDate(t.dueAt) }}
              </span>
            </li>
          </ul>
        </div>

        <div class="wb__side">
          <h2 class="wb__block-title">常用入口</h2>
          <button
            v-for="l in recipe.quickLinks"
            :key="l.to"
            class="wb__link"
            type="button"
            @click="go(l.to)"
          >{{ l.label }}</button>
          <!-- 消息中心路由尚为 planned；只展示计数，不下钻到无关的待办页冒充 -->
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
 *
 * 与旧 AdminWorkbenchView 菜单桥接页的区别：本页消费真实待办数据，回答「我今天要处理什么」。
 *
 * 角色以后端 /todos/summary 返回的 role 为准，前端不自行推断，
 * 也不提供「视角切换」——切身份必须走真实的 /auth/switch-role。
 */
import AppMetricCard from '@/components/common/AppMetricCard.vue'
import {
  fetchMessageCount,
  fetchTodoCount,
  fetchTodoList,
  fetchTodoSummary
} from '../api/workbench.api'
import { resolveRecipe, TODO_TYPE_ROUTES } from '../config/workbenchRecipes'

const EMPTY_SUMMARY = Object.freeze({
  pending: 0,
  overdue: 0,
  nearDeadline: 0,
  doneToday: 0
})

export default {
  name: 'WorkbenchView',
  components: { AppMetricCard },
  props: {
    displayName: { type: String, default: '老师' }
  },
  data() {
    return {
      loading: true,
      error: '',
      role: '',
      summary: { ...EMPTY_SUMMARY },
      byType: {},
      todos: [],
      unread: 0
    }
  },
  computed: {
    recipe() {
      return resolveRecipe(this.role)
    },
    headline() {
      try {
        return this.recipe.headline({ summary: this.summary, byType: this.byType })
      } catch {
        return ''
      }
    },
    hasOverdue() {
      return (this.summary.overdue || 0) > 0
    },
    /** 该角色配方里、当前确实有数据的分类磁贴（为 0 的类型不占版面） */
    visibleTypeCues() {
      return (this.recipe.typeCues || []).filter((c) => this.valueOf(c.source) > 0)
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
        // 并发拉取；任一失败即整体报错，不用默认值掩盖（工作台数字必须可信）
        const [summary, count, list, msg] = await Promise.all([
          fetchTodoSummary(),
          fetchTodoCount(),
          fetchTodoList(),
          fetchMessageCount()
        ])
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
      } catch (e) {
        // 失败后清空业务态，避免重试失败时仍展示上一轮成功数字
        this.role = ''
        this.summary = { ...EMPTY_SUMMARY }
        this.byType = {}
        this.todos = []
        this.unread = 0
        this.error = (e && e.message) || '请求失败'
      } finally {
        this.loading = false
      }
    },
    /** 'summary.pending' / 'todoType.LEAVE_APPROVAL' / 'message.unread' → 数值 */
    valueOf(source) {
      const [ns, key] = String(source || '').split('.')
      if (ns === 'summary') return this.summary[key] || 0
      if (ns === 'todoType') return this.byType[key] || 0
      if (ns === 'message') return this.unread || 0
      return 0
    },
    go(path) {
      if (!path) return
      if (this.$route.path !== path) this.$router.push(path).catch(() => {})
    },
    /** 点单条待办：跳到该业务类型对应的列表页（暂不做详情弹层，避免半成品交互） */
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
.wb__hero-side { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
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
