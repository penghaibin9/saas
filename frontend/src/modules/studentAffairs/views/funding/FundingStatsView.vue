<template>
  <AppPageShell
    title="资助成效与到账核对"
    subtitle="统一核对奖助获批、勤工在岗、贷款确认、减免落实和银行发放结果。人数按学生去重，金额与名单按权限展示。"
    :role-name="ctx?.currentRole?.roleName || '学工处 / 资助老师'"
    :data-scope-name="stats.scope?.label || ctx?.dataScope?.scopeName || '当前数据范围'"
    watermark-purpose="资助统计与到账核对"
  >
    <template #actions>
      <button type="button" class="fs-refresh" :disabled="loading" @click="load">刷新数据</button>
    </template>

    <AppGlobalState
      :state="pageState"
      :description="errorMessage"
      loading-text="正在汇总资助成效与发放台账..."
      @retry="load"
      @back="$router.push('/admin/student-affairs/funding')"
    >
      <section class="fs-overview" aria-label="资助成效概览">
        <div class="fs-overview__lead">
          <span class="fs-eyebrow">当前范围 · 学生去重口径</span>
          <div class="fs-coverage">
            <strong>{{ stats.beneficiaryStudents || 0 }}</strong>
            <span>/ {{ stats.visibleStudents || 0 }} 人受助</span>
            <em>{{ percent(stats.coverageRate) }}</em>
          </div>
          <p>{{ stats.definitions?.coverage || '奖助、勤工、贷款和减免四类台账合并后按学生去重。' }}</p>
        </div>
        <button type="button" class="fs-overview__metric" @click="openDrill('DIFFICULT_BENEFICIARY', '困难学生受助名单')">
          <span>困难学生受助</span>
          <strong>{{ stats.difficultBeneficiaries || 0 }}<small> / {{ stats.difficultStudents || 0 }} 人</small></strong>
          <em>{{ percent(stats.difficultCoverageRate) }} · 查看脱敏名单</em>
        </button>
        <div class="fs-overview__metric">
          <span>奖助申请</span>
          <strong>{{ stats.grantedApplications || 0 }}<small> 获批</small></strong>
          <em>{{ stats.inProgressApplications || 0 }} 笔仍在办理</em>
        </div>
        <button
          type="button"
          class="fs-overview__metric"
          :class="{ 'is-attention': stats.ledger?.attention }"
          @click="openDrill('DISBURSEMENT_ATTENTION', '发放待处理学生')"
        >
          <span>发放对账</span>
          <strong>{{ stats.ledger?.attention || 0 }}<small> 笔待处理</small></strong>
          <em>{{ stats.ledger?.missing || 0 }} 笔获批后尚未建台账</em>
        </button>
      </section>

      <AppInlineAlert
        v-if="stats.ledger?.attention"
        type="warning"
        :description="`发现 ${stats.ledger.attention} 笔发放事项需要核对，其中 ${stats.ledger.missing || 0} 笔尚未建立发放台账。统计只提示问题，实际处理请进入发放登记。`"
      />

      <section class="fs-actions" aria-label="资助业务分支">
        <button v-for="item in serviceCards" :key="item.key" type="button" class="fs-action" @click="go(item.path)">
          <span class="fs-action__dot" :class="`is-${item.tone}`"></span>
          <span class="fs-action__copy"><strong>{{ item.label }}</strong><small>{{ item.hint }}</small></span>
          <b>{{ item.value }}</b>
          <i aria-hidden="true">›</i>
        </button>
      </section>

      <div class="fs-grid fs-grid--top">
        <AppSectionCard title="需要处理" subtitle="按真实台账状态给出入口；统计页不直接改业务数据。" compact>
          <div class="fs-todos">
            <button type="button" @click="go('/admin/student-affairs/funding/ledger')">
              <span><strong>奖助审核与公示</strong><small>已提交、审核、公示或退回的申请</small></span>
              <b>{{ stats.inProgressApplications || 0 }}</b>
            </button>
            <button type="button" @click="go('/admin/student-affairs/funding/disbursements')">
              <span><strong>银行发放核对</strong><small>未建台账、待发放、失败或退回</small></span>
              <b :class="{ 'is-danger': stats.ledger?.attention }">{{ stats.ledger?.attention || 0 }}</b>
            </button>
          </div>
        </AppSectionCard>

        <AppSectionCard title="资金口径" subtitle="获批不等于到账，五类金额分别汇总。" compact>
          <div v-if="stats.amounts?.visible" class="fs-money">
            <div><span>奖助获批</span><strong>{{ money(stats.amounts.approvedAmountTotal) }}</strong></div>
            <div><span>银行已登记发放</span><strong>{{ money(stats.amounts.issuedAmountTotal) }}</strong></div>
            <div><span>勤工补贴累计</span><strong>{{ money(stats.amounts.workStudySubsidyTotal) }}</strong></div>
            <div><span>贷款已确认</span><strong>{{ money(stats.amounts.confirmedLoanAmountTotal) }}</strong></div>
            <div><span>减免/临补已落实</span><strong>{{ money(stats.amounts.issuedReductionAmountTotal) }}</strong></div>
          </div>
          <div v-else class="fs-hidden">
            <strong>金额汇总按权限隐藏</strong>
            <p>你仍可查看人数、覆盖率和脱敏名单；金额只向学校管理员、学工管理员和资助老师开放。</p>
          </div>
        </AppSectionCard>
      </div>

      <div class="fs-grid fs-grid--bottom">
        <AppSectionCard title="奖助申请进度" subtitle="用于识别审核、公示和退回积压。" compact>
          <BreakdownTable :rows="stats.byStatus" :label-map="STATUS_LABELS" empty="当前范围暂无奖助申请" />
        </AppSectionCard>
        <AppSectionCard title="奖助项目结构" subtitle="仅统计奖学金与助学金申请；勤贷补在上方单独列示。" compact>
          <BreakdownTable :rows="stats.byType" :label-map="TYPE_LABELS" empty="当前范围暂无项目申请" />
        </AppSectionCard>
        <AppSectionCard title="发放台账结果" subtitle="获批后未建台账会单独计入待处理。" compact>
          <BreakdownTable :rows="stats.ledger?.byStatus" :label-map="BANK_LABELS" empty="当前范围暂无发放记录" />
        </AppSectionCard>
      </div>

      <AppSectionCard v-if="stats.byYear?.length" title="分学年奖助结果" subtitle="这里统计奖助申请，不与勤工、贷款和减免金额混算。" compact class="fs-years-card">
        <div class="fs-years" role="table" aria-label="分学年奖助结果">
          <div class="fs-years__head" role="row"><span>学年</span><span>申请</span><span>获批</span><span>获批率</span></div>
          <div v-for="row in stats.byYear" :key="row.key" class="fs-years__row" role="row">
            <strong>{{ row.key }}</strong><span>{{ row.count }}</span><span>{{ row.granted }}</span><em>{{ percent(row.count ? row.granted / row.count : 0) }}</em>
          </div>
        </div>
      </AppSectionCard>

      <p class="fs-definition">统计口径：{{ stats.definitions?.granted || '奖助申请获批不等同于银行到账。' }} 名单为脱敏只读结果，办理状态以各业务台账为准。</p>
    </AppGlobalState>

    <AppDrawer
      v-model:visible="drill.visible"
      :title="drill.title"
      :subtitle="`${drill.scopeLabel || stats.scope?.label || '当前数据范围'} · 姓名与学号已脱敏 · 共 ${drill.total} 人`"
      size="large"
      @close="closeDrill"
    >
      <AppGlobalState
        :state="drillState"
        :description="drill.errorMessage"
        loading-text="正在读取脱敏名单..."
        @retry="loadDrill"
      >
        <div v-if="drill.items.length" class="fs-drill-list">
          <div class="fs-drill-head"><span>学生</span><span>年级</span><span>业务来源</span></div>
          <div v-for="(student, index) in drill.items" :key="`${student.studentNo}-${index}`" class="fs-drill-row">
            <span><strong>{{ student.realName }}</strong><small>{{ student.studentNo }}</small></span>
            <span>{{ student.grade || '—' }}</span>
            <span class="fs-sources"><em v-for="source in student.sources" :key="source">{{ source }}</em></span>
          </div>
        </div>
        <div v-else class="fs-empty">当前指标暂无学生</div>
        <AppPagination
          v-if="drill.total > drill.pageSize"
          v-model:page="drill.page"
          v-model:pageSize="drill.pageSize"
          :total="drill.total"
          :disabled="drill.loading"
          @change="loadDrill"
        />
      </AppGlobalState>
      <template #footer>
        <button type="button" class="fs-close" @click="closeDrill">关闭</button>
      </template>
    </AppDrawer>
  </AppPageShell>
