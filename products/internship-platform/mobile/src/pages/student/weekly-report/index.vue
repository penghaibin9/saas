<template>
  <view class="page-wrap wr">
    <MobileNavBar variant="brand" title="实习周报" :subtitle="subtitle" show-back :before-back="beforeBack" />
    <MobileGlobalState :state="state" :description="loadError" @retry="load">
      <view v-if="loaded" class="page-pad">
        <view class="card wr__context"><text>{{ batchName }}</text><text>提交后交给{{ schoolMentor || '指导教师' }}批阅；退回后在原周报修改重交。</text></view>
        <MobileInlineAlert v-if="historyMode" type="info" description="历史实习记录仅供查看，不能新增或修改报告。" />
        <view class="card wr__weeks">
          <view v-for="week in weekTabs" :key="week.week" class="wr__week" :class="{ 'is-on': selectedWeek === week.week }" @click="selectWeek(week.week)">
            <text class="wr__week-num">第{{ week.week }}周</text><text class="wr__week-tag">{{ week.tagText }}</text>
          </view>
        </view>
        <view v-if="receipt" class="card wr__receipt"><text class="t-bold">{{ receipt.title }}</text><text>周报编号：{{ receipt.id }} · 第 {{ receipt.version }} 版</text><text>{{ receipt.nextStep }}</text></view>
        <MobileInlineAlert v-if="submitError" type="warning" :description="submitError" />
        <view v-if="conflict" class="card wr__conflict">
          <text>填写内容已保留，请先读取最新周报，核对教师意见和状态。</text>
          <button class="btn btn-secondary" :disabled="detailState === 'loading'" @click="reloadConflict">读取最新记录并核对</button>
          <button v-if="conflictReviewed && selectedReport?.status === 'RETURNED'" class="btn btn-secondary" @click="continueAfterConflict">已核对，保留填写内容继续修改</button>
        </view>
        <template v-if="isEditableWeek">
          <view class="card wr__form">
            <view class="row-between"><text class="card-title">第 {{ selectedWeek }} 周 · {{ selectedReport ? '修改重交' : '填写中' }}</text><MobileStatusTag :label="selectedReport ? '已退回' : '填写中'" :type="selectedReport ? 'warning' : 'processing'" /></view>
            <view class="wr__field"><text class="wr__label">本周工作内容 <text class="wr__req">*</text></text><textarea v-model="form.workContent" class="wr__textarea" maxlength="8000" placeholder="描述本周完成的主要任务" /></view>
            <view class="wr__field"><text class="wr__label">本周收获 <text class="wr__req">*</text></text><textarea v-model="form.harvestContent" class="wr__textarea" maxlength="8000" placeholder="学到的技能、经验与体会" /></view>
            <view class="wr__field"><text class="wr__label">存在问题 / 下周计划</text><textarea v-model="form.planContent" class="wr__textarea" maxlength="8000" placeholder="遇到的问题及下周安排（可选）" /></view>
            <text class="wr__count">正文合计 {{ wordCount }} 字，当前计划要求至少 {{ minimum }} 字</text>
            <text class="wr__hint">切换周次时保留本页未提交内容；返回前会提醒核对。</text>
          </view>
          <MobileInlineAlert :type="selectedReport ? 'warning' : 'info'" :description="selectedReport ? ('教师意见：' + (selectedReport.reviewComment || '请按要求修改后重交')) : '请结合本周岗位工作填写；提交后等待指导教师批阅。'" />
          <view class="card wr__files">
            <text class="card-title">图片、视频及附件</text><text class="wr__hint">图片最多 {{ rules.maxImages }} 张，视频最多 {{ rules.maxVideos }} 个，文档或压缩文件最多 9 个。</text>
            <view v-for="(file,index) in form.attachments" :key="file.fileId" class="wr__file">
              <view class="flex-1"><text class="wr__filename" @click="openAttachment(file)">{{ file.fileName || '报告附件' }}</text><text class="wr__hint">{{ file.kindLabel }} · {{ file.statusText }}</text></view>
              <button class="wr__remove" :disabled="uploading || submitting" @click="removeAttachment(index)">移除</button>
            </view>
            <view class="wr__file-actions"><button class="btn btn-secondary" :disabled="uploading || submitting" @click="addAttachment('image')">添加图片</button><button class="btn btn-secondary" :disabled="uploading || submitting" @click="addAttachment('video')">添加视频</button><button class="btn btn-secondary" :disabled="uploading || submitting" @click="addAttachment('file')">添加文件</button></view>
            <text v-if="uploading" class="wr__hint">附件上传中，请稍候…</text>
            <button v-if="form.attachments.length" class="btn btn-secondary" :disabled="scanning || uploading || submitting" @click="refreshAttachments">{{ scanning ? '正在读取扫描结果…' : '查看附件安全扫描结果' }}</button>
            <text v-if="!attachmentsReady" class="wr__hint">附件安全就绪前不能提交；扫描失败的附件可移除后重新上传。</text>
          </view>
        </template>
        <view v-else-if="selectedReport" class="card wr__ro">
          <view class="row-between"><text class="card-title">第 {{ selectedWeek }} 周 · 第 {{ selectedReport.reportVersion || 1 }} 版</text><MobileStatusTag :label="selectedReport.statusLabel" /></view>
          <view class="wr__ro-block"><text class="wr__ro-label">本周工作内容</text><text class="wr__ro-text">{{ selectedReport.workContent || '暂无正文' }}</text></view>
          <view class="wr__ro-block"><text class="wr__ro-label">本周收获</text><text class="wr__ro-text">{{ selectedReport.harvestContent || '暂无正文' }}</text></view>
          <view v-if="selectedReport.planContent" class="wr__ro-block"><text class="wr__ro-label">存在问题 / 下周计划</text><text class="wr__ro-text">{{ selectedReport.planContent }}</text></view>
          <text v-if="selectedReport.reviewComment" class="wr__feedback">教师意见：{{ selectedReport.reviewComment }}</text>
          <text>{{ detail?.ratingLabel || '暂无评价' }}</text>
          <button v-for="file in selectedReport.attachments || []" :key="file.fileId" class="btn btn-secondary" @click="openAttachment(file)">{{ file.fileName || '报告附件' }}</button>
        </view>
        <view v-if="selectedReport" class="card wr__history">
          <text class="card-title">提交版本与批阅记录</text>
          <text v-if="detailState === 'loading'">正在读取版本与评分…</text>
          <view v-else-if="detailState === 'error'"><text>版本与评分读取失败，当前正文和填写内容已保留。</text><button class="btn btn-secondary" @click="loadDetail">重试读取记录</button></view>
          <template v-else-if="detail">
            <text v-if="!detail.immutableVersions.length" class="wr__hint">此报告暂无历史版本记录。</text>
            <view v-for="version in detail.immutableVersions" :key="version.id" class="wr__version">
              <text class="t-bold">第 {{ version.versionNo }} 版 · {{ version.wordCount }} 字</text>
              <text v-if="version.review" class="wr__feedback">{{ version.review.actionLabel }} · {{ version.review.ratingLabel }} · {{ version.review.reviewerName || '指导教师' }}</text>
              <text v-if="version.review?.comment" class="wr__feedback">{{ version.review.comment }}</text>
              <text v-else-if="!version.review" class="wr__hint">等待指导教师批阅</text>
              <text class="wr__ro-label">本周工作内容</text><text class="wr__ro-text">{{ version.content.workContent || '暂无正文' }}</text>
              <text class="wr__ro-label">本周收获</text><text class="wr__ro-text">{{ version.content.harvestContent || '暂无正文' }}</text>
              <text v-if="version.content.planContent" class="wr__ro-text">{{ version.content.planContent }}</text>
              <button v-for="file in version.attachments || []" :key="file.fileId" class="btn btn-secondary" @click="openAttachment(file)">{{ file.fileName || '该版附件' }}</button>
            </view>
          </template>
        </view>
        <ReportFilePreview ref="reportPreview" />
        <view v-if="hasMore" class="wr__more"><button class="btn btn-secondary" :disabled="loadingMore" @click="loadMore">{{ loadingMore ? '加载中…' : '加载更多历史周报' }}</button></view>
      </view>
    </MobileGlobalState>
    <MobileSafeAreaBar v-if="loaded && state === 'ready' && isEditableWeek"><button class="btn btn-primary flex-1" :disabled="!canSubmit" @click="submit">{{ submitting ? '提交中…' : selectedReport ? '重新提交周报' : '提交周报' }}</button></MobileSafeAreaBar>
  </view>
