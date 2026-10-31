<template>
  <view class="internship-surface mobile-page mobile-teacher page-wrap">
    <MobileNavBar variant="teacher" title="免签审批" show-back />
    <view v-if="state === 'ready'" class="page-pad ce__context">
      <picker v-if="batches.length > 1" class="mobile-picker card" :range="batchLabels" :value="batchIndex" :disabled="!!actingId" @change="onBatch">
        <view class="ce__batch">
          <text>{{ batches[batchIndex]?.name || '请选择批次' }}</text>
          <text class="ce__switch">切换批次 ▾</text>
        </view>
      </picker>
      <view class="ce__tabs">
        <button class="mobile-control" v-for="item in statusOptions" :key="item.value" :class="{ 'is-on': status === item.value }" @click="setStatus(item.value)">{{ item.label }}</button>
      </view>
    </view>
    <MobileGlobalState :state="state" :description="error" @retry="load">
      <view class="page-pad stack" v-if="list">
        <view v-if="focusId" class="card ce"><text>正在查看待办对应的免签申请。</text><button class="mobile-control btn btn-ghost" @click="clearFocus">查看本批次全部免签申请</button></view>
        <MobileGlobalState v-if="!batches.length" state="empty" title="暂无实习批次" description="当前数据范围没有可办理批次。" />
        <MobileGlobalState v-else-if="!list.length" state="empty" :title="focusId ? '该原单当前不可见' : status === 'ALL' ? '暂无免签申请' : '暂无' + statusOptions.find(item => item.value === status)?.label + '免签申请'" :description="focusId ? '请返回待办刷新，核对该事项当前状态和办理范围。' : '可切换分类查看。'" />
        <view v-for="item in list" :key="item.id" class="card ce">
          <view class="row-between">
            <view class="flex-1"><text class="t-md t-bold">{{ item.studentName }}</text><text class="ce__sub">{{ item.studentNo }}</text></view>
            <MobileStatusTag :label="item.statusLabel" :type="tone(item.status)" />
          </view>
          <view class="ce__facts">
            <view><text>免签日期</text><text>{{ item.startDate }} ～ {{ item.endDate }}</text></view>
            <button v-if="item.status === 'APPROVED'" class="mobile-control btn btn-ghost" :aria-expanded="expandedNotesId === item.id" @click="expandedNotesId = expandedNotesId === item.id ? '' : item.id">{{ expandedNotesId === item.id ? '收起申请详情' : '查看申请详情' }}</button>
            <template v-if="item.status !== 'APPROVED' || expandedNotesId === item.id"><view><text>申请理由</text><text>{{ item.reason }}</text></view>
            <view v-if="item.reviewComment"><text>审核意见</text><text>{{ item.reviewComment }}</text></view></template>
          </view>
          <button v-if="item.evidenceFileId" class="mobile-control ce__file" @click="preview(item)">查看学生佐证材料</button>
          <view v-if="item.status === 'PENDING' && canReview" class="ce__actions">
            <button class="mobile-control ce__reject flex-1" :disabled="actingId === item.id" @click="review(item, 'REJECT')">驳回</button>
            <button class="mobile-control ce__approve flex-1" :disabled="actingId === item.id" @click="review(item, 'APPROVE')">通过免签</button>
          </view>
        </view>
        <button v-if="hasMore" class="mobile-control btn btn-ghost" :disabled="loadingMore" @click="loadMore">{{ loadingMore ? '加载中…' : '加载更多' }}</button>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import {
  teacherInternshipCheckinExemptions,
  teacherInternshipCheckinExemptionReview
} from '@/services/internshipApi'
import { openBusinessFile } from '@/services/fileApi'
import { useInternshipContextStore } from '@/stores/internshipContext'
import { toast } from '@/utils/nav'
import { normalizeError } from '@/services/request'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'

const STATUS_OPTIONS = [
  { value: 'PENDING', label: '待审核' },
  { value: 'APPROVED', label: '已通过' },
  { value: 'REJECTED', label: '已驳回' },
  { value: 'ALL', label: '全部' }
]

