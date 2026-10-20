<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="免签审批" subtitle="核对日期、理由与佐证后办理" show-back />
    <view class="page-pad ce__context">
      <view v-if="batches.length" class="card ce__batch">
        <text>{{ batches[batchIndex]?.name || '请选择批次' }}</text>
        <picker :range="batchLabels" :value="batchIndex" :disabled="!!actingId" @change="onBatch">
          <text class="ce__switch">切换批次 ▾</text>
        </picker>
      </view>
      <view class="ce__tabs">
        <button v-for="item in statusOptions" :key="item.value" :class="{ 'is-on': status === item.value }" @click="setStatus(item.value)">{{ item.label }}</button>
      </view>
    </view>
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="list">
        <MobileGlobalState v-if="!batches.length" state="empty" title="暂无实习批次" description="当前数据范围没有可办理批次。" />
        <MobileGlobalState v-else-if="!list.length" state="empty" title="当前没有免签申请" description="学生提交免签后会进入这里。" />
        <view v-for="item in list" :key="item.id" class="card ce">
          <view class="row-between">
            <view class="flex-1"><text class="t-md t-bold">{{ item.studentName }}</text><text class="ce__sub">{{ item.studentNo }}</text></view>
            <MobileStatusTag :label="item.statusLabel" :type="tone(item.status)" />
          </view>
          <view class="ce__facts">
            <view><text>免签日期</text><text>{{ item.startDate }} ～ {{ item.endDate }}</text></view>
            <view><text>申请理由</text><text>{{ item.reason }}</text></view>
            <view v-if="item.reviewComment"><text>审核意见</text><text>{{ item.reviewComment }}</text></view>
          </view>
          <button v-if="item.evidenceFileId" class="ce__file" @click="preview(item)">查看学生佐证材料</button>
          <view v-if="item.status === 'PENDING' && canReview" class="ce__actions">
            <button class="ce__reject flex-1" :disabled="actingId === item.id" @click="review(item, 'REJECT')">驳回</button>
            <button class="ce__approve flex-1" :disabled="actingId === item.id" @click="review(item, 'APPROVE')">通过免签</button>
          </view>
        </view>
        <button v-if="hasMore" class="btn btn-ghost" :disabled="loadingMore" @click="loadMore">{{ loadingMore ? '加载中…' : '加载更多' }}</button>
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

const STATUS_OPTIONS = [
  { value: 'PENDING', label: '待审核' },
  { value: 'APPROVED', label: '已通过' },
  { value: 'REJECTED', label: '已驳回' },
  { value: 'ALL', label: '全部' }
]

