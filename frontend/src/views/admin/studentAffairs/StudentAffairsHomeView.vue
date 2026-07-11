<template>
  <ModulePageShell
    title="学工首页"
    :subtitle="subtitle"
    :role-name="roleName"
    :data-scope-name="dataScopeName"
    watermark-purpose="学工首页查阅"
  >
    <LoadingState v-if="loading" text="正在加载学工首页…" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <template v-else-if="board">
      <!-- 三角色视图 + 数据范围 + 更新时间 -->
      <section class="sa-hero">
        <div class="sa-hero__main">
          <span class="sa-hero__view">{{ board.viewLabel }}</span>
          <span class="sa-hero__scope">数据范围口径：{{ scopeModeLabel }}</span>
        </div>
        <span class="sa-hero__time">数据更新于 {{ updatedAtText }}</span>
      </section>

      <!-- 9 张统计卡（真实聚合，按数据范围）；有对应现有页面者可下钻 -->
      <section class="sa-block">
        <h3 class="sa-block__title">关键指标</h3>
        <div class="sa-cards">
          <button
            v-for="c in board.summaryCards"
            :key="c.key"
            type="button"
            class="sa-card"
            :class="{ 'is-link': !!summaryLink(c.key), 'is-alert': isAlert(c) }"
            @click="onSummary(c)"
          >
            <span class="sa-card__value">{{ c.value }}<i class="sa-card__unit">{{ c.unit }}</i></span>
            <span class="sa-card__label">{{ c.label }}</span>
            <span v-if="summaryLink(c.key)" class="sa-card__go">查看 →</span>
          </button>
        </div>
      </section>

      <!-- 13 张业务模块卡：在用可进现有页；后端就绪但前端待施工者点提示；后续上线者置灰 -->
      <section class="sa-block">
        <div class="sa-block__head">
          <h3 class="sa-block__title">学工业务模块</h3>
          <span class="sa-block__hint">共 {{ board.moduleCards.length }} 个模块 · 后端已就绪，前端按 V1 阶段逐个上线</span>
        </div>
        <div class="sa-modules">
          <button
            v-for="m in board.moduleCards"
            :key="m.key"
            type="button"
            class="sa-mod"
            :class="moduleClass(m)"
            @click="onModule(m)"
          >
            <span class="sa-mod__label">{{ m.label }}</span>
            <span class="sa-mod__pill" :class="'sa-mod__pill--' + moduleState(m)">{{ moduleStateLabel(m) }}</span>
          </button>
        </div>
      </section>
    </template>
  </ModulePageShell>
</template>

<script>
/**
 * 学工首页（/admin/student-affairs）—— 学工中心门面。
 * 数据全部来自真实后端 GET /api/v1/student-affairs/dashboard（三角色视图 + 9 统计卡 + 13 模块卡）。
 * 下钻遵循 CLAUDE.md「不做假跳转」：仅链接到真实存在的现有页面；13A 业务页尚未施工者点击提示待施工。
 */
import { ModulePageShell, LoadingState, ErrorState } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'

// 统计卡 → 现有可达页面（无映射者仅展示，不跳转）
const SUMMARY_LINK = {
  studentTotal: '/admin/student/list',
  pendingTodo: '/admin/approval/todos',
  pendingLeave: '/admin/student-affairs/leave',
  overdueLeave: '/admin/student-affairs/leave',
  pendingAid: '/admin/student-affairs/aid',
  pendingFunding: '/admin/student-affairs/funding',
  pendingDiscipline: '/admin/student-affairs/discipline',
  riskStudents: '/admin/student-affairs/risk'
}

// 值>0 时高亮的「待处理」类指标 key
const ALERT_KEYS = new Set(['pendingLeave', 'overdueLeave', 'pendingAid', 'pendingFunding', 'pendingDiscipline', 'riskStudents'])

// 模块卡 → 现有可达页面（过渡期指向在校服务/学生画像等已实现页面；无映射者=前端待施工）
const MODULE_LINK = {
  profile: '/admin/student-affairs/profile',
  class: '/admin/student-affairs/classes',
  leave: '/admin/student-affairs/leave',
  aid: '/admin/student-affairs/aid',
  funding: '/admin/student-affairs/funding',
  discipline: '/admin/student-affairs/discipline',
  dorm: '/admin/student-affairs/dorm',
  risk: '/admin/student-affairs/risk',
  talk: '/admin/student-affairs/talks',
  family: '/admin/student-affairs/family',
  archive: '/admin/student-affairs/archive'
}

const SCOPE_MODE_LABEL = {
  ADMIN_TENANT: '全校',
  TENANT_FALLBACK: '全校（试点期）',
  COLLEGE: '本学院',
  CLASS: '本班级'
}

