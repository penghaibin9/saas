<template>
  <ModulePageShell
    title="成果检查"
    :subtitle="pageSubtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppExportButton
        v-if="exportPerm.visible"
        :export-fn="exportFinalsFn"
        :has-permission="exportPerm.allowed"
      >导出成果清单</AppExportButton>
    </template>

    <div class="mp-stack">
      <GraduationBatchStrip />

      <div class="mp-tabs">
        <button v-for="t in tabs" :key="t.value" class="mp-tab" :class="{ 'is-active': filters.status === t.value }" @click="switchTab(t.value)">
          {{ t.label }}<span v-if="tabCount(t.value) !== null" class="fr-tab-count">{{ tabCount(t.value) }}</span>
        </button>
      </div>

      <AdvancedFilter v-model="filters" :fields="filterFields" @search="onFilterSearch" @reset="onFilterReset" />

      <!-- 连续批阅双栏：左队列 + 右批阅面板；窄屏降级为「列表 ⇄ 整屏详情」切换 -->
      <div class="fr-split" :class="{ 'is-narrow': isNarrow }">
        <aside v-if="!isNarrow || !selectedRow" class="fr-list">
          <AppSearchBox v-model="filters.keyword" placeholder="搜索学生 / 学号 / 课题" @search="onFilterSearch" />
          <ErrorState v-if="error" :description="error" @retry="load" />
          <LoadingState v-else-if="loading" />
          <EmptyState v-else-if="!rows.length" title="当前页签暂无成果提交" description="可切换页签或调整筛选" />
          <ul v-else class="fr-rows">
            <li
              v-for="(row, i) in rows"
              :key="rowKey(row)"
              class="fr-row"
              :class="{ 'is-active': rowKey(row) === selKey }"
              tabindex="0"
              role="button"
              @click="select(row)"
              @keydown.enter.prevent="select(row)"
              @keydown.space.prevent="select(row)"
            >
              <div class="fr-row__main">
                <span class="fr-row__name">{{ row.studentName }}</span>
                <span class="fr-row__cls">{{ row.className }}</span>
                <StatusTag :status="row.status === 'NOT_SUBMITTED' ? 'PENDING_SUBMIT' : row.status" :label="row.statusLabel" dot />
              </div>
              <div class="fr-row__sub" :title="row.topicTitle">{{ row.topicTitle }}</div>
              <div class="fr-row__meta">
                <span>{{ row.type || '—' }} {{ row.version || '' }}</span>
                <span v-if="row.plagiarismRate" :class="{ 'fr-over': row.plagiarismTone === 'danger' }">查重 {{ row.plagiarismRate }}</span>
                <span class="fr-row__idx">{{ pageStartIndex + i + 1 }}</span>
              </div>
            </li>
          </ul>
          <div class="fr-list__foot">
            <AppPagination :total="total" :page="page" :page-size="pageSize" :show-size-changer="false" @update:page="turnPage" />
          </div>
        </aside>

        <section v-if="!isNarrow || selectedRow" class="fr-pane">
          <div class="fr-pane__bar">
            <button v-if="isNarrow" class="mp-link" @click="clearSelection">← 返回列表</button>
            <span class="fr-pane__pos">本页第 {{ selIndex + 1 }} / {{ rows.length }} 条 · 共 {{ total }} 条</span>
            <label class="fr-pane__auto"><input v-model="autoNext" type="checkbox" /> 处理后自动进入下一条待审</label>
            <span class="fr-pane__nav">
              <button class="mp-link" :disabled="selIndex <= 0" @click="step(-1)">← 上一条</button>
              <button class="mp-link" :disabled="!hasNext" @click="step(1)">下一条 →</button>
            </span>
          </div>

          <EmptyState v-if="!selectedRow" title="从左侧选择一条成果记录" description="↑↓ 方向键可快速切换，处理后自动进入下一条待审" />
          <div v-else class="mp-stack">
            <section class="mp-card">
              <div class="mp-card__head">
                <span class="mp-card__title">{{ selectedRow.type || '成果' }} {{ selectedRow.version || '' }}</span>
                <button class="mp-link" @click="openDossier(selectedRow)">查看学生完整档案 →</button>
              </div>
              <div class="mp-card__body">
                <div class="mp-kv"><span class="mp-kv__k">学生</span><span class="mp-kv__v">{{ selectedRow.studentName }} · {{ selectedRow.className }}</span></div>
                <div class="mp-kv"><span class="mp-kv__k">课题</span><span class="mp-kv__v">{{ selectedRow.topicTitle }}</span></div>
                <div class="mp-kv"><span class="mp-kv__k">指导教师</span><span class="mp-kv__v">{{ selectedRow.advisorName || '—' }}</span></div>
                <div class="mp-kv"><span class="mp-kv__k">提交时间</span>
                  <span class="mp-kv__v"><AppDateDisplay :value="selectedRow.submitAt" mode="datetime" empty-text="未提交" /></span>
                </div>
                <div class="mp-kv"><span class="mp-kv__k">当前状态</span>
                  <span class="mp-kv__v"><StatusTag :status="selectedRow.status === 'NOT_SUBMITTED' ? 'PENDING_SUBMIT' : selectedRow.status" :label="selectedRow.statusLabel" dot /></span>
                </div>
                <div class="mp-kv"><span class="mp-kv__k">查重</span>
                  <span class="mp-kv__v">
                    <StatusTag v-if="selectedRow.plagiarismRate" :type="selectedRow.plagiarismTone === 'danger' ? 'danger' : 'success'" :label="selectedRow.plagiarismRate + ' · ' + selectedRow.plagiarismStatus" />
                    <span v-else>{{ selectedRow.plagiarismStatus || '未检测' }}</span>
                  </span>
                </div>
                <p v-if="selectedRow.plagiarismTone === 'danger'" class="mp-note" style="color: var(--danger, #dc2626); margin-top: var(--space-2)">
                  查重率超标（&gt;30%），系统将拦截「通过」，须退回修改后由学生重交。
                </p>
              </div>
            </section>

            <!-- 未提交：催交 -->
            <section v-if="selectedRow.status === 'NOT_SUBMITTED'" class="mp-card">
              <div class="mp-card__head"><span class="mp-card__title">尚未提交成果</span></div>
              <div class="mp-card__body">
                <AppButton variant="primary" :loading="reminding" @click="remind(selectedRow)">发送成果催交提醒</AppButton>
                <p class="mp-note" style="margin-top: var(--space-2)">催办通过站内消息送达学生端并留痕；学生提交后将出现在「待审阅」页签。</p>
              </div>
            </section>

            <!-- 待审阅：批阅表单 -->
            <section v-else-if="selectedRow.status === 'PENDING_REVIEW'" class="mp-card">
              <div class="mp-card__head"><span class="mp-card__title">批阅</span></div>
              <div class="mp-card__body">
                <div v-if="!canReview" class="mp-note" style="margin-bottom: var(--space-2); color: var(--warning-600)">
                  {{ reviewReason }}（以下操作已置灰，仅指导教师可批阅）
                </div>
                <label class="mp-note" style="display: block; margin-bottom: var(--space-1)">批阅意见（退回时必填，≥5 字）</label>
                <textarea v-model="comment" class="mp-textarea" :disabled="!canReview" rows="3" placeholder="批阅意见将同步学生端…"></textarea>
                <AppTemplateChips v-if="canReview" :options="REJECT_REASON_CHIPS" @pick="(t) => (comment = comment ? comment + '\n' + t : t)" />
                <p v-if="formError" class="mp-form-err">{{ formError }}</p>
                <div style="display: flex; gap: var(--space-2); margin-top: var(--space-3)">
                  <AppPermissionButton :allowed="canReview" :reason="reviewReason" variant="primary" :loading="submitting" style="flex: 1" @click="submitReview('APPROVE')">✓ 通过</AppPermissionButton>
                  <AppPermissionButton :allowed="canReview" :reason="reviewReason" variant="warning" :loading="submitting" style="flex: 1" @click="submitReview('REJECT')">↩ 退回修改</AppPermissionButton>
                </div>
                <p class="mp-note" style="text-align: center; margin-top: var(--space-2)">批阅写入审批留痕；成果文件与查重报告在学生档案「成果 / 查重」页签查看</p>
              </div>
            </section>

            <!-- 已批阅：结果 -->
            <section v-else class="mp-card">
              <div class="mp-card__head"><span class="mp-card__title">批阅结果</span></div>
              <div class="mp-card__body">
                <div class="mp-kv"><span class="mp-kv__k">结果</span><span class="mp-kv__v">{{ selectedRow.statusLabel }}</span></div>
                <p class="mp-note" style="margin-top: var(--space-2)">
                  批阅意见与留痕在学生档案中查看；已退回的成果待学生重交后将出现新的待审记录。
                </p>
              </div>
            </section>
          </div>
        </section>
      </div>

      <p class="mp-note">初稿 / 定稿顺序、查重超标拦截均由后端真实状态机校验；筛选默认「全部时间」。</p>
    </div>
    <!-- 首次进入本模块时的 4 步说明；「已看过」存后端偏好，顶栏「?」可重看 -->
    <AppPageGuide guide-key="graduation.gd-final-review" />
  </ModulePageShell>
