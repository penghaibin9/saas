<template>
  <view class="page-wrap pr">
    <MobileGlobalState :state="pageState" @retry="load">
      <view class="page-pad stack" v-if="loaded">
        <view class="card">
          <text class="card-title">{{ typeLabel }}</text>
          <text class="pr__hint">提交后由指导教师批阅，退回后可在原报告上修改重交。</text>
          <view v-if="showTypePick" class="pr__types">
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
          :description="`${typeLabel} ${currentReport.periodLabel} 已提交，当前状态：${currentReport.statusLabel}。`" />
        <MobileInlineAlert v-else-if="currentReport" type="warning"
          :description="`教师退回：${currentReport.reviewComment || '请按要求修改正文后重新提交'}`" />
        <view class="card stack">
          <view v-if="reportType !== 'SUMMARY'" class="pr__field">
            <text class="pr__label">{{ periodLabel }} <text class="pr__req">*</text></text>
            <input v-model="form.periodKey" class="pr__input" :placeholder="periodPlaceholder" />
          </view>
          <view class="pr__field">
            <text class="pr__label">正文 <text class="pr__req">*</text></text>
            <textarea v-model="form.content" class="pr__textarea" maxlength="8000" :placeholder="contentPlaceholder" />
            <text class="pr__count">{{ (form.content || '').length }} / 至少 {{ minimum }} 字</text>
          </view>
          <view class="pr__field">
            <view class="row-between">
              <text class="pr__label">图片/视频附件</text>
              <text class="pr__count">图片≤{{ rules.maxImages }}，视频≤{{ rules.maxVideos }}</text>
            </view>
            <view v-for="(file, index) in form.attachments" :key="file.fileId" class="pr__attachment">
              <view class="flex-1" @click="openAttachment(file)">
                <text class="t-sm t-bold">{{ file.fileName || '附件' }}</text>
                <text class="pr__attachment-meta">{{ file.kindLabel }} · {{ file.statusText }}</text>
              </view>
              <text class="pr__remove" @click.stop="removeAttachment(index)">删除</text>
            </view>
            <button class="pr__attach-btn" :disabled="uploading || submitting" @click="addAttachment('image')">添加图片</button>
            <button class="pr__attach-btn" :disabled="uploading || submitting" @click="addAttachment('video')">添加视频</button>
            <button class="pr__attach-btn" :disabled="uploading || submitting" @click="addAttachment('file')">添加文件</button>
            <button v-if="form.attachments.length" class="pr__attach-btn" :disabled="scanning || uploading || submitting" @click="refreshAttachments">{{ scanning ? '正在读取扫描结果…' : '查看附件安全扫描结果' }}</button>
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
        </view>
        <ReportFilePreview ref="reportPreview" />
      </view>
    </MobileGlobalState>
    <MobileSafeAreaBar v-if="loaded && pageState === 'ready'">
      <button class="btn btn-primary flex-1" :disabled="submitting || !canSubmit" @click="submit">{{ submitting ? '提交中…' : (currentReport ? '重新提交' : '提交') + typeLabel }}</button>
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
      pageState: 'loading', loaded: false, submitting: false, uploading: false, scanning: false, showTypePick: false,
      reportType: 'DAILY',
      typeOptions: [
        { v: 'DAILY', l: '日报' }, { v: 'MONTHLY', l: '月报' }, { v: 'SUMMARY', l: '实习总结' }
      ],
      form: { periodKey: '', content: '', attachments: [] }, reports: [], receipt: null,
      rules: { dailyMinWords: 30, weeklyMinWords: 30, monthlyMinWords: 100, summaryMinWords: 300, maxImages: 9, maxVideos: 3 },
      batchId: '', internshipId: '', loadSequence: 0, hidden: false, generation: currentSessionGeneration()
    }
  },
  computed: {
    typeLabel() { return TYPE_LABEL[this.reportType] || '过程报告' },
    periodLabel() { return this.reportType === 'DAILY' ? '日期' : '月份' },
    periodPlaceholder() {
      return this.reportType === 'DAILY' ? '如 2026-07-10' : '如 2026-07'
    },
    contentPlaceholder() {
      return `请填写${this.typeLabel}正文（至少 ${this.minimum} 字）`
    },
    minimum() {
      return {
        DAILY: Number(this.rules.dailyMinWords || 30),
        MONTHLY: Number(this.rules.monthlyMinWords || 100),
        SUMMARY: Number(this.rules.summaryMinWords || 300)
      }[this.reportType] || 30
    },
    typeReports() { return this.reports.filter((item) => item.reportType === this.reportType) },
    currentReport() {
      const period = this.reportType === 'SUMMARY' ? 'FINAL' : this.form.periodKey
      return this.typeReports.find((item) => item.periodKey === period) || null
    },
    attachmentsReady() { return reportFilesReady(this.form.attachments) },
    canSubmit() {
      return this.pageState === 'ready' && !this.hidden && this.generation === currentSessionGeneration() && !this.uploading && !this.scanning && this.attachmentsReady && (!this.currentReport || this.currentReport.status === 'RETURNED') &&
        (this.reportType === 'SUMMARY' || !!this.form.periodKey) && this.form.content.trim().length >= this.minimum
    }
  },
  onLoad(q) {
    this.requestedBatchId = String(q?.batchId || '')
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
      this.form = { periodKey: '', content: '', attachments: [] }; this.reports = []; this.receipt = null; this.loaded = false
      this.batchId = ''; this.internshipId = ''; this.generation = currentSessionGeneration(); this.prepareForm(this.reportType); this.load()
    } else if (wasHidden && this.pageState === 'loading') this.load()
  },
  onHide() { this.hidden = true; this.loadSequence += 1; this.$refs.reportPreview?.reset() },
  onUnload() { this.hidden = true; this.loadSequence += 1; this.$refs.reportPreview?.reset() },
  methods: {
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
      this.pageState = 'loading'
      try {
        const dashboard = await studentApi.getInternship(this.requestedBatchId)
        if (this.hidden || generation !== currentSessionGeneration() || sequence !== this.loadSequence) return
        this.batchId = dashboard.batchId || ''
        this.internshipId = dashboard.recordId || ''
        const result = await studentApi.getInternshipProcessReports(this.batchId, this.internshipId)
        if (this.hidden || generation !== currentSessionGeneration() || sequence !== this.loadSequence) return
        this.reports = (result.items || []).map(processReportView)
        this.rules = { ...this.rules, ...(result.rules || {}) }
        const current = this.currentReport
        if (current?.status === 'RETURNED') {
          this.form.content = current.content || this.form.content
          this.form.attachments = (current.attachments || []).map(reportFileState)
        }
        this.loaded = true
        this.pageState = 'ready'
        if (this.form.attachments.length) await this.refreshAttachments()
      } catch (e) {
        if (!this.hidden && generation === currentSessionGeneration() && sequence === this.loadSequence) this.pageState = 'error'
      }
    },
    pickType(v) {
      if (this.submitting) return
      this.reportType = v
      uni.setNavigationBarTitle({ title: '填写' + this.typeLabel })
      this.prepareForm(v)
      if (this.currentReport) {
        this.form.content = this.currentReport.content || ''
        this.form.attachments = (this.currentReport.attachments || []).map(reportFileState)
        this.refreshAttachments()
      }
    },
    selectRecord(item) {
      if (this.submitting) return
      this.form.periodKey = item.periodKey
      this.form.content = item.content || ''
      this.form.attachments = (item.attachments || []).map(reportFileState)
      this.refreshAttachments()
    },
    async addAttachment(kind = 'file') {
      if (this.uploading || this.submitting) return
      const form = this.form, generation = currentSessionGeneration(), internshipId = this.internshipId
      const current = () => !this.hidden && form === this.form && generation === currentSessionGeneration() && internshipId === this.internshipId
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
      } catch (e) {
        if (current()) toast(normalizeError(e).text)
      } finally {
        this.uploading = false
      }
    },
    removeAttachment(index) {
      if (this.submitting || this.uploading) return
      this.form.attachments = this.form.attachments.filter((_, i) => i !== index)
    },
    async refreshAttachments() {
      if (this.scanning || this.uploading) return
      const files = this.form.attachments, sequence = this.loadSequence, generation = currentSessionGeneration()
      this.scanning = true
      try {
        const updated = await refreshReportFiles(files, id => fileSdk.metadata(id), () => !this.hidden && files === this.form.attachments && sequence === this.loadSequence && generation === currentSessionGeneration())
        if (updated) this.form.attachments = updated
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
          expectedVersion: current?.version ?? 0
        })
        if (this.hidden || form !== this.form || generation !== currentSessionGeneration()) return
        this.receipt = {
          actionLabel: current ? `${this.typeLabel}已重新提交` : `${this.typeLabel}已提交`,
          id: result.id, version: result.version, statusLabel: '待批阅',
          nextStep: '等待指导教师批阅；退回后可从本页继续修改。'
        }
        await this.load()
      } catch (e) {
        if (!this.hidden && form === this.form && generation === currentSessionGeneration()) toast(normalizeError(e).text + '，正文已保留')
      } finally { this.submitting = false }
    }
  }
}
</script>

