<template>
  <view class="mobile-page mobile-teacher page-wrap teacher-guidance">
    <MobileNavBar variant="teacher" :title="receiptId ? '指导记录' : '新增指导记录'" show-back />
    <MobileGlobalState :state="state" :description="actionError" @retry="load">
      <view class="page-pad ig__page" v-if="state === 'ready'">
        <view v-if="receiptId" class="card ig__section">
          <text class="ig__section-title">{{ receipt ? '指导记录已保存' : '核对指导记录' }}</text>
          <template v-if="receipt">
            <text>指导编号：{{ receipt.id }}</text>
            <text>{{ receipt.studentName }} · {{ receipt.guidanceDateLabel }} · {{ receipt.methodLabel }}</text>
            <text>{{ receipt.content }}</text>
            <button v-if="receipt.attachment" class="mobile-control btn btn-outline" @click="openReceiptAttachment">查看指导佐证</button>
            <ReportFilePreview ref="receiptPreview" />
            <MobileInlineAlert v-if="receipt.attachmentError" type="warning" :description="receipt.attachmentError" />
            <button class="mobile-control btn btn-outline" @click="startNext">继续登记指导</button>
          </template>
          <MobileInlineAlert v-if="actionError" type="warning" :description="actionError" />
          <button v-if="!receipt" class="mobile-control btn btn-outline" :disabled="submitting" @click="readReceipt">重新读取指导记录</button>
        </view>
        <template v-else>
        <view class="ig__batch" v-if="batches.length">
          <view class="ig__batch-copy">
            <text class="ig__batch-name">{{ batches[batchIndex]?.name || '请选择批次' }}</text>
          </view>
          <picker v-if="batches.length > 1" class="mobile-picker ig__picker" mode="selector" :range="batchLabels" :value="batchIndex" :disabled="draftLocked" @change="onBatch">
            <view class="ig__pick-val">切换批次 <text class="ig__arrow">▾</text></view>
          </picker>
        </view>


        <MobileGlobalState v-if="!batches.length" state="empty" title="暂无实习批次"
          description="当前身份的数据范围内没有可办理的实习批次。" />
        <MobileGlobalState v-else-if="!students.length" state="empty" title="暂无可记录学生"
          description="当前批次仅可对本人指导的实习学生新增指导记录。" />
        <view class="ig__row ig__student-search">
          <input class="mobile-input ig__input" v-model="draftKeyword" placeholder="按姓名或学号查找学生" :disabled="draftLocked" />
          <button class="mobile-control btn btn-outline" :disabled="draftLocked" @click="searchStudents">查询</button>
        </view>
        <button v-if="page * 20 < total" class="mobile-control btn btn-outline" :disabled="loadingMore || draftLocked" @click="loadMore">{{ loadingMore ? '正在读取…' : '加载更多学生' }}</button>

        <template v-if="students.length">
          <view class="card ig__section">
            <view class="ig__section-head">
              <text class="ig__section-title">指导对象与方式</text>
            </view>
            <view class="ig__row">
              <text class="ig__label">指导日期 <text class="ig__required">*</text></text>
              <picker class="mobile-picker ig__picker" mode="date" :value="guidanceDate" :disabled="draftLocked" @change="(e) => { if (!draftLocked) guidanceDate = e.detail.value }">
                <view class="ig__pick-field">{{ guidanceDate || '请选择实际指导日期' }}</view>
              </picker>
            </view>
            <view class="ig__row">
              <text class="ig__label">指导学生 <text class="ig__required">*</text></text>
              <picker class="mobile-picker ig__picker" mode="selector" :range="studentLabels" :value="studentIndex" :disabled="draftLocked" @change="onStudent">
                <view class="ig__pick-field">{{ studentLabels[studentIndex] || '请选择' }}<text class="ig__arrow">▾</text></view>
              </picker>
            </view>
            <view class="ig__row">
              <text class="ig__label">指导方式 <text class="ig__required">*</text></text>
              <picker class="mobile-picker ig__picker" mode="selector" :range="methodLabels" :value="methodIndex" :disabled="draftLocked" @change="onMethod">
                <view class="ig__pick-field">{{ methodLabels[methodIndex] }}<text class="ig__arrow">▾</text></view>
              </picker>
            </view>
            <view class="ig__row">
              <text class="ig__label">指导主题</text>
              <input class="mobile-input ig__input" v-model="topic" :disabled="draftLocked" placeholder="如：岗位适应情况回访" maxlength="200" />
            </view>
          </view>

          <view class="card ig__section">
            <view class="ig__section-head">
              <text class="ig__section-title">指导内容</text>
            </view>
            <view class="ig__field">
              <text class="ig__field-label">本次指导内容 <text class="ig__required">*</text></text>
              <textarea class="mobile-textarea ig__textarea" v-model="content" :disabled="draftLocked" :maxlength="8000" placeholder="说明学生当前表现、遇到的问题和本次指导过程" placeholder-class="ig__ph" />
              <text class="ig__count">{{ content.length }}/8000</text>
            </view>
            <button class="mobile-control btn btn-ghost" :aria-expanded="detailsExpanded" @click="detailsExpanded=!detailsExpanded">{{ detailsExpanded ? '收起处理建议与后续安排' : '处理建议与后续安排（选填）' }}</button>
            <view v-show="detailsExpanded" class="ig__field">
              <text class="ig__field-label">处理建议</text>
              <textarea class="mobile-textarea ig__textarea ig__textarea--sm" v-model="suggestion" :disabled="draftLocked" :maxlength="1000" placeholder="填写学生下一步可执行的改进建议（可选）" placeholder-class="ig__ph" />
              <text class="ig__count">{{ suggestion.length }}/1000</text>
            </view>
          </view>

          <view v-show="detailsExpanded" class="card ig__section">
            <view class="ig__section-head">
              <text class="ig__section-title">后续安排</text>
            </view>
            <view class="ig__row">
              <text class="ig__label">下次跟进</text>
              <picker class="mobile-picker ig__picker" mode="date" :value="nextFollowDate" :disabled="draftLocked" @change="onFollow">
                <view class="ig__pick-field">{{ nextFollowDate || '暂不设置' }}<text class="ig__arrow">▾</text></view>
              </picker>
            </view>
            <view class="ig__switch-row">
              <view class="ig__switch-copy"><text class="ig__switch-title">标记为风险</text><text class="ig__switch-hint">保存后自动生成风险单并进入处置流程</text></view>
              <switch :checked="toRisk" :disabled="draftLocked" color="var(--danger-500)" @change="(e) => { if (!draftLocked) toRisk = e.detail.value }" />
            </view>
            <view class="ig__switch-row">
              <view class="ig__switch-copy"><text class="ig__switch-title">通知辅导员</text><text class="ig__switch-hint">用于需要班级协同或家校跟进的情况</text></view>
              <switch :checked="notifyCounselor" :disabled="draftLocked" color="var(--teacher-600)" @change="(e) => { if (!draftLocked) notifyCounselor = e.detail.value }" />
            </view>
          </view>

          <MobileInlineAlert v-if="toRisk" type="warning" description="本次记录会同步生成风险单，请确保指导内容和风险事实描述完整。" />
          <view class="card ig__section">
            <text class="ig__section-title">指导照片佐证（选填）</text>
            <text>照片完成安全检查后可保存。</text>
            <button class="mobile-control btn btn-outline" :disabled="submitting || uploading || !!pendingBody" @click="choosePhoto">拍照或选择照片</button>
            <template v-if="photo">
              <text>{{ photo.fileName }} · {{ photo.statusText }}</text>
              <button v-if="photo.readyForBusiness" class="mobile-control btn btn-outline" @click="openPhoto">查看照片</button>
              <button v-else class="mobile-control btn btn-outline" :disabled="uploading" @click="refreshPhoto">重新核对安全状态</button>
              <button class="mobile-control btn btn-outline" :disabled="submitting || uploading || !!pendingBody" @click="photo = null">移除照片</button>
            </template>
          </view>
        </template>
        <MobileInlineAlert v-if="actionError" type="warning" :description="actionError" />
        <button v-if="pendingBody" class="mobile-control btn btn-outline" :disabled="submitting || uploading"
          @click="load(true)">重新读取学生名单</button>
        </template>
      </view>
    </MobileGlobalState>

    <MobileSafeAreaBar v-if="state === 'ready' && students.length && !receiptId">
      <button class="mobile-control btn btn-primary flex-1" :disabled="submitting || uploading || (photo && !photo.readyForBusiness)" @click="submit">{{ submitting ? '保存中…' : pendingBody ? '重试原提交并核对结果' : '保存指导记录' }}</button>
    </MobileSafeAreaBar>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { teacherInternshipRoster, teacherInternshipStudentDetail } from '@/services/internshipApi'
