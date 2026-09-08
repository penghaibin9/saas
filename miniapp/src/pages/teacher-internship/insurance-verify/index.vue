<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="实习保险核验" subtitle="核对保单信息与原始凭证" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack">
        <view v-if="batches.length" class="card iv__batch">
          <view class="iv__batch-copy">
            <text class="iv__eyebrow">当前核验批次</text>
            <text class="iv__batch-name">{{ batches[batchIndex]?.name || '请选择批次' }}</text>
          </view>
          <picker class="iv__picker" mode="selector" :range="batchLabels" :value="batchIndex" :disabled="acting" @change="onBatch">
            <view class="iv__pick">切换批次 <text>▾</text></view>
          </picker>
        </view>

        <view v-if="batches.length" class="card iv__summary">
          <view class="iv__summary-main">
            <text class="iv__summary-label">待核验保险</text>
            <view class="iv__summary-number"><text>{{ list.length }}</text><text>条</text></view>
            <text class="iv__summary-note">{{ summaryConclusion }}</text>
          </view>
          <view class="iv__summary-metrics">
            <view class="iv__metric"><text>{{ completeFileCount }}</text><text>凭证齐全</text></view>
            <view class="iv__metric is-danger"><text>{{ missingFileCount }}</text><text>缺少凭证</text></view>
          </view>
        </view>

        <MobileInlineAlert type="info" description="先核对承保单位、保单号、保障期和原始凭证，再执行通过或驳回。学生重交后请刷新，以最新版本为准。" />
        <button class="btn btn-ghost" :disabled="acting" @click="refreshReview">刷新待核验保单</button>
        <MobileInlineAlert v-if="receipt" type="success" :description="receipt" />
        <MobileGlobalState v-if="!batches.length" state="empty" title="暂无实习批次" description="当前身份的数据范围内没有可核验批次。" />
        <MobileGlobalState v-else-if="!list.length" state="empty" title="当前批次没有待核验保险" description="学生提交保险凭证后会出现在这里。" />

        <view v-for="item in list" :key="item.id" class="card iv">
          <view class="row-between iv__head">
            <view class="flex-1 iv__identity">
              <text class="t-md t-bold">{{ item.studentName || '—' }}</text>
              <text class="iv__sub">{{ item.studentNo || '' }} · {{ item.enterpriseName || '企业待落实' }}</text>
            </view>
            <MobileStatusTag :label="item.statusLabel" type="warning" />
          </view>

          <view class="iv__detail-box">
            <view class="iv__row"><text class="iv__row-k">承保单位</text><text class="iv__row-v">{{ item.insurerName || '—' }}</text></view>
            <view class="iv__row"><text class="iv__row-k">保单号</text><text class="iv__row-v iv__policy">{{ item.policyNo || '—' }}</text></view>
            <view class="iv__row"><text class="iv__row-k">保障期</text><text class="iv__row-v">{{ item.effectiveDate || '—' }} ~ {{ item.expiryDate || '—' }}</text></view>
          </view>

          <view class="iv__evidence" :class="{ 'is-missing': !item.hasFile }">
            <view class="iv__evidence-copy">
              <text class="iv__evidence-title">原始保险凭证</text>
              <text class="iv__evidence-text">{{ item.hasFile ? '已上传，可按保单信息进行核验。' : '尚未上传，当前记录禁止通过。' }}</text>
            </view>
            <MobileStatusTag :label="item.hasFile ? '已上传' : '缺失'" :type="item.hasFile ? 'success' : 'danger'" />
          </view>
          <button v-if="item.fileId" class="btn btn-ghost" :disabled="acting || !!opening" @click="openEvidence(item)">{{ opening === String(item.id) ? '正在打开凭证…' : '查看原始保单凭证' }}</button>
          <view v-if="preview?.id === String(item.id)" class="iv__preview">
            <view class="row-between"><text class="iv__evidence-title">当前保单原件</text><button class="iv__preview-close" @click="closePreview">关闭预览</button></view>
            <!-- #ifdef H5 -->
            <view v-if="preview.loading" class="iv__preview-loading">正在安全渲染原件…</view>
            <image v-for="(page, pageIndex) in preview.pages" :key="page" class="iv__preview-page" :src="page" mode="widthFix" :alt="`保险凭证第${pageIndex + 1}页`" />
            <!-- #endif -->
            <text class="iv__preview-note">{{ evidenceReady(item) ? '原件已在当前页打开，请核对姓名、保单号和保障期。' : '正在打开原件，加载完成前不能通过。' }}</text>
          </view>
          <MobileInlineAlert v-if="evidenceErrors[item.id]" type="warning" :description="evidenceErrors[item.id]" />
          <MobileInlineAlert v-if="item.coverageReason" type="warning" :description="item.coverageReason" />

          <view class="iv__meta"><text>{{ evidenceReady(item) ? '凭证已打开，请核对保障信息' : '通过前请先打开原始凭证' }}</text></view>
          <view v-if="review?.id === item.id" class="stack">
            <text class="t-md t-bold">{{ review.action === 'REJECT' ? '退回补充材料' : '确认保险核验通过' }}</text>
            <textarea v-model="review.comment" class="iv__comment" :disabled="acting" :placeholder="review.action === 'REJECT' ? '写清需要补充或更正的材料，不少于5个字' : '核验备注（选填）'" />
            <MobileInlineAlert v-if="reviewError" type="warning" :description="reviewError" />
            <view class="iv__actions"><button class="btn btn-ghost flex-1" :disabled="acting" @click="closeReview">取消</button><button class="btn btn-primary flex-1" :disabled="acting || conflict" @click="submitReview">{{ acting ? '提交中…' : review.action === 'REJECT' ? '确认退回' : '确认通过' }}</button></view>
            <button v-if="conflict" class="btn btn-ghost" :disabled="acting" @click="refreshReview">重新读取并核对保单</button>
          </view>
          <view v-else class="iv__actions">
            <button class="iv__reject flex-1" :disabled="acting" @click="verify(item, 'REJECT')">驳回补充</button>
            <button class="iv__approve flex-1" :disabled="acting || !evidenceReady(item)" @click="verify(item, 'APPROVE')">核验通过</button>
          </view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { useInternshipContextStore } from '@/stores/internshipContext'
