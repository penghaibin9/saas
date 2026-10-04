<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="材料审核" subtitle="已交/缺交名单 · 退回重交 · 最终版本" show-back />
    <view class="page-pad mr__context">
      <view v-if="batches.length" class="card mr__batch">
        <text>{{ batches[batchIndex]?.name || '请选择批次' }}</text>
        <picker :range="batchLabels" :value="batchIndex" :disabled="!!actingId" @change="onBatch">
          <text class="mr__switch">切换批次 ▾</text>
        </picker>
      </view>
      <view v-if="requirements.length" class="card mr__requirement">
        <text class="mr__eyebrow">当前收件要求</text>
        <picker :range="requirementLabels" :value="requirementIndex" :disabled="!!actingId" @change="onRequirement">
          <view class="mr__requirement-choice">
            <view class="flex-1"><text class="t-md t-bold">{{ currentRequirement?.materialName }}</text></view>
            <text class="mr__switch">切换 ▾</text>
          </view>
        </picker>
      </view>
      <view v-if="coverage" class="card mr__summary">
        <view><text>{{ coverage.requiredStudents }}</text><text>应交</text></view>
        <view><text>{{ coverage.effectiveSubmittedStudents }}</text><text>已交</text></view>
        <view class="is-danger"><text>{{ coverage.missingStudents }}</text><text>缺交/待重交</text></view>
        <view class="is-warning"><text>{{ coverage.pendingReviewStudents }}</text><text>待审核</text></view>
      </view>
      <view class="mr__tabs" v-if="currentRequirement">
        <button v-for="item in states" :key="item.value" :class="{ 'is-on': stateFilter === item.value }" @click="setState(item.value)">{{ item.label }}</button>
      </view>
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="currentRequirement">
        <MobileGlobalState v-if="!rows.length" state="empty" :title="emptyTitle" description="可切换已交、缺交或全部学生查看。" />
        <view v-for="row in rows" :key="row.internshipId" class="card mr">
          <view class="row-between">
            <view class="flex-1"><text class="t-md t-bold">{{ row.studentName }}</text><text class="mr__sub">{{ row.studentNo }} · {{ row.enterpriseName || '企业待定' }}</text></view>
            <MobileStatusTag :label="submissionLabel(row)" :type="submissionTone(row)" />
          </view>

          <template v-if="row.submission">
            <view v-for="file in row.submission.files" :key="file.slotNo" class="mr__file">
              <view class="flex-1">
                <text>{{ file.fileName || ('第' + file.slotNo + '份材料') }}</text>
                <text class="mr__sub">第{{ file.versionNo }}版 · {{ file.statusText }}</text>
              </view>
              <button @click="preview(file.fileId)">查看</button>
            </view>
            <text v-if="row.submission.submitComment" class="mr__comment">学生说明：{{ row.submission.submitComment }}</text>
            <text v-if="row.submission.reviewComment" class="mr__review">上次审核：{{ row.submission.reviewComment }}</text>
            <view v-if="row.submission.status === 'SUBMITTED' && canReview" class="mr__actions">
              <button class="mr__return flex-1" :disabled="actingId === row.submission.id" @click="review(row, 'RETURN')">退回重交</button>
              <button class="mr__approve flex-1" :disabled="actingId === row.submission.id" @click="review(row, 'APPROVE')">审核通过</button>
            </view>
          </template>
          <MobileInlineAlert v-else type="warning" description="该学生当前没有有效提交；缺交名单由应交人群减去待审核/已通过提交计算，不按当前分页猜测。" />
        </view>
        <button v-if="hasMore" class="btn btn-ghost" :disabled="loadingMore" @click="loadMore">{{ loadingMore ? '加载中…' : '加载更多' }}</button>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import {
  teacherInternshipMaterialRequirements,
  teacherInternshipMaterialCoverage,
  teacherInternshipMaterialStudents,
  teacherInternshipMaterialReview
} from '@/services/internshipApi'
import { openBusinessFile } from '@/services/fileApi'
import fileSdk from '@/services/fileSdk'
import { materialSubmissionView, refreshFileReadiness, filesReadyForBusiness } from '@/services/fileReadiness.mjs'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { normalizeError } from '@/services/request'
import { useInternshipContextStore } from '@/stores/internshipContext'
import { toast } from '@/utils/nav'

const STATES = [
  { value: 'PENDING_REVIEW', label: '待审核' },
  { value: 'SUBMITTED', label: '已交材料' },
  { value: 'MISSING', label: '缺交' },
  { value: 'ALL', label: '全部' }
]