<style scoped>
.pr__hint { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: var(--space-2); }
.pr__receipt { display: flex; flex-direction: column; gap: 4px; border-color: #86efac; background: #f0fdf4; color: #166534; font-size: var(--font-size-xs); }
.pr__empty { color: var(--text-tertiary); font-size: var(--font-size-sm); }
.pr__record { display: flex; flex-direction: column; gap: 5px; padding: 10px 0; border-top: 1px solid var(--border-light); }
.pr__record view { display: flex; justify-content: space-between; gap: 10px; font-size: var(--font-size-sm); }
.pr__record view text:last-child, .pr__record > text { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.pr__types { display: flex; gap: 8px; margin-top: 10px; flex-wrap: wrap; }
.pr__type { padding: 6px 12px; border-radius: var(--radius-md); background: var(--gray-100); font-size: var(--font-size-sm); color: var(--text-secondary); }
.pr__type.is-on { background: var(--brand-primary); color: #fff; }
.pr__field { display: flex; flex-direction: column; gap: 6px; }
.pr__label { font-size: var(--font-size-sm); color: var(--text-secondary); }
.pr__req { color: var(--danger-500); }
.pr__input { border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: 10px 12px; font-size: var(--font-size-sm); }
.pr__textarea { border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: 10px 12px; min-height: 160px; font-size: var(--font-size-sm); width: 100%; box-sizing: border-box; }
.pr__count { font-size: var(--font-size-xs); color: var(--text-tertiary); text-align: right; }
.pr__attachment { display: flex; align-items: center; gap: 10px; padding: 10px; border: 1px solid var(--border-light); border-radius: var(--radius-md); }
.pr__attachment-meta { display: block; margin-top: 3px; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.pr__remove { flex-shrink: 0; font-size: var(--font-size-sm); color: var(--danger-600); }
.pr__attach-btn { margin: 0; min-height: var(--touch-target-min); border: 1px dashed var(--border-base); background: var(--bg-card); color: var(--brand-primary); font-size: var(--font-size-sm); }
.pr__attach-btn::after { border: none; }
</style>