import { useInternshipContextStore } from '@/stores/internshipContext'
import { realRequest, normalizeError } from '@/services/request'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { uploadBusinessFile, fileSdk } from '@/services/fileApi'
import { normalizeFileReadiness, refreshFileReadiness } from '@/services/fileReadiness.mjs'
import ReportFilePreview from '@/components/ReportFilePreview.vue'
import { toast } from '@/utils/nav'

const METHODS = [
  { key: 'ONSITE', label: '现场' }, { key: 'ONLINE', label: '微信或QQ（即时聊天）指导' }, { key: 'PHONE', label: '电话' },
  { key: 'VIDEO', label: '视频' }, { key: 'ENTERPRISE_FEEDBACK', label: '企业导师反馈' }
]

export default {
  components: { ReportFilePreview },
  data() {
    return {
      state: 'loading', students: [], studentIndex: 0,
      batches: [], batchId: '', batchIndex: 0,
      methodLabels: METHODS.map((m) => m.label), methodIndex: 0,
      detailsExpanded:false, topic: '', content: '', suggestion: '', nextFollowDate: '', guidanceDate: '',
      toRisk: false, notifyCounselor: false, submitting: false, active: true, disposed: false,
      page: 1, total: 0, draftKeyword: '', keyword: '', loadingMore: false,
      epoch: 0, photoEpoch: 0, uploading: false, selectingPhoto: false, photo: null, actionError: '',
      generation: currentSessionGeneration(), requestKey: '', pendingBody: null, receiptId: '', receipt: null,
      requestedBatch: '', requestedRecord: ''
    }
  },
  onLoad(options = {}) { this.requestedBatch = String(options.batchId || ''); this.requestedRecord = String(options.internshipId || ''); this.receiptId = String(options.guidanceId || ''); this.load() },
  onHide() { if (this.selectingPhoto) return; this.$refs.receiptPreview?.reset(); this.active = false; this.epoch++; this.photoEpoch++; this.uploading = false; this.submitting = false; this.loadingMore = false },
  onShow() { if (!this.active) { this.active = true; this.load(true) } },
  onUnload() { this.$refs.receiptPreview?.reset(); this.disposed = true; this.active = false; this.epoch++; this.photoEpoch++; this.photo = null; this.pendingBody = null; this.selectingPhoto = false; this.uploading = false },
  computed: {
    studentLabels() { return this.students.map((s) => `${s.name}（${s.studentNo}）· ${s.enterpriseName || '未落实企业'}`) },
    batchLabels() { return this.batches.map((b) => b.name) },
    selectedStudent() { return this.students[this.studentIndex] || null },
    draftLocked() { return this.submitting || this.uploading || !!this.pendingBody }
  },
  methods: {
    fence() {
      const epoch = this.epoch, generation = currentSessionGeneration(), batch = this.batchId,
        student = this.selectedStudent?.id || ''
      return () => this.active && !this.disposed && epoch === this.epoch && generation === currentSessionGeneration() &&
        generation === this.generation && batch === this.batchId && student === (this.selectedStudent?.id || '')
    },
    resetDraft() {
      this.topic = ''; this.content = ''; this.suggestion = ''; this.nextFollowDate = ''; this.guidanceDate = ''
      this.toRisk = false; this.notifyCounselor = false; this.photo = null; this.requestKey = ''; this.pendingBody = null; this.actionError = ''
      this.photoEpoch++; this.uploading = false; this.selectingPhoto = false
    },
    async load(preserve = false) {
      const epoch = ++this.epoch, generation = currentSessionGeneration(), previousBatch = this.batchId
      let oldStudent = this.pendingBody?.internshipId || (preserve ? this.selectedStudent?.id : this.requestedRecord)
      if (generation !== this.generation) { this.resetDraft(); this.receiptId = ''; this.receipt = null; this.requestedBatch = ''; this.requestedRecord = ''; oldStudent = ''; preserve = false }
      this.generation = generation
      const current = () => this.active && !this.disposed && epoch === this.epoch && generation === currentSessionGeneration()
      this.state = 'loading'; this.loadingMore = false
      try {
        const context = useInternshipContextStore()
        context.restore()
        const selected = await context.load(true)
        if (!current()) return
        if (!context.can('internship.guidance.manage')) { this.students = []; this.receipt = null; this.state = 'forbidden'; return }
        if (this.requestedBatch && context.selectedBatchId !== this.requestedBatch) context.selectBatch(this.requestedBatch)
        if (this.requestedBatch && String(context.selectedBatchId) !== this.requestedBatch) throw { message: '该批次不在当前可办理范围内' }
        this.batches = context.batches || []
        this.batchId = context.selectedBatchId || selected || ''
        this.batchIndex = Math.max(0, this.batches.findIndex((b) => String(b.id) === String(this.batchId)))
        if (this.pendingBody && String(this.batchId) !== String(this.pendingBody.batchId)) throw { message: '当前批次已切换，请返回核对原指导对象' }
        if (!this.batchId) {
          this.students = []
          this.state = 'ready'
          return
        }
        if (preserve && previousBatch && String(this.batchId) !== String(previousBatch)) throw { message: '当前批次已切换，请返回核对原指导对象' }
        const data = await teacherInternshipRoster(this.batchId, { keyword: this.keyword, page: 1 })
        if (!current()) return
        const rows = data.items || []
        if (oldStudent && !rows.some(row => String(row.id) === String(oldStudent))) {
          const target = await teacherInternshipStudentDetail(oldStudent)
          if (!current()) return
          if (String(target.id) !== String(oldStudent) || String(target.batchId) !== String(this.batchId)) throw { message: '原指导学生已不在当前批次，请返回核对' }
          rows.unshift(target)
        }
        this.students = rows
        this.total = data.total || 0; this.page = 1
        this.studentIndex = Math.max(0, this.students.findIndex(row => String(row.id) === String(oldStudent || '')))
        this.state = 'ready'
        if (this.receiptId) await this.readReceipt()
      } catch (e) {
        if (!current()) return
        this.students = []; this.receipt = null; this.actionError = normalizeError(e).text
        this.state = 'error'
      }
    },
    async onBatch(e) {
      if (this.submitting || this.uploading || this.pendingBody) return
      this.resetDraft(); this.receiptId = ''; this.receipt = null; this.requestedRecord = ''; this.keyword = ''; this.draftKeyword = ''
      this.batchIndex = Number(e.detail.value)
      const batch = this.batches[this.batchIndex]
      const context = useInternshipContextStore()
      context.selectBatch(batch && batch.id)
      this.requestedBatch = String(context.selectedBatchId)
      this.students = []
      await this.load()
    },
    onStudent(e) { if (!this.draftLocked) { this.resetDraft(); this.requestedRecord = ''; this.studentIndex = Number(e.detail.value) } },
    onMethod(e) { if (!this.draftLocked) this.methodIndex = Number(e.detail.value) },
    onFollow(e) { if (!this.draftLocked) this.nextFollowDate = e.detail.value },
    async searchStudents() { if (this.draftLocked) return; this.resetDraft(); this.requestedRecord = ''; this.keyword = this.draftKeyword.trim(); await this.load() },
    async loadMore() {
      if (this.loadingMore || this.draftLocked || this.page * 20 >= this.total) return
      const current = this.fence(); this.loadingMore = true
      try {
        const data = await teacherInternshipRoster(this.batchId, { keyword: this.keyword, page: this.page + 1 })
        if (!current()) return
        this.students.push(...(data.items || []).filter(row => !this.students.some(existing => existing.id === row.id))); this.page++; this.total = data.total || 0
      } catch (e) { if (current()) this.actionError = normalizeError(e).text }
      finally { if (current()) this.loadingMore = false }
    },
    async choosePhoto() {
      if (this.uploading || this.submitting || this.pendingBody) return
      const current = this.fence(), op = ++this.photoEpoch; this.uploading = true; this.selectingPhoto = true; this.actionError = ''
      try {
        const picked = await fileSdk.choose({ kind: 'image' })
        this.selectingPhoto = false
        if (!current() || op !== this.photoEpoch || !picked) return
        const uploaded = normalizeFileReadiness(await uploadBusinessFile(picked, { bizType: 'ATTACHMENT' }))
        if (!current() || op !== this.photoEpoch) return
        if (!uploaded.fileId) throw { message: '照片接收结果不完整，请重新选择' }
        this.photo = uploaded
      } catch (e) { if (current() && op === this.photoEpoch) this.actionError = normalizeError(e).text }
      finally { if (op === this.photoEpoch) { this.uploading = false; this.selectingPhoto = false } }
    },
    async refreshPhoto() {
      if (!this.photo || this.uploading || this.submitting) return
      const current = this.fence(), photo = this.photo, op = ++this.photoEpoch; this.uploading = true
      try {
        const files = await refreshFileReadiness([photo], id => fileSdk.metadata(id), () => current() && photo === this.photo && op === this.photoEpoch)
        if (current() && photo === this.photo && op === this.photoEpoch && files) this.photo = files[0]
      } catch (e) { if (current()) this.actionError = normalizeError(e).text }
      finally { if (current() && op === this.photoEpoch) this.uploading = false }
    },
    async openPhoto() { const current = this.fence(); try { if (current() && this.photo?.readyForBusiness) await fileSdk.open(this.photo.fileId) } catch (e) { if (current()) this.actionError = normalizeError(e).text } },
    async readReceipt() {
      this.$refs.receiptPreview?.reset()
      const current = this.fence(), id = this.receiptId; this.actionError = ''
      try {
        const data = await realRequest('/internship/guidances/' + encodeURIComponent(id))
        if (!current() || id !== this.receiptId) return
        if (String(data.id) !== id || String(data.batchId) !== this.batchId || (this.requestedRecord && String(data.internId) !== this.requestedRecord)) throw { message: '指导记录与当前对象不一致，请返回核对' }
        this.receipt = data
      } catch (e) { if (current() && id === this.receiptId) { this.receipt = null; this.actionError = '指导记录回读未完成，请重新读取或返回核对' } }
    },
    async openReceiptAttachment() {
      const current = this.fence(), receipt = this.receipt, viewer = this.$refs.receiptPreview
      if (!current() || !receipt?.attachment || !viewer) return
      await viewer.open(receipt.attachment)
      if (!current() || receipt !== this.receipt) viewer.reset()
    },
    startNext() { const batchId = this.batchId; uni.redirectTo({ url: '/pages/teacher-internship/internship-guidance/index?batchId=' + encodeURIComponent(batchId) }) },
    async submit() {
      if (this.submitting || this.uploading || !this.fence()() || (this.photo && !this.photo.readyForBusiness)) return
      const stu = this.students[this.studentIndex]
      if (!stu) { toast('请选择指导学生'); return }
      if (this.content.trim().length < 2) { toast('指导内容至少 2 个字'); return }
      if (!this.guidanceDate) { toast('请选择实际指导日期'); return }
      const wasUnconfirmed = !!this.pendingBody
      this.requestKey ||= `guide-${Date.now()}-${Math.random().toString(36).slice(2)}`
      const current = this.fence()
      this.submitting = true
      this.actionError = ''
      const body = this.pendingBody || {
        internshipId: stu.id, batchId: this.batchId, method: METHODS[this.methodIndex].key,
        guidanceDate: this.guidanceDate, requestKey: this.requestKey, fileId: this.photo?.fileId || null,
        topic: this.topic.trim(), content: this.content.trim(), suggestion: this.suggestion.trim(),
        nextFollowDate: this.nextFollowDate, toRisk: this.toRisk, notifyCounselor: this.notifyCounselor
      }
      this.pendingBody = body
      try {
        const result = await teacherApi.createInternshipGuidance(body)
        if (!current()) return
        if (!result.id || String(result.batchId) !== this.batchId || String(result.internshipId) !== String(stu.id)) throw { message: '保存回执不完整，请用原提交重试核对' }
        this.receiptId = String(result.id); this.pendingBody = null
        uni.redirectTo({ url: '/pages/teacher-internship/internship-guidance/index?batchId=' + encodeURIComponent(this.batchId) + '&internshipId=' + encodeURIComponent(stu.id) + '&guidanceId=' + encodeURIComponent(this.receiptId) })
      } catch (e) {
        if (!current()) return
        this.actionError = normalizeError(e).text
        if (!wasUnconfirmed && e?.biz && [400, 401, 403, 404, 422].includes(Number(e.httpStatus))) { this.pendingBody = null; this.requestKey = '' }
      } finally { if (current()) this.submitting = false }
    }
  }
}
</script>