export default {
  data() {
    return {
      state: 'loading',
      batches: [], batchId: '', batchIndex: 0,
      requirements: [], requirementIndex: 0,
      coverage: null, rows: [],
      stateFilter: 'PENDING_REVIEW', states: STATES,
      page: 1, hasMore: false, loadingMore: false, actingId: '', requestSeq:0, viewSequence:0, generation:currentSessionGeneration(), hidden:false
    }
  },
  computed: {
    context() { return useInternshipContextStore() },
    batchLabels() { return this.batches.map((b) => `${b.name} · ${b.studentCount}人`) },
    requirementLabels() { return this.requirements.map((r) => r.materialName) },
    currentRequirement() { return this.requirements[this.requirementIndex] || null },
    canReview() { return this.context.can('internship.report.review') },
    emptyTitle() { return this.stateFilter === 'MISSING' ? '当前没有缺交学生' : this.stateFilter === 'PENDING_REVIEW' ? '当前没有待审核材料' : this.stateFilter==='SUBMITTED'?'当前没有已交材料':'当前没有材料记录' }
  },
  onLoad() { this.load() },
  onShow() {const wasHidden=this.hidden;this.hidden=false;if(this.generation!==currentSessionGeneration()){this.rows=[];this.requirements=[];this.coverage=null;this.load()}else if(wasHidden){if(this.currentRequirement)return this.loadRequirement();if(this.state==='loading')return this.load()}},
  onHide() {this.hidden=true;this.viewSequence++},
  onUnload() {this.hidden=true;this.requestSeq++;this.viewSequence++},
  onReachBottom() { this.loadMore() },
  methods: {
    current(seq,generation,batchId=this.batchId) {return !this.hidden && seq===this.viewSequence && generation===currentSessionGeneration() && String(batchId)===String(this.batchId)},
    submissionLabel(row) { return row.submission?.statusLabel || '未提交' },
    submissionTone(row) {
      const value = row.submission?.status
      if (value === 'APPROVED') return 'success'
      if (value === 'RETURNED' || !value) return 'danger'
      if (value === 'SUBMITTED') return 'warning'
      return 'default'
    },
    async load() {
      const seq=++this.requestSeq,generation=this.generation=currentSessionGeneration()
      this.viewSequence++;this.rows=[];this.coverage=null;this.requirements=[];this.actingId='';this.loadingMore=false
      this.state = 'loading'
      try {
        this.context.restore()
        await this.context.load(true)
        if(this.hidden || seq!==this.requestSeq || generation!==currentSessionGeneration())return
        this.batches = this.context.batches || []
        this.batchId = this.context.selectedBatchId || ''
        this.batchIndex = Math.max(0, this.batches.findIndex((b) => String(b.id) === String(this.batchId)))
        if (!this.batchId) {
          this.requirements = []; this.rows = []; this.coverage = null; this.state = 'ready'; return
        }
        const requirements = await teacherInternshipMaterialRequirements(this.batchId) || []
        if(this.hidden || seq!==this.requestSeq || generation!==currentSessionGeneration())return
        this.requirements=requirements
        if (this.requirementIndex >= this.requirements.length) this.requirementIndex = 0
        await this.loadRequirement()
      } catch (e) {
        if(this.hidden || seq!==this.requestSeq || generation!==currentSessionGeneration())return
        this.rows = []; this.coverage = null; this.state = 'error'; toast('材料审核读取失败，请重新读取')
      }
    },
    async loadRequirement() {
      const req = this.currentRequirement
      const seq=++this.viewSequence,generation=this.generation,batchId=this.batchId
      this.rows=[];this.coverage=null;this.loadingMore=false
      this.page = 1; this.hasMore = false
      if (!req) {this.state='ready';return}
      this.state='loading'
      try {
        const [coverage, data] = await Promise.all([teacherInternshipMaterialCoverage(req.id),teacherInternshipMaterialStudents(req.id, { state: this.stateFilter, page: 1, pageSize: 20 })])
        if(!this.current(seq,generation,batchId))return
        this.coverage = coverage;this.rows = (data?.items || []).map(row=>({...row,submission:materialSubmissionView(row.submission)}));this.hasMore = !!data?.hasMore;this.state='ready'
      }catch {if(this.current(seq,generation,batchId)){this.state='error';toast('材料名单读取失败，请重新读取')}}
    },
    async onBatch(e) {
      this.batchIndex = Number(e.detail.value) || 0
      this.context.selectBatch(this.batches[this.batchIndex]?.id)
      this.batchId = this.context.selectedBatchId
      this.requirementIndex = 0
      await this.load()
    },
    async onRequirement(e) {
      this.requirementIndex = Number(e.detail.value) || 0
      await this.loadRequirement()
    },
    async setState(value) {
      if (this.actingId || this.stateFilter === value) return
      this.stateFilter = value
      await this.loadRequirement()
    },
    async loadMore() {
      const req = this.currentRequirement
      if (!req || !this.hasMore || this.loadingMore) return
      this.loadingMore = true
      const seq=this.viewSequence,generation=this.generation,batchId=this.batchId
      try {
        const next = this.page + 1
        const data = await teacherInternshipMaterialStudents(req.id, {
          state: this.stateFilter, page: next, pageSize: 20
        })
        if(!this.current(seq,generation,batchId))return
        this.rows = [...this.rows, ...(data?.items || []).map(row=>({...row,submission:materialSubmissionView(row.submission)}))]
        this.page = next
        this.hasMore = !!data?.hasMore
      } catch {if(this.current(seq,generation,batchId))toast('更多材料读取失败，当前名单已保留，请重试')}
      finally {if(this.current(seq,generation,batchId))this.loadingMore = false}
    },
    async preview(fileId) {
      if(this.hidden || this.generation!==currentSessionGeneration())return
      try { await openBusinessFile(fileId) }
      catch (e) { toast('材料暂时无法打开，请重新读取后重试') }
    },
    review(row, action) {
      const submission = row.submission
      if (!submission || submission.status !== 'SUBMITTED' || this.actingId || !this.canReview || this.hidden || this.generation!==currentSessionGeneration()) return
      const seq=this.viewSequence,generation=this.generation,batchId=this.batchId
      const current=()=>this.current(seq,generation,batchId) && this.rows.some(item=>String(item.submission?.id)===String(submission.id) && item.submission.version===submission.version)
      const returning = action === 'RETURN'
      uni.showModal({
        title: returning ? '退回学生重交' : '审核通过',
        editable: true,
        confirmText:returning?'确认退回':'确认通过',cancelText:'取消',
        placeholderText: returning ? '请写明需要修改的内容（至少5字）' : '可填写审核意见',
        success: async (r) => {
          if (!r.confirm || !current() || this.actingId) return
          const comment = String(r.content || '').trim()
          if (returning && comment.length < 5) return toast('退回原因至少5个字')
          this.actingId = submission.id
          try {
            if(!returning) {
              let files
              try {files=await refreshFileReadiness(submission.files || [],id=>fileSdk.metadata(id),current)}
              catch {if(current())toast('材料安全状态读取失败，请重新读取后审核');return}
              if(!current())return
              if(!files?.length || !filesReadyForBusiness(files)){toast('材料尚未安全可用，不能审核通过');return}
            }
            if(!current())return
            await teacherInternshipMaterialReview(submission.id, {
              action, comment, expectedVersion: submission.version
            })
            if(!current())return
            toast(returning ? '已退回，学生可提交新文件版本' : '审核通过，最终版本可进入归档')
            await this.loadRequirement()
          } catch (e) {if(current())toast(normalizeError(e).text)}
          finally {if(String(this.actingId)===String(submission.id))this.actingId = ''}
        }
      })
    }
  }
}
</script>

