<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="实习审批" subtitle="补卡 · 请假 · 超期销假办结" show-back />
    <view class="tabs">
      <view v-for="item in tabOptions" :key="item.key" class="tab" :class="{ on: tab === item.key }" @click="tab = item.key">
        {{ item.label }}<text v-if="item.count" class="badge">{{ item.count }}</text><text v-if="tab === item.key" class="underline" />
      </view>
    </view>
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack">
        <view v-if="batches.length" class="card batch-card">
          <text class="muted">实习批次</text>
          <picker mode="selector" :range="batchLabels" :value="batchIndex" :disabled="acting" @change="onBatch">
            <view class="picker-value">{{ batchLabels[batchIndex] || '请选择批次' }} <text>▾</text></view>
          </picker>
        </view>
        <MobileInlineAlert type="info" description="所有审批按当前批次和数据版本处理。补卡通过会生成打卡留痕；请假通过会写入请假留痕；销假办结会关闭关联风险。" />
        <MobileGlobalState v-if="!batches.length" state="empty" title="暂无实习批次" description="当前身份的数据范围内没有可办理批次。" />

        <template v-else-if="tab === 'makeup'">
          <MobileGlobalState v-if="!makeups.length" state="empty" title="暂无待审补卡" description="当前批次本人指导范围内没有待审核补卡。" />
          <ApprovalCard v-for="item in makeups" :key="item.id" :item="item" kind="makeup" :acting="acting" @review="review" />
        </template>
        <template v-else-if="tab === 'leave'">
          <MobileGlobalState v-if="!leaves.length" state="empty" title="暂无待审请假" description="当前批次本人指导范围内没有待审批请假。" />
          <ApprovalCard v-for="item in leaves" :key="item.id" :item="item" kind="leave" :acting="acting" @review="review" />
        </template>
        <template v-else>
          <MobileGlobalState v-if="!overdues.length" state="empty" title="暂无待办结销假" description="当前批次没有超期未归或已销假待关闭风险的记录。" />
          <view v-for="item in overdues" :key="item.id" class="card item-card">
            <view class="row-between"><view class="flex-1"><text class="title">{{ item.studentName || '—' }}</text><text class="sub">{{ item.studentNo || '' }} · {{ item.leaveTypeLabel || item.leaveType }}</text></view><MobileStatusTag :label="item.statusLabel || item.status" :type="item.status === 'OVERDUE' ? 'danger' : 'success'" /></view>
            <view class="detail"><text class="key">请假起止</text><text>{{ item.startDate || '—' }} ~ {{ item.endDate || '—' }}</text></view>
            <view v-if="item.returnNote" class="detail"><text class="key">销假说明</text><text>{{ item.returnNote }}</text></view>
            <view class="detail"><text class="key">数据版本</text><text>v{{ item.version }}</text></view>
            <button class="approve" :disabled="acting" @click="ackReturn(item)">确认办结并同步风险</button>
          </view>
        </template>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import ApprovalCard from './ApprovalCard.vue'
import { useInternshipContextStore } from '@/stores/internshipContext'
import { teacherInternshipLeaves, teacherInternshipLeaveReview, teacherInternshipMakeups, teacherInternshipMakeupReview } from '@/services/internshipApi'
import { realRequest } from '@/services/request'
import { toast } from '@/utils/nav'