<style scoped>
.ig__page{display:flex;flex-direction:column;gap:var(--space-3);padding-bottom:calc(var(--safe-bottom) + 92px)}.ig__batch{display:flex;align-items:center;justify-content:space-between;gap:var(--space-3);padding:var(--space-3)}.ig__batch-copy{min-width:0;display:flex;flex-direction:column;gap:3px}.ig__eyebrow{font-size:var(--font-size-xs);color:var(--text-tertiary)}.ig__batch-name{font-size:var(--font-size-md);font-weight:600;color:var(--text-primary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.ig__picker{flex:1}.ig__pick-val{color:var(--teacher-700);font-size:var(--font-size-sm);white-space:nowrap;text-align:right}.ig__pick-field{font-size:var(--font-size-sm);color:var(--text-primary);text-align:right;word-break:break-word}.ig__arrow{color:var(--text-tertiary);font-size:var(--font-size-xs);margin-left:4px}.ig__selected{display:flex;align-items:center;justify-content:space-between;gap:var(--space-3);padding:var(--space-3);background:var(--teacher-50,#eff6ff);border-color:var(--teacher-200,#bfdbfe)}.ig__selected-copy{min-width:0}.ig__selected-label{display:block;font-size:10px;color:var(--text-tertiary)}.ig__selected-name{display:block;margin-top:3px;font-size:var(--font-size-md);font-weight:600;color:var(--text-primary)}.ig__selected-meta{display:block;margin-top:3px;font-size:var(--font-size-xs);color:var(--text-secondary);word-break:break-word}.ig__selected-method{flex-shrink:0;padding:5px 9px;border-radius:var(--radius-full);background:var(--bg-card);color:var(--teacher-700);font-size:var(--font-size-xs);font-weight:600}.ig__section{display:flex;flex-direction:column;padding:var(--space-3)}.ig__section-head{display:flex;align-items:center;gap:10px;padding-bottom:var(--space-2);border-bottom:1px solid var(--border-light)}.ig__step{display:flex;align-items:center;justify-content:center;width:26px;height:26px;flex-shrink:0;border-radius:50%;background:var(--teacher-600);color:#fff;font-size:var(--font-size-sm);font-weight:700}.ig__section-title{display:block;font-size:var(--font-size-sm);font-weight:600;color:var(--text-primary)}.ig__section-hint{display:block;margin-top:2px;font-size:var(--font-size-xs);color:var(--text-tertiary)}.ig__row{display:flex;align-items:center;min-height:52px;border-bottom:1px solid var(--border-light);gap:var(--space-3)}.ig__label{width:84px;flex-shrink:0;font-size:var(--font-size-sm);color:var(--text-secondary)}.ig__required{color:var(--danger-600)}.ig__input{flex:1;min-width:0;font-size:var(--font-size-sm);color:var(--text-primary);text-align:right}.ig__field{display:flex;flex-direction:column;gap:7px;padding-top:var(--space-3)}.ig__field+.ig__field{padding-top:var(--space-4)}.ig__field-label{font-size:var(--font-size-sm);font-weight:600;color:var(--text-secondary)}.ig__textarea{width:100%;min-height:112px;box-sizing:border-box;font-size:var(--font-size-base);color:var(--text-primary);line-height:1.65;background:var(--gray-50);border:1px solid var(--border-light);border-radius:var(--radius-md);padding:var(--space-3)}.ig__textarea--sm{min-height:82px}.ig__ph{color:var(--text-tertiary)}.ig__count{align-self:flex-end;font-size:10px;color:var(--text-tertiary)}.ig__switch-row{display:flex;align-items:center;justify-content:space-between;gap:var(--space-3);padding:var(--space-3) 0;border-bottom:1px solid var(--border-light)}.ig__switch-row:last-child{border-bottom:0;padding-bottom:0}.ig__switch-copy{min-width:0}.ig__switch-title{display:block;font-size:var(--font-size-sm);font-weight:600;color:var(--text-primary)}.ig__switch-hint{display:block;margin-top:3px;font-size:var(--font-size-xs);line-height:1.45;color:var(--text-tertiary)}@media(max-width:360px){.ig__batch{align-items:flex-start}.ig__selected{align-items:flex-start}.ig__row{align-items:flex-start;padding:12px 0}.ig__pick-field{padding-top:1px}}
.teacher-guidance .ig__page{width:100%;max-width:760px;margin:0 auto;box-sizing:border-box}.teacher-guidance .card{border-radius:8px;box-shadow:none}.teacher-guidance button,.teacher-guidance input{min-height:44px;font-size:15px}.ig__batch{padding:4px 0 12px;border-bottom:1px solid var(--border-light)}.ig__batch-name{font-size:15px;line-height:22px;margin:0;overflow-wrap:anywhere}.ig__pick-val,.ig__pick-field{min-height:44px;display:flex;align-items:center;justify-content:flex-end;font-size:14px;line-height:22px}.ig__section-title,.ig__switch-title{font-size:16px;line-height:24px}.ig__label,.ig__field-label,.ig__switch-hint,.ig__count{font-size:14px;line-height:22px}.ig__textarea{font-size:15px;line-height:22px}.ig__student-search .ig__input{text-align:left}.ig__student-search{gap:12px}.ig__section-head{padding-bottom:10px}.ig__row,.ig__switch-row{min-height:44px}
.ig__row{flex-direction:column;align-items:stretch;gap:8px}.ig__row>.ig__label{width:auto;flex:none}.ig__row>.ig__picker,.ig__row>.ig__input{width:100%;min-width:0;flex:auto;box-sizing:border-box}.ig__pick-field{min-height:44px;height:auto;line-height:1.6;white-space:normal;overflow-wrap:anywhere}
.ig__student-search{flex-direction:row;align-items:center}.ig__student-search>.ig__input{flex:1;width:auto}.ig__student-search>.btn{flex:none;margin:0}.ig__pick-field{text-align:left;justify-content:space-between;align-items:flex-start}.ig__row>.ig__input{text-align:left}
</style>
