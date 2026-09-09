<template>
  <ModulePageShell
    title="开题报告批阅"
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

    <div class="mp-stack pr-page">
      <section v-if="hasBatch" class="pr-hero" aria-label="开题批阅结论">
        <div class="pr-hero__copy">
          <span class="pr-hero__eyebrow">当前工作队列</span>
          <strong>{{ queueConclusion }}</strong>
          <p>左侧选人，右侧核验当前版本并提交结论；提交期间系统会锁定当前对象，避免意见写错学生。</p>
        </div>
        <div class="pr-hero__metrics" aria-label="开题关键数量">
          <div><span>{{ pendingCount }}</span><small>待审阅</small></div>
          <div><span>{{ notSubmittedCount }}</span><small>逾期未交</small></div>
          <div><span>{{ total }}</span><small>当前队列</small></div>
        </div>
      </section>

      <div class="mp-tabs" aria-label="开题状态筛选">
        <button
          v-for="t in tabs"
          :key="t.value"
          class="mp-tab"
          :class="{ 'is-active': filters.status === t.value }"
          :disabled="reviewSubmitting"
          @click="switchTab(t.value)"
        >
          {{ t.label }}<span v-if="tabCount(t.value) !== null" class="pr-tab-count">{{ tabCount(t.value) }}</span>
        </button>
      </div>

      <AdvancedFilter
        v-if="hasBatch && filterFields.length"
        v-model="filters"
        :fields="filterFields"
        @search="onFilterSearch"
        @reset="onFilterReset"
      />

      <!-- 连续批阅双栏：左队列 + 右批阅卡；窄屏自动降级为整页详情。 -->
      <div class="pr-split" :class="{ 'is-narrow': isNarrow }" :aria-busy="reviewSubmitting">
        <aside class="pr-list" aria-label="开题批阅队列">
          <div class="pr-list__head">
            <div>
              <span>批阅队列</span>
              <small>{{ activeTabLabel }} · 第 {{ page }} 页</small>
            </div>
            <span v-if="reviewSubmitting" class="pr-lock" role="status">提交中 · 已锁定</span>
          </div>

          <AppSearchBox
            v-if="hasBatch"
            v-model="filters.keyword"
            :disabled="reviewSubmitting"
            placeholder="搜索学生 / 学号 / 课题"
            @search="onFilterSearch"
          />
          <ErrorState v-if="error" :description="error" @retry="load" />
          <LoadingState v-else-if="loading" />
          <EmptyState v-else-if="!rows.length" :title="emptyTitle" :description="emptyDesc" />
          <ul v-else class="pr-rows">
            <li
              v-for="(row, i) in rows"
              :key="rowKey(row)"
              class="pr-row"
              :class="{ 'is-active': rowKey(row) === selKey, 'is-disabled': reviewSubmitting }"
              :tabindex="reviewSubmitting ? -1 : 0"
              :aria-disabled="reviewSubmitting"
              :aria-current="rowKey(row) === selKey ? 'true' : undefined"
              role="button"
              @click="select(row)"
              @keydown.enter.prevent="select(row)"
              @keydown.space.prevent="select(row)"
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
            <AppPagination
              :total="total"
              :page="page"
              :page-size="pageSize"
              :show-size-changer="false"
              @update:page="turnPage"
            />
          </div>
        </aside>

        <section v-if="!isNarrow" class="pr-pane" aria-label="当前开题批阅对象">
          <div class="pr-pane__bar">
            <span class="pr-pane__pos">本页第 {{ selIndex + 1 }} / {{ rows.length }} 条 · 共 {{ total }} 条</span>
            <label class="pr-pane__auto"><input v-model="autoNext" type="checkbox" :disabled="reviewSubmitting" /> 批阅后自动进入下一条待审</label>
            <span class="pr-pane__nav">
              <button class="mp-link" :disabled="reviewSubmitting || selIndex <= 0" @click="step(-1)">← 上一条</button>
              <button class="mp-link" :disabled="reviewSubmitting || !hasNext" @click="step(1)">下一条 →</button>
            </span>
          </div>

          <div v-if="selectedRow" class="pr-subject" :data-selected-record="rowKey(selectedRow)">
            <div class="pr-subject__identity">
              <span>当前批阅对象</span>
              <strong>{{ selectedRow.studentName }}</strong>
              <small>{{ selectedRow.className || '班级待确认' }} · {{ selectedRow.topicTitle || '课题待确认' }}</small>
            </div>
            <div class="pr-subject__facts">
              <span><b>当前提交</b>{{ selectedRow.version || '版本待确认' }}</span>
              <span><b>提交时间</b><AppDateDisplay v-if="selectedRow.submitAt" :value="selectedRow.submitAt" mode="date" /><template v-else>未提交</template></span>
              <span v-if="reviewSubmitting" class="is-lock"><b>状态</b>正在提交，禁止切换对象</span>
            </div>
          </div>

          <template v-if="!selectedRow">
            <EmptyState title="从左侧选择一条开题记录" description="↑↓ 方向键可快速切换，处理后可自动进入下一条待审" />
          </template>
          <template v-else-if="selectedRow.status === 'NOT_SUBMITTED'">
            <section class="mp-card pr-not-submitted">
              <div class="mp-card__head"><span class="mp-card__title">尚未提交开题报告</span></div>
              <div class="mp-card__body">
                <div class="mp-kv"><span class="mp-kv__k">学生</span><span class="mp-kv__v">{{ selectedRow.studentName }} · {{ selectedRow.className }}</span></div>
                <div class="mp-kv"><span class="mp-kv__k">课题</span><span class="mp-kv__v">{{ selectedRow.topicTitle }}</span></div>
                <div class="mp-kv"><span class="mp-kv__k">指导教师</span><span class="mp-kv__v">{{ selectedRow.advisorName || '—' }}</span></div>
                <div class="pr-remind-action">
                  <AppButton variant="primary" :loading="reminding" @click="remind(selectedRow)">发送开题催交提醒</AppButton>
                </div>
                <p class="mp-note pr-remind-note">本操作会创建真实站内消息并写入催办留痕；学生提交后将进入「待审阅」页签。</p>
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
            @submitting-change="onReviewSubmittingChange"
          />
        </section>
      </div>

      <p class="mp-note">筛选、分页与当前对象会写入 URL；窄屏进入独立详情时保留批次及返回工作上下文。</p>
    </div>
    <AppPageGuide guide-key="graduation.gd-proposal" />
  </ModulePageShell>