</template>

<script>
import {
  AppGlobalState, AppInlineAlert, AppPageShell, AppPagination, AppSectionCard
} from '@/components/common'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import BreakdownTable from '@/modules/studentAffairs/views/common/BreakdownTable.vue'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'

const STATUS_LABELS = {
  DRAFT: '草稿', SUBMITTED: '已提交', COUNSELOR_REVIEW: '辅导员初审', COLLEGE_REVIEW: '学院复审',
  SCHOOL_REVIEW: '学校终审', PUBLICITY: '公示中', GRANTED: '已获资助', REJECTED: '已驳回',
  RETURNED: '已退回', CANCELLED: '已取消', ARCHIVED: '已归档'
}
const TYPE_LABELS = { SCHOLARSHIP: '奖学金', GRANT: '助学金' }
const BANK_LABELS = { PENDING: '待发放', ISSUED: '已发放', FAILED: '发放失败', RETURNED: '银行退回' }

function emptyStats() {
  return {
    totalApplications: 0, applicantStudents: 0, grantedApplications: 0, grantedStudents: 0,
    inProgressApplications: 0, visibleStudents: 0, beneficiaryStudents: 0, coverageRate: 0,
    difficultStudents: 0, difficultBeneficiaries: 0, difficultCoverageRate: 0,
    workStudyOnboard: 0, confirmedLoans: 0, issuedReductions: 0,
    byStatus: [], byType: [], byYear: [], ledger: { total: 0, byStatus: [], missing: 0, attention: 0 },
    amounts: { visible: false }, scope: {}, definitions: {}
  }
}

