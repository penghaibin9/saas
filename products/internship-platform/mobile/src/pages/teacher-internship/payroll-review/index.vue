<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="工资单审核" subtitle="实际发放金额、币种、照片与更正版本" show-back />
    <view class="page-pad pr__context">
      <view v-if="batches.length" class="card pr__batch">
        <text>{{ batches[batchIndex]?.name || '请选择批次' }}</text>
        <picker :range="batchLabels" :value="batchIndex" :disabled="!!actingId" @change="onBatch">
          <text class="pr__switch">切换批次 ▾</text>
        </picker>
      </view>
      <view class="pr__tabs">
        <button v-for="item in states" :key="item.value" :class="{ 'is-on': status === item.value }" @click="setStatus(item.value)">{{ item.label }}</button>
      </view>
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="list">
        <MobileGlobalState v-if="!batches.length" state="empty" title="暂无实习批次" description="当前数据范围没有可办理批次。" />
        <MobileGlobalState v-else-if="!list.length" state="empty" title="当前没有工资单" description="学生提交月度工资单后会进入这里。" />
        <view v-for="item in list" :key="item.id" class="card pr">
          <view class="row-between">
            <view class="flex-1">
              <text class="t-md t-bold">{{ item.studentName }}</text>
              <text class="pr__sub">{{ item.studentNo }} · {{ item.payMonth }}</text>
            </view>
            <MobileStatusTag :label="item.current?.statusLabel || '无当前版本'" :type="tone(item.current?.status)" />
          </view>
          <view v-if="item.current" class="pr__facts">
            <view><text>约定报酬</text><text>{{ money(item.agreedSalary, item.agreedSalaryCurrency) }}</text></view>
            <view><text>实际发放</text><text>{{ money(item.current.actualAmount, item.current.currency) }}</text></view>
            <view><text>发薪日期</text><text>{{ item.current.paidOn || '未填写' }}</text></view>
            <view><text>当前版本</text><text>V{{ item.current.revisionNo }}</text></view>
          </view>
          <button v-if="item.current?.evidenceFileId" class="pr__file" @click="preview(item.current)">查看工资凭证照片</button>
          <text v-if="item.current?.correctionReason" class="pr__correction">更正原因：{{ item.current.correctionReason }}</text>
          <text v-if="item.current?.reviewComment" class="pr__review">审核意见：{{ item.current.reviewComment }}</text>
          <view v-if="item.current?.status === 'SUBMITTED' && canReview" class="pr__actions">
            <button class="pr__return flex-1" :disabled="actingId === item.current.id" @click="review(item, 'RETURN')">退回更正</button>
            <button class="pr__approve flex-1" :disabled="actingId === item.current.id" @click="review(item, 'APPROVE')">确认工资单</button>
          </view>
          <details v-if="item.history?.length > 1" class="pr__history">
            <summary>历史版本（{{ item.history.length }}）</summary>
            <view v-for="ver in item.history" :key="ver.id" class="pr__history-row">
              <text>V{{ ver.revisionNo }} · {{ ver.statusLabel }}</text><text>{{ money(ver.actualAmount, ver.currency) }}</text>
            </view>
          </details>
        </view>
        <button v-if="hasMore" class="btn btn-ghost" :disabled="loadingMore" @click="loadMore">{{ loadingMore ? '加载中…' : '加载更多' }}</button>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherInternshipPayroll, teacherInternshipPayrollReview } from '@/services/internshipApi'
import { openBusinessFile } from '@/services/fileApi'
import { useInternshipContextStore } from '@/stores/internshipContext'
import { toast } from '@/utils/nav'

const STATES = [
  { value: 'SUBMITTED', label: '待审核' },
  { value: 'APPROVED', label: '已确认' },
  { value: 'RETURNED', label: '已退回' },
  { value: 'ALL', label: '全部' }
]