</template>

<script>
/**
 * 成果检查 · 连续双栏批阅工作区（/admin/graduation/finals）。
 * 左：成果队列（搜索/页签计数/分页）；右：行摘要 + 查重摘要 + 真实批阅（通过/退回≥5字）/催交。
 * 查重超标（>30%）由后端拦截「通过」（GD 业务规则），前端仅提示不伪造结果。
 * 连续处理：处理后自动进入下一条待审；↑↓ 键切换；?sel= 刷新保留；窄屏为「列表 ⇄ 整屏详情」切换。
 */
import { ModulePageShell, AdvancedFilter, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppExportButton, AppSearchBox, AppPagination, AppPermissionButton, AppTemplateChips, AppPageGuide } from '@/components/common'
import { AppDateDisplay } from '@/components/common/date'
import { graduationApi } from '@/modules/graduation/api/graduation.api'
import { graduationMoreApi } from '@/modules/graduation/api/graduation-more.api'
import { toast } from '@/utils/toast'
import GraduationBatchStrip from './_shared/GraduationBatchStrip.vue'

const REJECT_REASON_CHIPS = ['材料不完整，请补充', '内容质量不达标，需修改', '格式不符合学校规范', '与选题方向不符']

export default {
  name: 'FinalSubmissionListView',
  components: { AppPageGuide,
    ModulePageShell, AdvancedFilter, StatusTag, LoadingState, ErrorState, EmptyState,
    AppButton, AppExportButton, AppSearchBox, AppPagination, AppPermissionButton, AppDateDisplay,
    GraduationBatchStrip, AppTemplateChips
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      REJECT_REASON_CHIPS,
      loading: true,
      error: '',
      rows: [],
      total: 0,
      page: 1,
      pageSize: 20,
      filters: { status: 'PENDING_REVIEW', keyword: '', dateStart: '', dateEnd: '' },
      selKey: '',
      autoNext: true,
      comment: '',
      formError: '',
      submitting: false,
      reminding: false,
      stats: null,
      isNarrow: false,
      tabs: [
        { value: 'PENDING_REVIEW', label: '待审阅' },
        { value: 'APPROVED', label: '已通过' },
        { value: 'REJECTED', label: '已退回修改' },
        { value: 'NOT_SUBMITTED', label: '未提交' },
        { value: '', label: '全部' }
      ]
    }
  },
  computed: {
    pageSubtitle() {
      const s = this.stats
      if (!s) return '初稿 / 定稿连续批阅 · 查重超标不可直接通过，须退回修改'
      return `待审阅 ${this.statusCount('PENDING_REVIEW')} · 查重超标 ${s.plagiarismOver ?? 0} · 连续批阅不返回列表`
    },
    exportPerm() {
      const pa = this.ctx.permissionActions.exportStats || {}
      return { visible: !!pa.visible, allowed: !!pa.allowed }
    },
    canReview() {
      const pa = this.ctx.permissionActions.reviewFinal
      return !!(pa && pa.visible && pa.allowed)
    },
    reviewReason() {
      const pa = this.ctx.permissionActions.reviewFinal
      return pa && !pa.allowed ? pa.reason : ''
    },
    filterFields() {
      return [{
        key: 'date', label: '提交时间', type: 'daterange',
        startKey: 'dateStart', endKey: 'dateEnd',
        memoryKey: 'graduation.finals.dateRange', emptyLabel: '全部时间'
      }]
    },
    pageStartIndex() { return (this.page - 1) * this.pageSize },
    selectedRow() { return this.rows.find((r) => this.rowKey(r) === this.selKey) || null },
    selIndex() { return this.rows.findIndex((r) => this.rowKey(r) === this.selKey) },
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
      if (!this.stats || v === '') return null
      if (v === 'NOT_SUBMITTED') return null
      return this.statusCount(v)
    },
    async loadStats() {
      const res = await graduationMoreApi.getFinalStats()
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
      this.selKey = this.rowKey(row)
      this.comment = ''
      this.formError = ''
      this.$router.replace({ query: { ...this.$route.query, sel: this.selKey } })
    },
    clearSelection() {
      this.selKey = ''
      const q = { ...this.$route.query }
      delete q.sel
      this.$router.replace({ query: q })
    },
    step(delta) {
      const i = this.selIndex
      const target = i + delta
      if (target >= 0 && target < this.rows.length) { this.select(this.rows[target]); return }
      if (delta > 0 && this.page * this.pageSize < this.total) {
        this.turnPage(this.page + 1)
      } else if (delta < 0 && this.page > 1) {
        this._selectLastAfterLoad = true
        this.turnPage(this.page - 1)
      }
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
        toast.success('本页待审成果已全部处理完')
      }
    },
    ensureSelection() {
      if (this.selectedRow) return
      if (!this.rows.length) { this.selKey = ''; return }
      let target = null
      if (this._selectLastAfterLoad) target = this.rows[this.rows.length - 1]
      else target = this.rows.find((r) => r.status === 'PENDING_REVIEW') || this.rows[0]
      this._selectLastAfterLoad = false
      this._selectPendingAfterLoad = false
      if (target && !this.isNarrow) this.select(target)
    },
    openDossier(row) {
      if (row.projectId) this.$router.push('/admin/graduation/students/' + row.projectId)
    },
    exportFinalsFn() {
      return graduationApi.exportFinals(this.filters.status)
    },
    async submitReview(action) {
      if (!this.canReview || !this.selectedRow) return
      this.formError = ''
      if (action === 'REJECT' && (!this.comment || this.comment.trim().length < 5)) {
        this.formError = '退回原因必填且不少于 5 个字'
        return
      }
      this.submitting = true
      const res = await graduationApi.reviewFinal(this.selectedRow.id, { action, comment: this.comment })
      this.submitting = false
      if (res.code === 0) {
        toast.success('批阅完成：' + res.data.statusLabel + '，已留痕并同步学生端')
        const row = this.selectedRow
        row.status = res.data.status
        row.statusLabel = res.data.statusLabel
        this.comment = ''
        this.loadStats()
        if (this.autoNext) this.nextPending()
      } else if (res.message && res.message.includes('已批阅')) {
        // 并发冲突：他人已处理，刷新队列
        this.formError = res.message
        this.loadStats()
        this.load()
      } else {
        this.formError = res.message
      }
    },
    async remind(row) {
      this.reminding = true
      const res = await graduationApi.remindFinal(row.projectId || row.gdStudentId)
      this.reminding = false
      if (res.code === 0) toast.success('已向 ' + row.studentName + ' 发送成果催交提醒，催办已留痕')
      else toast.error(res.message || '催交失败')
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await graduationApi.getFinalSubmissions({ ...this.filters, page: this.page, pageSize: this.pageSize })
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
.fr-tab-count { margin-left: 4px; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.mp-tab.is-active .fr-tab-count { color: inherit; }
.fr-tabs-side { margin-left: auto; }
.mp-tabs { display: flex; align-items: center; flex-wrap: wrap; gap: var(--space-1); }

.fr-split { display: flex; gap: var(--space-4); align-items: flex-start; }
.fr-list { width: 340px; flex: none; display: flex; flex-direction: column; gap: var(--space-2); padding: var(--space-3); border: 1px solid var(--border-light, #e2e8f0); border-radius: var(--radius-md, 8px); background: var(--card, #fff); box-shadow: 0 1px 2px rgba(15, 23, 42, .03); }
.fr-split.is-narrow .fr-list { width: 100%; }
.fr-pane { flex: 1; min-width: 0; padding: var(--space-4); border: 1px solid var(--border-light, #e2e8f0); border-radius: var(--radius-md, 8px); background: var(--card, #fff); box-shadow: 0 1px 2px rgba(15, 23, 42, .03); }
.fr-split.is-narrow .fr-pane { width: 100%; }

.fr-rows { list-style: none; margin: 0; padding: 0; max-height: 640px; overflow-y: auto; border: 1px solid var(--border-light, #e2e8f0); border-radius: var(--radius-md, 8px); }
.fr-row { padding: 10px 12px; border-bottom: 1px solid var(--border-light, #eef1f6); cursor: pointer; transition: background .12s ease, box-shadow .12s ease; }
.fr-row:last-child { border-bottom: none; }
.fr-row:hover { background: var(--gray-50, #f8fafc); }
.fr-row.is-active { background: var(--primary-50, #eff6ff); box-shadow: inset 2px 0 0 var(--brand-primary, #2563eb); }
.fr-row:focus-visible { position: relative; z-index: 1; outline: 2px solid var(--primary-400, #60a5fa); outline-offset: -2px; }
.fr-row__main { display: flex; align-items: center; gap: var(--space-2); }
.fr-row__name { font-weight: var(--font-weight-medium, 500); color: var(--text-primary); }
.fr-row__cls { font-size: var(--font-size-xs); color: var(--text-tertiary); flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.fr-row__sub { margin-top: 2px; font-size: var(--font-size-sm); color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.fr-row__meta { margin-top: 2px; display: flex; gap: var(--space-2); font-size: var(--font-size-xs); color: var(--text-tertiary); }
.fr-row__idx { margin-left: auto; }
.fr-over { color: var(--danger, #dc2626); }
.fr-list__foot { display: flex; justify-content: center; }

.fr-pane__bar {
  display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap;
  padding: var(--space-2) var(--space-3); margin-bottom: var(--space-3);
  background: var(--gray-50, #f8fafc); border: 1px solid var(--border-light, #e2e8f0); border-radius: var(--radius-md, 8px);
  font-size: var(--font-size-sm);
}
.fr-pane__pos { color: var(--text-secondary); }
.fr-pane__auto { color: var(--text-secondary); display: inline-flex; align-items: center; gap: 4px; cursor: pointer; }
.fr-pane__nav { margin-left: auto; display: inline-flex; gap: var(--space-3); }
.fr-pane__nav .mp-link:disabled { opacity: 0.4; cursor: not-allowed; }
@media (max-width: 1100px) {
  .fr-pane { padding: var(--space-3); }
}
</style>
