<template>
  <ModulePageShell
    title="开题审核"
    :subtitle="pageSubtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppExportButton
        v-if="exportPerm.visible"
        :export-fn="exportProposalsFn"
        :has-permission="exportPerm.allowed"
      >导出开题材料</AppExportButton>
    </template>

    <div class="mp-stack">
      <GraduationBatchStrip />

      <div class="mp-tabs">
        <button v-for="t in tabs" :key="t.value" class="mp-tab" :class="{ 'is-active': filters.status === t.value }" @click="switchTab(t.value)">
          {{ t.label }}<span v-if="tabCount(t.value) !== null" class="pr-tab-count">{{ tabCount(t.value) }}</span>
        </button>
      </div>

      <AdvancedFilter v-model="filters" :fields="filterFields" @search="onFilterSearch" @reset="onFilterReset" />

      <!-- 连续批阅双栏：左队列 + 右批阅卡；窄屏自动降级为整页列表（点击进独立详情页） -->
      <div class="pr-split" :class="{ 'is-narrow': isNarrow }">
        <aside class="pr-list">
          <AppSearchBox v-model="filters.keyword" placeholder="搜索学生 / 学号 / 课题" @search="onFilterSearch" />
          <ErrorState v-if="error" :description="error" @retry="load" />
          <LoadingState v-else-if="loading" />
          <EmptyState v-else-if="!rows.length" title="当前页签暂无开题材料" description="可切换页签或调整筛选" />
          <ul v-else class="pr-rows">
            <li
              v-for="(row, i) in rows"
              :key="rowKey(row)"
              class="pr-row"
              :class="{ 'is-active': rowKey(row) === selKey }"
              @click="select(row)"
            >
              <div class="pr-row__main">
                <span class="pr-row__name">{{ row.studentName }}</span>
                <span class="pr-row__cls">{{ row.className }}</span>
                <StatusTag :status="row.status === 'NOT_SUBMITTED' ? 'OVERDUE' : row.status" :label="row.statusLabel" dot />
              </div>
              <div class="pr-row__sub" :title="row.topicTitle">{{ row.topicTitle }}</div>
              <div class="pr-row__meta">
                <span>{{ row.version || '—' }}<template v-if="row.isResubmit"> · 重交</template></span>
                <AppDateDisplay v-if="row.submitAt" :value="row.submitAt" mode="date" />
                <span v-else>未提交</span>
                <span class="pr-row__idx">{{ pageStartIndex + i + 1 }}</span>
              </div>
            </li>
          </ul>
          <div class="pr-list__foot">
            <AppPagination :total="total" :page="page" :page-size="pageSize" :show-size-changer="false" @update:page="turnPage" />
          </div>
        </aside>

        <section v-if="!isNarrow" class="pr-pane">
          <div class="pr-pane__bar">
            <span class="pr-pane__pos">本页第 {{ selIndex + 1 }} / {{ rows.length }} 条 · 共 {{ total }} 条</span>
            <label class="pr-pane__auto"><input v-model="autoNext" type="checkbox" /> 批阅后自动进入下一条待审</label>
            <span class="pr-pane__nav">
              <button class="mp-link" :disabled="selIndex <= 0" @click="step(-1)">← 上一条</button>
              <button class="mp-link" :disabled="!hasNext" @click="step(1)">下一条 →</button>
            </span>
          </div>

          <template v-if="!selectedRow">
            <EmptyState title="从左侧选择一条开题记录" description="↑↓ 方向键可快速切换，处理后自动进入下一条待审" />
          </template>
          <template v-else-if="selectedRow.status === 'NOT_SUBMITTED'">
            <section class="mp-card">
              <div class="mp-card__head"><span class="mp-card__title">尚未提交开题报告</span></div>
              <div class="mp-card__body">
                <div class="mp-kv"><span class="mp-kv__k">学生</span><span class="mp-kv__v">{{ selectedRow.studentName }} · {{ selectedRow.className }}</span></div>
                <div class="mp-kv"><span class="mp-kv__k">课题</span><span class="mp-kv__v">{{ selectedRow.topicTitle }}</span></div>
                <div class="mp-kv"><span class="mp-kv__k">指导教师</span><span class="mp-kv__v">{{ selectedRow.advisorName || '—' }}</span></div>
                <div style="margin-top: var(--space-3)">
                  <AppButton variant="primary" :loading="reminding" @click="remind(selectedRow)">发送开题催交提醒</AppButton>
                </div>
                <p class="mp-note" style="margin-top: var(--space-2)">催办通过站内消息送达学生端并留痕；学生提交后将出现在「待审阅」页签。</p>
              </div>
            </section>
          </template>
          <ProposalReviewCard
            v-else
            :ctx="ctx"
            :proposal-id="selectedRow.id"
            compact
            @reviewed="onReviewed"
            @conflict="onConflict"
          />
        </section>
      </div>

      <p class="mp-note">筛选默认「全部时间」，空日期不会导致查无数据；窄屏下点击列表将进入整页批阅详情。</p>
    </div>
  </ModulePageShell>
