<template>
  <view class="mobile-page mobile-teacher page-wrap teacher-materials">
    <MobileNavBar variant="teacher" title="材料审核" show-back />
    <view class="page-pad mr__context">
      <view v-if="batches.length" class="mr__batch"><text>{{ batches[batchIndex]?.name || '请选择批次' }}</text><picker class="mobile-picker" v-if="batches.length > 1" :range="batchLabels" :value="batchIndex" :disabled="!!actingId" @change="onBatch"><text class="mr__switch">切换批次</text></picker></view>
      <view v-if="requirements.length" class="card mr__requirement"><text class="mr__eyebrow">当前收件要求</text><button class="mobile-control mr__requirement-choice" :aria-expanded="requirementMenuOpen" :disabled="!!actingId" @click="requirementMenuOpen = !requirementMenuOpen"><text>{{ currentRequirement?.materialName }}</text><MobileTaskIcon name="chevron-right" tone="teal" plain /></button><view v-if="requirementMenuOpen" class="mr__choices" role="group" aria-label="选择材料收件要求"><button class="mobile-control" v-for="(choice,index) in requirements" :key="choice.id" :aria-pressed="currentRequirement?.id === choice.id" :disabled="!!actingId" @click="chooseRequirement(index)">{{ choice.materialName }}</button></view></view>
      <view v-if="currentRequirement" class="mr__primary-filters">
        <button class="mobile-control" v-for="item in mainStates" :key="item.value" :class="{ 'is-on': stateFilter === item.value }" :disabled="!!actingId" @click="setState(item.value)"><text>{{ item.label }}</text><text v-if="coverage" class="mr__count">{{ stateCount(item.value) }}</text></button>
        <button class="mobile-control" :aria-expanded="moreOpen" :class="{ 'is-on': !mainStates.some(item => item.value === stateFilter) }" :disabled="!!actingId" @click="moreOpen = !moreOpen">更多筛选</button>
      </view>
      <view v-if="currentRequirement && moreOpen" class="card mr__more">
        <view class="mr__search-row"><input class="mobile-input" v-model.trim="keyword" :disabled="!!actingId" placeholder="搜索姓名、学号或企业" @confirm="loadRequirement" /><button class="mobile-control" :disabled="!!actingId" @click="loadRequirement">查询</button></view>
        <view class="mr__tabs"><button class="mobile-control" v-for="item in states" :key="item.value" :class="{ 'is-on': stateFilter === item.value }" :disabled="!!actingId" @click="setState(item.value)">{{ item.label }}</button></view>
        <view v-if="coverage" class="mr__summary"><text>应交 {{ coverage.requiredStudents }} 人</text><text>已交 {{ coverage.effectiveSubmittedStudents }} 人</text><text>缺交/待重交 {{ coverage.missingStudents }} 人</text></view>
      </view>
      <view v-if="currentRequirement && (appliedKeyword || !mainStates.some(item => item.value === stateFilter))" class="mr__active-filter"><text>当前：{{ selectedStateLabel }}{{ appliedKeyword ? ' · ' + appliedKeyword : '' }}</text><button class="mobile-control" v-if="appliedKeyword" @click="clearKeyword">清空搜索</button></view>
      <view v-if="rows.length > 1 || hasMore" class="mr__queue"><button class="mobile-control" :disabled="!!actingId || loadingMore || !activeRowIndex" @click="selectReviewRow(activeRowIndex - 1)">上一位</button><text>第{{ activeRowIndex + 1 }}位 · 已读取{{ rows.length }}位</text><button class="mobile-control" :disabled="!!actingId || loadingMore || (!hasMore && activeRowIndex >= rows.length - 1)" @click="nextReviewRow">{{ loadingMore ? '读取中…' : '下一位' }}</button></view>
    </view>
    <MobileGlobalState :state="state" :description="loadError" @retry="load">
      <MobileGlobalState v-if="!currentRequirement" state="empty" title="暂无可审核的收件要求" description="等待学校发布本批次收件要求。" />
      <view class="page-pad stack" v-if="currentRequirement">
        <MobileGlobalState v-if="!rows.length" state="empty" :title="emptyTitle" description="可切换已通过、已退回或更多筛选查看。" />
        <view v-for="row in displayedRows" :key="row.internshipId" class="card mr">
          <view class="mr__identity"><view class="flex-1"><text class="mr__student">{{ row.studentName }}</text><text class="mr__sub">学号 {{ row.studentNo }}</text><text class="mr__sub">{{ row.enterpriseName || '企业待定' }}</text></view><MobileStatusTag :label="submissionLabel(row)" :type="submissionTone(row)" /></view>
          <template v-if="row.submission">
            <text v-if="row.submission.submitComment" class="mr__comment">学生说明：{{ row.submission.submitComment }}</text>
            <text v-if="row.submission.reviewComment" class="mr__review">审核意见：{{ row.submission.reviewComment }}</text>
            <view class="mr__file-heading"><text>本次提交</text><text>{{ row.submission.files.length }} 份材料</text></view>
            <view v-for="file in visibleFiles(row)" :key="file.slotNo" class="mr__file"><MobileTaskIcon :name="fileIcon(file.fileName)" tone="teal" /><view class="flex-1"><text class="mr__file-name">{{ file.fileName || ('第' + file.slotNo + '份材料') }}</text><text class="mr__sub">第{{ file.versionNo }}版 · {{ file.statusText }}</text></view><button class="mobile-control" @click="preview(file.fileId)">查看</button></view>
            <button v-if="row.submission.files.length > 3" class="mobile-control mr__expand" :aria-expanded="!!expandedFiles[row.submission.id]" @click="toggleFiles(row)">{{ expandedFiles[row.submission.id] ? '收起文件' : '展开全部' + row.submission.files.length + '份' }}</button>
            <view v-if="row.submission.status === 'SUBMITTED' && canReview" class="mr__review-form">
              <text class="mr__file-heading">审核说明</text>
              <textarea class="mobile-textarea" :value="reviewDrafts[row.submission.id]?.comment || ''" :maxlength="-1" :disabled="!!actingId" placeholder="通过可不填；退回请写明补正内容（至少5字）" @input="setReviewComment(row, $event)" />
              <view v-if="draftConflict(row)" class="mr__review"><text>材料版本已变化，原审核意见已保留。请先核对最新文件。</text><button class="mobile-control" :disabled="!!actingId" @click="adoptReviewDraft(row)">已核对最新材料，保留意见继续</button></view>
              <text class="mr__next">通过后学生可查看结果，学校收件台账同步更新。</text>
            </view>
          </template>
          <MobileInlineAlert v-else type="warning" description="尚未收到有效材料。" />
        </view>
        <button v-if="hasMore" class="mobile-control btn btn-ghost" :disabled="loadingMore || !!actingId" @click="loadMore">{{ loadingMore ? '加载中…' : '读取后续学生' }}</button>
      </view>
    </MobileGlobalState>
    <MobileSafeAreaBar v-if="state === 'ready' && activeRow?.submission?.status === 'SUBMITTED' && canReview"><view class="mr__submit-bar"><text>{{ activeRow.studentName }} · 本次材料审核</text><view class="mr__actions"><button class="mobile-control mr__return flex-1" :disabled="!!actingId || draftConflict(activeRow)" @click="review(activeRow, 'RETURN')">退回重交</button><button class="mobile-control mr__approve flex-1" :disabled="!!actingId || draftConflict(activeRow)" @click="review(activeRow, 'APPROVE')">{{ actingId ? '处理中…' : '审核通过' }}</button></view></view></MobileSafeAreaBar>
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
  { value: 'REVIEWED', label: '已审核' },
  { value: 'APPROVED', label: '已通过' },
  { value: 'RETURNED', label: '已退回' },
  { value: 'DRAFT', label: '草稿' },
  { value: 'WITHDRAWN', label: '已撤回' },
  { value: 'MISSING', label: '缺交' },
  { value: 'ALL', label: '全部' }
]