export default {
  name: 'StudentAffairsHomeView',
  components: { ModulePageShell, LoadingState, ErrorState },
  props: {
    ctx: { type: Object, default: null }
  },
  data() {
    return { loading: true, error: '', board: null }
  },
  computed: {
    subtitle() {
      return this.board ? this.board.viewLabel : '学工中心'
    },
    roleName() {
      return (this.ctx && this.ctx.currentRole && this.ctx.currentRole.roleName) || ''
    },
    dataScopeName() {
      return (this.ctx && this.ctx.dataScope && this.ctx.dataScope.scopeName) || ''
    },
    scopeModeLabel() {
      const m = this.board && this.board.scopeMode
      return SCOPE_MODE_LABEL[m] || m || '—'
    },
    updatedAtText() {
      const t = this.board && this.board.updatedAt
      return t ? String(t).replace('T', ' ').slice(0, 19) : '—'
    }
  },
  created() {
    this.load()
  },
  methods: {
    async load() {
      this.loading = true
      this.error = ''
      const res = await studentAffairsApi.getDashboard()
      this.loading = false
      if (res.code === 0 && res.data) {
        this.board = res.data
      } else {
        this.error = res.message || '学工首页加载失败'
      }
    },
    summaryLink(key) {
      return SUMMARY_LINK[key] || ''
    },
    isAlert(c) {
      return ALERT_KEYS.has(c.key) && Number(c.value) > 0
    },
    onSummary(c) {
      const to = this.summaryLink(c.key)
      if (to) this.$router.push(to)
    },
    moduleState(m) {
      if (m.status !== 'LIVE') return 'pending'
      return MODULE_LINK[m.key] ? 'live' : 'building'
    },
    moduleStateLabel(m) {
      return { live: '可进入', building: '待施工', pending: '后续上线' }[this.moduleState(m)]
    },
    moduleClass(m) {
      const s = this.moduleState(m)
      return { 'is-live': s === 'live', 'is-building': s === 'building', 'is-pending': s === 'pending' }
    },
    onModule(m) {
      const s = this.moduleState(m)
      if (s === 'live') {
        this.$router.push(MODULE_LINK[m.key])
      } else if (s === 'building') {
        toast.info(`「${m.label}」后端已就绪，前端页面按 V1 阶段陆续上线`)
      } else {
        toast.info(m.emptyHint || `「${m.label}」将于后续阶段上线`)
      }
    }
  }
}
</script>

<style scoped>
.sa-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  flex-wrap: wrap;
  padding: var(--space-4);
  margin-bottom: var(--space-4);
  background: var(--primary-50);
  border: 1px solid var(--primary-100);
  border-radius: var(--radius-lg);
}
.sa-hero__main {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}
.sa-hero__view {
  font-size: var(--font-size-lg);
  font-weight: 600;
  color: var(--primary-700);
}
.sa-hero__scope {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.sa-hero__time {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  white-space: nowrap;
}
.sa-block {
  margin-bottom: var(--space-5);
}
.sa-block__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-3);
  flex-wrap: wrap;
}
.sa-block__title {
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 var(--space-3);
}
.sa-block__hint {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.sa-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: var(--space-3);
}
.sa-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-4);
  background: var(--bg-card);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-lg);
  text-align: left;
  cursor: default;
  transition: border-color 0.15s, box-shadow 0.15s, transform 0.15s;
}
.sa-card.is-link {
  cursor: pointer;
}
.sa-card.is-link:hover {
  border-color: var(--primary-300);
  box-shadow: var(--shadow-sm);
  transform: translateY(-1px);
}
.sa-card__value {
  font-size: var(--font-size-2xl);
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.1;
}
.sa-card.is-alert .sa-card__value {
  color: var(--danger-600, #dc2626);
}
.sa-card__unit {
  font-size: var(--font-size-xs);
  font-weight: 500;
  color: var(--text-tertiary);
  font-style: normal;
  margin-left: 2px;
}
.sa-card__label {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.sa-card__go {
  font-size: var(--font-size-xs);
  color: var(--primary-600);
}
.sa-modules {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: var(--space-3);
}
.sa-mod {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  background: var(--bg-card);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s, transform 0.15s;
}
.sa-mod.is-live:hover {
  border-color: var(--primary-300);
  box-shadow: var(--shadow-sm);
  transform: translateY(-1px);
}
.sa-mod.is-pending {
  opacity: 0.6;
  cursor: not-allowed;
}
.sa-mod__label {
  font-size: var(--font-size-sm);
  font-weight: 500;
  color: var(--text-primary);
}
.sa-mod__pill {
  font-size: var(--font-size-xs);
  padding: 1px var(--space-2);
  border-radius: var(--radius-full);
  white-space: nowrap;
}
.sa-mod__pill--live {
  color: var(--success-700, #15803d);
  background: var(--success-50, #f0fdf4);
  border: 1px solid var(--success-100, #dcfce7);
}
.sa-mod__pill--building {
  color: var(--warning-700, #b45309);
  background: var(--warning-50, #fffbeb);
  border: 1px solid var(--warning-100, #fef3c7);
}
.sa-mod__pill--pending {
  color: var(--text-tertiary);
  background: var(--bg-muted, #f5f5f5);
  border: 1px solid var(--border-base);
}
</style>
