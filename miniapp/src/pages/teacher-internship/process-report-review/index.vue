<template>
  <view class="internship-surface mobile-page mobile-teacher page-wrap teacher-period-reports internship-flow">
    <view :inert="reviewPanel ? true : undefined" :aria-hidden="reviewPanel ? 'true' : undefined">
    <MobileNavBar variant="teacher" title="过程报告批阅" show-back />

    <view v-if="state === 'ready'" class="page-pad pr__context">
      <view class="pr__batch" v-if="batches.length">
        <view class="pr__batch-copy">
          <text class="pr__batch-name">{{ batches[batchIndex]?.name || '请选择批次' }}</text>
        </view>
        <picker v-if="batches.length > 1" class="mobile-picker pr__picker" mode="selector" :range="batchLabels" :value="batchIndex" :disabled="!!actingId" @change="onBatch">
          <view class="pr__pick-val">切换批次 <text class="pr__arrow">▾</text></view>
        </picker>
      </view>
      <view v-if="focusReportId" class="card stack"><text>来自待办的原报告 · 已定位本次对象和批次</text><button class="mobile-control btn btn-ghost" :disabled="!!actingId" @click="clearFocus">查看本批次其他报告</button></view>

      <button v-if="batches.length && list && total > 0" class="mobile-control btn btn-ghost" :aria-expanded="summaryOpen" @click="summaryOpen=!summaryOpen">{{ summaryOpen ? '收起报告统计' : '查看报告统计（当前查询共' + total + '篇）' }}</button>
      <view v-if="batches.length && list && total > 0 && summaryOpen" class="card pr__summary">
        <view class="pr__summary-main">
          <text class="pr__summary-label">当前查询报告总数</text>
          <view class="pr__summary-value"><text>{{ total }}</text><text>篇</text></view>
          <text class="pr__summary-note">{{ summaryConclusion }}</text>
        </view>
        <view class="pr__summary-metrics">
          <view class="pr__metric"><text>{{ dailyCount }}</text><text>已读取日报</text></view>
          <view class="pr__metric"><text>{{ monthlyCount }}</text><text>已读取月报</text></view>
          <view class="pr__metric"><text>{{ summaryCount }}</text><text>已读取总结</text></view>
        </view>
      </view>
      <view v-if="!focusReportId" class="card stack pr__filters">
        <picker class="mobile-picker" mode="selector" :range="typeFilters.map(item => item.label)" :value="typeIndex" @change="typeIndex = Number($event.detail.value)"><view>报告类型：{{ typeFilters[typeIndex].label }}</view></picker>
        <picker class="mobile-picker" mode="selector" :range="statusFilters.map(item => item.label)" :value="statusIndex" @change="statusIndex = Number($event.detail.value)"><view>状态：{{ statusFilters[statusIndex].label }}</view></picker>
        <input class="mobile-input" v-model.trim="filters.keyword" placeholder="学生姓名或学号" />
        <button class="mobile-control btn btn-ghost" :aria-expanded="advancedFiltersOpen" @click="advancedFiltersOpen=!advancedFiltersOpen">{{ advancedFiltersOpen ? '收起提交日期筛选' : '日期筛选' }}</button>
        <text v-if="!advancedFiltersOpen && (filters.startDate || filters.endDate)" class="pr__summary-note">已选日期：{{ filters.startDate || '不限' }} 至 {{ filters.endDate || '不限' }}</text>
        <picker v-show="advancedFiltersOpen" class="mobile-picker" mode="date" :value="filters.startDate" @change="filters.startDate = $event.detail.value"><view>提交开始日期：{{ filters.startDate || '请选择' }}</view></picker>
        <picker v-show="advancedFiltersOpen" class="mobile-picker" mode="date" :value="filters.endDate" @change="filters.endDate = $event.detail.value"><view>提交结束日期：{{ filters.endDate || '请选择' }}</view></picker>
        <button class="mobile-control" :disabled="!!actingId" @click="queryReports">查询报告</button>
      </view>

      <ReportObligations v-if="batchId && !hidden && !focusReportId" :key="batchId + ':' + generation" :batch-id="batchId" :can-review="canReview" />
    </view>

    <MobileGlobalState :state="state" :description="loadError" @retry="load">
      <view class="page-pad pr__list" v-if="list">
        <MobileGlobalState v-if="!batches.length" state="empty" title="暂无实习批次"
          description="当前身份的数据范围内没有可办理的岗位实习批次。" />
        <MobileGlobalState v-else-if="!list.length" state="empty" title="暂无符合条件的报告"
          description="请调整筛选条件。" />
        <view class="stack" v-else>
          <view v-for="r in list" :key="r.id" class="card pr" :class="{ 'is-expanded': expanded === r.id }">
            <view class="row-between pr__head" @click="toggle(r)">
              <view class="flex-1 pr__identity">
                <text class="t-md t-bold">{{ r.studentName || '—' }}</text>
                <text class="pr__sub">{{ r.studentNo || '' }} · {{ r.reportTypeLabel }}</text>
              </view>
              <view class="pr__head-right">
                <MobileStatusTag :label="r.statusLabel" type="warning" />
                <text class="pr__chevron">{{ expanded === r.id ? '收起 ▲' : '展开正文 ▼' }}</text>
              </view>
            </view>

            <view class="pr__brief">
              <view><text>报告周期</text><text>{{ r.periodLabel }}</text></view>
              <view><text>正文长度</text><text>{{ r.wordCount || 0 }} 字</text></view>
              <view><text>提交版本</text><text>第 {{ r.reportVersion || 1 }} 版</text></view>
            </view>

            <template v-if="expanded === r.id">
              <view v-if="loadingDetail === r.id" class="pr__loading"><text class="t-sm t-tertiary">正在加载正文…</text></view>
              <template v-else-if="detail[r.id]">
                <view class="pr__meta">
                  <text>企业：{{ detail[r.id].enterpriseName || '—' }}</text>
                  <text>提交：{{ fmt(detail[r.id].submitAt) }}</text>
                </view>
                <view class="pr__content">
                  <text class="pr__content-label">报告正文</text>
                  <text class="pr__content-text">{{ detail[r.id].content || '（无正文）' }}</text>
                </view>
                <view v-if="latestAttachments(r.id).length" class="pr__attachments">
                  <text class="pr__content-label">图片/视频附件</text>
                  <view v-for="file in latestAttachments(r.id)" :key="file.fileId"
                    class="pr__attachment" @click.stop="openAttachment(file)">
                    <view class="flex-1">
                      <text class="t-sm t-bold">{{ file.fileName || '附件' }}</text>
                      <text class="pr__attachment-meta">{{ file.kindLabel }}</text>
                    </view>
                    <text class="pr__open">查看</text>
                  </view>
                </view>
                <view v-if="detail[r.id].versions?.[0]?.review" class="stack">
                  <text v-if="detail[r.id].versions[0].review.summaryScore != null">本次提交总结评分：{{ detail[r.id].versions[0].review.summaryScore }}分（百分制）</text>
                  <text v-else-if="detail[r.id].versions[0].review.ratingLevel">本次提交五级评价：{{ detail[r.id].versions[0].review.ratingLevel }}级</text>
                  <text>教师意见：{{ detail[r.id].versions[0].review.comment || '暂无' }}</text>
                </view>
                <view class="pr__actions" v-if="canReview && detail[r.id].status === 'PENDING_REVIEW'">
                  <button class="mobile-control pr__reject flex-1" tabindex="0" :disabled="actingId === r.id" @click.stop="review(r, 'RETURN')">退回修改</button>
                  <button class="mobile-control pr__approve flex-1" tabindex="0" :disabled="actingId === r.id" @click.stop="review(r, 'APPROVE')">通过报告</button>
                </view>
                <MobileInlineAlert v-else type="info" :description="detail[r.id].status === 'PENDING_REVIEW' ? '当前身份仅可查看，无过程报告批阅权限。' : '本次提交已办理，可查看正文、附件和批阅结果。'" />
              </template>
            </template>
          </view>
        </view>
        <button class="mobile-control" v-if="hasMore" :disabled="loadingMore" @click="loadMore">{{ loadingMore ? '正在读取…' : '加载更多报告' }}</button>
      </view>
    </MobileGlobalState>
    </view>
    <view v-if="reviewPanel" class="review-overlay">
      <view class="review-overlay__mask" @click="closeReview" @touchmove.stop.prevent />
      <view ref="reviewSheet" class="review-sheet" role="dialog" aria-modal="true" aria-labelledby="report-review-title">
        <view class="review-sheet__header">
          <view>
            <text id="report-review-title" class="review-sheet__title">本次批阅</text>
            <text class="review-sheet__context">{{ reviewPanel.typeLabel }} · {{ reviewPanel.studentName }}</text>
          </view>
          <button class="mobile-control review-sheet__close" role="button" :tabindex="actingId ? -1 : 0" :disabled="!!actingId" aria-label="关闭批阅，保留草稿" @click="closeReview">关闭</button>
        </view>
        <scroll-view scroll-y class="review-sheet__body">
          <view class="review-sheet__decision" role="group" aria-label="批阅结果">
            <button class="mobile-control" role="button" :tabindex="actingId ? -1 : 0" :class="{ 'is-selected': reviewPanel.draft.action === 'APPROVE' }" :aria-pressed="reviewPanel.draft.action === 'APPROVE'" :disabled="!!actingId" @click="setReviewAction('APPROVE')">通过</button>
            <button class="mobile-control" role="button" :tabindex="actingId ? -1 : 0" :class="{ 'is-selected': reviewPanel.draft.action === 'RETURN', 'is-return': reviewPanel.draft.action === 'RETURN' }" :aria-pressed="reviewPanel.draft.action === 'RETURN'" :disabled="!!actingId" @click="setReviewAction('RETURN')">退回修改</button>
          </view>
          <view v-if="reviewPanel.draft.action === 'APPROVE'" class="review-sheet__field">
            <template v-if="reviewPanel.isSummary">
              <label for="report-summary-score" class="review-sheet__label">总结评分<text class="review-sheet__optional">（百分制）</text></label>
              <view class="review-sheet__score">
                <input class="mobile-input" id="report-summary-score" v-model="reviewPanel.draft.summaryScore" type="digit" placeholder="请输入0～100" :disabled="!!actingId" :adjust-position="true" :cursor-spacing="24" aria-label="总结评分，0至100分" @input="reviewError = ''" />
                <text>分</text>
              </view>
              <text class="review-sheet__hint">0分有效，请明确填写分数。</text>
            </template>
            <template v-else>
              <text class="review-sheet__label">五级评价</text>
              <view class="review-sheet__levels" role="group" aria-label="五级评价">
                <button class="mobile-control" v-for="level in 5" :key="level" role="button" :tabindex="actingId ? -1 : 0" :class="{ 'is-selected': reviewPanel.draft.ratingLevel === level }" :aria-label="`${level}级`" :aria-pressed="reviewPanel.draft.ratingLevel === level" :disabled="!!actingId" @click="setReviewRating(level)">{{ level }}</button>
              </view>
              <text class="review-sheet__hint">{{ reviewPanel.draft.ratingLevel ? `已选 ${reviewPanel.draft.ratingLevel} 级` : '请选择评价等级' }}</text>
            </template>
          </view>
          <view class="review-sheet__field">
            <label for="report-review-comment" class="review-sheet__label">{{ reviewPanel.draft.action === 'RETURN' ? '修改要求' : '批阅意见' }}<text class="review-sheet__optional">{{ reviewPanel.draft.action === 'RETURN' ? '（必填）' : '（选填）' }}</text></label>
            <textarea id="report-review-comment" v-model="reviewPanel.draft.comment" class="mobile-textarea review-sheet__comment" :placeholder="reviewPanel.draft.action === 'RETURN' ? '请写清需要补充或修改的内容，至少5个字' : '写下建议，帮助学生完成下一步工作'" :maxlength="-1" :disabled="!!actingId" :adjust-position="true" :cursor-spacing="24" :aria-label="reviewPanel.draft.action === 'RETURN' ? '修改要求' : '批阅意见'" @input="reviewError = ''" />
            <text class="review-sheet__count">已填写 {{ reviewPanel.draft.comment.length }} 字</text>
          </view>
          <text v-if="reviewError" class="review-sheet__error" role="alert">{{ reviewError }}</text>
        </scroll-view>
        <view class="review-sheet__footer">
          <text class="review-sheet__hint">本次评价对应第 {{ reviewPanel.reportVersion }} 次提交</text>
          <button class="mobile-control review-sheet__submit" role="button" :tabindex="actingId ? -1 : 0" :class="{ 'is-return': reviewPanel.draft.action === 'RETURN' }" :disabled="!!actingId" @click="submitReview">{{ actingId ? '正在提交…' : reviewPanel.draft.action === 'RETURN' ? '确认退回修改' : '确认通过' }}</button>
        </view>
      </view>
    </view>
    <ReportFilePreview ref="reportPreview" />
  </view>