</template>

<script>
/**
 * 开题审核 · 连续双栏批阅工作区（/admin/graduation/proposals）。
 * 左：待审队列；右：ProposalReviewCard 真实批阅。
 * tab / sel / page / keyword 均写入 URL，提交期间锁定当前对象。
 */
import { ModulePageShell, AdvancedFilter, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppExportButton, AppSearchBox, AppPagination, AppPageGuide } from '@/components/common'
import { AppDateDisplay } from '@/components/common/date'
import { graduationApi } from '@/modules/graduation/api/graduation.api'
import { graduationMoreApi } from '@/modules/graduation/api/graduation-more.api'
import { buildMaterialQuery, exportFilenameHint } from '@/modules/graduation/utils/queryParams'
import { useGraduationBatchStore } from '@/stores/graduationBatch'
import { toast } from '@/utils/toast'
import ProposalReviewCard from './_shared/ProposalReviewCard.vue'

export default {
  name: 'ProposalListView',
  components: {
    AppPageGuide,
    ModulePageShell, AdvancedFilter, StatusTag, LoadingState, ErrorState, EmptyState,
    AppButton, AppExportButton, AppSearchBox, AppPagination, AppDateDisplay,
    ProposalReviewCard
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      batchStore: useGraduationBatchStore(),
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
      reviewSubmitting: false,
      loadToken: 0,
      statsToken: 0,
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
    hasBatch() {
      return !!this.batchStore.selectedBatchId
    },
    activeTab() {
      return this.tabs.find((item) => item.value === this.filters.status) || this.tabs[this.tabs.length - 1]
    },
    activeTabLabel() {
      return this.activeTab?.label || '全部'
    },
    pendingCount() {
      return this.statusCount('PENDING_REVIEW')
    },
    notSubmittedCount() {
      return this.stats?.notSubmitted ?? 0
    },
    queueConclusion() {
      if (this.reviewSubmitting && this.selectedRow) return `正在提交 ${this.selectedRow.studentName} 的批阅结论，请勿切换对象。`
      if (this.filters.status === 'PENDING_REVIEW' && this.pendingCount > 0) return `待审阅 ${this.pendingCount} 份；从当前选中学生开始连续处理。`
      if (this.filters.status === 'NOT_SUBMITTED' && this.notSubmittedCount > 0) return `逾期未交 ${this.notSubmittedCount} 人；优先发送催交并保留留痕。`
      if (!this.total) return `「${this.activeTabLabel}」当前没有需要处理的记录。`
      return `当前查看「${this.activeTabLabel}」${this.total} 条记录。`
    },
    pageSubtitle() {
      if (!this.hasBatch) return '请先在顶部选择或创建毕设批次'
      const batch = this.batchStore.selectedBatchName ? `${this.batchStore.selectedBatchName} · ` : ''
      const p = this.stats
      if (!p) return `${batch}学生提交开题材料，教师连续批阅 · 驳回需填写原因并即时同步学生端`
      return `${batch}待审阅 ${this.statusCount('PENDING_REVIEW')} · 逾期未交 ${p.notSubmitted ?? 0} · 连续批阅不返回列表`
    },
    emptyTitle() {
      return this.hasBatch ? '当前页签暂无开题材料' : '请先选择或创建毕设批次'
    },
    emptyDesc() {
      return this.hasBatch ? '可切换页签或调整搜索条件' : '顶部批次条选择当前工作批次后，再批阅开题材料。'
    },
    exportPerm() {
      const pa = this.ctx.permissionActions.exportProposals || {}
      return { visible: !!pa.visible && this.hasBatch, allowed: !!pa.allowed }
    },
    filterFields() {
      return []
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
    this.applyInitialRouteState(this.$route.query)
    this.loadStats()
    this.load()
  },
  watch: {
    'batchStore.selectedBatchId'(batchId) {
      ++this.loadToken
      ++this.statsToken
      this.reviewSubmitting = false
      this.page = 1
      this.selKey = ''
      this.replaceListQuery({ batchId: batchId ? String(batchId) : undefined, page: '1', sel: undefined })
      this.loadStats()
      this.load()
    },
    '$route.query': {
      deep: true,
      handler(query) {
        this.onRouteQueryChanged(query)
      }
    }
  },
  mounted() {
    this._mq = window.matchMedia('(max-width: 1100px)')
    this.isNarrow = this._mq.matches
    this._onMq = (e) => { this.isNarrow = e.matches }
    this._mq.addEventListener ? this._mq.addEventListener('change', this._onMq) : this._mq.addListener(this._onMq)
    this._onKey = (e) => {
      if (this.isNarrow || this.reviewSubmitting) return
      const tag = (e.target && e.target.tagName) || ''
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
      if (e.key === 'ArrowDown') { e.preventDefault(); this.step(1) }
      if (e.key === 'ArrowUp') { e.preventDefault(); this.step(-1) }
    }
    window.addEventListener('keydown', this._onKey)
  },
  beforeUnmount() {
    ++this.loadToken
    ++this.statsToken
    if (this._mq) { this._mq.removeEventListener ? this._mq.removeEventListener('change', this._onMq) : this._mq.removeListener(this._onMq) }
    window.removeEventListener('keydown', this._onKey)
  },
  methods: {
    routeText(value) {
      return Array.isArray(value) ? String(value[0] || '') : String(value || '')
    },
    normalizePage(value) {
      const page = Number.parseInt(this.routeText(value), 10)
      return Number.isFinite(page) && page > 0 ? page : 1
    },
    normalizeTab(value) {
      const tab = this.routeText(value)
      return this.tabs.some((item) => item.value === tab) ? tab : 'PENDING_REVIEW'
    },
    applyInitialRouteState(query) {
      this.filters.status = this.normalizeTab(query.tab)
      this.filters.keyword = this.routeText(query.keyword)
      this.page = this.normalizePage(query.page)
      this.selKey = this.routeText(query.sel)
    },
    onRouteQueryChanged(query) {
      const nextStatus = this.normalizeTab(query.tab)
      const nextKeyword = this.routeText(query.keyword)
      const nextPage = this.normalizePage(query.page)
      const nextSel = this.routeText(query.sel)
      const listChanged = nextStatus !== this.filters.status || nextKeyword !== this.filters.keyword || nextPage !== this.page
      const selectionChanged = nextSel !== this.selKey
      if (!listChanged && !selectionChanged) return

      this.filters.status = nextStatus
      this.filters.keyword = nextKeyword
      this.page = nextPage
      this.selKey = nextSel
      if (listChanged) this.load()
      else if (nextSel && !this.selectedRow && !this.loading) this.load()
    },
    buildListQuery(overrides = {}) {
      const keyword = String(this.filters.keyword || '').trim()
      const query = {
        ...this.$route.query,
        batchId: this.batchStore.selectedBatchId ? String(this.batchStore.selectedBatchId) : undefined,
        tab: this.filters.status || undefined,
        page: String(this.page),
        keyword: keyword || undefined,
        sel: this.selKey || undefined,
        ...overrides
      }
      Object.keys(query).forEach((key) => {
        if (query[key] == null || query[key] === '') delete query[key]
      })
      return query
    },
    replaceListQuery(overrides = {}) {
      return this.$router.replace({ query: this.buildListQuery(overrides) })
    },
    listReturnTo(row) {
      return this.$router.resolve({
        path: '/admin/graduation/proposals',
        query: this.buildListQuery({ sel: this.rowKey(row) })
      }).fullPath
    },
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
    onReviewSubmittingChange(value) {
      this.reviewSubmitting = Boolean(value)
    },
    async loadStats() {
      const batchId = this.batchStore.selectedBatchId
      const token = ++this.statsToken
      if (!batchId) {
        this.stats = null
        return false
      }
      try {
        const res = await graduationMoreApi.getProposalStats({ batchId })
        if (token !== this.statsToken || String(batchId) !== String(this.batchStore.selectedBatchId)) return false
        if (res.code === 0) this.stats = res.data
        return res.code === 0
      } catch {
        if (token === this.statsToken && String(batchId) === String(this.batchStore.selectedBatchId)) this.stats = null
        return false
      }
    },
    switchTab(v) {
      if (this.reviewSubmitting) return
      this.filters.status = v
      this.page = 1
      this.selKey = ''
      this.replaceListQuery({ tab: v || undefined, page: '1', sel: undefined })
      this.load()
    },
    onFilterSearch() {
      if (this.reviewSubmitting) return
      this.page = 1
      this.selKey = ''
      this.replaceListQuery({ page: '1', sel: undefined })
      this.load()
    },
    onFilterReset() {
      if (this.reviewSubmitting) return
      this.filters = { ...this.filters, keyword: '', dateStart: '', dateEnd: '' }
      this.page = 1
      this.selKey = ''
      this.replaceListQuery({ keyword: undefined, page: '1', sel: undefined })
      this.load()
    },
    turnPage(p, { force = false } = {}) {
      if (this.reviewSubmitting && !force) return
      this.page = p
      this.selKey = ''
      this.replaceListQuery({ page: String(p), sel: undefined })
      this.load()
    },
    select(row, { force = false } = {}) {
      if (this.reviewSubmitting && !force) return
      const selectedKey = this.rowKey(row)
      if (this.isNarrow) {
        if (row.status !== 'NOT_SUBMITTED' && row.id != null) {
          this.$router.push({
            path: '/admin/graduation/proposals/' + row.id,
            query: {
              batchId: this.batchStore.selectedBatchId ? String(this.batchStore.selectedBatchId) : undefined,
              returnTo: this.listReturnTo(row)
            }
          })
        }
        return
      }
      this.selKey = selectedKey
      this.replaceListQuery({ sel: selectedKey })
    },
    step(delta) {
      if (this.reviewSubmitting) return
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
    /** 批阅成功：待审页签重新取同一服务端页，避免 offset 收缩后跳过学生。 */
    async onReviewed(payload) {
      const reviewedIndex = Math.max(0, this.rows.findIndex((r) => String(r.id) === String(payload.id)))
      const row = this.rows.find((r) => String(r.id) === String(payload.id))
      const pendingQueue = this.filters.status === 'PENDING_REVIEW'
      if (row) { row.status = payload.status; row.statusLabel = payload.statusLabel }
      await this.loadStats()
      if (!this.autoNext) return
      if (!pendingQueue) { this.nextPending({ force: true }); return }

      this.selKey = ''
      this._selectIndexAfterLoad = reviewedIndex
      await this.load()
      if (!this.rows.length && this.page > 1) {
        this.page -= 1
        this._selectIndexAfterLoad = this.pageSize - 1
        await this.load()
      }
      if (!this.rows.length) toast.success('待审记录已全部处理完')
    },
    onConflict() {
      this.loadStats()
      this.load()
    },
    nextPending({ force = false } = {}) {
      if (this.reviewSubmitting && !force) return
      const from = this.selIndex
      for (let i = from + 1; i < this.rows.length; i++) {
        if (this.rows[i].status === 'PENDING_REVIEW') { this.select(this.rows[i], { force }); return }
      }
      for (let i = 0; i < from; i++) {
        if (this.rows[i].status === 'PENDING_REVIEW') { this.select(this.rows[i], { force }); return }
      }
      if (this.page * this.pageSize < this.total) {
        this._selectPendingAfterLoad = true
        this.turnPage(this.page + 1, { force })
      } else {
        toast.success('本页待审记录已全部处理完')
      }
    },
    ensureSelection() {
      if (this.selectedRow) return
      if (!this.rows.length) {
        this.selKey = ''
        this._selectIndexAfterLoad = null
        this.replaceListQuery({ sel: undefined })
        return
      }
      let target = null
      if (Number.isInteger(this._selectIndexAfterLoad)) {
        target = this.rows[Math.min(this._selectIndexAfterLoad, this.rows.length - 1)]
      } else if (this._selectLastAfterLoad) target = this.rows[this.rows.length - 1]
      else if (this._selectPendingAfterLoad) target = this.rows.find((r) => r.status === 'PENDING_REVIEW') || this.rows[0]
      else target = this.rows.find((r) => r.status === 'PENDING_REVIEW') || this.rows[0]
      this._selectIndexAfterLoad = null
      this._selectFirstAfterLoad = false
      this._selectLastAfterLoad = false
      this._selectPendingAfterLoad = false
      if (target && !this.isNarrow) this.select(target, { force: true })
    },
    exportProposalsFn() {
      const hint = exportFilenameHint(this.batchStore.selectedBatchName, '开题材料')
      const p = buildMaterialQuery(this.filters, { batchId: this.batchStore.selectedBatchId })
      return graduationApi.exportProposals(p).then((res) => {
        if (res.code === 0 && res.data) {
          res.data = { ...res.data, filename: res.data.filename || `${hint}.xlsx` }
        }
        return res
      })
    },
    async remind(row) {
      if (this.reminding) return
      this.reminding = true
      try {
        const res = await graduationApi.remindProposal(row.projectId || row.gdStudentId)
        if (res.code === 0) toast.success('已向 ' + row.studentName + ' 发送开题催交站内消息并记录催办留痕')
        else toast.error(res.message || '催交失败')
      } catch (error) {
        toast.error(error?.message || '催交失败')
      } finally {
        this.reminding = false
      }
    },
    async load() {
      const batchId = this.batchStore.selectedBatchId
      const token = ++this.loadToken
      if (!batchId) {
        this.loading = false
        this.error = ''
        this.rows = []
        this.total = 0
        this.selKey = ''
        return false
      }
      this.loading = true
      this.error = ''
      try {
        const res = await graduationApi.getProposals(buildMaterialQuery(this.filters, {
          page: this.page,
          pageSize: this.pageSize,
          batchId
        }))
        if (token !== this.loadToken || String(batchId) !== String(this.batchStore.selectedBatchId)) return false
        if (res.code === 0) {
          this.rows = Array.isArray(res.data?.list) ? res.data.list : []
          this.total = Number(res.data?.total) || 0
          this.ensureSelection()
        } else {
          this.error = res.message
        }
        return res.code === 0
      } catch (error) {
        if (token === this.loadToken && String(batchId) === String(this.batchStore.selectedBatchId)) {
          this.error = error?.message || '开题列表加载失败，请稍后重试'
        }
        return false
      } finally {
        if (token === this.loadToken && String(batchId) === String(this.batchStore.selectedBatchId)) this.loading = false
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.pr-page { gap: var(--space-3); }
.pr-hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--space-4);
  padding: 16px 18px;
  border: 1px solid var(--primary-100, #dbeafe);
  border-radius: var(--radius-lg, 12px);
  background: linear-gradient(120deg, var(--primary-50, #eff6ff), var(--card, #fff) 72%);
  box-shadow: 0 14px 30px -28px rgba(37, 99, 235, .7);
}
.pr-hero__copy { min-width: 0; }
.pr-hero__eyebrow { display: block; margin-bottom: 4px; color: var(--primary-600, #2563eb); font-size: 11px; font-weight: 700; letter-spacing: .08em; }
.pr-hero__copy strong { display: block; color: var(--text-primary); font-size: 17px; line-height: 1.45; }
.pr-hero__copy p { margin: 5px 0 0; color: var(--text-secondary); font-size: var(--font-size-xs); line-height: 1.55; }
.pr-hero__metrics { display: grid; grid-template-columns: repeat(3, minmax(72px, 1fr)); gap: 8px; }
.pr-hero__metrics div { display: grid; justify-items: center; gap: 2px; padding: 9px 12px; border: 1px solid var(--border-light); border-radius: var(--radius-md); background: rgba(255, 255, 255, .76); }
.pr-hero__metrics span { color: var(--primary-700, #1d4ed8); font-size: 20px; font-weight: 700; }
.pr-hero__metrics small { color: var(--text-tertiary); font-size: 11px; white-space: nowrap; }
.pr-tab-count { margin-left: 4px; color: var(--text-tertiary); font-size: var(--font-size-xs); }
.mp-tab.is-active .pr-tab-count { color: inherit; }
.mp-tabs { display: flex; align-items: center; flex-wrap: wrap; gap: var(--space-1); }
.pr-split { display: flex; align-items: flex-start; gap: var(--space-3); }
.pr-list { display: flex; flex: 0 0 350px; flex-direction: column; gap: var(--space-2); width: 350px; padding: var(--space-3); border: 1px solid var(--border-light, #e2e8f0); border-radius: var(--radius-lg, 12px); background: var(--card, #fff); box-shadow: 0 10px 26px -26px rgba(15, 23, 42, .5); }
.pr-split.is-narrow .pr-list { flex-basis: auto; width: 100%; }
.pr-list__head { display: flex; align-items: center; justify-content: space-between; gap: 8px; min-height: 32px; }
.pr-list__head > div { display: grid; gap: 1px; }
.pr-list__head span:first-child { color: var(--text-primary); font-size: var(--font-size-sm); font-weight: 700; }
.pr-list__head small { color: var(--text-tertiary); font-size: 11px; }
.pr-lock { flex: none; padding: 4px 7px; border-radius: var(--radius-full); background: var(--warning-50, #fffbeb); color: var(--warning-700, #a16207); font-size: 11px; font-weight: 700; }
.pr-pane { flex: 1; min-width: 0; padding: var(--space-3); border: 1px solid var(--border-light, #e2e8f0); border-radius: var(--radius-lg, 12px); background: var(--card, #fff); box-shadow: 0 10px 26px -26px rgba(15, 23, 42, .5); }
.pr-rows { max-height: 640px; margin: 0; padding: 0; overflow-y: auto; border: 1px solid var(--border-light, #e2e8f0); border-radius: var(--radius-md, 8px); list-style: none; }
.pr-row { padding: 10px 12px; border-bottom: 1px solid var(--border-light, #eef1f6); cursor: pointer; transition: background .12s ease, box-shadow .12s ease; }
.pr-row:last-child { border-bottom: none; }
.pr-row:hover { background: var(--gray-50, #f8fafc); }
.pr-row.is-active { background: var(--primary-50, #eff6ff); box-shadow: inset 3px 0 0 var(--brand-primary, #2563eb); }
.pr-row.is-disabled { cursor: not-allowed; opacity: .72; }
.pr-row:focus-visible { position: relative; z-index: 1; outline: 2px solid var(--primary-400, #60a5fa); outline-offset: -2px; }
.pr-row__main { display: flex; align-items: center; gap: var(--space-2); }
.pr-row__name { color: var(--text-primary); font-weight: var(--font-weight-medium, 500); }
.pr-row__cls { flex: 1; overflow: hidden; color: var(--text-tertiary); font-size: var(--font-size-xs); text-overflow: ellipsis; white-space: nowrap; }
.pr-row__sub { margin-top: 3px; overflow: hidden; color: var(--text-secondary); font-size: var(--font-size-sm); text-overflow: ellipsis; white-space: nowrap; }
.pr-row__meta { display: flex; gap: var(--space-2); margin-top: 3px; color: var(--text-tertiary); font-size: var(--font-size-xs); }
.pr-row__idx { margin-left: auto; }
.pr-list__foot { display: flex; justify-content: center; }
.pr-pane__bar { display: flex; align-items: center; flex-wrap: wrap; gap: var(--space-3); padding: var(--space-2) var(--space-3); margin-bottom: var(--space-2); border: 1px solid var(--border-light, #e2e8f0); border-radius: var(--radius-md, 8px); background: var(--gray-50, #f8fafc); font-size: var(--font-size-sm); }
.pr-pane__pos { color: var(--text-secondary); }
.pr-pane__auto { display: inline-flex; align-items: center; gap: 4px; color: var(--text-secondary); cursor: pointer; }
.pr-pane__nav { display: inline-flex; gap: var(--space-3); margin-left: auto; }
.pr-pane__nav .mp-link:disabled { cursor: not-allowed; opacity: .4; }
.pr-subject { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center; gap: var(--space-3); padding: 10px 12px; margin-bottom: var(--space-3); border: 1px solid var(--primary-100, #dbeafe); border-radius: var(--radius-md); background: var(--primary-50, #eff6ff); }
.pr-subject__identity { display: grid; min-width: 0; gap: 2px; }
.pr-subject__identity > span { color: var(--primary-600, #2563eb); font-size: 10px; font-weight: 700; letter-spacing: .08em; }
.pr-subject__identity strong { color: var(--text-primary); font-size: 15px; }
.pr-subject__identity small { overflow: hidden; color: var(--text-secondary); font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.pr-subject__facts { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 6px 12px; color: var(--text-secondary); font-size: 11px; }
.pr-subject__facts span { display: inline-flex; align-items: center; gap: 4px; }
.pr-subject__facts b { color: var(--text-tertiary); font-weight: 500; }
.pr-subject__facts .is-lock { color: var(--warning-700, #a16207); font-weight: 700; }
.pr-not-submitted { border-color: var(--warning-100, #fef3c7); }
.pr-remind-action { margin-top: var(--space-3); }
.pr-remind-note { margin-top: var(--space-2); }
@media (max-width: 1180px) {
  .pr-list { flex-basis: 320px; width: 320px; }
  .pr-subject { grid-template-columns: 1fr; }
  .pr-subject__facts { justify-content: flex-start; }
}
@media (max-width: 1100px) {
  .pr-hero { grid-template-columns: 1fr; }
  .pr-hero__metrics { justify-self: stretch; }
  .pr-pane { padding: var(--space-3); }
}
@media (max-width: 720px) {
  .pr-hero__metrics { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .pr-hero__metrics div { padding-inline: 6px; }
}
</style>