import { teacherInternshipInsurancePending, teacherInternshipInsuranceVerify } from '@/services/internshipApi'
import { fileSdk } from '@/services/fileSdk'

export default {
  data() {
    return { list: [], state: 'loading', acting: false, batches: [], batchId: '', batchIndex: 0,
      loadSeq: 0, opening: '', evidence: {}, evidenceErrors: {}, preview: null, review: null, reviewError: '', conflict: false, drafts: {}, receipt: '' }
  },
  computed: {
    batchLabels() { return this.batches.map((x) => `${x.name} · ${x.status} · ${x.studentCount}人`) },
    missingFileCount() { return this.list.filter((item) => !item.hasFile).length },
    completeFileCount() { return this.list.length - this.missingFileCount },
    summaryConclusion() {
      if (!this.list.length) return '当前没有需要核验的保险记录。'
      if (this.missingFileCount) return `优先处理 ${this.missingFileCount} 条缺少原始凭证的记录。`
      return '所有待办均已上传凭证，可逐条核对保单信息。'
    }
  },
  onLoad() { this.load() },
  onUnload() { this.loadSeq++; this.closePreview() },
  onPullDownRefresh() {
    if (this.state === 'loading' || this.acting) { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  methods: {
    async load(done) {
      const seq = ++this.loadSeq
      this.closeReview(); this.closePreview(); this.evidence = {}; this.evidenceErrors = {}; this.list = []
      this.state = 'loading'
      try {
        const context = useInternshipContextStore()
        context.restore()
        await context.load(true)
        if (seq !== this.loadSeq) return
        this.batches = context.batches || []
        this.batchId = context.selectedBatchId || ''
        this.batchIndex = Math.max(0, this.batches.findIndex((x) => String(x.id) === String(this.batchId)))
        if (!this.batchId) this.list = []
        else {
          const data = await teacherInternshipInsurancePending(this.batchId)
          if (seq !== this.loadSeq) return
          this.list = data?.list || data?.items || []
        }
        this.state = 'ready'
      } catch (e) {
        if (seq === this.loadSeq) this.state = 'error'
      } finally { if (done) done() }
    },
    async onBatch(e) {
      if (this.acting) return
      this.drafts = {}; this.receipt = ''; this.review = null
      this.batchIndex = Number(e.detail.value)
      const selected = this.batches[this.batchIndex]
      const context = useInternshipContextStore()
      context.selectBatch(selected?.id)
      this.batchId = context.selectedBatchId
      await this.load()
    },
    verify(item, action) {
      if (this.acting || this.state !== 'ready' || !['APPROVE', 'REJECT'].includes(action) || !Number.isInteger(item.version)) return
      if (action === 'APPROVE' && !this.evidenceReady(item)) return
      this.closeReview()
      this.review = { ...item, action, comment: action === 'REJECT' ? (this.drafts[item.id] || '') : '', batchId: this.batchId, seq: this.loadSeq }
    },
    closeReview() {
      if (this.review?.action === 'REJECT') this.drafts[this.review.id] = this.review.comment
      this.review = null; this.reviewError = ''; this.conflict = false
    },
    refreshReview() { if (!this.acting) return this.load() },
    evidenceReady(item) {
      const evidence = this.evidence[item.id]
      return Boolean(item.fileId && evidence?.version === item.version && evidence.fileId === String(item.fileId))
    },
    async openEvidence(item) {
      if (this.acting || this.opening || !item.fileId) return
      const seq = this.loadSeq, batchId = this.batchId
      this.opening = String(item.id); delete this.evidence[item.id]; delete this.evidenceErrors[item.id]
      try {
        const meta = await fileSdk.openInline(String(item.fileId))
        if (seq !== this.loadSeq || batchId !== this.batchId) return
        if (String(meta?.fileId) !== String(item.fileId) || !meta.readyForBusiness || !(meta.canPreview || meta.canDownload)) throw new Error('原始凭证尚未安全可读，不能通过核验')
        if (meta.inlineUrl) {
          this.preview = { id: String(item.id), fileId: String(item.fileId), version: item.version, url: meta.inlineUrl, loading: true, pages: [] }
          await this.renderInlinePreview(item)
        }
        else this.evidence[item.id] = { fileId: String(item.fileId), version: item.version }
      } catch (e) { if (seq === this.loadSeq && batchId === this.batchId) this.evidenceErrors[item.id] = e?.message || '凭证打开失败，请重试' }
      finally { this.opening = '' }
    },
    async renderInlinePreview(item) {
      try {
        // #ifdef H5
        const [{ getDocument, GlobalWorkerOptions }, worker] = await Promise.all([
          import('pdfjs-dist/build/pdf.mjs'), import('pdfjs-dist/build/pdf.worker.min.mjs?url')
        ])
        GlobalWorkerOptions.workerSrc = worker.default
        const documentTask = getDocument({ url: String(this.preview.url) })
        const pdf = await documentTask.promise
        const pages = []
        for (let pageNumber = 1; pageNumber <= pdf.numPages; pageNumber++) {
          const page = await pdf.getPage(pageNumber)
          const viewport = page.getViewport({ scale: 1.35 })
          const canvas = document.createElement('canvas')
          canvas.width = Math.ceil(viewport.width); canvas.height = Math.ceil(viewport.height)
          await page.render({ canvas, canvasContext: canvas.getContext('2d'), viewport }).promise
          const blob = await new Promise((resolve, reject) => canvas.toBlob((value) => value ? resolve(value) : reject(new Error('原件页面渲染失败')), 'image/png'))
          pages.push(URL.createObjectURL(blob))
        }
        if (this.preview?.id !== String(item.id) || this.preview.fileId !== String(item.fileId) || this.preview.version !== item.version) {
          pages.forEach((url) => URL.revokeObjectURL(url)); return
        }
        this.preview.pages = pages; this.preview.loading = false
        // #endif
        this.evidence[item.id] = { fileId: String(item.fileId), version: item.version }
      } catch (e) {
        delete this.evidence[item.id]
        if (this.preview) this.preview.loading = false
        this.evidenceErrors[item.id] = e?.message || '原件页内预览失败，请刷新后重试'
      }
    },
    closePreview() {
      const urls = [this.preview?.url, ...(this.preview?.pages || [])]
      if (typeof URL !== 'undefined') urls.filter((url) => url?.startsWith?.('blob:')).forEach((url) => URL.revokeObjectURL(url))
      this.preview = null
    },
    async submitReview() {
      const review = this.review
      if (!review || this.acting || this.conflict || review.seq !== this.loadSeq || review.batchId !== this.batchId) return
      if (review.action === 'APPROVE' && !this.evidenceReady(review)) { this.reviewError = '请重新打开凭证并核对'; return }
      const comment = review.comment.trim()
      if (review.action === 'REJECT' && comment.length < 5) { this.reviewError = '请填写至少5个字的具体修改要求'; return }
      this.acting = true
      try {
        await teacherInternshipInsuranceVerify(review.id, { action: review.action, comment, expectedVersion: review.version })
        if (review.seq !== this.loadSeq || review.batchId !== this.batchId) return
        this.receipt = review.action === 'REJECT' ? `${review.studentName}的保险已退回，等待学生补正重交。` : `${review.studentName}的保险已通过核验，请继续关注其他上岗条件。`
        delete this.drafts[review.id]; this.review = null
        await this.load()
      } catch (e) {
        if (review.seq !== this.loadSeq || review.batchId !== this.batchId) return
        this.conflict = Number(e?.code) === 409 || Math.floor(Number(e?.code) / 1000) === 409 || e?.code === 'DATA_CONFLICT'
        this.reviewError = this.conflict ? '保单已变化，意见已保留。请重新读取保单、打开凭证并核对后再提交。' : (e?.message || '核验失败，意见已保留，请重试')
      } finally { this.acting = false }
    }
  }
}
</script>

<style scoped>
.iv__comment{box-sizing:border-box;width:100%;min-height:120px;padding:12px;border:1px solid var(--border-light);border-radius:var(--radius-md);background:var(--bg-card);font-size:var(--font-size-md);line-height:1.6}
.iv__preview{display:flex;flex-direction:column;gap:10px;padding:12px;border:1px solid var(--border-light);border-radius:var(--radius-md);background:var(--gray-50)}.iv__preview-close{width:auto;min-height:36px;margin:0;padding:0 12px;border:1px solid var(--border-light);background:var(--bg-card);color:var(--text-secondary);font-size:var(--font-size-sm)}.iv__preview-loading{padding:36px 12px;text-align:center;color:var(--text-secondary);background:#fff;border-radius:8px}.iv__preview-page{display:block;width:100%;border-radius:8px;background:#fff;box-shadow:0 1px 4px rgba(15,23,42,.08)}.iv__preview-note{font-size:var(--font-size-xs);line-height:1.5;color:var(--text-secondary)}
.iv__batch{display:flex;align-items:center;justify-content:space-between;gap:var(--space-3);padding:var(--space-3)}.iv__batch-copy{min-width:0;display:flex;flex-direction:column;gap:3px}.iv__eyebrow{font-size:var(--font-size-xs);color:var(--text-tertiary)}.iv__batch-name{font-size:var(--font-size-md);font-weight:600;color:var(--text-primary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.iv__picker{flex-shrink:0}.iv__pick{color:var(--teacher-700);font-size:var(--font-size-sm);white-space:nowrap}.iv__summary{display:flex;gap:var(--space-3);align-items:stretch;padding:var(--space-3)}.iv__summary-main{flex:1;min-width:0}.iv__summary-label{display:block;font-size:var(--font-size-xs);color:var(--text-tertiary)}.iv__summary-number{display:flex;align-items:baseline;gap:4px;margin-top:4px}.iv__summary-number text:first-child{font-size:34px;line-height:1;font-weight:700;color:var(--teacher-700)}.iv__summary-number text:last-child{font-size:var(--font-size-sm);color:var(--text-secondary)}.iv__summary-note{display:block;margin-top:8px;font-size:var(--font-size-xs);line-height:1.5;color:var(--text-secondary)}.iv__summary-metrics{width:42%;display:grid;grid-template-columns:1fr 1fr;background:var(--gray-50);border-radius:var(--radius-md);overflow:hidden}.iv__metric{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;padding:10px 5px;border-left:1px solid var(--border-light)}.iv__metric:first-child{border-left:0}.iv__metric text:first-child{font-size:var(--font-size-lg);font-weight:700;color:var(--success-700)}.iv__metric.is-danger text:first-child{color:var(--danger-600)}.iv__metric text:last-child{font-size:10px;color:var(--text-tertiary)}.iv{display:flex;flex-direction:column;gap:var(--space-3);padding:var(--space-3)}.iv__head{align-items:flex-start}.iv__identity{min-width:0}.iv__sub{display:block;font-size:var(--font-size-xs);color:var(--text-tertiary);margin-top:3px;word-break:break-word}.iv__detail-box{display:flex;flex-direction:column;gap:8px;padding:var(--space-2) var(--space-3);background:var(--gray-50);border-radius:var(--radius-md)}.iv__row{display:flex;gap:var(--space-3);min-width:0}.iv__row-k{font-size:var(--font-size-xs);color:var(--text-tertiary);width:62px;flex-shrink:0}.iv__row-v{min-width:0;flex:1;font-size:var(--font-size-sm);line-height:1.5;color:var(--text-primary);word-break:break-word}.iv__policy{font-family:monospace}.iv__evidence{display:flex;align-items:center;justify-content:space-between;gap:var(--space-3);padding:var(--space-2) var(--space-3);border:1px solid var(--success-200,#bbf7d0);border-radius:var(--radius-md);background:var(--success-50)}.iv__evidence.is-missing{border-color:var(--danger-200,#fecaca);background:var(--danger-50)}.iv__evidence-copy{min-width:0}.iv__evidence-title{display:block;font-size:var(--font-size-sm);font-weight:600;color:var(--text-primary)}.iv__evidence-text{display:block;margin-top:3px;font-size:var(--font-size-xs);line-height:1.45;color:var(--text-secondary)}.iv__meta{display:flex;flex-wrap:wrap;justify-content:space-between;gap:5px 12px;font-size:var(--font-size-xs);color:var(--text-tertiary)}.iv__actions{display:flex;gap:var(--space-2)}.iv__reject,.iv__approve{min-height:var(--touch-target-min);border-radius:var(--radius-md);font-size:var(--font-size-md)}.iv__reject{border:1px solid var(--danger-500);background:var(--bg-card);color:var(--danger-600)}.iv__approve{border:none;background:var(--teacher-600);color:#fff}.iv__reject::after,.iv__approve::after{border:none}.iv__reject[disabled],.iv__approve[disabled]{opacity:.5}@media(max-width:360px){.iv__summary{flex-direction:column}.iv__summary-metrics{width:100%}.iv__batch{align-items:flex-start}}
</style>