export default {
  data() {
    return {
      state: 'loading', list: null, batches: [], batchId: '', batchIndex: 0,
      status: 'SUBMITTED', states: STATES, page: 1, hasMore: false,
      loadingMore: false, actingId: ''
    }
  },
  computed: {
    context() { return useInternshipContextStore() },
    batchLabels() { return this.batches.map((b) => `${b.name} · ${b.studentCount}人`) },
    canReview() { return this.context.can('internship.payroll.review') }
  },
  onLoad() { this.load() },
  onReachBottom() { this.loadMore() },
  methods: {
    tone(status) { return status === 'APPROVED' ? 'success' : status === 'RETURNED' ? 'danger' : status === 'SUBMITTED' ? 'warning' : 'default' },
    money(value, currency = 'CNY') { return value == null ? '未填写' : `${currency || 'CNY'} ${Number(value).toFixed(2)}` },
    async load() {
      this.state = 'loading'; this.page = 1; this.hasMore = false
      try {
        this.context.restore()
        await this.context.load(true)
        this.batches = this.context.batches || []
        this.batchId = this.context.selectedBatchId || ''
        this.batchIndex = Math.max(0, this.batches.findIndex((b) => String(b.id) === String(this.batchId)))
        if (!this.batchId) { this.list = []; this.state = 'ready'; return }
        const data = await teacherInternshipPayroll(this.batchId, 1, 20, this.status)
        this.list = data?.items || []
        this.hasMore = !!data?.hasMore
        this.state = 'ready'
      } catch (e) { this.list = []; this.state = 'error'; toast(e?.message || '工资单加载失败') }
    },
    async onBatch(e) {
      if (this.actingId) return
      this.batchIndex = Number(e.detail.value) || 0
      this.context.selectBatch(this.batches[this.batchIndex]?.id)
      this.batchId = this.context.selectedBatchId
      await this.load()
    },
    async setStatus(value) { if (!this.actingId && this.status !== value) { this.status = value; await this.load() } },
    async loadMore() {
      if (!this.batchId || !this.hasMore || this.loadingMore) return
      this.loadingMore = true
      try {
        const next = this.page + 1
        const data = await teacherInternshipPayroll(this.batchId, next, 20, this.status)
        this.list = [...(this.list || []), ...(data?.items || [])]
        this.page = next; this.hasMore = !!data?.hasMore
      } finally { this.loadingMore = false }
    },
    async preview(version) {
      try { await openBusinessFile(version.evidenceFileId) }
      catch (e) { toast(e?.message || '工资凭证无法打开') }
    },
    review(item, action) {
      const version = item.current
      if (!version || version.status !== 'SUBMITTED' || this.actingId || !this.canReview) return
      const returning = action === 'RETURN'
      uni.showModal({
        title: returning ? '退回工资单' : '确认工资单',
        editable: true,
        placeholderText: returning ? '请填写退回原因（至少5字）' : '可填写审核意见',
        success: async (result) => {
          if (!result.confirm) return
          const comment = String(result.content || '').trim()
          if (returning && comment.length < 5) return toast('退回原因至少5个字')
          this.actingId = version.id
          try {
            await teacherInternshipPayrollReview(version.id, {
              action, comment, expectedVersion: version.version
            })
            toast(returning ? '已退回，学生可提交更正版本' : '工资单已确认')
            await this.load()
          } catch (e) { toast(e?.message || '工资单审核失败') }
          finally { this.actingId = '' }
        }
      })
    }
  }
}
</script>

<style scoped>
.pr__context{display:flex;flex-direction:column;gap:10px}.pr__batch{display:flex;align-items:center;justify-content:space-between;padding:12px}.pr__switch{color:var(--teacher-700);font-size:12px}.pr__tabs{display:grid;grid-template-columns:repeat(4,1fr);gap:6px}.pr__tabs button{min-height:38px;border:1px solid var(--border-light);border-radius:8px;background:#fff;font-size:12px}.pr__tabs button::after{border:none}.pr__tabs button.is-on{border-color:var(--teacher-500);background:var(--teacher-50);color:var(--teacher-700);font-weight:600}.pr{display:flex;flex-direction:column;gap:10px;padding:13px}.pr__sub{display:block;margin-top:3px;font-size:11px;color:var(--text-tertiary)}.pr__facts{display:grid;grid-template-columns:1fr 1fr;gap:6px}.pr__facts view{padding:8px;border-radius:7px;background:var(--gray-50)}.pr__facts text{display:block}.pr__facts text:first-child{font-size:9px;color:var(--text-tertiary)}.pr__facts text:last-child{margin-top:3px;font-size:12px;font-weight:600}.pr__file{margin:0;padding:7px 0;min-height:0;border:0;background:transparent;color:var(--teacher-700);font-size:12px;text-align:left}.pr__file::after{border:none}.pr__correction,.pr__review{display:block;padding:8px;border-radius:6px;font-size:12px}.pr__correction{background:var(--primary-50);color:var(--text-secondary)}.pr__review{background:var(--warning-50);color:var(--warning-700)}.pr__actions{display:flex;gap:8px}.pr__return,.pr__approve{min-height:44px;border-radius:8px;font-size:14px}.pr__return{border:1px solid var(--danger-500);background:#fff;color:var(--danger-600)}.pr__approve{border:0;background:var(--teacher-600);color:#fff}.pr__return::after,.pr__approve::after{border:none}.pr__history{font-size:11px;color:var(--text-secondary)}.pr__history-row{display:flex;justify-content:space-between;padding:7px 0;border-top:1px solid var(--border-light)}
</style>