</template>
<script>
import { studentApi } from '@/services/studentApi'
import fileSdk from '@/services/fileSdk'
import { normalizeError } from '@/services/request'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { weeklyReportView, reportFileState, reportFilesReady, refreshReportFiles } from '@/services/weeklyReportPresentation.mjs'
import ReportFilePreview from '@/components/ReportFilePreview.vue'
import { toast } from '@/utils/nav'

const blank = () => ({ workContent: '', harvestContent: '', planContent: '', attachments: [] })
const clone = form => ({ ...form, attachments: (form.attachments || []).map(file => ({ ...file })) })
export default {
  components: { ReportFilePreview },
  data() { return {
    state: 'loading', loaded: false, loadError: '', company: '', post: '', schoolMentor: '', batchName: '', historyMode: false,
    currentWeek: 1, selectedWeek: 1, weeklyList: [], form: blank(), drafts: {}, baseVersion: 0,
    rules: { weeklyMinWords: 30, maxImages: 9, maxVideos: 3 }, batchId: '', internshipId: '', requestedBatchId: '',
    focusReportId: '', focusWeek: 0, receipt: null, submitError: '', conflict: false, conflictReviewed: false,
    detail: null, detailState: '', detailSequence: 0, loadSequence: 0, attachmentSequence: 0, generation: currentSessionGeneration(), hidden: false,
    submitting: false, uploading: false, scanning: false, loadingMore: false, weeklyPageSize: 20, weeklyTotal: 0, loadedWeeklyPages: [], hasMore: false
  } },
  computed: {
    subtitle() { return [this.company, this.post].filter(Boolean).join(' · ') },
    weekTabs() {
      const tabs = this.weeklyList.map(row => ({ week: row.week, tagText: row.statusLabel }))
      if (!tabs.some(row => row.week === this.currentWeek)) tabs.push({ week: this.currentWeek, tagText: this.historyMode ? '暂无记录' : '填写中' })
      return tabs.sort((a,b) => a.week - b.week)
    },
    selectedReport() { return this.weeklyList.find(row => row.week === this.selectedWeek) || null },
    isEditableWeek() { return !this.historyMode && ((!this.selectedReport && this.selectedWeek === this.currentWeek) || this.selectedReport?.status === 'RETURNED') },
    minimum() { return Number(this.rules.weeklyMinWords) > 0 ? Number(this.rules.weeklyMinWords) : 30 },
    wordCount() { return this.form.workContent.trim().length + this.form.harvestContent.trim().length + this.form.planContent.trim().length },
    attachmentsReady() { return reportFilesReady(this.form.attachments) },
    draftKey() { return [this.batchId, this.internshipId, this.selectedWeek].join(':') },
    canSubmit() { return this.state === 'ready' && this.isEditableWeek && !this.hidden && this.generation === currentSessionGeneration()
      && !this.submitting && !this.uploading && !this.scanning && !this.conflict && (!this.selectedReport || this.detailState === 'ready')
      && !!this.form.workContent.trim() && !!this.form.harvestContent.trim() && this.wordCount >= this.minimum && this.attachmentsReady }
  },
  onLoad(options = {}) { this.requestedBatchId = String(options.batchId || ''); this.focusReportId = String(options.reportId || ''); this.focusWeek = Number(options.weekNo || 0); this.load() },
  onShow() {
    if (this.generation !== currentSessionGeneration()) this.clearContext()
    if (this.hidden) { this.hidden = false; return this.load() }
  },
  onHide() { this.saveDraft(); this.hidden = true; this.loadSequence += 1; this.detailSequence += 1; this.attachmentSequence += 1; this.$refs.reportPreview?.reset() },
  onUnload() { this.hidden = true; this.loadSequence += 1; this.detailSequence += 1; this.attachmentSequence += 1; this.drafts = {}; this.$refs.reportPreview?.reset() },
  onReachBottom() { this.loadMore() },
  methods: {
    clearContext() { this.form = blank(); this.drafts = {}; this.weeklyList = []; this.detail = null; this.receipt = null; this.batchId = ''; this.internshipId = ''; this.company = ''; this.post = ''; this.schoolMentor = ''; this.batchName = ''; this.submitError = ''; this.historyMode = false; this.conflict = false; this.loaded = false; this.generation = currentSessionGeneration(); this.$refs.reportPreview?.reset() },
    readCurrent(sequence, generation) { return !this.hidden && sequence === this.loadSequence && generation === currentSessionGeneration() },
    saveDraft() { if (this.loaded && this.isEditableWeek && this.generation === currentSessionGeneration()) this.drafts[this.draftKey] = { form: clone(this.form), baseVersion: this.baseVersion, conflict: this.conflict } },
    applyWeeklyPage(result) {
      const rows = new Map(this.weeklyList.map(row => [row.id, row]))
      for (const row of result.items || []) { const mapped = weeklyReportView(row); rows.set(mapped.id, mapped) }
      this.weeklyList = [...rows.values()].sort((a,b) => b.week - a.week)
      this.weeklyTotal = Number(result.total || 0)
      const page = Number(result.page || 1)
      if (!this.loadedWeeklyPages.includes(page)) this.loadedWeeklyPages.push(page)
      this.hasMore = this.loadedWeeklyPages.length < Math.ceil(this.weeklyTotal / this.weeklyPageSize)
    },
    async load(options = {}) {
      if (this.generation !== currentSessionGeneration()) this.clearContext()
      if (!options.afterSubmit) this.saveDraft()
      const oldContext = this.batchId + ':' + this.internshipId, oldWeek = this.selectedWeek
      const sequence = ++this.loadSequence, generation = currentSessionGeneration()
      this.state = 'loading'; this.loadError = ''; this.loadingMore = false
      try {
        const dashboard = await studentApi.getInternship(this.requestedBatchId)
        if (!this.readCurrent(sequence, generation)) return
        if (!dashboard.hasBatch && (!dashboard.batchId || !dashboard.recordId)) { this.clearContext(); this.state = 'empty'; this.loadError = dashboard.needSelect ? '请返回岗位实习首页选择批次后继续。' : '当前没有可办理的岗位实习记录。'; return }
        const batchId = String(dashboard.batchId), internshipId = String(dashboard.recordId)
        const changed = oldContext !== batchId + ':' + internshipId
        if (changed) { this.form = blank(); this.drafts = {}; this.receipt = null; this.submitError = ''; this.conflict = false; this.$refs.reportPreview?.reset() }
        this.batchId = batchId; this.internshipId = internshipId; this.historyMode = !!dashboard.historyMode
        this.company = dashboard.company || ''; this.post = dashboard.post || ''; this.schoolMentor = dashboard.schoolMentor || ''; this.batchName = dashboard.batch || '当前实习批次'
        const result = await studentApi.getInternshipWeeklyReports(batchId, internshipId, 1, this.weeklyPageSize, this.focusReportId)
        if (!this.readCurrent(sequence, generation)) return
        this.weeklyList = []; this.loadedWeeklyPages = []; this.applyWeeklyPage(result); this.rules = { ...this.rules, ...(result.rules || {}) }
        if (this.focusReportId && Number(result.focusPage) > 1) {
          const page = await studentApi.getInternshipWeeklyReports(batchId, internshipId, Number(result.focusPage), this.weeklyPageSize)
          if (!this.readCurrent(sequence, generation)) return
          this.applyWeeklyPage(page)
        }
        this.currentWeek = Number(String(dashboard.weekly?.week || '1').match(/\d+/)?.[0] || 1)
        const focus = this.weeklyList.find(row => row.id === this.focusReportId)
        this.loaded = true; this.state = 'ready'; this.generation = generation
        await this.selectWeek(focus?.week || this.focusWeek || (!changed ? oldWeek : this.currentWeek), false)
      } catch (error) {
        if (this.readCurrent(sequence, generation)) { const shown = normalizeError(error); this.state = shown.pageState || 'error'; this.loadError = shown.text }
        if (options.afterSubmit && this.receipt) this.receipt.nextStep = '提交已收到回执，结果读取失败；请重试读取后核对，避免再次提交。'
      }
    },
    async loadMore() {
      if (!this.loaded || this.state !== 'ready' || this.loadingMore || !this.hasMore) return
      const page = Array.from({ length: Math.ceil(this.weeklyTotal / this.weeklyPageSize) }, (_,i) => i + 1).find(value => !this.loadedWeeklyPages.includes(value))
      if (!page) return
      const sequence = this.loadSequence, generation = this.generation; this.loadingMore = true
      try { const result = await studentApi.getInternshipWeeklyReports(this.batchId, this.internshipId, page, this.weeklyPageSize); if (this.readCurrent(sequence,generation)) this.applyWeeklyPage(result) }
      catch (error) { if (this.readCurrent(sequence,generation)) toast('历史周报读取失败，请检查网络后重试') }
      finally { if (this.readCurrent(sequence,generation)) this.loadingMore = false }
    },
    async selectWeek(week, preserve = true) {
      if (this.submitting || (preserve && (this.uploading || this.scanning))) return
      if (preserve) this.saveDraft()
      this.selectedWeek = Number(week); this.detail = null; this.detailState = ''; this.detailSequence += 1; this.attachmentSequence += 1; this.$refs.reportPreview?.reset()
      const row = this.selectedReport, draft = this.drafts[this.draftKey]
      this.form = draft ? clone(draft.form) : row?.status === 'RETURNED' ? { workContent: row.workContent, harvestContent: row.harvestContent, planContent: row.planContent, attachments: (row.attachments || []).map(reportFileState) } : blank()
      this.baseVersion = draft?.baseVersion ?? row?.version ?? 0; this.conflict = !!draft?.conflict; this.conflictReviewed = false
      if (row) await this.loadDetail()
      if (this.form.attachments.length && this.isEditableWeek) await this.refreshAttachments()
    },
    async loadDetail() {
      const row = this.selectedReport
      if (!row) return
      const sequence = ++this.detailSequence, generation = this.generation, key = this.draftKey
      this.detailState = 'loading'
      try {
        const detail = weeklyReportView(await studentApi.getInternshipWeeklyReportDetail(row.id, this.batchId, this.internshipId))
        if (this.hidden || sequence !== this.detailSequence || generation !== currentSessionGeneration() || key !== this.draftKey) return
        this.detail = detail; this.detailState = 'ready'
        this.weeklyList = this.weeklyList.map(item => item.id === detail.id ? detail : item)
        if (detail.version !== this.baseVersion && this.isEditableWeek) this.conflict = true
      } catch (error) { if (!this.hidden && sequence === this.detailSequence && generation === currentSessionGeneration()) this.detailState = 'error' }
    },
    async reloadConflict() { await this.loadDetail(); this.conflictReviewed = this.detailState === 'ready' },
    continueAfterConflict() { if (!this.conflictReviewed || this.selectedReport?.status !== 'RETURNED') return; this.baseVersion = this.selectedReport.version; this.conflict = false; this.submitError = ''; this.saveDraft() },
    async addAttachment(kind) {
      if (!this.isEditableWeek || this.uploading || this.submitting) return
      const form = this.form, key = this.draftKey, generation = this.generation; this.uploading = true
      const current = () => !this.hidden && form === this.form && key === this.draftKey && generation === currentSessionGeneration()
      try {
        const picked = await fileSdk.choose({ kind }); if (!picked || !current()) return
        const uploaded = await fileSdk.upload(picked, { bizType: 'INTERNSHIP_REPORT' })
        if (!current()) return
        if (!uploaded?.fileId) throw new Error('附件上传未完成')
        if (!form.attachments.some(file => file.fileId === String(uploaded.fileId))) form.attachments.push(reportFileState(uploaded))
        this.submitError = ''; this.saveDraft(); toast(uploaded.readyForBusiness ? '附件已上传，可继续提交' : '附件已接收，请等待安全扫描后读取结果')
      } catch (error) { if (current() && !String(error?.errMsg || '').includes('cancel')) this.submitError = normalizeError(error).text }
      finally { this.uploading = false }
    },
    removeAttachment(index) { if (this.submitting || this.uploading || this.scanning) return; this.form.attachments.splice(index,1); this.saveDraft() },
    async refreshAttachments() {
      if (this.scanning || this.uploading || this.submitting) return
      const form = this.form, files = form.attachments, key = this.draftKey, sequence = ++this.attachmentSequence, generation = this.generation
      const current = () => !this.hidden && form === this.form && key === this.draftKey && files === form.attachments && sequence === this.attachmentSequence && generation === currentSessionGeneration()
      this.scanning = true
      try { const updated = await refreshReportFiles(files, id => fileSdk.metadata(id), current); if (updated) { this.form.attachments = updated; this.saveDraft() } }
      catch (error) { if (current()) this.submitError = '扫描结果读取失败，正文和附件已保留，请重试' }
      finally { this.scanning = false }
    },
    async openAttachment(file) { await this.$refs.reportPreview.open(file); if (!this.hidden) uni.pageScrollTo({ selector: '.report-preview', duration: 200 }) },
    async beforeBack() {
      if (this.submitting || this.uploading) { toast('正在提交或上传，请稍候再返回'); return false }
      if (!this.isEditableWeek || !this.wordCount && !this.form.attachments.length) return true
      return new Promise(resolve => uni.showModal({ title: '返回前请确认', content: '本页内容尚未提交，返回后不会保存。是否返回？', confirmText: '返回', cancelText: '继续填写', success: result => resolve(!!result.confirm), fail: () => resolve(false) }))
    },
    async submit() {
      if (!this.canSubmit) return
      const key = this.draftKey, generation = this.generation, current = this.selectedReport, form = clone(this.form)
      this.submitting = true; this.submitError = ''
      try {
        const result = await studentApi.submitInternshipWeeklyReport({ batchId: this.batchId, internshipId: this.internshipId, expectedVersion: this.baseVersion, weekNo: this.selectedWeek,
          workContent: form.workContent.trim(), harvestContent: form.harvestContent.trim(), planContent: form.planContent.trim(), attachmentFileIds: form.attachments.map(file => String(file.fileId)) })
        if (this.hidden || generation !== currentSessionGeneration() || key !== this.draftKey) return
        this.receipt = { title: current ? '周报已重新提交' : '周报已提交', id: String(result.id), version: result.reportVersion || result.immutableVersion || 1, nextStep: '等待指导教师批阅；若被退回，可从本页查看意见并修改重交。' }
        delete this.drafts[key]; this.form = blank(); this.conflict = false; this.focusReportId = String(result.id); this.focusWeek = this.selectedWeek
        this.submitting = false
        await this.load({ afterSubmit: true })
      } catch (error) {
        if (this.hidden || generation !== currentSessionGeneration()) return
        const shown = normalizeError(error)
        if (shown.kind === 'conflict' || Number(error?.httpStatus) === 409 || String(error?.code || '').startsWith('409')) {
          this.conflict = true; this.conflictReviewed = false; this.submitError = '周报状态或版本已变化，填写内容已保留；请读取最新记录后核对。'
        } else this.submitError = shown.text + '，填写内容已保留'
        this.saveDraft()
      } finally { this.submitting = false }
    }
  }
}
</script>
<style scoped>
.wr__context, .wr__receipt, .wr__conflict { display:flex; flex-direction:column; gap:6px; font-size:13px; margin-top:12px; }
.wr__context text:last-child, .wr__hint { display:block; color:var(--text-tertiary); font-size:12px; margin-top:6px; line-height:1.6; }
.wr__receipt { background:#f0fdf4; color:#166534; border-color:#86efac; }
.wr__weeks { display:flex; gap:8px; overflow-x:auto; margin-top:12px; }
.wr__week { flex-shrink:0; min-width:64px; text-align:center; padding:10px 6px; border-radius:8px; border:1.5px solid var(--border-base); }
.wr__week.is-on { border-color:var(--brand-primary); background:var(--primary-50); }
.wr__week-num, .wr__week-tag { display:block; font-size:13px; }
.wr__week-tag { color:var(--text-tertiary); font-size:11px; margin-top:3px; }
.wr__form, .wr__ro, .wr__files, .wr__history { margin-top:12px; }
.wr__field { padding:12px 0; border-bottom:1px solid var(--border-light); }
.wr__label, .wr__ro-label { display:block; font-size:13px; color:var(--text-secondary); margin-bottom:8px; }
.wr__req { color:var(--danger-500); }
.wr__textarea { width:100%; min-height:100px; box-sizing:border-box; font-size:14px; line-height:1.7; }
.wr__count { display:block; color:var(--text-secondary); font-size:12px; margin-top:10px; }
.wr__file { display:flex; align-items:center; gap:8px; padding:10px 0; border-bottom:1px solid var(--border-light); }
.wr__filename { display:block; font-size:13px; color:var(--brand-primary); word-break:break-all; }
.wr__remove { flex-shrink:0; margin:0; padding:0 8px; background:transparent; color:var(--danger-600); font-size:13px; }
.wr__file-actions { display:flex; flex-wrap:wrap; gap:8px; margin:12px 0; }
.wr__file-actions button { flex:1; min-width:85px; padding:8px; font-size:13px; }
.wr__ro-block { margin:12px 0; }.wr__ro-text { display:block; white-space:pre-wrap; word-break:break-word; font-size:14px; line-height:1.7; }
.wr__feedback { display:block; margin:10px 0; font-size:13px; color:var(--text-secondary); }
.wr__version { display:flex; flex-direction:column; gap:8px; padding:14px 0; border-top:1px solid var(--border-light); }
.wr__more { margin:12px 0; }
</style>
