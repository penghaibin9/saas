<template>
  <view class="internship-surface mobile-page mobile-student page-wrap pr">
    <MobileNavBar :title="typeLabel" show-back :fallback-url="'/pages/student-internship/index' + (batchId ? '?batchId=' + encodeURIComponent(batchId) : '')" />
    <MobileGlobalState :state="pageState" :description="loadError" @retry="load">
      <view class="page-pad stack" v-if="loaded">
        <view v-if="showTypePick" class="card">
          <view class="pr__types">
            <text
              v-for="t in typeOptions"
              :key="t.v"
              class="pr__type"
              :class="{ 'is-on': reportType === t.v }"
              @click="pickType(t.v)"
            >{{ t.l }}</text>
          </view>
        </view>
        <view v-if="receipt" class="card pr__receipt">
          <text class="t-md t-bold">{{ receipt.actionLabel }}</text>
          <text>报告编号：{{ receipt.id }} · 第 {{ receipt.version }} 版 · {{ receipt.statusLabel }}</text>
          <text>{{ receipt.nextStep }}</text>
        </view>
        <MobileInlineAlert v-if="currentReport && currentReport.status !== 'RETURNED'" type="info"
          :description="`${currentReport.periodLabel === typeLabel ? '' : currentReport.periodLabel + ' · '}${currentReport.statusLabel}`" />
        <MobileInlineAlert v-else-if="currentReport" type="warning"
          :description="`教师退回：${currentReport.reviewComment || '请按要求修改正文后重新提交'}`" />
        <MobileInlineAlert v-if="historyMode && !currentReport" type="info" description="历史报告仅供查阅，可从下方记录打开原文。" />
        <view v-if="!historyMode || currentReport || conflict" class="card stack">
          <view v-if="reportType !== 'SUMMARY'" class="pr__field">
            <text class="pr__label">{{ periodLabel }} <text class="pr__req">*</text></text>
            <picker class="mobile-picker" mode="date" :fields="reportType === 'MONTHLY' ? 'month' : 'day'" :value="form.periodKey" :disabled="!canChangePeriod" @change="changePeriod($event.detail.value)"><view class="pr__input">{{ form.periodKey || periodPlaceholder }}</view></picker>
          </view>
          <view class="pr__field">
            <text class="pr__label">正文 <text class="pr__req">*</text></text>
            <textarea v-if="canEditReport" v-model="form.content" class="mobile-textarea pr__textarea" auto-height :cursor-spacing="120" :maxlength="-1" :disabled="submitting" :placeholder="contentPlaceholder" @input="saveDraft" /><text v-else class="pr__read-body" selectable>{{ form.content }}</text>
            <text v-if="canEditReport" class="pr__count">{{ (form.content || '').length }} / 至少 {{ minimum }} 字</text>
          </view>
          <view class="pr__field">
            <view class="row-between">
              <text class="pr__label">附件</text>
              <text v-if="canEditReport" class="pr__count">图片≤{{ rules.maxImages }}，视频≤{{ rules.maxVideos }}</text>
            </view>
            <view v-for="(file, index) in form.attachments" :key="file.fileId" class="pr__attachment">
              <view class="flex-1" @click="openAttachment(file)">
                <text class="t-sm t-bold">{{ file.fileName || '附件' }}</text>
                <text class="pr__attachment-meta">{{ file.kindLabel }} · {{ file.statusText }}</text>
              </view>
              <text v-if="canEditReport" class="pr__remove" @click.stop="removeAttachment(index)">删除</text>
            </view>
            <view v-if="canEditReport" class="pr__attach-actions">
              <button class="mobile-control pr__attach-btn" :disabled="!canEditReport || uploading || submitting" @click="addAttachment('image')">添加图片</button>
              <button class="mobile-control pr__attach-btn" :disabled="!canEditReport || uploading || submitting" @click="addAttachment('video')">添加视频</button>
              <button class="mobile-control pr__attach-btn" :disabled="!canEditReport || uploading || submitting" @click="addAttachment('file')">添加文件</button>
            </view>
            <text v-if="currentReport && currentReport.status !== 'RETURNED'" class="pr__hint">本次提交的正文和附件只读；教师退回后可在原单修改。</text>
            <text v-if="!canEditReport && !form.attachments.length" class="pr__hint">本次未上传附件。</text>
            <button v-if="form.attachments.length" class="mobile-control pr__attach-btn" :disabled="scanning || uploading || submitting" @click="refreshAttachments">{{ scanning ? '正在读取扫描结果…' : '查看附件安全扫描结果' }}</button>
            <text v-if="!attachmentsReady" class="pr__count">附件安全就绪前不能提交，正文和附件会保留。</text>
          </view>
        </view>
        <view class="card stack">
          <text class="card-title">我的{{ typeLabel }}记录</text>
          <text v-if="!typeReports.length" class="pr__empty">暂无记录</text>
          <view v-for="item in typeReports" :key="item.id" class="pr__record" @click="selectRecord(item)">
            <view><text>{{ item.periodLabel }}</text><text>第 {{ item.reportVersion || 1 }} 版 · {{ item.statusLabel }}</text></view>
            <text>{{ item.reviewComment || '等待教师批阅' }}</text>
          </view>
          <text v-if="typeReports.length || reportsTotal">已读取 {{ typeReports.length }} / {{ reportsTotal }} 篇</text>
          <button class="mobile-control" v-if="hasMore" :disabled="loadingMore" @click="loadMore">{{ loadingMore ? '正在读取…' : '加载更多历史报告' }}</button>
        </view>
        <view v-if="detailReading || detailError" class="card"><text>{{ detailReading ? '正在读取原报告…' : detailError }}</text></view>
        <view v-if="selectedDetail" class="card stack">
          <text class="card-title">原报告与批阅历史 · {{ selectedDetail.periodLabel }}</text>
          <text>第 {{ selectedDetail.reportVersion }} 次提交 · {{ selectedDetail.statusLabel }}</text>
          <button class="mobile-control" :disabled="downloading" @click="downloadReport">{{ downloading ? '正在生成…' : '下载当前提交版报告文书' }}</button>
          <text v-if="selectedDetail.review?.summaryScore != null">总结评分：{{ selectedDetail.review.summaryScore }}分（百分制）</text>
          <text v-else-if="selectedDetail.review?.ratingLevel">教师评价：{{ selectedDetail.review.ratingLabel }}</text>
          <view v-for="version in selectedDetail.immutableVersions" :key="version.versionNo" class="pr__record">
            <text @click="historyVersion = historyVersion === version.versionNo ? null : version.versionNo">第 {{ version.versionNo }} 次提交 · {{ version.review?.actionLabel || '等待批阅' }} · {{ historyVersion === version.versionNo ? '收起' : '查看正文与附件' }}</text>
            <view v-if="historyVersion === version.versionNo" class="stack">
              <text class="pr__history-body">{{ version.content }}</text>
              <text v-if="version.review?.summaryScore != null">总结评分：{{ version.review.summaryScore }}分（百分制）</text>
              <text v-else-if="version.review?.ratingLevel">教师评价：{{ version.review.ratingLabel }}</text>
              <text v-if="version.review?.comment">教师意见：{{ version.review.comment }}</text>
              <text v-for="file in version.attachments || []" :key="file.fileId" @click="openAttachment(file)">{{ file.fileName || '查看该次附件' }}</text>
            </view>
          </view>
        </view>
        <view v-if="conflict" class="card stack">
          <text>原报告已有变化，填写内容和原版本已保留。请读取最新原单并核对。</text>
          <button class="mobile-control" @click="rereadConflict">读取最新原单核对</button>
          <text v-if="latestDetail">最新正文：{{ latestDetail.content }}；教师意见：{{ latestDetail.reviewComment || '暂无' }}</text>
          <button class="mobile-control" v-if="latestDetail?.status === 'RETURNED'" @click="continueAfterConflict">已核对，保留填写内容继续修改</button>
        </view>
        <MobileInlineAlert v-if="draftStorageError" type="warning" :description="draftStorageError" />
        <ReportFilePreview ref="reportPreview" />
      </view>
    </MobileGlobalState>
    <MobileSafeAreaBar v-if="loaded && pageState === 'ready' && canEditReport">
      <button class="mobile-control btn btn-primary flex-1" :disabled="submitting || !canSubmit" @click="submit">{{ submitting ? '提交中…' : (currentReport ? '重新提交' : '提交') + typeLabel }}</button>
    </MobileSafeAreaBar>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import fileSdk from '@/services/fileSdk'