function emptyDrill() {
  return {
    visible: false, loading: false, errorMessage: '', metric: '', title: '', scopeLabel: '',
    items: [], total: 0, page: 1, pageSize: 20, seq: 0
  }
}

export default {
  name: 'FundingStatsView',
  components: { AppDrawer, AppGlobalState, AppInlineAlert, AppPageShell, AppPagination, AppSectionCard, BreakdownTable },
  props: { ctx: { type: Object, default: null } },
  data() {
    return {
      loading: true, errorMessage: '', loadSeq: 0, stats: emptyStats(), drill: emptyDrill(),
      STATUS_LABELS, TYPE_LABELS, BANK_LABELS
    }
  },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    drillState() { return this.drill.loading ? 'loading' : (this.drill.errorMessage ? 'error' : 'ready') },
    serviceCards() {
      return [
        { key: 'work', label: '勤工助学', hint: '当前在岗', value: `${this.stats.workStudyOnboard || 0} 人`, tone: 'green', path: '/admin/student-affairs/funding/work-study' },
        { key: 'loan', label: '助学贷款', hint: '已确认', value: `${this.stats.confirmedLoans || 0} 人`, tone: 'blue', path: '/admin/student-affairs/funding/loans' },
        { key: 'fee', label: '减免与临补', hint: '已落实', value: `${this.stats.issuedReductions || 0} 人`, tone: 'amber', path: '/admin/student-affairs/funding/fee-reductions' },
        { key: 'award', label: '奖学金与助学金', hint: '申请学生', value: `${this.stats.applicantStudents || 0} 人`, tone: 'violet', path: '/admin/student-affairs/funding/ledger' }
      ]
    }
  },
  mounted() { this.load() },
  beforeUnmount() { this.loadSeq++; this.drill.seq++ },
  methods: {
    async load() {
      const seq = ++this.loadSeq
      this.loading = true
      this.errorMessage = ''
      try {
        const response = await studentAffairsApi.getFundingStats()
        if (seq !== this.loadSeq) return
        if (response.code !== 0 || !response.data) throw new Error(response.message || '资助统计加载失败')
        this.stats = { ...emptyStats(), ...response.data, ledger: { ...emptyStats().ledger, ...(response.data.ledger || {}) } }
      } catch (error) {
        if (seq === this.loadSeq) this.errorMessage = error.message || '资助统计加载失败'
      } finally {
        if (seq === this.loadSeq) this.loading = false
      }
    },
    openDrill(metric, title) {
      this.drill = { ...emptyDrill(), visible: true, metric, title, seq: this.drill.seq + 1 }
      this.loadDrill()
    },
    closeDrill() { this.drill.seq++; this.drill.loading = false; this.drill.visible = false },
    async loadDrill() {
      const context = { metric: this.drill.metric, page: this.drill.page, pageSize: this.drill.pageSize }
      const seq = ++this.drill.seq
      this.drill.loading = true
      this.drill.errorMessage = ''
      try {
        const response = await studentAffairsApi.getFundingStatsDrill(context)
        if (seq !== this.drill.seq || context.metric !== this.drill.metric) return
        if (response.code !== 0 || !response.data) throw new Error(response.message || '脱敏名单加载失败')
        this.drill.items = response.data.items || []
        this.drill.total = Number(response.data.total || 0)
        this.drill.scopeLabel = response.data.scopeLabel || ''
      } catch (error) {
        if (seq === this.drill.seq) this.drill.errorMessage = error.message || '脱敏名单加载失败'
      } finally {
        if (seq === this.drill.seq) this.drill.loading = false
      }
    },
    go(path) { this.$router.push(path) },
    percent(value) { return `${(Number(value || 0) * 100).toFixed(1)}%` },
    money(value) {
      if (value == null || value === '') return '—'
      return `¥${Number(value).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
    }
  }
}
</script>

<style scoped>
.fs-refresh, .fs-close { min-height: 34px; padding: 0 14px; border: 1px solid var(--border-base); border-radius: var(--radius-md); background: var(--bg-card); color: var(--text-primary); font-weight: 650; cursor: pointer; }
.fs-refresh:hover, .fs-close:hover { border-color: var(--color-primary); color: var(--color-primary); }
.fs-refresh:disabled { opacity: .55; cursor: wait; }
.fs-overview { display: grid; grid-template-columns: minmax(280px, 1.5fr) repeat(3, minmax(160px, .8fr)); min-height: 126px; margin-bottom: var(--space-3); overflow: hidden; border: 1px solid var(--border-base); border-radius: var(--radius-lg); background: var(--bg-card); box-shadow: var(--shadow-sm); }
.fs-overview__lead { padding: 18px 20px; background: linear-gradient(135deg, color-mix(in srgb, var(--color-primary) 10%, var(--bg-card)), var(--bg-card)); }
.fs-eyebrow { display: block; color: var(--color-primary); font-size: var(--font-size-xs); font-weight: 750; letter-spacing: .06em; }
.fs-coverage { display: flex; align-items: baseline; gap: 6px; margin-top: 6px; }
.fs-coverage strong { color: var(--text-primary); font-size: 32px; line-height: 1; font-variant-numeric: tabular-nums; }
.fs-coverage span { color: var(--text-secondary); font-size: var(--font-size-sm); }
.fs-coverage em { margin-left: auto; color: var(--color-primary); font-size: 18px; font-style: normal; font-weight: 750; }
.fs-overview__lead p { margin: 9px 0 0; color: var(--text-secondary); font-size: var(--font-size-xs); line-height: 1.55; }
.fs-overview__metric { display: flex; flex-direction: column; justify-content: center; min-width: 0; padding: 16px 18px; border: 0; border-left: 1px solid var(--border-light); background: transparent; color: inherit; text-align: left; }
button.fs-overview__metric { cursor: pointer; }
button.fs-overview__metric:hover { background: var(--bg-subtle); }
.fs-overview__metric > span { color: var(--text-secondary); font-size: var(--font-size-xs); }
.fs-overview__metric > strong { margin-top: 8px; color: var(--text-primary); font-size: 24px; font-variant-numeric: tabular-nums; }
.fs-overview__metric > strong small { font-size: var(--font-size-xs); font-weight: 550; }
.fs-overview__metric > em { margin-top: 7px; color: var(--text-tertiary); font-size: 12px; font-style: normal; line-height: 1.4; }
.fs-overview__metric.is-attention > strong, .fs-overview__metric.is-attention > em { color: var(--color-warning, #b45309); }
.fs-actions { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--space-2); margin: var(--space-3) 0; }
.fs-action { display: grid; grid-template-columns: 8px minmax(0, 1fr) auto 14px; align-items: center; gap: 10px; min-height: 62px; padding: 10px 13px; border: 1px solid var(--border-base); border-radius: var(--radius-md); background: var(--bg-card); color: inherit; text-align: left; cursor: pointer; transition: border-color var(--motion-fast), transform var(--motion-fast), box-shadow var(--motion-fast); }
.fs-action:hover { border-color: var(--color-primary); box-shadow: var(--shadow-sm); transform: translateY(-1px); }
.fs-action__dot { width: 8px; height: 30px; border-radius: 999px; background: var(--color-primary); }
.fs-action__dot.is-green { background: var(--color-success, #15803d); }
.fs-action__dot.is-blue { background: #3478c9; }
.fs-action__dot.is-amber { background: var(--color-warning, #b45309); }
.fs-action__dot.is-violet { background: #7c5ce0; }
.fs-action__copy { min-width: 0; }
.fs-action__copy strong, .fs-action__copy small { display: block; }
.fs-action__copy strong { color: var(--text-primary); font-size: var(--font-size-sm); }
.fs-action__copy small { margin-top: 3px; color: var(--text-tertiary); font-size: 11px; }
.fs-action b { color: var(--text-primary); font-size: var(--font-size-sm); white-space: nowrap; }
.fs-action i { color: var(--text-tertiary); font-size: 20px; font-style: normal; }
.fs-grid { display: grid; gap: var(--space-3); margin-top: var(--space-3); }
.fs-grid--top { grid-template-columns: minmax(300px, .85fr) minmax(480px, 1.3fr); }
.fs-grid--bottom { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.fs-todos { display: grid; gap: 6px; }
.fs-todos button { display: flex; align-items: center; justify-content: space-between; gap: 12px; width: 100%; padding: 9px 11px; border: 1px solid var(--border-light); border-radius: var(--radius-md); background: var(--bg-subtle); color: inherit; text-align: left; cursor: pointer; }
.fs-todos button:hover { border-color: var(--color-primary); }
.fs-todos span strong, .fs-todos span small { display: block; }
.fs-todos span strong { color: var(--text-primary); font-size: var(--font-size-sm); }
.fs-todos span small { margin-top: 3px; color: var(--text-tertiary); font-size: 11px; }
.fs-todos b { min-width: 32px; color: var(--color-primary); font-size: 20px; text-align: right; }
.fs-todos b.is-danger { color: var(--color-danger, #c2410c); }
.fs-money { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 8px; }
.fs-money div { min-width: 0; padding: 9px 10px; border-radius: var(--radius-md); background: var(--bg-subtle); }
.fs-money span, .fs-money strong { display: block; }
.fs-money span { color: var(--text-tertiary); font-size: 11px; }
.fs-money strong { margin-top: 5px; overflow: hidden; color: var(--text-primary); font-size: var(--font-size-sm); text-overflow: ellipsis; white-space: nowrap; font-variant-numeric: tabular-nums; }
.fs-hidden { padding: 10px 12px; border: 1px dashed var(--border-base); border-radius: var(--radius-md); background: var(--bg-subtle); }
.fs-hidden strong { color: var(--text-primary); font-size: var(--font-size-sm); }
.fs-hidden p { margin: 5px 0 0; color: var(--text-secondary); font-size: var(--font-size-xs); line-height: 1.55; }
.fs-years-card { margin-top: var(--space-3); }
.fs-years { display: grid; }
.fs-years__head, .fs-years__row { display: grid; grid-template-columns: minmax(120px, 1fr) repeat(3, minmax(72px, .5fr)); align-items: center; min-height: 34px; padding: 0 8px; border-bottom: 1px solid var(--border-light); }
.fs-years__head { color: var(--text-tertiary); font-size: 11px; font-weight: 650; }
.fs-years__row { color: var(--text-secondary); font-size: var(--font-size-xs); }
.fs-years__row strong { color: var(--text-primary); }
.fs-years__row em { color: var(--color-primary); font-style: normal; font-weight: 650; }
.fs-definition { margin: var(--space-3) 0 0; color: var(--text-tertiary); font-size: 11px; line-height: 1.55; }
.fs-drill-list { min-width: 560px; border: 1px solid var(--border-base); border-radius: var(--radius-md); overflow: hidden; }
.fs-drill-head, .fs-drill-row { display: grid; grid-template-columns: minmax(180px, 1fr) 100px minmax(220px, 1.2fr); align-items: center; gap: 12px; min-height: 48px; padding: 7px 14px; border-bottom: 1px solid var(--border-light); }
.fs-drill-head { min-height: 38px; background: var(--bg-subtle); color: var(--text-tertiary); font-size: var(--font-size-xs); font-weight: 650; }
.fs-drill-row:last-child { border-bottom: 0; }
.fs-drill-row > span { color: var(--text-secondary); font-size: var(--font-size-sm); }
.fs-drill-row > span:first-child strong, .fs-drill-row > span:first-child small { display: block; }
.fs-drill-row > span:first-child strong { color: var(--text-primary); }
.fs-drill-row > span:first-child small { margin-top: 3px; color: var(--text-tertiary); font-size: 11px; }
.fs-sources { display: flex; flex-wrap: wrap; gap: 5px; }
.fs-sources em { padding: 3px 7px; border-radius: 999px; background: color-mix(in srgb, var(--color-primary) 10%, var(--bg-card)); color: var(--color-primary); font-size: 11px; font-style: normal; }
.fs-empty { padding: 48px 16px; color: var(--text-tertiary); text-align: center; }
@media (max-width: 1180px) {
  .fs-overview { grid-template-columns: minmax(260px, 1.4fr) repeat(3, minmax(145px, .8fr)); }
  .fs-money { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
@media (max-width: 960px) {
  .fs-overview { grid-template-columns: 1fr 1fr; }
  .fs-overview__lead { grid-column: 1 / -1; }
  .fs-overview__metric { border-top: 1px solid var(--border-light); }
  .fs-actions, .fs-grid--bottom { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .fs-grid--top { grid-template-columns: 1fr; }
}
@media (max-width: 640px) {
  .fs-overview, .fs-actions, .fs-grid--bottom, .fs-money { grid-template-columns: 1fr; }
  .fs-overview__lead { grid-column: auto; }
  .fs-overview__metric { border-left: 0; border-top: 1px solid var(--border-light); }
}
</style>