export default {
  data() {
    return {
      state: 'loading', error: '', list: null, batches: [], batchId: '', batchIndex: 0,
      page: 1, hasMore: false, loadingMore: false, actingId: '',
      status: 'PENDING', statusOptions: STATUS_OPTIONS, requestedBatchId: '', focusId: '',
      expandedNotesId: '', requestSeq: 0, reviewSeq: 0, generation: currentSessionGeneration(), hidden: false
    }
  },
  computed: {
    context() { return useInternshipContextStore() },
    batchLabels() { return this.batches.map((b) => `${b.name} · ${b.studentCount}人`) },
    canReview() { return this.context.can('internship.attendance.review') }
  },
  onLoad(options = {}) {
    this.requestedBatchId = String(options.batchId || ''); this.focusId = String(options.exemptionId || '')
    if (STATUS_OPTIONS.some(item => item.value === options.status)) this.status = options.status
    if (this.focusId) this.status = 'ALL'
    return this.load()
  },
  onShow() { const refresh = this.hidden || this.generation !== currentSessionGeneration(); this.hidden = false; if (refresh) return this.load() },
  onHide() { this.expandedNotesId = ''; this.hidden = true; this.requestSeq++; this.reviewSeq++; this.list = null; this.actingId = ''; this.loadingMore = false },
  onUnload() { this.hidden = true; this.requestSeq++; this.reviewSeq++; this.list = null; this.actingId = '' },
  onReachBottom() { this.loadMore() },
  methods: {
    current(seq, generation, batchId = this.batchId, status = this.status) { return !this.hidden && seq === this.requestSeq && generation === currentSessionGeneration() && String(batchId) === String(this.batchId) && status === this.status },
    clearFocus() {
      if (this.actingId) return
      this.focusId = ''; this.list = null; this.requestSeq++; this.reviewSeq++
      uni.redirectTo({ url:'/pages/teacher-internship/checkin-exemption/index?batchId='+encodeURIComponent(this.batchId)+'&status=PENDING' })
    },
    tone(value) { return value === 'APPROVED' ? 'success' : value === 'REJECTED' ? 'danger' : value === 'PENDING' ? 'warning' : 'default' },
    async load() {
      this.expandedNotesId = ''
      if (this.generation !== currentSessionGeneration()) { this.batches = []; this.batchId = ''; this.actingId = ''; this.reviewSeq++ }
      const seq = ++this.requestSeq, generation = this.generation = currentSessionGeneration()
      this.state = 'loading'; this.error = ''; this.page = 1; this.hasMore = false; this.list = null; this.loadingMore = false
      try {
        if ((this.requestedBatchId && !/^[1-9]\d*$/.test(this.requestedBatchId)) || (this.focusId && (!/^[1-9]\d*$/.test(this.focusId) || !this.requestedBatchId))) throw new Error('待办定位信息不完整，请返回待办重新进入')
        this.context.restore()
        await this.context.load(true)
        if (this.hidden || seq !== this.requestSeq || generation !== currentSessionGeneration()) return
        if (this.requestedBatchId && !this.context.selectBatch(this.requestedBatchId)) throw { httpStatus: 403, message: '当前身份无权处理该待办所属批次，请返回待办刷新核对' }
        this.batches = this.context.batches || []
        this.batchId = this.context.selectedBatchId || ''
        this.batchIndex = Math.max(0, this.batches.findIndex((b) => String(b.id) === String(this.batchId)))
        if (!this.batchId) { this.list = []; this.state = 'ready'; return }
        const batchId = this.batchId, status = this.status
        const data = await teacherInternshipCheckinExemptions(batchId, 1, 20, status, this.focusId)
        if (!this.current(seq, generation, batchId, status)) return
        if (!Array.isArray(data?.items)) throw new Error('免签申请读取未完整返回，请重试')
        this.list = data?.items || []
        this.hasMore = !!data?.hasMore
        this.state = 'ready'
      } catch (e) {
        if (!this.current(seq, generation)) return
        const error = normalizeError(e); this.list = null; this.state = error.pageState || 'error'; this.error = error.text
      }
    },
    async onBatch(e) {
      if (this.actingId) return
      const hadRouteContext = !!(this.requestedBatchId || this.focusId)
      this.focusId = ''; this.requestedBatchId = ''
      this.batchIndex = Number(e.detail.value) || 0
      const batch = this.batches[this.batchIndex]
      this.context.selectBatch(batch?.id)
      this.batchId = this.context.selectedBatchId
      if (hadRouteContext) {
        this.list = null; this.requestSeq++; this.reviewSeq++
        uni.redirectTo({ url:'/pages/teacher-internship/checkin-exemption/index?batchId='+encodeURIComponent(this.batchId)+'&status='+encodeURIComponent(this.status) })
        return
      }
      await this.load()
    },
    async setStatus(value) {
      if (this.actingId || this.status === value) return
      this.status = value
      await this.load()
    },
    async loadMore() {
      if (!this.batchId || !this.hasMore || this.loadingMore || this.state !== 'ready') return
      this.loadingMore = true
      const seq = this.requestSeq, generation = currentSessionGeneration(), batchId = this.batchId, status = this.status
      try {
        const next = this.page + 1
        const data = await teacherInternshipCheckinExemptions(batchId, next, 20, status, this.focusId)
        if (!this.current(seq, generation, batchId, status)) return
        this.list = [...(this.list || []), ...(data?.items || [])]
        this.page = next
        this.hasMore = !!data?.hasMore
      } catch (e) { if (this.current(seq, generation, batchId, status)) toast('后续申请读取失败，已加载免签申请保留') }
      finally { if (this.current(seq, generation, batchId, status)) this.loadingMore = false }
    },
    async preview(item) {
      try { await openBusinessFile(item.evidenceFileId) }
      catch (e) { toast(e?.message || '佐证材料无法打开') }
    },
    review(item, action) {
      if (!this.canReview || this.actingId || this.state !== 'ready' || this.hidden || item.status !== 'PENDING') return
      const seq = this.requestSeq, generation = currentSessionGeneration(), batchId = this.batchId, status = this.status
      const operation = ++this.reviewSeq
      const snapshot = { id: item.id, version: item.version }
      const current = () => operation === this.reviewSeq && this.current(seq, generation, batchId, status) && this.canReview && (this.list || []).some(row => row.id === snapshot.id && row.version === snapshot.version && row.status === 'PENDING')
      const reject = action === 'REJECT'
      uni.showModal({
        title: reject ? '驳回免签申请' : '通过免签申请',
        editable: true,
        placeholderText: reject ? '请填写具体驳回原因（至少5字）' : '可填写审核意见',
        success: async (r) => {
          if (!r.confirm || !current()) return
          const comment = String(r.content || '').trim()
          if (reject && comment.length < 5) return toast('驳回原因至少5个字')
          this.actingId = item.id
          try {
            await teacherInternshipCheckinExemptionReview(snapshot.id, batchId, {
              action, comment, expectedVersion: snapshot.version
            })
            if (!current()) return
            toast(reject ? '已驳回免签申请' : '免签已生效并进入学生签到日历')
            await this.load()
          } catch (e) { if (this.current(seq, generation, batchId, status)) toast(e?.message || '免签审批失败') }
          finally { if (operation === this.reviewSeq) this.actingId = '' }
        }
      })
    }
  }
}
</script>