import MobileInlineAlert from '@/components/MobileInlineAlert.vue'
import ReportFilePreview from '@/components/ReportFilePreview.vue'
import { normalizeError } from '@/services/request'
import { processReportView, reportFileState, reportFilesReady, refreshReportFiles } from '@/services/weeklyReportPresentation.mjs'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { useSessionStore } from '@/stores/session'
import { readInternshipDraft, writeInternshipDraft } from '@/services/internshipDraftStorage.mjs'
import { toast } from '@/utils/nav'

const TYPE_LABEL = { DAILY: '日报', MONTHLY: '月报', SUMMARY: '实习总结' }
// 默认结构模板（20-岗位实习预设便捷字段与提示词.md §7.5/§7.9），仅用于新建报告时预填骨架，学生按小节填空
const DEFAULT_TPL = {
  MONTHLY: '一、本月实习概况：\n\n二、主要工作与成果：\n\n三、能力提升：\n\n四、存在问题与改进：\n\n五、下月计划：\n',
  SUMMARY: '一、单位与岗位：\n\n二、工作内容：\n\n三、收获体会：\n\n四、不足与改进：\n'
}

export default {
  components: { MobileInlineAlert, ReportFilePreview },
  data() {
    return {
      pageState: 'loading', loadError: '', loaded: false, submitting: false, uploading: false, scanning: false, showTypePick: false,
      reportType: 'DAILY',
      typeOptions: [
        { v: 'DAILY', l: '日报' }, { v: 'MONTHLY', l: '月报' }, { v: 'SUMMARY', l: '实习总结' }
      ],
      form: { periodKey: '', content: '', attachments: [] }, drafts: {}, reports: [], receipt: null,
      selectedDetail: null, detailReading: false, detailError: '', detailSequence: 0, historyVersion: null,
      conflict: false, latestDetail: null, focusReportId: '', draftStorageError: '',
      reportsTotal: 0, reportPageSize: 20, loadedPages: [], loadingMore: false, downloading: false,
      rules: { dailyMinWords: 30, weeklyMinWords: 30, monthlyMinWords: 100, summaryMinWords: 300, maxImages: 9, maxVideos: 3 },
      batchId: '', internshipId: '', historyMode: false, loadSequence: 0, hidden: false, generation: currentSessionGeneration()
    }
  },
  computed: {
    typeLabel() { return TYPE_LABEL[this.reportType] || '过程报告' },
    periodLabel() { return this.reportType === 'DAILY' ? '日期' : '月份' },
    periodPlaceholder() {
      return this.reportType === 'DAILY' ? '如 2026-07-10' : '如 2026-07'
    },
    contentPlaceholder() {
      return `请填写${this.typeLabel}正文`
    },
    minimum() {
      return {
        DAILY: Number(this.rules.dailyMinWords || 30),
        MONTHLY: Number(this.rules.monthlyMinWords || 100),
        SUMMARY: Number(this.rules.summaryMinWords || 300)
      }[this.reportType] || 30
    },
    typeReports() { return this.reports.filter((item) => item.reportType === this.reportType) },
    hasMore() { return this.loadedPages.length * this.reportPageSize < this.reportsTotal },
    currentReport() {
      const period = this.reportType === 'SUMMARY' ? 'FINAL' : this.form.periodKey
      return this.typeReports.find((item) => item.periodKey === period) || null
    },
    attachmentsReady() { return reportFilesReady(this.form.attachments) },
    draftKey() { return [this.batchId, this.internshipId, this.reportType, this.form.periodKey].join(':') },
    canChangePeriod() { return this.loaded && this.pageState === 'ready' && !this.hidden && this.generation === currentSessionGeneration() &&
      !this.submitting && !this.uploading && !this.scanning && !this.detailReading },
    canEditReport() { return this.loaded && this.pageState === 'ready' && !this.historyMode && !this.hidden && this.generation === currentSessionGeneration() && !this.detailReading &&
      (!this.currentReport || this.currentReport.status === 'RETURNED') },
    canSubmit() {
      return this.pageState === 'ready' && !this.historyMode && !this.hidden && this.generation === currentSessionGeneration() && !this.detailReading && !this.detailError && !this.conflict && !this.uploading && !this.scanning && this.attachmentsReady &&
        (!this.currentReport || (this.currentReport.status === 'RETURNED' && this.selectedDetail?.id === this.currentReport.id)) &&
        (this.reportType === 'SUMMARY' || !!this.form.periodKey) && this.form.content.trim().length >= this.minimum
    }
  },
  onLoad(q) {
    this.requestedBatchId = String(q?.batchId || '')
    this.focusReportId = String(q?.reportId || '')
    const raw = String((q && q.type) || '').toLowerCase()
    if (raw === 'monthly') this.reportType = 'MONTHLY'
    else if (raw === 'summary') this.reportType = 'SUMMARY'
    else if (raw === 'daily') this.reportType = 'DAILY'
    else this.reportType = 'DAILY'
    // 无 type 参数时提供类型切换，避免永远默认日报
    this.showTypePick = !raw
    uni.setNavigationBarTitle({ title: '填写' + this.typeLabel })
    this.prepareForm(this.reportType)
    this.load()
  },
  onShow() {
    const wasHidden = this.hidden
    this.hidden = false
    if (this.generation !== currentSessionGeneration()) {
      this.form = { periodKey: '', content: '', attachments: [] }; this.drafts = {}; this.reports = []; this.receipt = null; this.loaded = false
      this.selectedDetail = null; this.latestDetail = null; this.conflict = false; this.detailSequence++; this.detailReading = false
      this.batchId = ''; this.internshipId = ''; this.generation = currentSessionGeneration(); this.prepareForm(this.reportType); this.load()
    } else if (wasHidden && this.pageState === 'loading') this.load()
  },
  onHide() { this.saveDraft(); this.hidden = true; this.loadSequence += 1; this.detailSequence++; this.detailReading = false; this.latestDetail = null; this.$refs.reportPreview?.reset() },
  onUnload() { this.hidden = true; this.loadSequence += 1; this.detailSequence++; this.drafts = {}; this.$refs.reportPreview?.reset() },
  onReachBottom() { this.loadMore() },
  methods: {
    persistDrafts() {
      const session = useSessionStore()
      if (!session.logged || session.isTeacher || !session.identity?.userId || this.generation !== currentSessionGeneration()) return
      try {
        writeInternshipDraft(session, 'process-report', [this.batchId, this.internshipId], { activeKey: this.draftKey, drafts: this.drafts })
        this.draftStorageError = ''
      } catch { this.draftStorageError = '本机草稿保存失败，刷新前请复制正文并保留附件名称。' }
    },
    restoreDrafts() {
      const session = useSessionStore(), saved = readInternshipDraft(session, 'process-report', [this.batchId, this.internshipId])
      if (!session.logged || session.isTeacher || !saved) return false
      this.drafts = saved.drafts || {}
      const draft = saved.drafts?.[saved.activeKey]
      if (!saved.activeKey?.startsWith([this.batchId, this.internshipId, this.reportType, ''].join(':')) || !draft?.form || !Array.isArray(draft.form.attachments)) return false
      this.form = JSON.parse(JSON.stringify(draft.form)); this.selectedDetail = draft.detail; this.conflict = !!draft.conflict
      if (!this.focusReportId && draft.detail?.id) this.focusReportId = String(draft.detail.id)
      return true
    },
    saveDraft() {
      if (this.loaded && this.pageState === 'ready' && !this.hidden && !this.detailReading && !this.submitting && this.generation === currentSessionGeneration() && (!this.currentReport || this.currentReport.status === 'RETURNED' || this.conflict) &&
        (this.selectedDetail || this.form.content !== (DEFAULT_TPL[this.reportType] || '') || this.form.attachments.length)) {
        const detail = this.selectedDetail?.reportType === this.reportType && this.selectedDetail?.periodKey === this.form.periodKey ? this.selectedDetail : null
        this.drafts[this.draftKey] = { form: JSON.parse(JSON.stringify(this.form)), detail, conflict: this.conflict }
        this.persistDrafts()
      }
    },
    prepareForm(v) {
      const d = new Date()
      this.form.periodKey = v === 'DAILY'
        ? `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
        : v === 'MONTHLY' ? `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}` : 'FINAL'
      this.form.content = DEFAULT_TPL[v] || ''
      this.form.attachments = []
    },
    async load() {
      const sequence = ++this.loadSequence
      const generation = currentSessionGeneration()
      let hadDraft = this.loaded && !this.selectedDetail && !!(this.form.content.trim() || this.form.attachments.length)
      this.pageState = 'loading'
      this.loadError = ''
      this.loadingMore = false
      try {
        const dashboard = await studentApi.getInternship(this.requestedBatchId)
        if (this.hidden || generation !== currentSessionGeneration() || sequence !== this.loadSequence) return
        if (this.loaded && (String(this.batchId) !== String(dashboard.batchId || '') || String(this.internshipId) !== String(dashboard.recordId || ''))) {
          this.drafts = {}; this.selectedDetail = null; this.latestDetail = null; this.conflict = false; this.receipt = null
          this.prepareForm(this.reportType); this.detailSequence++; this.$refs.reportPreview?.reset()
        }
        this.historyMode = !!dashboard.historyMode
        this.batchId = dashboard.batchId || ''
        this.internshipId = dashboard.recordId || ''
        if (!this.loaded) hadDraft = this.restoreDrafts() || hadDraft
        const result = await studentApi.getInternshipProcessReports(this.batchId, this.internshipId, 1, this.reportPageSize, this.reportType, this.focusReportId)
        if (this.hidden || generation !== currentSessionGeneration() || sequence !== this.loadSequence) return
        this.reports = []; this.loadedPages = []; this.applyReportPage(result)
        if (this.focusReportId && Number(result.focusPage) > 1) {
          const focusedPage = await studentApi.getInternshipProcessReports(this.batchId, this.internshipId, Number(result.focusPage), this.reportPageSize, this.reportType)
          if (this.hidden || generation !== currentSessionGeneration() || sequence !== this.loadSequence) return
          this.applyReportPage(focusedPage)
        }
        this.rules = { ...this.rules, ...(result.rules || {}) }
        const current = this.currentReport
        this.loaded = true
        this.pageState = 'ready'
        if (this.focusReportId) {
          const id = this.focusReportId
          await this.selectRecord({ id })
          if (this.selectedDetail?.id === id) this.focusReportId = ''
        } else if (current && !this.selectedDetail && !hadDraft) await this.selectRecord(current)
        else if (current && !this.selectedDetail && hadDraft) this.conflict = true
        else if (current && this.selectedDetail?.id === current.id && current.version !== this.selectedDetail.version) this.conflict = true
        if (this.form.attachments.length) await this.refreshAttachments()
      } catch (e) {
        if (!this.hidden && generation === currentSessionGeneration() && sequence === this.loadSequence) {
          const shown = normalizeError(e)
          this.pageState = shown.pageState || 'error'; this.loadError = shown.text
        }
      }
    },
    applyReportPage(result) {
      const items = (result.items || []).map(processReportView)
      const ids = new Set(items.map(row => String(row.id)))
      this.reports = [...this.reports.filter(row => !ids.has(String(row.id))), ...items]
      const page = Number(result.page || 1)
      if (!this.loadedPages.includes(page)) this.loadedPages.push(page)
      this.reportsTotal = Number(result.total ?? this.reports.length)
    },
    async loadMore() {
      if (!this.hasMore || this.loadingMore || this.pageState !== 'ready') return
      const page = Array.from({ length: Math.ceil(this.reportsTotal / this.reportPageSize) }, (_,i) => i+1).find(value => !this.loadedPages.includes(value))
      const sequence = this.loadSequence, generation = currentSessionGeneration(), type = this.reportType
      this.loadingMore = true
      try {
        const result = await studentApi.getInternshipProcessReports(this.batchId, this.internshipId, page, this.reportPageSize, type)
        if (!this.hidden && sequence === this.loadSequence && generation === currentSessionGeneration() && type === this.reportType) this.applyReportPage(result)
      } catch { if (!this.hidden && sequence === this.loadSequence) toast('历史报告读取失败，填写内容已保留，请重试') }
      finally { if (sequence === this.loadSequence) this.loadingMore = false }
    },
    async downloadReport() {
      if (this.downloading || !this.selectedDetail) return
      const id = this.selectedDetail.id, sequence = this.detailSequence, generation = currentSessionGeneration()
      this.downloading = true
      try {
        await studentApi.downloadInternshipReportPdf(this.batchId, this.internshipId, 'PROCESS', id,
          () => !this.hidden && sequence === this.detailSequence && generation === currentSessionGeneration())
      } catch { if (!this.hidden && sequence === this.detailSequence) toast('报告文书下载未完成，请重试') }
      finally { this.downloading = false }
    },
    pickType(v) {
      if (this.submitting || this.uploading || this.scanning || this.detailReading) return
      if (v === this.reportType) return
      this.saveDraft()
      this.reportType = v
      this.selectedDetail = null; this.latestDetail = null; this.conflict = false; this.detailSequence++; this.detailReading = false; this.detailError = ''
      uni.setNavigationBarTitle({ title: '填写' + this.typeLabel })
      this.prepareForm(v)
      const draft = this.drafts[this.draftKey]
      if (draft) { this.form = JSON.parse(JSON.stringify(draft.form)); this.selectedDetail = draft.detail; this.conflict = draft.conflict }
      this.reports = []; this.loadedPages = []; this.reportsTotal = 0; this.load()
    },
    async changePeriod(value) {
      if (!this.canChangePeriod || this.reportType === 'SUMMARY' || String(value) === this.form.periodKey) return
      this.saveDraft()
      this.detailSequence++; this.selectedDetail = null; this.latestDetail = null; this.conflict = false
      this.detailError = ''; this.historyVersion = null; this.receipt = null; this.$refs.reportPreview?.reset()
      this.form = { periodKey: String(value), content: DEFAULT_TPL[this.reportType] || '', attachments: [] }
      const draft = this.drafts[this.draftKey]
      if (draft) { this.form = JSON.parse(JSON.stringify(draft.form)); this.selectedDetail = draft.detail; this.conflict = !!draft.conflict }
      if (this.currentReport) await this.selectRecord(this.currentReport)
      else this.saveDraft()
    },
    async selectRecord(item, preserveDraft = false) {
      if (this.submitting || this.uploading || !item?.id) return
      if (!preserveDraft) this.saveDraft()
      const sequence = ++this.detailSequence, generation = currentSessionGeneration(), batchId = this.batchId, internshipId = this.internshipId
      const current = () => !this.hidden && sequence === this.detailSequence && generation === currentSessionGeneration() && batchId === this.batchId && internshipId === this.internshipId
      this.detailReading = true; this.detailError = ''
      if (!preserveDraft) this.selectedDetail = null
      try {
        const data = await studentApi.getInternshipProcessReportDetail(item.id, batchId, internshipId)
        if (!current()) return
        if (String(data?.id) !== String(item.id) || String(data.batchId) !== String(batchId) || String(data.internshipId) !== String(internshipId)) throw new Error('原报告所属实习记录不一致')
        const detail = processReportView(data)
        this.reports = this.reports.some(row => row.id === detail.id) ? this.reports.map(row => row.id === detail.id ? detail : row) : [...this.reports, detail]
        if (preserveDraft) { this.latestDetail = detail; return }
        this.selectedDetail = detail; this.reportType = detail.reportType; this.historyVersion = null
        this.conflict = false; this.latestDetail = null
        this.form.periodKey = detail.periodKey; this.form.content = detail.content || ''
        this.form.attachments = (detail.attachments || []).map(reportFileState)
        const draft = this.drafts[this.draftKey]
        if (draft) {
          this.form = JSON.parse(JSON.stringify(draft.form)); this.selectedDetail = draft.detail
          this.conflict = draft.conflict || !draft.detail || draft.detail.version !== detail.version
          if (this.conflict) this.latestDetail = detail
        }
        await this.refreshAttachments()
      } catch (error) { if (current()) this.detailError = normalizeError(error).text + '，填写内容已保留' }
      finally { if (current()) this.detailReading = false }
    },
    continueAfterConflict() {
      if (this.hidden || this.generation !== currentSessionGeneration() || this.detailReading || this.submitting || !this.conflict || this.latestDetail?.status !== 'RETURNED' ||
        (this.selectedDetail && this.latestDetail.id !== this.selectedDetail.id) || this.latestDetail.reportType !== this.reportType || this.latestDetail.periodKey !== this.form.periodKey) return
      this.selectedDetail = this.latestDetail; this.latestDetail = null; this.conflict = false
      this.saveDraft()
    },
    async rereadConflict() {
      if (!this.conflict || this.submitting || this.detailReading) return
      const generation = currentSessionGeneration(), sequence = this.loadSequence, batchId = this.batchId, internshipId = this.internshipId
      const current = () => !this.hidden && generation === currentSessionGeneration() && sequence === this.loadSequence && batchId === this.batchId && internshipId === this.internshipId
      this.latestDetail = null
      try {
        const original = this.selectedDetail || this.currentReport
        if (!original) { this.detailError = '未读到该周期的原报告，填写内容已保留，请重新读取'; return }
        await this.selectRecord(original, true)
      } catch (error) { if (current()) this.detailError = '最新原报告读取失败，填写内容已保留，请重试' }
    },
    async addAttachment(kind = 'file') {
      if (!this.canEditReport || this.uploading || this.submitting) return
      const form = this.form, generation = currentSessionGeneration(), internshipId = this.internshipId, reportType = this.reportType, period = form.periodKey
      const current = () => !this.hidden && form === this.form && generation === currentSessionGeneration() && internshipId === this.internshipId && reportType === this.reportType && period === this.form.periodKey
      this.uploading = true
      try {
        const picked = await fileSdk.choose({ kind })
        if (!picked || !current()) return
        const uploaded = await fileSdk.upload(picked, {
          bizType: 'INTERNSHIP_REPORT',
          bizId: internshipId || ''
        })
        if (!current()) return
        if (!uploaded?.fileId) throw new Error('上传结果缺少文件编号')
        this.form.attachments = [...this.form.attachments, reportFileState(uploaded)]
        this.saveDraft()
      } catch (e) {
        if (current()) toast(normalizeError(e).text)
      } finally {
        this.uploading = false
      }
    },
    removeAttachment(index) {
      if (!this.canEditReport || this.submitting || this.uploading || this.scanning) return
      this.form.attachments = this.form.attachments.filter((_, i) => i !== index)
      this.saveDraft()
    },
    async refreshAttachments() {
      if (this.scanning || this.uploading) return
      const files = this.form.attachments, sequence = this.loadSequence, generation = currentSessionGeneration()
      this.scanning = true
      try {
        const updated = await refreshReportFiles(files, id => fileSdk.metadata(id), () => !this.hidden && files === this.form.attachments && sequence === this.loadSequence && generation === currentSessionGeneration())
        if (updated) { this.form.attachments = updated; this.saveDraft() }
      } catch (error) { if (!this.hidden && generation === currentSessionGeneration()) toast('扫描结果读取失败，正文和附件已保留，请重试') }
      finally { this.scanning = false }
    },
    async openAttachment(file) {
      await this.$refs.reportPreview.open(file)
      if (!this.hidden) uni.pageScrollTo({ selector: '.report-preview', duration: 200 })
    },
    async submit() {
      if (this.submitting || !this.canSubmit) return
      this.submitting = true
      const current = this.currentReport
      const form = this.form, generation = currentSessionGeneration()
      try {
        const result = await studentApi.submitInternshipProcessReport({
          batchId: this.batchId, internshipId: this.internshipId,
          reportType: this.reportType,
          periodKey: this.reportType === 'SUMMARY' ? 'FINAL' : this.form.periodKey,
          content: this.form.content.trim(),
          attachmentFileIds: this.form.attachments.map((file) => file.fileId),
          expectedVersion: current ? this.selectedDetail.version : 0
        })
        if (this.hidden || form !== this.form || generation !== currentSessionGeneration()) return
        delete this.drafts[this.draftKey]
        this.persistDrafts()
        this.receipt = {
          actionLabel: current ? `${this.typeLabel}已重新提交` : `${this.typeLabel}已提交`,
          id: result.id, version: result.reportVersion || 1, statusLabel: '待批阅',
          nextStep: '等待指导教师批阅；退回后可从本页继续修改。'
        }
        this.selectedDetail = null; this.conflict = false; this.submitting = false; this.focusReportId = String(result.id)
        this.prepareForm(this.reportType)
        await this.load()
      } catch (e) {
        if (!this.hidden && form === this.form && generation === currentSessionGeneration() && normalizeError(e).kind === 'conflict') this.conflict = true
        if (!this.hidden && form === this.form && generation === currentSessionGeneration()) toast(normalizeError(e).text + '，正文已保留')
      } finally { this.submitting = false; if (this.conflict) this.saveDraft() }
    }
  }
}
</script>

<style scoped>
.pr__history-body { white-space: pre-wrap; overflow-wrap: anywhere; }
.pr__hint { display: block; font-size: var(--font-size-base); color: var(--text-tertiary); margin-top: var(--space-2); }
.pr__receipt { display: flex; flex-direction: column; gap: 4px; border-color: #86efac; background: #f0fdf4; color: #166534; font-size: var(--font-size-base); }
.pr__empty { color: var(--text-tertiary); font-size: var(--font-size-base); }
.pr__record { display: flex; flex-direction: column; gap: 5px; padding: 10px 0; border-top: 1px solid var(--border-light); }
.pr__record view { display: flex; justify-content: space-between; gap: 10px; font-size: var(--font-size-base); }
.pr__record view text:last-child, .pr__record > text { color: var(--text-tertiary); font-size: var(--font-size-base); }
.pr__types { display: flex; gap: 8px; margin-top: 10px; flex-wrap: wrap; }
.pr__type { padding: 6px 12px; border-radius: var(--radius-md); background: var(--gray-100); font-size: var(--font-size-base); color: var(--text-secondary); }
.pr__type.is-on { background: var(--brand-primary); color: #fff; }
.pr__field { display: flex; flex-direction: column; gap: 6px; }
.pr__label { font-size: var(--font-size-base); color: var(--text-secondary); }
.pr__req { color: var(--danger-500); }
.pr__input { border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: 10px 12px; font-size: var(--font-size-base); }
.pr__textarea { border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: 10px 12px; min-height: 160px; font-size: var(--font-size-base); width: 100%; box-sizing: border-box; }
.pr__count { font-size: var(--font-size-base); color: var(--text-tertiary); text-align: right; }
.pr__attachment { display: flex; align-items: center; gap: 10px; padding: 10px; border: 1px solid var(--border-light); border-radius: var(--radius-md); }
.pr__attachment-meta { display: block; margin-top: 3px; font-size: var(--font-size-base); color: var(--text-tertiary); }
.pr__remove { flex-shrink: 0; font-size: var(--font-size-base); color: var(--danger-600); }
.pr__attach-btn { margin: 0; min-height: var(--touch-target-min); border: 1px dashed var(--border-base); background: var(--bg-card); color: var(--brand-primary); font-size: var(--font-size-base); }
.pr__attach-btn::after { border: none; }
.pr__attach-actions{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.pr__attach-actions .pr__attach-btn{padding:0 4px;font-size:14px;line-height:44px}.pr__input{height:44px;min-height:44px;box-sizing:border-box;padding:0 12px}.pr__count{line-height:1.6}.pr__remove{min-height:44px;display:flex;align-items:center}.pr__type{min-height:44px;display:flex;align-items:center;box-sizing:border-box}.pr__types{margin-top:0}.pr__textarea{min-height:260px;height:auto}.pr__read-body{display:block;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.8;font-size:var(--font-size-md)}
</style>