</template>

<script>
import {
  teacherInternshipProcessReports,
  teacherInternshipProcessReportDetail,
  teacherInternshipProcessReportReview
} from '@/services/internshipApi'
import { useInternshipContextStore } from '@/stores/internshipContext'
import ReportFilePreview from '@/components/ReportFilePreview.vue'
import ReportObligations from '@/components/teacher/ReportObligations.vue'
import { normalizeError } from '@/services/request'
import { processReportView, reportFileState } from '@/services/weeklyReportPresentation.mjs'
import { toast } from '@/utils/nav'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { formatDateTime } from '@/utils/format'

export default {
  components: { ReportFilePreview, ReportObligations },
  data() {
    return { summaryOpen:false, advancedFiltersOpen:false, focusReportId:'', requestedBatchId:'',
      list: null, state: 'loading', loadError: '', expanded: '', detail: {}, loadingDetail: '', actingId: '', generation: currentSessionGeneration(), reviewDrafts: {}, reviewPanel: null, reviewError: '',
      batches: [], batchId: '', batchIndex: 0, page: 1, total: 0, hasMore: false, loadingMore: false, loadSeq: 0, hidden: false,
      typeIndex: 0, statusIndex: 0, filters: { keyword: '', startDate: '', endDate: '' }, appliedFilters: {},
      typeFilters: [{label:'全部类型',value:''},{label:'日报',value:'DAILY'},{label:'月报',value:'MONTHLY'},{label:'实习总结',value:'SUMMARY'}],
      statusFilters: [{label:'待批阅',value:'PENDING_REVIEW'},{label:'已通过',value:'APPROVED'},{label:'已退回',value:'RETURNED'},{label:'全部状态',value:''}]
    }
  },
  computed: {
    batchLabels() { return this.batches.map((b) => `${b.name} · ${b.studentCount}人`) },
    canReview() { return useInternshipContextStore().can('internship.report.review') },
    dailyCount() { return (this.list || []).filter((item) => String(item.reportType || item.reportTypeLabel || '').includes('DAILY') || String(item.reportTypeLabel || '').includes('日报')).length },
    monthlyCount() { return (this.list || []).filter((item) => String(item.reportType || item.reportTypeLabel || '').includes('MONTH') || String(item.reportTypeLabel || '').includes('月报')).length },
    summaryCount() { return Math.max(0, (this.list || []).length - this.dailyCount - this.monthlyCount) },
    summaryConclusion() {
      if (!this.list?.length) return '当前查询没有过程报告。'
      return '按提交顺序展开正文，核对本次提交的内容、附件与评价。'
    }
  },
  onLoad(options={}) { this.focusReportId=String(options.reportId || '');this.requestedBatchId=String(options.batchId || '');this.load() },
  onShow() { if (this.hidden || this.generation !== currentSessionGeneration()) { this.hidden = false; this.load() } },
  onHide() { this.reviewPanel = null; this.hidden = true; this.loadSeq++; this.$refs.reportPreview?.reset() },
  onUnload() { this.reviewPanel = null; this.hidden = true; this.loadSeq++; this.$refs.reportPreview?.reset() },
  onReachBottom() { this.loadMore() },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  methods: {
    clearFocus() { if(!this.actingId)uni.redirectTo({url:'/pages/teacher-internship/process-report-review/index?batchId='+encodeURIComponent(this.batchId)}) },
    queryReports() {
      if (this.actingId) return
      if (this.filters.startDate && this.filters.endDate && this.filters.startDate > this.filters.endDate) { toast('开始日期不能晚于结束日期'); return }
      this.appliedFilters = { ...this.filters, startDate: this.filters.startDate || undefined, endDate: this.filters.endDate || undefined,
        reportType: this.typeFilters[this.typeIndex].value, status: this.statusFilters[this.statusIndex].value }
      this.load()
    },
    fmt: formatDateTime,
    async load(done) {
      const sequence = ++this.loadSeq
      const generation = currentSessionGeneration()
      this.state = 'loading'
      this.loadError = ''
      this.reviewPanel = null; this.reviewError = ''
      this.batches = []; this.batchId = ''; this.batchIndex = 0; this.detail = {}; this.expanded = ''
      this.$refs.reportPreview?.reset()
      if (this.generation !== generation) {
        this.reviewDrafts = {}
        this.focusReportId='';this.requestedBatchId=''
        this.generation = generation; this.typeIndex = 0; this.statusIndex = 0
        this.filters = { keyword: '', startDate: '', endDate: '' }; this.appliedFilters = {}
      }
      this.list = []; this.total = 0; this.loadingMore = false; this.loadingDetail = ''; this.actingId = ''
      this.page = 1
      this.hasMore = false
      try {
        const context = useInternshipContextStore()
        context.restore()
        await context.load(true)
        if (this.hidden || generation !== currentSessionGeneration() || sequence !== this.loadSeq) return
        this.batches = context.batches || []
        if(this.focusReportId){
          if(!/^[1-9]\d*$/.test(this.focusReportId))throw Error('原报告编号无效，请从待办重新进入')
          const report=await teacherInternshipProcessReportDetail(this.focusReportId)
          if(this.hidden || generation!==currentSessionGeneration() || sequence!==this.loadSeq)return
          if(String(report?.id)!==this.focusReportId || !report.batchId || (this.requestedBatchId && String(report.batchId)!==this.requestedBatchId) || !context.selectBatch(String(report.batchId)))throw Error('原报告不属于当前可查看批次，请从待办重新进入')
          this.batchId=String(report.batchId);this.batchIndex=Math.max(0,this.batches.findIndex(b=>String(b.id)===this.batchId))
          this.list=[processReportView(report)];this.detail={[this.focusReportId]:report};this.expanded=this.focusReportId;this.total=1;this.hasMore=false;this.state='ready';return
        }
        if(this.requestedBatchId && !context.selectBatch(this.requestedBatchId))throw Error('当前账号无权查看所选批次')
        this.requestedBatchId=''
        this.batchId = context.selectedBatchId || ''
        this.batchIndex = Math.max(0, this.batches.findIndex((b) => String(b.id) === String(this.batchId)))
        this.expanded = ''
        this.detail = {}
        if (!this.batchId) { this.list = []; this.state = 'ready'; return }
        const data = await teacherInternshipProcessReports(this.batchId, 1, 20, this.appliedFilters)
        if (this.hidden || generation !== currentSessionGeneration() || sequence !== this.loadSeq) return
        this.list = ((data && (data.items || data.list)) || []).map(processReportView)
        this.hasMore = !!data?.hasMore
        this.total = Number(data?.total ?? this.list.length)
        this.state = 'ready'
      } catch (e) {
        if (this.hidden || generation !== currentSessionGeneration() || sequence !== this.loadSeq) return
        this.list = []
        const shown = normalizeError(e)
        this.state = shown.pageState || 'error'; this.loadError = shown.text
      } finally { if (done) done() }
    },
    async onBatch(e) {
      if (this.actingId) return
      this.reviewDrafts = {}
      this.batchIndex = Number(e.detail.value)
      const batch = this.batches[this.batchIndex]
      const context = useInternshipContextStore()
      context.selectBatch(batch && batch.id)
      this.batchId = context.selectedBatchId
      if(this.focusReportId){this.clearFocus();return}
      this.list = []
      await this.load()
    },
    async loadMore() {
      if (!this.batchId || !this.hasMore || this.loadingMore || this.state !== 'ready') return
      const selectedBatch = this.batchId
      const sequence = this.loadSeq
      const generation = currentSessionGeneration()
      this.loadingMore = true
      try {
        const nextPage = this.page + 1
        const data = await teacherInternshipProcessReports(selectedBatch, nextPage, 20, this.appliedFilters)
        if (this.hidden || generation !== currentSessionGeneration() || sequence !== this.loadSeq || selectedBatch !== this.batchId) return
        this.list = [...(this.list || []), ...(data?.items || []).map(processReportView)]
        this.page = nextPage
        this.hasMore = !!data?.hasMore
      } catch (e) { if (!this.hidden && generation === currentSessionGeneration() && sequence === this.loadSeq) toast(normalizeError(e).text) }
      finally { if (generation === currentSessionGeneration() && sequence === this.loadSeq) this.loadingMore = false }
    },
    async toggle(r) {
      if (this.expanded === r.id) { this.expanded = ''; return }
      this.expanded = r.id
      if (this.detail[r.id]) return
      this.loadingDetail = r.id
      const sequence = this.loadSeq
      const generation = currentSessionGeneration(), batchId = this.batchId
      try {
        const data = await teacherInternshipProcessReportDetail(r.id)
        if (this.hidden || generation !== currentSessionGeneration() || sequence !== this.loadSeq || batchId !== this.batchId) return
        if (String(data?.id) !== String(r.id) || String(data.batchId) !== String(batchId)) throw new Error('报告所属批次不一致，请重新读取原单')
        this.detail = { ...this.detail, [r.id]: data }
      } catch (e) {
        if (this.hidden || generation !== currentSessionGeneration() || sequence !== this.loadSeq) return
        toast(normalizeError(e).text)
        this.expanded = ''
      } finally { if (generation === currentSessionGeneration() && sequence === this.loadSeq && this.loadingDetail === r.id) this.loadingDetail = '' }
    },
    latestAttachments(reportId) {
      const versions = this.detail[reportId]?.versions || []
      return (versions[0]?.attachments || []).map(reportFileState)
    },
    async openAttachment(file) {
      await this.$refs.reportPreview.open(file)
      uni.pageScrollTo({ selector: '.report-preview', duration: 200 })
    },
    review(r, action) {
      if (!['APPROVE', 'RETURN'].includes(action) || !this.canReview || this.actingId || this.hidden || this.state !== 'ready' || (this.detail[r.id]?.status && this.detail[r.id].status !== 'PENDING_REVIEW')) return
      const version = this.detail[r.id]?.version
      if (version == null) { toast('请先打开报告正文'); return }
      this.reviewOpener = this.$el?.querySelector?.(action === 'RETURN' ? '.is-expanded .pr__reject' : '.is-expanded .pr__approve')
      const command = { id: r.id, version, batchId: this.batchId, sequence: this.loadSeq, generation: currentSessionGeneration() }
      const key = `${this.batchId}:${r.id}`, draft = this.reviewDrafts[key]
      if (draft && draft.version !== version) draft.conflicted = true
      if (draft?.conflicted) {
        if (draft.version === version) { toast('原意见和评分已保留，请刷新并重新打开最新正文'); return }
        uni.showModal({ title: '采用已核对的报告版本', content: `原第${draft.version}版，现第${version}版。确认保留原意见和评分继续？`, success: m => {
          if (!m.confirm || !this.reviewCurrent(command)) return
          draft.version = version; draft.conflicted = false; this.review(r, action)
        } }); return
      }
      const isSummary = String(r.reportType || this.detail[r.id]?.reportType || '').toUpperCase() === 'SUMMARY'
      this.reviewDrafts[key] = draft || { action, comment: '', ratingLevel: null, summaryScore: '', version, conflicted: false }
      this.reviewDrafts[key].action = action
      this.reviewPanel = { command, draft: this.reviewDrafts[key], isSummary, studentName: r.studentName || '当前学生',
        typeLabel: r.reportTypeLabel || (isSummary ? '实习总结' : r.reportType === 'MONTHLY' ? '月报' : '日报'), reportVersion: this.detail[r.id].reportVersion || r.reportVersion || 1 }
      this.reviewError = ''
      this.$nextTick(() => {
        const el = this.$refs.reviewSheet?.$el || this.$refs.reviewSheet
        // uni-app normalizes component events without KeyboardEvent.key; bind the H5 DOM directly.
        el?.addEventListener?.('keydown', this.onReviewKeydown)
        el?.querySelector?.('button, uni-button')?.focus?.()
      })
    },
    reviewCurrent(command) {
      return !this.hidden && command.generation === currentSessionGeneration() && command.sequence === this.loadSeq &&
        command.batchId === this.batchId && command.version === this.detail[command.id]?.version
    },
    closeReview() {
      if (this.actingId) return
      const command = this.reviewPanel?.command, opener = this.reviewOpener
      this.reviewPanel = null; this.reviewError = ''
      this.$nextTick(() => { if (command && this.reviewCurrent(command)) opener?.focus?.() })
    },
    onReviewKeydown(event) {
      if (event.key === 'Escape') { event.preventDefault(); this.closeReview(); return }
      if (event.key === 'Tab') { this.trapReviewFocus(event); return }
      if (!this.actingId && ['Enter', ' '].includes(event.key) && ['BUTTON', 'UNI-BUTTON'].includes(event.target?.tagName)) {
        event.preventDefault(); event.target.click()
      }
    },
    trapReviewFocus(event) {
      const el = this.$refs.reviewSheet?.$el || this.$refs.reviewSheet
      const controls = [...(el?.querySelectorAll?.('button, uni-button, input, textarea') || [])].filter(item => !item.hasAttribute('disabled') && item.getClientRects().length)
      const first = controls[0], last = controls[controls.length - 1]
      if (first && ((event.shiftKey && event.target === first) || (!event.shiftKey && event.target === last))) {
        event.preventDefault(); (event.shiftKey ? last : first).focus()
      }
    },
    setReviewAction(action) {
      if (!this.reviewPanel || this.actingId || !['APPROVE', 'RETURN'].includes(action)) return
      this.reviewPanel.draft.action = action; this.reviewError = ''
    },
    setReviewRating(level) {
      if (!this.reviewPanel || this.actingId || !Number.isInteger(level) || level < 1 || level > 5) return
      this.reviewPanel.draft.ratingLevel = level; this.reviewError = ''
    },
    async submitReview() {
      const panel = this.reviewPanel
      if (!panel || !this.canReview || this.actingId || !this.reviewCurrent(panel.command)) return
      const { command, draft } = panel, { action } = draft, reject = action === 'RETURN'
      const comment = String(draft.comment || '').trim()
      if (reject && comment.length < 5) { this.reviewError = '请写清修改要求，至少5个字。'; return }
      let ratingLevel = null, summaryScore = null
      if (!reject && panel.isSummary) {
        const text = String(draft.summaryScore ?? '').trim(), score = Number(text)
        if (!text || !Number.isFinite(score) || score < 0 || score > 100) { this.reviewError = '请填写0～100分，0分有效。'; return }
        summaryScore = score
      } else if (!reject) {
        if (!Number.isInteger(draft.ratingLevel) || draft.ratingLevel < 1 || draft.ratingLevel > 5) { this.reviewError = '请先选择1～5级评价。'; return }
        ratingLevel = draft.ratingLevel
      }
      const key = `${command.batchId}:${command.id}`
      this.reviewError = ''; this.actingId = command.id
      try {
        await teacherInternshipProcessReportReview(command.id, command.batchId, {
          action, comment, ratingLevel, summaryScore, expectedVersion: command.version, batchId: command.batchId
        })
        if (!this.reviewCurrent(command)) return
        delete this.reviewDrafts[key]; this.reviewPanel = null; this.actingId = ''
        toast(reject ? '已退回学生修改' : panel.isSummary ? '总结百分制批阅已完成' : '报告已完成五级批阅')
        await this.load()
      } catch (e) {
        if (!this.reviewCurrent(command)) return
        this.actingId = ''
        if (normalizeError(e).kind === 'conflict') {
          draft.conflicted = true; this.reviewPanel = null
          toast('报告已变化，意见和评分已保留，请重新打开正文核对')
          await this.load()
        } else this.reviewError = normalizeError(e).text + '，意见和评分已保留。'
      } finally { if (this.reviewCurrent(command)) this.actingId = '' }
    }
  }
}
</script>