</template>

<script>
/**
 * 开题审核 · 连续双栏批阅工作区（/admin/graduation/proposals）。
 * 左：待审队列（搜索/页签/分页/当前选中）；右：ProposalReviewCard 真实批阅（通过/驳回≥5字/开题答辩/留痕）。
 * 连续处理：批阅成功后可自动进入下一条待审；↑↓ 键切换；选中项写入 ?sel= 刷新不丢。
 * 窄屏（<1100px）降级：隐藏右栏，点击行进入独立批阅详情页（不用窄抽屉）。
 */
import { ModulePageShell, AdvancedFilter, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppExportButton, AppSearchBox, AppPagination } from '@/components/common'
import { AppDateDisplay } from '@/components/common/date'
import { graduationApi } from '@/modules/graduation/api/graduation.api'
import { graduationMoreApi } from '@/modules/graduation/api/graduation-more.api'
import { toast } from '@/utils/toast'
import GraduationBatchStrip from './_shared/GraduationBatchStrip.vue'
import ProposalReviewCard from './_shared/ProposalReviewCard.vue'

export default {
  name: 'ProposalListView',
  components: {
    ModulePageShell, AdvancedFilter, StatusTag, LoadingState, ErrorState, EmptyState,
    AppButton, AppExportButton, AppSearchBox, AppPagination, AppDateDisplay,
    GraduationBatchStrip, ProposalReviewCard
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      total: 0,
      page: 1,
      pageSize: 20,
      filters: { status: 'PENDING_REVIEW', keyword: '', dateStart: '', dateEnd: '' },
      selKey: '',
      autoNext: true,
      reminding: false,
      stats: null,
      isNarrow: false,
      tabs: [
        { value: 'PENDING_REVIEW', label: '待审阅' },
        { value: 'APPROVED', label: '已通过' },
        { value: 'REJECTED', label: '已驳回' },
        { value: 'NOT_SUBMITTED', label: '逾期未交' },
        { value: '', label: '全部' }
      ]
    }
  },
  computed: {
    pageSubtitle() {
      const p = this.stats
      if (!p) return '学生提交开题材料，教师连续批阅 · 驳回需填写原因并即时同步学生端'
      return `待审阅 ${this.statusCount('PENDING_REVIEW')} · 逾期未交 ${p.notSubmitted ?? 0} · 连续批阅不返回列表`
    },
    exportPerm() {
      const pa = this.ctx.permissionActions.exportProposals || {}
      return { visible: !!pa.visible, allowed: !!pa.allowed }
    },
    filterFields() {
      return [{
        key: 'date', label: '提交时间', type: 'daterange',
        startKey: 'dateStart', endKey: 'dateEnd',
        memoryKey: 'graduation.proposals.dateRange', emptyLabel: '全部时间'
      }]
    },
    pageStartIndex() {
      return (this.page - 1) * this.pageSize
    },
    selectedRow() {
      return this.rows.find((r) => this.rowKey(r) === this.selKey) || null
    },
    selIndex() {
      return this.rows.findIndex((r) => this.rowKey(r) === this.selKey)
    },
    hasNext() {
      if (this.selIndex < this.rows.length - 1) return true
      return this.page * this.pageSize < this.total
    }
  },
  created() {
    const qTab = (this.$route.query.tab || '').toString()
    if (this.tabs.some((x) => x.value === qTab)) this.filters.status = qTab
    this.selKey = (this.$route.query.sel || '').toString()
    this.loadStats()
    this.load()
  },
  mounted() {
    this._mq = window.matchMedia('(max-width: 1100px)')
    this.isNarrow = this._mq.matches
    this._onMq = (e) => { this.isNarrow = e.matches }
    this._mq.addEventListener ? this._mq.addEventListener('change', this._onMq) : this._mq.addListener(this._onMq)
    this._onKey = (e) => {
      if (this.isNarrow) return
      const tag = (e.target && e.target.tagName) || ''
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
      if (e.key === 'ArrowDown') { e.preventDefault(); this.step(1) }
      if (e.key === 'ArrowUp') { e.preventDefault(); this.step(-1) }
    }
    window.addEventListener('keydown', this._onKey)
  },
  beforeUnmount() {
    if (this._mq) { this._mq.removeEventListener ? this._mq.removeEventListener('change', this._onMq) : this._mq.removeListener(this._onMq) }
    window.removeEventListener('keydown', this._onKey)
  },
  methods: {
    rowKey(row) {
      return row.id != null ? String(row.id) : 'ns-' + row.gdStudentId
    },
    statusCount(status) {
      const s = (this.stats?.byStatus || []).find((x) => x.status === status)
      return s ? s.count : 0
    },
    tabCount(v) {
      if (!this.stats) return null
      if (v === '') return null
      if (v === 'NOT_SUBMITTED') return this.stats.notSubmitted ?? 0
      return this.statusCount(v)
    },
    async loadStats() {
      const res = await graduationMoreApi.getProposalStats()
      if (res.code === 0) this.stats = res.data
    },
    switchTab(v) {
      this.filters.status = v
      this.page = 1
      this.selKey = ''
      const q = { ...this.$route.query, tab: v || undefined }
      delete q.sel
      this.$router.replace({ query: q })
      this.load()
    },
    onFilterSearch() { this.page = 1; this.load() },
    onFilterReset() {
      this.filters = { ...this.filters, keyword: '', dateStart: '', dateEnd: '' }
      this.page = 1
      this.load()
    },
    turnPage(p) { this.page = p; this.load() },
    select(row) {
      if (this.isNarrow) {
        if (row.status !== 'NOT_SUBMITTED' && row.id != null) this.$router.push('/admin/graduation/proposals/' + row.id)
        return
      }
      this.selKey = this.rowKey(row)
      this.$router.replace({ query: { ...this.$route.query, sel: this.selKey } })
    },
    step(delta) {
      const i = this.selIndex
      const target = i + delta
      if (target >= 0 && target < this.rows.length) {
        this.select(this.rows[target])
        return
      }
      if (delta > 0 && this.page * this.pageSize < this.total) {
        this._selectFirstAfterLoad = true
        this.turnPage(this.page + 1)
      } else if (delta < 0 && this.page > 1) {
        this._selectLastAfterLoad = true
        this.turnPage(this.page - 1)
      }
    },
    /** 批阅成功：更新行状态 + 刷新计数 + 自动进入下一条待审 */
    onReviewed(payload) {
      const row = this.rows.find((r) => String(r.id) === String(payload.id))
      if (row) { row.status = payload.status; row.statusLabel = payload.statusLabel }
      this.loadStats()
      if (this.autoNext) this.nextPending()
    },
    onConflict() {
      // 并发冲突：他人已批阅，刷新本页与计数
      this.loadStats()
      this.load()
    },
    nextPending() {
      const from = this.selIndex
      for (let i = from + 1; i < this.rows.length; i++) {
        if (this.rows[i].status === 'PENDING_REVIEW') { this.select(this.rows[i]); return }
      }
      for (let i = 0; i < from; i++) {
        if (this.rows[i].status === 'PENDING_REVIEW') { this.select(this.rows[i]); return }
      }
      if (this.page * this.pageSize < this.total) {
        this._selectPendingAfterLoad = true
        this.turnPage(this.page + 1)
      } else {
        toast.success('本页待审记录已全部处理完')
      }
    },
    ensureSelection() {
      if (this.selectedRow) return
      if (!this.rows.length) { this.selKey = ''; return }
      let target = null
      if (this._selectLastAfterLoad) target = this.rows[this.rows.length - 1]
      else if (this._selectPendingAfterLoad) target = this.rows.find((r) => r.status === 'PENDING_REVIEW') || this.rows[0]
      else target = this.rows.find((r) => r.status === 'PENDING_REVIEW') || this.rows[0]
      this._selectFirstAfterLoad = false
      this._selectLastAfterLoad = false
      this._selectPendingAfterLoad = false
      if (target && !this.isNarrow) this.select(target)
    },
    exportProposalsFn() {
      return graduationApi.exportProposals(this.filters.status)
    },
    async remind(row) {
      this.reminding = true
      const res = await graduationApi.remindProposal(row.projectId || row.gdStudentId)
      this.reminding = false
      if (res.code === 0) toast.success('已向 ' + row.studentName + ' 发送开题催交提醒，催办已留痕')
      else toast.error(res.message || '催交失败')
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await graduationApi.getProposals({ ...this.filters, page: this.page, pageSize: this.pageSize })
      if (res.code === 0) {
        this.rows = res.data.list
        this.total = res.data.total
        this.ensureSelection()
      } else {
        this.error = res.message
      }
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.pr-tab-count {
  margin-left: 4px;
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.mp-tab.is-active .pr-tab-count { color: inherit; }
.pr-tabs-side { margin-left: auto; }
.mp-tabs { display: flex; align-items: center; flex-wrap: wrap; gap: var(--space-1); }

.pr-split { display: flex; gap: var(--space-4); align-items: flex-start; }
.pr-list { width: 340px; flex: none; display: flex; flex-direction: column; gap: var(--space-2); }
.pr-split.is-narrow .pr-list { width: 100%; }
.pr-pane { flex: 1; min-width: 0; }

.pr-rows { list-style: none; margin: 0; padding: 0; max-height: 640px; overflow-y: auto; border: 1px solid var(--border-light, #e2e8f0); border-radius: var(--radius-md, 8px); }
.pr-row { padding: 10px 12px; border-bottom: 1px solid var(--border-light, #eef1f6); cursor: pointer; }
.pr-row:last-child { border-bottom: none; }
.pr-row:hover { background: var(--gray-50, #f8fafc); }
.pr-row.is-active { background: var(--primary-50, #eff6ff); box-shadow: inset 2px 0 0 var(--brand-primary, #2563eb); }
.pr-row__main { display: flex; align-items: center; gap: var(--space-2); }
.pr-row__name { font-weight: var(--font-weight-medium, 500); color: var(--text-primary); }
.pr-row__cls { font-size: var(--font-size-xs); color: var(--text-tertiary); flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pr-row__sub { margin-top: 2px; font-size: var(--font-size-sm); color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pr-row__meta { margin-top: 2px; display: flex; gap: var(--space-2); font-size: var(--font-size-xs); color: var(--text-tertiary); }
.pr-row__idx { margin-left: auto; }
.pr-list__foot { display: flex; justify-content: center; }

.pr-pane__bar {
  display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap;
  padding: var(--space-2) var(--space-3); margin-bottom: var(--space-3);
  background: var(--gray-50, #f8fafc); border: 1px solid var(--border-light, #e2e8f0); border-radius: var(--radius-md, 8px);
  font-size: var(--font-size-sm);
}
.pr-pane__pos { color: var(--text-secondary); }
.pr-pane__auto { color: var(--text-secondary); display: inline-flex; align-items: center; gap: 4px; cursor: pointer; }
.pr-pane__nav { margin-left: auto; display: inline-flex; gap: var(--space-3); }
.pr-pane__nav .mp-link:disabled { opacity: 0.4; cursor: not-allowed; }
</style>