export default {
  data() {
    return {
      state: 'loading', loadError: '',
      batches: [], batchId: '', batchIndex: 0,
      requirements: [], requirementIndex: 0,
      coverage: null, rows: [],
      keyword: '', appliedKeyword: '',
      moreOpen: false, expandedFiles: {}, reviewDrafts: {}, requestedBatch: '', activeInternshipId: '', requirementMenuOpen:false,
      stateFilter: 'PENDING_REVIEW', states: STATES,
      page: 1, hasMore: false, loadingMore: false, actingId: '', requestSeq:0, viewSequence:0, generation:currentSessionGeneration(), hidden:false
    }
  },
  computed: {
    context() { return useInternshipContextStore() },
    batchLabels() { return this.batches.map((b) => `${b.name} · ${b.studentCount}人`) },
    requirementLabels() { return this.requirements.map((r) => r.materialName) },
    currentRequirement() { return this.requirements[this.requirementIndex] || null },
    activeRow() { return this.rows.find(row => String(row.internshipId) === this.activeInternshipId) || this.rows[0] || null },
    displayedRows() { return this.activeRow ? [this.activeRow] : [] },
    activeRowIndex() { return Math.max(0, this.rows.indexOf(this.activeRow)) },
    mainStates() { return this.states.filter(item => ['PENDING_REVIEW', 'APPROVED', 'RETURNED'].includes(item.value)) },
    selectedStateLabel() { return this.states.find(item => item.value === this.stateFilter)?.label || '全部' },
    canReview() { return this.context.can('internship.report.review') },
    emptyTitle() { return ({ MISSING: '当前没有缺交学生', PENDING_REVIEW: '当前没有待审核材料', SUBMITTED: '当前没有已交材料', REVIEWED: '当前没有已审核材料', APPROVED: '当前没有已通过材料', RETURNED: '当前没有退回材料', DRAFT: '当前没有草稿材料', WITHDRAWN: '当前没有撤回材料' })[this.stateFilter] || '当前没有材料记录' }
  },
  onLoad(options={}) { this.requestedBatch=String(options.batchId || '');this.load() },
  onShow() {const wasHidden=this.hidden;this.hidden=false;if(this.generation!==currentSessionGeneration()){this.rows=[];this.requirements=[];this.coverage=null;this.load()}else if(wasHidden){if(this.currentRequirement)return this.loadRequirement();if(this.state==='loading')return this.load()}},
  onHide() {this.hidden=true;this.viewSequence++},
  onUnload() {this.hidden=true;this.requestSeq++;this.viewSequence++},
  methods: {
    chooseRequirement(index) { this.requirementMenuOpen=false;return this.onRequirement({ detail:{ value:index } }) },
    selectReviewRow(index) { if (this.actingId || this.loadingMore || !this.rows[index]) return; this.activeInternshipId = String(this.rows[index].internshipId); this.viewSequence++ },
    async nextReviewRow() { if (this.actingId || this.loadingMore) return; const next = this.activeRowIndex + 1; if (next < this.rows.length) return this.selectReviewRow(next); if (!this.hasMore) return; const sequence = this.viewSequence, generation = this.generation; await this.loadMore(); if (this.current(sequence, generation) && this.rows[next]) this.selectReviewRow(next) },
    stateCount(value) { const field = { PENDING_REVIEW:'pendingReviewStudents', APPROVED:'approvedStudents', RETURNED:'returnedStudents' }[value]; return this.coverage?.[field] ?? '—' },
    visibleFiles(row) { const files = row.submission?.files || []; return this.expandedFiles[row.submission?.id] ? files : files.slice(0, 3) },
    toggleFiles(row) { const id = row.submission?.id; if (id) this.expandedFiles = { ...this.expandedFiles, [id]: !this.expandedFiles[id] } },
    fileIcon(name = '') { return /\.(zip|rar)$/i.test(name) ? 'folder' : 'file-text' },
    clearKeyword() { if (this.actingId) return; this.keyword = ''; return this.loadRequirement() },
    setReviewComment(row, event) { if (this.actingId || this.hidden || this.generation !== currentSessionGeneration() || !this.rows.includes(row)) return; const id = row.submission.id; this.reviewDrafts = { ...this.reviewDrafts, [id]: { version:this.reviewDrafts[id]?.version ?? row.submission.version, comment:event.detail.value } } },
    draftConflict(row) { const draft = this.reviewDrafts[row.submission?.id]; return !!draft && draft.version !== row.submission.version },
    adoptReviewDraft(row) { if (this.actingId || this.hidden || this.generation !== currentSessionGeneration() || !this.rows.includes(row)) return; const draft = this.reviewDrafts[row.submission?.id]; if (draft) this.reviewDrafts = { ...this.reviewDrafts, [row.submission.id]: { ...draft, version:row.submission.version } } },
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
      if(this.generation!==currentSessionGeneration()){this.reviewDrafts={};this.expandedFiles={};this.moreOpen=false;this.activeInternshipId='';this.requirementMenuOpen=false}
      const seq=++this.requestSeq,generation=this.generation=currentSessionGeneration()
      const previousBatch=this.batchId
      this.viewSequence++;this.rows=[];this.coverage=null;this.requirements=[];this.actingId='';this.loadingMore=false
      this.batches=[];this.batchId='';this.batchIndex=0
      this.state = 'loading'; this.loadError = ''
      try {
        this.context.restore()
        await this.context.load(true)
        if(this.hidden || seq!==this.requestSeq || generation!==currentSessionGeneration())return
        if(this.requestedBatch){if(!this.context.selectBatch(this.requestedBatch))throw new Error('此批次不在当前可查看范围');this.requestedBatch=''}
        this.batches = this.context.batches || []
        this.batchId = this.context.selectedBatchId || ''
        if(previousBatch && String(previousBatch)!==String(this.batchId)){this.reviewDrafts={};this.expandedFiles={};this.moreOpen=false}
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
        this.rows = []; this.coverage = null
        const shown=normalizeError(e);this.state=shown.pageState || 'error';this.loadError=shown.text || '材料读取失败，请重试';toast(shown.text)
      }
    },
    async loadRequirement() {
      if (this.actingId) return
      const req = this.currentRequirement
      const seq=++this.viewSequence,generation=this.generation,batchId=this.batchId
      this.rows=[];this.coverage=null;this.loadingMore=false
      this.loadError=''
      this.page = 1; this.hasMore = false
      this.appliedKeyword = this.keyword
      if (!req) {this.state='ready';return}
      this.state='loading'
      try {
        const [coverage, data] = await Promise.all([teacherInternshipMaterialCoverage(req.id, { keyword: this.appliedKeyword }),teacherInternshipMaterialStudents(req.id, { state: this.stateFilter, page: 1, pageSize: 20, keyword: this.appliedKeyword })])
        if(!this.current(seq,generation,batchId))return
        this.coverage = coverage;this.rows = (data?.items || []).map(row=>({...row,submission:materialSubmissionView(row.submission)}));this.hasMore = !!data?.hasMore;this.state='ready'
      }catch(e) {if(this.current(seq,generation,batchId)){const shown=normalizeError(e);this.state=shown.pageState || 'error';this.loadError=shown.text || '材料读取失败，请重试';toast(shown.text)}}
    },
    async onBatch(e) {
      if(this.actingId)return
      this.reviewDrafts={};this.expandedFiles={};this.moreOpen=false;this.activeInternshipId='';this.requirementMenuOpen=false
      this.batchIndex = Number(e.detail.value) || 0
      this.context.selectBatch(this.batches[this.batchIndex]?.id)
      this.batchId = this.context.selectedBatchId
      this.requirementIndex = 0
      this.keyword = ''
      await this.load()
    },
    async onRequirement(e) {
      if(this.actingId)return
      this.expandedFiles={};this.activeInternshipId=''
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
          state: this.stateFilter, page: next, pageSize: 20, keyword: this.appliedKeyword
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
      if(this.draftConflict(row))return toast('材料版本已变化，请核对最新文件后再审核')
      const seq=this.viewSequence,generation=this.generation,batchId=this.batchId
      const current=()=>this.current(seq,generation,batchId) && String(this.activeRow?.submission?.id)===String(submission.id) && this.rows.some(item=>String(item.submission?.id)===String(submission.id) && item.submission.version===submission.version)
      const returning = action === 'RETURN'
      uni.showModal({
        title: returning ? '退回学生重交' : '审核通过',
        editable: true,
        content: this.reviewDrafts[submission.id]?.comment || '',
        confirmText:returning?'确认退回':'确认通过',cancelText:'取消',
        placeholderText: returning ? '请写明需要修改的内容（至少5字）' : '可填写审核意见',
        success: async (r) => {
          if (!r.confirm || !current() || this.actingId) return
          const comment = String(r.content || '').trim()
          if (returning && comment.length < 5) return toast('退回原因至少5个字')
          this.reviewDrafts={...this.reviewDrafts,[submission.id]:{version:submission.version,comment}}
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
            const drafts={...this.reviewDrafts};delete drafts[submission.id];this.reviewDrafts=drafts
            this.actingId = ''
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
.teacher-materials{--brand-primary:var(--teacher-600);font-size:var(--font-size-md);padding-bottom:calc(132px + var(--safe-area-bottom))}
.teacher-materials :deep(.page-pad){width:100%;max-width:760px;margin:0 auto;box-sizing:border-box}
.mr__context{display:flex;flex-direction:column;gap:var(--space-3);padding-bottom:0}
.mr__batch{display:flex;align-items:center;justify-content:space-between;gap:var(--space-3);font-size:var(--font-size-md);line-height:1.6;color:var(--text-secondary)}
.mr__batch>text{min-width:0;overflow-wrap:anywhere}.mr__switch{display:flex;align-items:center;min-height:44px;color:var(--teacher-700);font-size:var(--font-size-base)}
.mr__requirement{padding:var(--space-3) var(--space-4)}.mr__eyebrow{display:block;font-size:var(--font-size-base);color:var(--text-secondary);line-height:1.6}
.mr__requirement-choice{display:flex;align-items:center;gap:var(--space-3);min-height:44px;width:100%;margin:0;padding:0;border:0;background:transparent;font-size:var(--font-size-lg);font-weight:var(--font-weight-semibold);line-height:1.5;text-align:left;color:var(--text-primary)}.mr__requirement-choice::after{border:0}.mr__requirement-choice>text{flex:1;min-width:0;overflow-wrap:anywhere}
.mr__choices{display:flex;flex-direction:column;border-top:1px solid var(--border-light);padding-top:var(--space-2)}.mr__choices>button{width:100%;min-height:44px;margin:0;padding:var(--space-3);line-height:1.6;border:0;background:var(--bg-card);color:var(--text-primary);font-size:var(--font-size-md);text-align:left}.mr__choices>button[aria-pressed=true]{background:var(--teacher-50);color:var(--teacher-700)}.mr__choices>button::after{border:0}
.mr__primary-filters{display:flex;align-items:stretch;gap:var(--space-1);padding:var(--space-1);background:var(--bg-card);border-radius:var(--radius-md)}
.mr__primary-filters>button{display:flex;align-items:center;justify-content:center;gap:var(--space-1);flex:1;min-width:0;min-height:44px;margin:0;padding:var(--space-1);font-size:var(--font-size-base);line-height:1.5;border:0;border-radius:var(--radius-md);background:transparent;color:var(--text-secondary)}
.mr__primary-filters>button::after,.mr__tabs button::after,.mr__file>button::after,.mr__expand::after,.mr__return::after,.mr__approve::after{border:0}
.mr__primary-filters>button.is-on,.mr__tabs>button.is-on{background:var(--teacher-50);color:var(--teacher-700);font-weight:var(--font-weight-semibold)}
.mr__count{font-size:var(--font-size-base);line-height:1.5;padding:0 var(--space-1);border-radius:var(--radius-sm);background:var(--gray-50)}
.mr__more{display:flex;flex-direction:column;gap:var(--space-3);padding:var(--space-3)}.mr__search-row{display:flex;align-items:center;gap:var(--space-2)}
.mr__search-row input{flex:1;min-width:0;min-height:44px;font-size:var(--font-size-md);padding:0 var(--space-2);background:var(--gray-50);border-radius:var(--radius-md)}
.mr__search-row>button,.mr__active-filter>button,.mr__queue>button{min-height:44px;margin:0;padding:0 var(--space-2);font-size:var(--font-size-base);line-height:44px;border:0;background:transparent;color:var(--teacher-700)}
.mr__tabs{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:var(--space-2)}.mr__tabs>button{min-height:44px;width:100%;margin:0;padding:var(--space-1);border:1px solid var(--border-light);border-radius:var(--radius-md);background:var(--bg-card);font-size:var(--font-size-base);line-height:1.5}
.mr__summary{display:flex;flex-wrap:wrap;gap:var(--space-3);font-size:var(--font-size-base);line-height:1.6;color:var(--text-secondary)}
.mr__active-filter,.mr__queue{display:flex;align-items:center;justify-content:space-between;gap:var(--space-2);font-size:var(--font-size-sm);line-height:1.6;color:var(--text-secondary)}
.mr__active-filter>text{min-width:0;overflow-wrap:anywhere}.mr__queue>button[disabled]{color:var(--text-disabled)}
.mr{display:flex;flex-direction:column;gap:var(--space-3);padding:var(--space-4)}
.mr__identity{display:flex;align-items:flex-start;gap:var(--space-3)}.mr__student{display:block;font-size:var(--font-size-xl);font-weight:var(--font-weight-semibold);line-height:1.5;color:var(--text-primary)}
.mr__sub{display:block;margin-top:var(--space-1);color:var(--text-secondary);font-size:var(--font-size-base);line-height:1.6;overflow-wrap:anywhere}
.mr__comment,.mr__review{padding:var(--space-3);border-radius:var(--radius-md);font-size:var(--font-size-base);line-height:1.7;white-space:pre-wrap;overflow-wrap:anywhere}.mr__comment{background:var(--gray-50);color:var(--text-secondary)}.mr__review{background:var(--warning-50);color:var(--warning-700)}
.mr__review>text{display:block}.mr__review>button{min-height:44px;padding:var(--space-2);margin:var(--space-2) 0 0;border:1px solid var(--teacher-600);background:var(--bg-card);font-size:var(--font-size-base);line-height:1.5;color:var(--teacher-700)}
.mr__file-heading{display:flex;align-items:center;justify-content:space-between;font-size:var(--font-size-lg);font-weight:var(--font-weight-semibold);line-height:1.6;color:var(--text-primary)}.mr__file-heading>text:last-child{font-size:var(--font-size-base);font-weight:400;color:var(--text-secondary)}
.mr__file{display:flex;align-items:center;gap:var(--space-3);padding:var(--space-3) 0;border-bottom:1px solid var(--border-light)}
.mr__file-name{display:block;font-size:var(--font-size-md);font-weight:var(--font-weight-medium);line-height:1.6;color:var(--text-primary);overflow-wrap:anywhere}
.mr__file>button{min-height:44px;min-width:44px;flex-shrink:0;padding:0 var(--space-1);margin:0;border:0;background:transparent;color:var(--teacher-700);font-size:var(--font-size-md)}
.mr__expand{display:flex;align-items:center;justify-content:center;min-height:44px;margin:0;padding:0;border:0;background:transparent;font-size:var(--font-size-md);color:var(--teacher-700)}
.mr__review-form{display:flex;flex-direction:column;gap:var(--space-3);padding-top:var(--space-3);border-top:1px solid var(--border-light)}
.mr__review-form textarea{box-sizing:border-box;width:100%;height:100px;padding:var(--space-3);font-size:var(--font-size-md);line-height:1.6;border:1px solid var(--border-base);border-radius:var(--radius-md);color:var(--text-primary)}
.mr__next{display:block;font-size:var(--font-size-sm);line-height:1.6;color:var(--text-secondary)}
.mr__submit-bar{width:100%;max-width:728px;margin:auto;display:flex;flex-direction:column;gap:var(--space-2)}.mr__submit-bar>text{font-size:var(--font-size-base);line-height:1.6;color:var(--text-secondary)}
.mr__actions{display:flex;gap:var(--space-3);width:100%}.mr__return,.mr__approve{min-height:44px;margin:0;padding:0 var(--space-3);line-height:44px;border-radius:var(--radius-md);font-size:var(--font-size-md)}
.mr__return{border:1px solid var(--teacher-600);color:var(--teacher-700);background:var(--bg-card)}.mr__approve{border:1px solid var(--teacher-600);background:var(--teacher-600);color:var(--text-inverse)}
button:focus-visible{outline:2px solid var(--teacher-600);outline-offset:-2px}
</style>