export default {
  components: { ApprovalCard },
  data: () => ({ tab: 'makeup', makeups: [], leaves: [], overdues: [], state: 'loading', acting: false, batches: [], batchId: '', batchIndex: 0 }),
  computed: {
    context() { return useInternshipContextStore() },
    batchLabels() { return this.batches.map((item) => `${item.name} · ${item.status} · ${item.studentCount}人`) },
    tabOptions() { return [{ key: 'makeup', label: '补卡审批', count: this.makeups.length }, { key: 'leave', label: '请假审批', count: this.leaves.length }, { key: 'overdue', label: '销假办结', count: this.overdues.length }] }
  },
  onLoad(options) { if (['makeup', 'leave', 'overdue'].includes(options?.tab)) this.tab = options.tab; this.load() },
  onPullDownRefresh() { this.load(() => uni.stopPullDownRefresh()) },
  methods: {
    async load(done) {
      this.state = 'loading'
      try {
        this.context.restore(); await this.context.load(true)
        this.batches = this.context.batches || []; this.batchId = this.context.selectedBatchId || ''
        this.batchIndex = Math.max(0, this.batches.findIndex((item) => String(item.id) === String(this.batchId)))
        if (!this.batchId) { this.makeups = []; this.leaves = []; this.overdues = []; this.state = 'ready'; return }
        const query = `?batchId=${encodeURIComponent(this.batchId)}`
        const [makeupData, leaveData, overdueData] = await Promise.all([
          teacherInternshipMakeups(this.batchId), teacherInternshipLeaves(this.batchId),
          realRequest(`/mobile/teacher/internship/context/leaves/overdue${query}`)
        ])
        this.makeups = makeupData?.list || []; this.leaves = leaveData?.list || []; this.overdues = overdueData?.list || []; this.state = 'ready'
      } catch (error) { this.state = 'error'; toast(error?.message || '实习审批数据加载失败') }
      finally { done?.() }
    },
    async onBatch(event) { this.batchIndex = Number(event.detail.value); this.context.selectBatch(this.batches[this.batchIndex]?.id); await this.load() },
    review({ kind, item, action }) {
      if (this.acting) return
      const reject = action === 'REJECT'; const label = kind === 'makeup' ? '补卡' : '请假'
      uni.showModal({ title: `${reject ? '驳回' : '通过'}${label}`, editable: true, placeholderText: reject ? '驳回原因（不少于5字）' : '审批意见（可选）', success: async (result) => {
        if (!result.confirm) return
        const comment = String(result.content || '').trim(); if (reject && comment.length < 5) return toast('驳回原因不少于5个字')
        this.acting = true
        try {
          const body = { action, comment, expectedVersion: item.version }
          if (kind === 'makeup') await teacherInternshipMakeupReview(item.id, body); else await teacherInternshipLeaveReview(item.id, body)
          toast(reject ? '已驳回' : '已通过'); await this.load()
        } catch (error) {
          if (String(error?.code || '') === 'DATA_CONFLICT') { toast('记录已变化，正在刷新'); await this.load() }
          else toast(error?.message || `${label}审批失败`)
        } finally { this.acting = false }
      } })
    },
    ackReturn(item) {
      if (this.acting) return
      uni.showModal({ title: '确认销假办结', editable: true, placeholderText: '办结说明（不少于2字）', success: async (result) => {
        if (!result.confirm) return
        const note = String(result.content || '').trim(); if (note.length < 2) return toast('办结说明不少于2个字')
        this.acting = true
        try {
          await realRequest(`/mobile/teacher/internship/context/leaves/${encodeURIComponent(item.id)}/ack-return`, { method: 'POST', data: { note, expectedVersion: item.version } })
          toast('销假已办结，关联风险已同步处理'); await this.load()
        } catch (error) {
          if (String(error?.code || '') === 'DATA_CONFLICT') { toast('记录已变化，正在刷新'); await this.load() }
          else toast(error?.message || '销假办结失败')
        } finally { this.acting = false }
      } })
    }
  }
}
</script>

<style scoped>
.tabs{display:flex;gap:24rpx;padding:20rpx 28rpx 0;background:var(--bg-card)}.tab{position:relative;padding-bottom:20rpx;color:var(--text-tertiary)}.tab.on{color:var(--text-primary);font-weight:600}.underline{position:absolute;left:50%;bottom:0;transform:translateX(-50%);width:44rpx;height:6rpx;border-radius:3rpx;background:var(--teacher-600)}.badge{margin-left:8rpx;font-size:20rpx;color:#fff;background:var(--danger-500);padding:2rpx 10rpx;border-radius:20rpx}.batch-card{display:flex;align-items:center;justify-content:space-between}.muted,.sub{color:var(--text-tertiary);font-size:24rpx}.picker-value{color:var(--teacher-700);font-size:26rpx}.item-card{display:flex;flex-direction:column;gap:14rpx}.title{font-size:30rpx;font-weight:600}.sub{display:block;margin-top:4rpx}.detail{display:flex;gap:20rpx;font-size:26rpx}.key{width:130rpx;color:var(--text-tertiary);flex-shrink:0}.approve{min-height:88rpx;background:var(--teacher-600);color:#fff;border:0;border-radius:16rpx}.approve::after{border:0}.approve[disabled]{opacity:.55}
</style>