<style scoped>
.mr__context{display:flex;flex-direction:column;gap:10px}.mr__batch,.mr__requirement{padding:12px}.mr__batch,.mr__requirement-choice{display:flex;align-items:center;justify-content:space-between;gap:10px}.mr__switch{color:var(--teacher-700);font-size:12px}.mr__eyebrow,.mr__sub{display:block;margin-bottom:3px;font-size:10px;color:var(--text-tertiary)}.mr__summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));overflow:hidden}.mr__summary view{display:flex;flex-direction:column;align-items:center;gap:3px;padding:10px 3px;border-left:1px solid var(--border-light)}.mr__summary view:first-child{border-left:0}.mr__summary text:first-child{font-size:20px;font-weight:700}.mr__summary text:last-child{font-size:10px;color:var(--text-tertiary)}.mr__summary .is-danger text:first-child{color:var(--danger-600)}.mr__summary .is-warning text:first-child{color:var(--warning-700)}.mr__tabs{display:grid;grid-template-columns:repeat(3,1fr);gap:6px}.mr__tabs button{min-height:38px;border:1px solid var(--border-light);border-radius:8px;background:var(--bg-card);font-size:12px}.mr__tabs button::after{border:none}.mr__tabs button.is-on{border-color:var(--teacher-500);background:var(--teacher-50);color:var(--teacher-700);font-weight:600}.mr{display:flex;flex-direction:column;gap:10px;padding:12px}.mr__file{display:flex;align-items:center;gap:10px;padding:8px 10px;border-radius:8px;background:var(--gray-50)}.mr__file button{margin:0;padding:3px 6px;min-height:0;border:0;background:transparent;color:var(--teacher-700);font-size:11px}.mr__file button::after{border:none}.mr__comment,.mr__review{display:block;padding:8px;border-radius:6px;font-size:12px;line-height:1.5}.mr__comment{background:var(--gray-50);color:var(--text-secondary)}.mr__review{background:var(--warning-50);color:var(--warning-700)}.mr__actions{display:flex;gap:8px}.mr__return,.mr__approve{min-height:44px;border-radius:8px;font-size:14px}.mr__return{border:1px solid var(--danger-500);background:var(--bg-card);color:var(--danger-600)}.mr__approve{border:0;background:var(--teacher-600);color:#fff}.mr__return::after,.mr__approve::after{border:none}
</style>