export default {
  data() {
    return {
      state: 'loading', list: null, batches: [], batchId: '', batchIndex: 0,
      page: 1, hasMore: false, loadingMore: false, actingId: '',
      status: 'PENDING', statusOptions: STATUS_OPTIONS
    }
  },
  computed: {
    context() { return useInternshipContextStore() },
    batchLabels() { return this.batches.map((b) => `${b.name} · ${b.studentCount}人`) },
    canReview() { return this.context.can('internship.attendance.review') }
  },
  onLoad() { this.load() },
  onReachBottom() { this.loadMore() },
  methods: {
    tone(value) { return value === 'APPROVED' ? 'success' : value === 'REJECTED' ? 'danger' : value === 'PENDING' ? 'warning' : 'default' },
    async load() {
      this.state = 'loading'; this.page = 1; this.hasMore = false
      try {
        this.context.restore()
        await this.context.load(true)
        this.batches = this.context.batches || []
        this.batchId = this.context.selectedBatchId || ''
        this.batchIndex = Math.max(0, this.batches.findIndex((b) => String(b.id) === String(this.batchId)))
        if (!this.batchId) { this.list = []; this.state = 'ready'; return }
        const data = await teacherInternshipCheckinExemptions(this.batchId, 1, 20, this.status)
        this.list = data?.items || []
        this.hasMore = !!data?.hasMore
        this.state = 'ready'
      } catch (e) {
        this.list = []; this.state = 'error'; toast(e?.message || '免签申请加载失败')
      }
    },
    async onBatch(e) {
      this.batchIndex = Number(e.detail.value) || 0
      const batch = this.batches[this.batchIndex]
      this.context.selectBatch(batch?.id)
      this.batchId = this.context.selectedBatchId
      await this.load()
    },
    async setStatus(value) {
      if (this.actingId || this.status === value) return
      this.status = value
      await this.load()
    },
    async loadMore() {
      if (!this.batchId || !this.hasMore || this.loadingMore) return
      this.loadingMore = true
      try {
        const next = this.page + 1
        const data = await teacherInternshipCheckinExemptions(this.batchId, next, 20, this.status)
        this.list = [...(this.list || []), ...(data?.items || [])]
        this.page = next
        this.hasMore = !!data?.hasMore
      } finally { this.loadingMore = false }
    },
    async preview(item) {
      try { await openBusinessFile(item.evidenceFileId) }
      catch (e) { toast(e?.message || '佐证材料无法打开') }
    },
    review(item, action) {
      if (!this.canReview || this.actingId || item.status !== 'PENDING') return
      const reject = action === 'REJECT'
      uni.showModal({
        title: reject ? '驳回免签申请' : '通过免签申请',
        editable: true,
        placeholderText: reject ? '请填写具体驳回原因（至少5字）' : '可填写审核意见',
        success: async (r) => {
          if (!r.confirm) return
          const comment = String(r.content || '').trim()
          if (reject && comment.length < 5) return toast('驳回原因至少5个字')
          this.actingId = item.id
          try {
            await teacherInternshipCheckinExemptionReview(item.id, this.batchId, {
              action, comment, expectedVersion: item.version
            })
            toast(reject ? '已驳回免签申请' : '免签已生效并进入学生签到日历')
            await this.load()
          } catch (e) { toast(e?.message || '免签审批失败') }
          finally { this.actingId = '' }
        }
      })
    }
  }
}
</script>

<style scoped>
.ce__context{display:flex;flex-direction:column;gap:10px}.ce__batch{display:flex;align-items:center;justify-content:space-between;padding:12px}.ce__switch{color:var(--teacher-700);font-size:var(--font-size-sm)}.ce__tabs{display:grid;grid-template-columns:repeat(4,1fr);gap:6px}.ce__tabs button{min-height:38px;border:1px solid var(--border-light);border-radius:8px;background:var(--bg-card);font-size:12px;color:var(--text-secondary)}.ce__tabs button::after{border:none}.ce__tabs button.is-on{border-color:var(--teacher-500);background:var(--teacher-50);color:var(--teacher-700);font-weight:600}.ce{display:flex;flex-direction:column;gap:12px;padding:12px}.ce__sub{display:block;margin-top:3px;font-size:11px;color:var(--text-tertiary)}.ce__facts{display:flex;flex-direction:column;gap:8px;padding:10px;background:var(--gray-50);border-radius:8px}.ce__facts view{display:grid;grid-template-columns:70px 1fr;gap:10px}.ce__facts text:first-child{font-size:11px;color:var(--text-tertiary)}.ce__facts text:last-child{font-size:13px;color:var(--text-primary);word-break:break-word}.ce__file{min-height:40px;border:1px solid var(--border-light);border-radius:8px;background:var(--bg-card);font-size:13px;color:var(--teacher-700)}.ce__file::after{border:none}.ce__actions{display:flex;gap:8px}.ce__reject,.ce__approve{min-height:44px;border-radius:8px;font-size:14px}.ce__reject{border:1px solid var(--danger-500);background:var(--bg-card);color:var(--danger-600)}.ce__approve{border:0;background:var(--teacher-600);color:#fff}.ce__reject::after,.ce__approve::after{border:none}
</style>
