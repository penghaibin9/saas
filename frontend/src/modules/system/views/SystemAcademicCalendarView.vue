<template>
  <ModulePageShell
    title="学年学期与业务日历"
    subtitle="全校统一切换：学期主数据由教务维护，这里决定全校何时切换、各模块窗口何时开放"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />

      <template v-else>
        <!-- 首屏结论：当前学期 + 下一次切换 + 阻断 -->
        <section class="mp-card ac-hero">
          <div class="ac-hero__main">
            <span class="ac-hero__label">当前生效学期</span>
            <strong v-if="activeRow" class="ac-hero__value">
              {{ activeRow.yearCode }} 第{{ activeRow.termNo }}学期
              <span class="ac-hero__sub">{{ activeRow.termName || '' }}</span>
            </strong>
            <strong v-else class="ac-hero__value is-empty">尚未激活任何学期</strong>
            <p class="ac-hero__hint">
              <template v-if="activeRow">
                激活于 {{ fmt(activeRow.activatedAt) }} · 时区 {{ activeRow.timezone }}
              </template>
              <template v-else>
                各业务模块无法确定当前学期，相关功能会明确报错而不是猜一个默认值。
              </template>
            </p>
          </div>
          <div class="ac-hero__side">
            <div class="ac-metric">
              <span class="ac-metric__num">{{ rows.length }}</span>
              <span class="ac-metric__cap">已纳入治理</span>
            </div>
            <div class="ac-metric" :class="{ 'is-warn': ungoverned.length }">
              <span class="ac-metric__num">{{ ungoverned.length }}</span>
              <span class="ac-metric__cap">未纳入治理</span>
            </div>
            <div class="ac-metric" :class="{ 'is-warn': scheduledRow }">
              <span class="ac-metric__num">{{ scheduledRow ? 1 : 0 }}</span>
              <span class="ac-metric__cap">已排期待激活</span>
            </div>
          </div>
        </section>

        <!-- 一致性问题：暴露而不是静默修复 -->
        <section v-if="issues.length" class="mp-card ac-issues">
          <header class="mp-card__head"><span class="mp-card__title">需要处理的一致性问题</span></header>
          <div class="mp-card__body">
            <p v-for="issue in issues" :key="issue.code" class="ac-issue">
              <span class="ac-issue__code">{{ issue.code }}</span>{{ issue.message }}
            </p>
          </div>
        </section>

        <!-- 治理列表 -->
        <section class="mp-card">
          <header class="mp-card__head">
            <span class="mp-card__title">学期治理</span>
            <span class="mp-note">切换会影响下方登记的全部模块</span>
          </header>
          <div class="mp-card__body" style="padding-top: 0">
            <table class="mp-audit">
              <thead>
                <tr>
                  <th style="width: 200px">学期</th>
                  <th style="width: 120px">全校状态</th>
                  <th style="width: 120px">教务状态</th>
                  <th>时间范围</th>
                  <th style="width: 150px">排期激活</th>
                  <th style="width: 190px">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in rows" :key="row.termId">
                  <td class="is-who">
                    {{ row.yearCode }} 第{{ row.termNo }}学期
                    <span class="ac-sub">{{ row.termName || '—' }}</span>
                  </td>
                  <td><StatusTag :status="row.governanceStatus" :label="statusLabel(row.governanceStatus)" /></td>
                  <td>
                    {{ row.academicStatus || '—' }}
                    <span v-if="row.academicIsCurrent" class="ac-flag">教务当前</span>
                  </td>
                  <td>{{ fmtDate(row.startDate) }} ~ {{ fmtDate(row.endDate) }}</td>
                  <td>{{ fmt(row.scheduledAt) }}</td>
                  <td>
                    <button class="mp-link" @click="openDetail(row)">详情</button>
                    <button
                      v-for="target in row.allowedTransitions"
                      :key="target"
                      class="mp-link"
                      @click="openTransition(row, target)"
                    >{{ actionLabel(target) }}</button>
                  </td>
                </tr>
              </tbody>
            </table>
            <EmptyState
              v-if="!rows.length"
              title="尚未纳入任何学期"
              description="教务建好学年学期后，在下方一键纳入全校治理"
            />
          </div>
        </section>

        <!-- 未纳入治理 -->
        <section v-if="ungoverned.length" class="mp-card">
          <header class="mp-card__head">
            <span class="mp-card__title">教务已建、尚未纳入全校治理</span>
          </header>
          <div class="mp-card__body" style="padding-top: 0">
            <table class="mp-audit">
              <thead>
                <tr><th>学期</th><th style="width: 130px">教务状态</th><th style="width: 110px">操作</th></tr>
              </thead>
              <tbody>
                <tr v-for="t in ungoverned" :key="t.termId">
                  <td class="is-who">{{ t.yearCode }} 第{{ t.termNo }}学期<span class="ac-sub">{{ t.termName || '—' }}</span></td>
                  <td>{{ t.academicStatus || '—' }}</td>
                  <td><button class="mp-link" :disabled="enrolling === t.termId" @click="enroll(t)">纳入治理</button></td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <!-- 受影响模块 -->
        <section class="mp-card">
          <header class="mp-card__head">
            <span class="mp-card__title">切换影响的模块</span>
            <span class="mp-note">未接入的模块仍按各自口径取值，需在后续施工卡收口</span>
          </header>
          <div class="mp-card__body" style="padding-top: 0">
            <table class="mp-audit">
              <thead><tr><th style="width: 190px">模块</th><th>依赖学期的业务</th><th style="width: 120px">接入状态</th></tr></thead>
              <tbody>
                <tr v-for="c in consumers" :key="c.moduleCode">
                  <td class="is-who">{{ c.moduleName }}</td>
                  <td>{{ c.usage }}</td>
                  <td>
                    <span :class="['ac-wired', c.wired ? 'is-on' : 'is-off']">{{ c.wired ? '已接入' : '未接入' }}</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </template>
    </div>

    <!-- 状态切换 -->
    <AppDrawer v-model:visible="form.open" :title="form.title">
      <p class="ac-form__tip">{{ form.tip }}</p>

      <template v-if="form.target === 'SCHEDULED'">
        <label class="ac-label">计划激活时间<span class="ac-required">*</span></label>
        <input v-model="form.scheduledAt" type="datetime-local" class="mp-input" />
      </template>

      <label class="ac-label" style="margin-top: var(--space-3)">
        变更原因<span class="ac-required">*</span>
      </label>
      <textarea v-model="form.reason" class="mp-textarea" rows="2" placeholder="至少 5 个字，将写入切换审计" />

      <div v-if="form.blockers.length" class="ac-blockers">
        <p class="ac-blockers__title">本学期仍有未收尾业务</p>
        <p v-for="b in form.blockers" :key="b.code" class="ac-blockers__item">
          <span class="ac-issue__code">{{ b.ownerModule }}</span>{{ b.message }}
        </p>
        <label class="ac-force">
          <input v-model="form.force" type="checkbox" />
          已与业务负责人确认，带未收尾业务强制结期（将完整记入审计）
        </label>
      </div>

      <div v-if="form.error" class="mp-form-err">{{ form.error }}</div>

      <template #footer>
        <AppButton variant="ghost" @click="form.open = false">取消</AppButton>
        <AppButton variant="primary" :loading="form.submitting" @click="submitTransition">确认变更</AppButton>
      </template>
    </AppDrawer>

    <!-- 详情 -->
    <AppDrawer v-model:visible="detail.open" :title="detail.title">
      <LoadingState v-if="detail.loading" />
      <template v-else-if="detail.data">
        <h4 class="ac-section">结期阻断项</h4>
        <p v-if="!detail.data.blockers.length" class="ac-ok">无阻断，可以进入结期</p>
        <p v-for="b in detail.data.blockers" :key="b.code" class="ac-blockers__item">
          <span class="ac-issue__code">{{ b.ownerModule }}</span>{{ b.message }}
        </p>

        <h4 class="ac-section">业务窗口</h4>
        <table v-if="detail.data.windows.length" class="mp-audit">
          <thead><tr><th>类型</th><th>模块</th><th>开始</th><th>结束</th></tr></thead>
          <tbody>
            <tr v-for="w in detail.data.windows" :key="w.windowType + w.moduleCode">
              <td>{{ w.windowType }}</td><td>{{ w.moduleCode }}</td>
              <td>{{ fmt(w.startAt) }}</td><td>{{ fmt(w.endAt) }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else class="ac-ok">尚未配置业务窗口</p>

        <h4 class="ac-section">切换历史</h4>
        <table v-if="detail.data.transitions.length" class="mp-audit">
          <thead><tr><th style="width: 150px">时间</th><th style="width: 130px">变更</th><th>原因</th></tr></thead>
          <tbody>
            <tr v-for="(t, i) in detail.data.transitions" :key="i">
              <td>{{ fmt(t.occurredAt) }}</td>
              <td>{{ t.fromStatus || '—' }} → {{ t.toStatus }}</td>
              <td>{{ t.reason || '—' }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else class="ac-ok">暂无切换记录</p>
      </template>
    </AppDrawer>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, LoadingState, ErrorState, EmptyState, StatusTag } from '@/components/business'
import { AppButton } from '@/components/ui'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import { systemApi } from '@/modules/system/api/system.api'
import { toast } from '@/utils/toast'

const STATUS_LABEL = {
  DRAFT: '草稿',
  VALIDATED: '已校验',
  SCHEDULED: '已排期',
  ACTIVE: '全校生效',
  CLOSING: '结期中',
  CLOSED: '已结束',
  ARCHIVED: '已归档'
}

const ACTION_LABEL = {
  DRAFT: '退回草稿',
  VALIDATED: '校验通过',
  SCHEDULED: '排期激活',
  ACTIVE: '立即激活',
  CLOSING: '开始结期',
  CLOSED: '确认结束',
  ARCHIVED: '归档'
}

const ACTION_TIP = {
  VALIDATED: '校验只标记学期信息已确认，不改变任何模块的当前学期。',
  SCHEDULED: '排期不会立即生效；到点后由定时任务激活，重复运行不会重复激活。',
  ACTIVE: '激活后全校（含教务既有链路）立刻切到该学期。同一时间只能有一个生效学期。',
  CLOSING: '进入结期意味着该学期不再是当前学期；有未收尾业务时会被阻断。',
  CLOSED: '确认结束后不可再撤回到生效状态。',
  ARCHIVED: '归档后该学期完全只读。',
  DRAFT: '退回草稿以便修改学期信息。'
}

export default {
  name: 'SystemAcademicCalendarView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, StatusTag, AppButton, AppDrawer },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      ungoverned: [],
      issues: [],
      consumers: [],
      enrolling: '',
      form: {
        open: false, termId: '', target: '', title: '', tip: '',
        reason: '', scheduledAt: '', force: false, blockers: [],
        expectedVersion: 0, error: '', submitting: false
      },
      detail: { open: false, loading: false, title: '', data: null }
    }
  },
  computed: {
    activeRow() { return this.rows.find((r) => r.governanceStatus === 'ACTIVE') || null },
    scheduledRow() { return this.rows.find((r) => r.governanceStatus === 'SCHEDULED') || null }
  },
  created() { this.load() },
  methods: {
    statusLabel(s) { return STATUS_LABEL[s] || s },
    actionLabel(s) { return ACTION_LABEL[s] || s },
    fmt(value) { return value ? String(value).replace('T', ' ').slice(0, 16) : '—' },
    fmtDate(value) { return value ? String(value).slice(0, 10) : '—' },

    async load() {
      this.loading = true
      this.error = ''
      const res = await systemApi.getAcademicCalendars()
      if (res.code === 0) {
        const data = res.data || {}
        this.rows = data.items || []
        this.ungoverned = data.ungovernedTerms || []
        this.issues = data.issues || []
        this.consumers = data.consumers || []
      } else {
        this.error = res.message
      }
      this.loading = false
    },

    async enroll(term) {
      this.enrolling = term.termId
      const res = await systemApi.enrollAcademicCalendar(term.termId)
      this.enrolling = ''
      if (res.code === 0) {
        toast.success('已纳入全校治理')
        this.load()
      } else {
        toast.error(res.message)
      }
    },

    openTransition(row, target) {
      this.form = {
        open: true,
        termId: row.termId,
        target,
        title: `${ACTION_LABEL[target] || target} · ${row.yearCode} 第${row.termNo}学期`,
        tip: ACTION_TIP[target] || '',
        reason: '',
        scheduledAt: '',
        force: false,
        blockers: [],
        expectedVersion: row.version,
        error: '',
        submitting: false
      }
      if (target === 'CLOSING') this.loadBlockers(row.termId)
    },

    async loadBlockers(termId) {
      const res = await systemApi.getAcademicCalendarBlockers(termId)
      if (res.code === 0) this.form.blockers = (res.data || {}).items || []
    },

    async submitTransition() {
      if (!this.form.reason || this.form.reason.trim().length < 5) {
        this.form.error = '变更原因不少于 5 个字'
        return
      }
      if (this.form.target === 'SCHEDULED' && !this.form.scheduledAt) {
        this.form.error = '请填写计划激活时间'
        return
      }
      this.form.submitting = true
      this.form.error = ''
      const res = await systemApi.transitionAcademicCalendar(this.form.termId, {
        targetStatus: this.form.target,
        reason: this.form.reason.trim(),
        expectedVersion: this.form.expectedVersion,
        scheduledAt: this.form.scheduledAt ? new Date(this.form.scheduledAt).toISOString() : null,
        force: this.form.force
      })
      this.form.submitting = false
      if (res.code === 0) {
        toast.success('学期状态已变更并写入审计')
        this.form.open = false
        this.load()
      } else {
        // 结期被阻断时后端会带回 blockers，必须显示出来而不是只报一句失败
        this.form.error = res.message
        if (this.form.target === 'CLOSING') this.loadBlockers(this.form.termId)
      }
    },

    async openDetail(row) {
      this.detail = {
        open: true, loading: true,
        title: `${row.yearCode} 第${row.termNo}学期 · 详情`, data: null
      }
      const res = await systemApi.getAcademicCalendarDetail(row.termId)
      this.detail.loading = false
      if (res.code === 0) this.detail.data = res.data
      else toast.error(res.message)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';

.ac-hero { display: flex; gap: var(--space-4); align-items: center; padding: var(--space-4); }
.ac-hero__main { flex: 1; min-width: 0; }
.ac-hero__label { font-size: var(--font-size-sm); color: var(--text-tertiary); }
.ac-hero__value { display: block; font-size: var(--font-size-xl); margin-top: var(--space-1); }
.ac-hero__value.is-empty { color: var(--danger-600); }
.ac-hero__sub { font-size: var(--font-size-sm); color: var(--text-tertiary); font-weight: normal; margin-left: var(--space-2); }
.ac-hero__hint { margin: var(--space-2) 0 0; font-size: var(--font-size-sm); color: var(--text-secondary); }
.ac-hero__side { display: flex; gap: var(--space-3); flex-wrap: wrap; }
.ac-metric { min-width: 92px; text-align: center; padding: var(--space-2); border-radius: var(--radius-md); background: var(--fill-secondary); }
.ac-metric.is-warn { background: var(--warning-50, var(--fill-secondary)); }
.ac-metric__num { display: block; font-size: var(--font-size-lg); font-weight: 600; }
.ac-metric__cap { font-size: var(--font-size-xs); color: var(--text-tertiary); }

.ac-issues { border-left: 3px solid var(--warning-500, var(--danger-600)); }
.ac-issue { margin: 0 0 var(--space-2); font-size: var(--font-size-sm); }
.ac-issue__code { display: inline-block; margin-right: var(--space-2); padding: 0 var(--space-1); border-radius: var(--radius-sm); background: var(--fill-secondary); font-size: var(--font-size-xs); color: var(--text-secondary); }

.ac-sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); font-weight: normal; }
.ac-flag { margin-left: var(--space-1); padding: 0 var(--space-1); border-radius: var(--radius-sm); background: var(--fill-secondary); font-size: var(--font-size-xs); color: var(--text-secondary); }
.ac-wired.is-on { color: var(--success-600, var(--text-primary)); }
.ac-wired.is-off { color: var(--text-tertiary); }

.ac-label { display: block; font-size: var(--font-size-sm); margin-bottom: var(--space-1); }
.ac-required { color: var(--danger-600); }
.ac-form__tip { margin: 0 0 var(--space-3); font-size: var(--font-size-sm); color: var(--text-secondary); }
.ac-blockers { margin-top: var(--space-3); padding: var(--space-3); border-radius: var(--radius-md); background: var(--fill-secondary); }
.ac-blockers__title { margin: 0 0 var(--space-2); font-size: var(--font-size-sm); font-weight: 600; color: var(--danger-600); }
.ac-blockers__item { margin: 0 0 var(--space-1); font-size: var(--font-size-sm); }
.ac-force { display: block; margin-top: var(--space-3); font-size: var(--font-size-sm); }
.ac-section { margin: var(--space-4) 0 var(--space-2); font-size: var(--font-size-sm); }
.ac-ok { margin: 0; font-size: var(--font-size-sm); color: var(--text-secondary); }
</style>