<style scoped>
.review-overlay{position:fixed;inset:0;z-index:var(--z-modal);display:flex;align-items:flex-end;justify-content:center}
.review-overlay__mask{position:absolute;inset:0;background:var(--bg-mask);touch-action:none}
.review-sheet{position:relative;width:100%;max-width:560px;max-height:90vh;max-height:90dvh;display:flex;flex-direction:column;box-sizing:border-box;background:var(--bg-card);border-radius:var(--space-6) var(--space-6) 0 0;overflow:hidden;color:var(--text-primary);box-shadow:var(--shadow-float)}
.review-sheet__header{display:flex;align-items:flex-start;justify-content:space-between;gap:var(--space-3);padding:var(--space-6) var(--space-5) var(--space-5)}
.review-sheet__title{display:block;font-size:var(--font-size-2xl);font-weight:700;line-height:1.4}
.review-sheet__context{display:block;margin-top:var(--space-2);color:var(--text-secondary);font-size:var(--font-size-base);line-height:1.5;overflow-wrap:anywhere}
.review-sheet__close{flex-shrink:0;margin:0;padding:0 var(--space-2);min-height:var(--touch-target-min);background:transparent;color:var(--text-secondary);font-size:var(--font-size-base);line-height:var(--touch-target-min)}
.review-sheet button::after{border:none}
.review-sheet__body{min-height:0;max-height:calc(90vh - 204px);max-height:calc(90dvh - 204px);overflow:auto;overscroll-behavior:contain}
.review-sheet__decision{display:flex;gap:var(--space-2);margin:0 var(--space-5);padding:var(--space-1);background:var(--gray-100);border-radius:var(--radius-lg)}
.review-sheet__decision button{flex:1;margin:0;padding:var(--space-3) var(--space-2);min-height:var(--touch-target-min);line-height:1.5;font-size:var(--font-size-lg);font-weight:600;background:transparent;color:var(--text-primary);border-radius:var(--radius-md)}
.review-sheet__decision button.is-selected,.review-sheet__levels button.is-selected{background:var(--teacher-600);color:var(--text-inverse)}
.review-sheet__decision button.is-return{background:var(--danger-50);color:var(--danger-600);box-shadow:inset 0 0 0 1px var(--danger-500)}
.review-sheet__field{margin:var(--space-6) var(--space-5) 0}
.review-sheet__label{display:block;margin-bottom:var(--space-3);font-size:var(--font-size-lg);font-weight:600;line-height:1.5}
.review-sheet__optional{font-size:var(--font-size-base);font-weight:400;color:var(--text-secondary)}
.review-sheet__levels{display:flex;gap:var(--space-2)}
.review-sheet__levels button{flex:1;min-width:0;min-height:52px;margin:0;padding:var(--space-3) 0;line-height:1.4;font-size:var(--font-size-xl);font-weight:600;color:var(--text-primary);background:var(--gray-100);border-radius:var(--radius-lg)}
.review-sheet__hint{display:block;margin-top:var(--space-2);font-size:var(--font-size-sm);line-height:1.5;color:var(--text-secondary)}
.review-sheet__comment{display:block;box-sizing:border-box;width:100%;height:136px;padding:var(--space-3);border:1px solid var(--border-base);border-radius:var(--radius-lg);font-size:var(--font-size-lg);line-height:1.65;background:var(--bg-card);color:var(--text-primary)}
.review-sheet__count{text-align:right;display:block;margin-top:var(--space-2);font-size:var(--font-size-xs);color:var(--text-secondary)}
.review-sheet__score{display:flex;align-items:center;gap:var(--space-3);padding:var(--space-3);border:1px solid var(--border-base);border-radius:var(--radius-lg)}
.review-sheet__score input{flex:1;min-width:0;font-size:var(--font-size-xl);height:var(--touch-target-min)}
.review-sheet__score text{font-size:var(--font-size-base);color:var(--text-secondary)}
.review-sheet__error{display:block;margin:var(--space-3) var(--space-5) 0;color:var(--danger-600);font-size:var(--font-size-base);line-height:1.5}
.review-sheet__footer{flex-shrink:0;padding:var(--space-4) var(--space-5) calc(var(--space-5) + var(--safe-area-bottom));background:var(--bg-card)}
.review-sheet__footer .review-sheet__hint{margin:0 0 var(--space-3)}
.review-sheet__submit{margin:0;width:100%;min-height:48px;padding:var(--space-3);line-height:1.5;font-size:var(--font-size-lg);font-weight:600;color:var(--text-inverse);background:var(--teacher-600);border-radius:var(--radius-lg)}
.review-sheet__submit.is-return{background:var(--danger-600)}
.review-sheet button[disabled]{opacity:.55}
.review-sheet button:focus-visible,.review-sheet input:focus-visible,.review-sheet textarea:focus-visible{outline:2px solid var(--teacher-700);outline-offset:2px}
.pr__context{display:flex;flex-direction:column;gap:var(--space-3)}.pr__batch{display:flex;align-items:center;justify-content:space-between;gap:var(--space-3);padding:var(--space-3)}.pr__batch-copy{min-width:0;display:flex;flex-direction:column;gap:3px}.pr__eyebrow{font-size:var(--font-size-xs);color:var(--text-tertiary)}.pr__batch-name{font-size:var(--font-size-md);font-weight:600;color:var(--text-primary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.pr__picker{flex-shrink:0}.pr__pick-val{color:var(--teacher-700);font-size:var(--font-size-sm);white-space:nowrap}.pr__arrow{margin-left:4px;color:var(--text-tertiary)}.pr__summary{display:flex;align-items:stretch;gap:var(--space-3);padding:var(--space-3)}.pr__summary-main{flex:1;min-width:0}.pr__summary-label{display:block;font-size:var(--font-size-xs);color:var(--text-tertiary)}.pr__summary-value{display:flex;align-items:baseline;gap:4px;margin-top:4px}.pr__summary-value text:first-child{font-size:34px;line-height:1;font-weight:700;color:var(--teacher-700)}.pr__summary-value text:last-child{font-size:var(--font-size-sm);color:var(--text-secondary)}.pr__summary-note{display:block;margin-top:8px;font-size:var(--font-size-xs);line-height:1.5;color:var(--text-secondary)}.pr__summary-metrics{width:48%;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));background:var(--gray-50);border-radius:var(--radius-md);overflow:hidden}.pr__metric{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;padding:10px 4px;border-left:1px solid var(--border-light)}.pr__metric:first-child{border-left:0}.pr__metric text:first-child{font-size:var(--font-size-lg);font-weight:700;color:var(--text-primary)}.pr__metric text:last-child{font-size:10px;color:var(--text-tertiary)}.pr__list{padding-top:0}.pr{display:flex;flex-direction:column;gap:var(--space-3);padding:var(--space-3)}.pr.is-expanded{border-color:var(--teacher-200,#bfdbfe)}.pr__head{align-items:flex-start}.pr__identity{min-width:0}.pr__sub{display:block;font-size:var(--font-size-xs);color:var(--text-tertiary);margin-top:3px}.pr__head-right{flex-shrink:0;display:flex;flex-direction:column;align-items:flex-end;gap:6px}.pr__chevron{font-size:10px;color:var(--teacher-700)}.pr__brief{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;padding:var(--space-2);background:var(--gray-50);border-radius:var(--radius-md)}.pr__brief>view{min-width:0;display:flex;flex-direction:column;gap:3px}.pr__brief text:first-child{font-size:10px;color:var(--text-tertiary)}.pr__brief text:last-child{font-size:var(--font-size-xs);font-weight:600;color:var(--text-primary);word-break:break-word}.pr__loading{padding:var(--space-4) 0;text-align:center}.pr__meta{display:flex;flex-wrap:wrap;justify-content:space-between;gap:6px 12px;font-size:var(--font-size-xs);color:var(--text-tertiary)}.pr__content{background:var(--gray-50);border-radius:var(--radius-md);padding:var(--space-3);max-height:420px;overflow:auto}.pr__content-label{display:block;margin-bottom:7px;font-size:var(--font-size-xs);font-weight:600;color:var(--text-secondary)}.pr__content-text{font-size:var(--font-size-sm);color:var(--text-primary);line-height:1.75;white-space:pre-wrap;word-break:break-word}.pr__attachments{display:flex;flex-direction:column;gap:8px}.pr__attachment{display:flex;align-items:center;gap:10px;padding:10px 12px;border:1px solid var(--border-light);border-radius:var(--radius-md);background:var(--bg-card)}.pr__attachment-meta{display:block;margin-top:3px;font-size:10px;color:var(--text-tertiary)}.pr__open{font-size:var(--font-size-xs);color:var(--teacher-700);flex-shrink:0}.pr__next{display:flex;gap:10px;padding:10px 12px;border-radius:var(--radius-md);background:var(--teacher-50,#eff6ff)}.pr__next-label{flex-shrink:0;font-size:var(--font-size-xs);font-weight:600;color:var(--text-secondary)}.pr__next-text{font-size:var(--font-size-xs);line-height:1.5;color:var(--text-secondary)}.pr__actions{display:flex;gap:var(--space-2)}.pr__reject,.pr__approve{min-height:var(--touch-target-min);border-radius:var(--radius-md);font-size:var(--font-size-md)}.pr__reject{border:1px solid var(--danger-500);background:var(--bg-card);color:var(--danger-600)}.pr__approve{border:none;background:var(--teacher-600);color:#fff}.pr__reject::after,.pr__approve::after{border:none}.pr__reject[disabled],.pr__approve[disabled]{opacity:.55}@media(max-width:360px){.pr__summary{flex-direction:column}.pr__summary-metrics{width:100%}.pr__brief{grid-template-columns:1fr}.pr__batch{align-items:flex-start}}
.teacher-period-reports .pr__context,.teacher-period-reports .pr__list{width:100%;max-width:760px;margin:0 auto;box-sizing:border-box}.teacher-period-reports .card{border-radius:8px;box-shadow:none}.teacher-period-reports button{min-height:44px;font-size:15px}.pr__batch{padding:4px 0 12px;border-bottom:1px solid var(--border-light)}.pr__batch-name{font-size:15px;line-height:22px;margin:0;overflow-wrap:anywhere}.pr__pick-val,.pr__filters picker>view,.pr__filters input{display:flex;align-items:center;min-height:44px;font-size:14px;line-height:22px}.pr__summary-label,.pr__summary-note,.pr__metric text:last-child,.pr__sub,.pr__chevron,.pr__brief text,.pr__meta,.pr__content-label,.pr__content-text,.pr__attachment-meta,.pr__open{font-size:14px;line-height:22px}.pr__head{min-height:44px}.pr__head-right{flex-shrink:0}.pr__attachment{min-height:44px}.pr__summary{flex-wrap:wrap}.pr__summary-main{flex-basis:100%}.pr__summary-metrics{width:100%}.review-sheet__hint,.review-sheet__field,.review-sheet__comment{font-size:14px;line-height:22px}
</style>