<style scoped>
.ce__context{display:flex;flex-direction:column;gap:10px}.ce__batch{display:flex;align-items:center;justify-content:space-between;padding:12px}.ce__switch{color:var(--teacher-700);font-size:var(--font-size-sm)}.ce__tabs{display:grid;grid-template-columns:repeat(4,1fr);gap:6px}.ce__tabs button{min-height:38px;border:1px solid var(--border-light);border-radius:8px;background:var(--bg-card);font-size:12px;color:var(--text-secondary)}.ce__tabs button::after{border:none}.ce__tabs button.is-on{border-color:var(--teacher-500);background:var(--teacher-50);color:var(--teacher-700);font-weight:600}.ce{display:flex;flex-direction:column;gap:12px;padding:12px}.ce__sub{display:block;margin-top:3px;font-size:11px;color:var(--text-tertiary)}.ce__facts{display:flex;flex-direction:column;gap:8px;padding:10px;background:var(--gray-50);border-radius:8px}.ce__facts view{display:grid;grid-template-columns:70px 1fr;gap:10px}.ce__facts text:first-child{font-size:11px;color:var(--text-tertiary)}.ce__facts text:last-child{font-size:13px;color:var(--text-primary);word-break:break-word}.ce__file{min-height:40px;border:1px solid var(--border-light);border-radius:8px;background:var(--bg-card);font-size:13px;color:var(--teacher-700)}.ce__file::after{border:none}.ce__actions{display:flex;gap:8px}.ce__reject,.ce__approve{min-height:44px;border-radius:8px;font-size:14px}.ce__reject{border:1px solid var(--danger-500);background:var(--bg-card);color:var(--danger-600)}.ce__approve{border:0;background:var(--teacher-600);color:#fff}.ce__reject::after,.ce__approve::after{border:none}
.ce__switch{display:inline-flex;align-items:center;min-height:44px;font-size:var(--font-size-base)}.ce__tabs button{min-height:44px;font-size:var(--font-size-base)}.ce__sub,.ce__facts text:first-child,.ce__facts text:last-child,.ce__file{font-size:var(--font-size-base)}.ce__sub{overflow-wrap:anywhere}.ce__file{min-height:44px}
.ce__batch>text:first-child{flex:1;min-width:0;overflow-wrap:anywhere}.ce__switch{flex-shrink:0;margin-left:12px}
</style>
