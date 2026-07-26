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
          <picker mode="selector" :range="batchLabels" :value="batchIndex" :disabled="hasActiveOperation" @change="onBatch">
            <view class="picker-value">{{ batchLabels[batchIndex] || '请选择批次' }} <text>▾</text></view>
          </picker>
        </view>

        <MobileInlineAlert type="info" description="审批按当前批次和数据版本处理。存在证明材料时必须先真实查看并留下审计；规则要求但缺少材料时，后端拒绝通过。" />
        <MobileGlobalState v-if="!batches.length" state="empty" title="暂无实习批次" description="当前身份的数据范围内没有可办理批次。" />

        <template v-else-if="tab === 'makeup'">
          <MobileInlineAlert v-if="!canReviewMakeup" type="warning" description="当前身份仅能查看补卡申请，没有补卡审批权限；页面已隐藏可执行能力，后端也会独立校验。" />
          <MobileGlobalState v-if="!makeups.length" state="empty" title="暂无待审补卡" description="当前批次本人指导范围内没有待审核补卡。" />
          <InternshipApprovalCard
            v-for="item in makeups"
            :key="item.id"
            :item="item"
            kind="makeup"
            :acting="isActing('makeup', item.id)"
            :viewing="isViewing('makeup', item.id)"
            :can-review="canReviewMakeup"
            :evidence-viewed="isEvidenceViewed('makeup', item)"
            @review="review"
            @view-evidence="viewEvidence"
          />
        </template>

        <template v-else-if="tab === 'leave'">
          <MobileInlineAlert v-if="!canReviewLeave" type="warning" description="当前身份仅能查看请假申请，没有实习请假审批权限；页面与后端均按权限码独立拦截。" />
          <MobileGlobalState v-if="!leaves.length" state="empty" title="暂无待审请假" description="当前批次本人指导范围内没有待审批请假。" />
          <InternshipApprovalCard
            v-for="item in leaves"
            :key="item.id"
            :item="item"
            kind="leave"
            :acting="isActing('leave', item.id)"
            :viewing="isViewing('leave', item.id)"
            :can-review="canReviewLeave"
            :evidence-viewed="isEvidenceViewed('leave', item)"
            @review="review"
            @view-evidence="viewEvidence"
          />
        </template>

        <template v-else>
          <MobileInlineAlert v-if="!canReviewLeave" type="warning" description="当前身份没有销假办结权限，仅可查看相关记录。" />
          <MobileGlobalState v-if="!overdues.length" state="empty" title="暂无待办结销假" description="当前批次没有超期未归或已销假待关闭风险的记录。" />
          <view v-for="item in overdues" :key="item.id" class="card item-card">
            <view class="row-between">
              <view class="flex-1">
                <text class="title">{{ item.studentName || '—' }}</text>
                <text class="sub">{{ item.studentNo || '' }} · {{ item.leaveTypeLabel || item.leaveType }}</text>
              </view>
              <MobileStatusTag :label="item.statusLabel || item.status" :type="item.status === 'OVERDUE' ? 'danger' : 'success'" />
            </view>
            <view class="detail"><text class="key">请假起止</text><text>{{ item.startDate || '—' }} ~ {{ item.endDate || '—' }}</text></view>
            <view v-if="item.returnNote" class="detail"><text class="key">销假说明</text><text class="flex-1">{{ item.returnNote }}</text></view>
            <view class="detail"><text class="key">提交时间</text><text>{{ formatTime(item.submittedAt || item.createdAt) }}</text></view>
            <view class="detail"><text class="key">数据版本</text><text>v{{ item.version }}</text></view>
            <button
              class="approve"
              :disabled="isActing('return', item.id) || !canReviewLeave"
              @click="ackReturn(item)"
            >{{ isActing('return', item.id) ? '办结中…' : (canReviewLeave ? '确认办结并同步风险' : '无办结权限') }}</button>
          </view>
        </template>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import InternshipApprovalCard from './ApprovalCard.vue'
import { useInternshipContextStore } from '@/stores/internshipContext'
import {
  teacherInternshipLeaveEvidenceViewed,
  teacherInternshipLeaves,
  teacherInternshipLeaveReview,
  teacherInternshipMakeupEvidenceViewed,
  teacherInternshipMakeups,
  teacherInternshipMakeupReview
} from '@/services/internshipApi'
import { openBusinessFile } from '@/services/fileApi'
import { realRequest } from '@/services/request'
import { toast } from '@/utils/nav'

export default {
  components: { InternshipApprovalCard },
  data: () => ({
    tab: 'makeup', makeups: [], leaves: [], overdues: [], state: 'loading',
    batches: [], batchId: '', batchIndex: 0,
    actingKeys: {}, viewingKeys: {}, viewedEvidence: {}
  }),
  computed: {
    context() { return useInternshipContextStore() },
    batchLabels() { return this.batches.map((item) => `${item.name} · ${item.status} · ${item.studentCount}人`) },
    tabOptions() {
      return [
        { key: 'makeup', label: '补卡审批', count: this.makeups.length },
        { key: 'leave', label: '请假审批', count: this.leaves.length },
        { key: 'overdue', label: '销假办结', count: this.overdues.length }
      ]
    },
    canReviewMakeup() { return this.context.can('internship.makeup.review') },
    canReviewLeave() { return this.context.can('internship.leave.review') },
    hasActiveOperation() {
      return Object.values(this.actingKeys).some(Boolean) || Object.values(this.viewingKeys).some(Boolean)
    }
  },
  onLoad(options) {
    if (['makeup', 'leave', 'overdue'].includes(options?.tab)) this.tab = options.tab
    this.load()
  },
  onPullDownRefresh() { this.load(() => uni.stopPullDownRefresh()) },
  methods: {
    recordKey(kind, id) { return `${kind}:${id}` },
    isActing(kind, id) { return !!this.actingKeys[this.recordKey(kind, id)] },
    isViewing(kind, id) { return !!this.viewingKeys[this.recordKey(kind, id)] },
    isEvidenceViewed(kind, item) {
      return !!item.evidenceViewed || !!this.viewedEvidence[this.recordKey(kind, item.id)]
    },
    setKey(mapName, key, value) {
      this[mapName] = { ...this[mapName], [key]: value }
    },
    formatTime(value) {
      if (!value) return '—'
      return String(value).replace('T', ' ').slice(0, 16)
    },
    async load(done) {
      this.state = 'loading'
      try {
        this.context.restore()
        await this.context.load(true)
        this.batches = this.context.batches || []
        this.batchId = this.context.selectedBatchId || ''
        this.batchIndex = Math.max(0, this.batches.findIndex((item) => String(item.id) === String(this.batchId)))
        if (!this.batchId) {
          this.makeups = []; this.leaves = []; this.overdues = []; this.state = 'ready'; return
        }
        const query = `?batchId=${encodeURIComponent(this.batchId)}`
        const [makeupData, leaveData, overdueData] = await Promise.all([
          teacherInternshipMakeups(this.batchId),
          teacherInternshipLeaves(this.batchId),
          realRequest(`/mobile/teacher/internship/context/leaves/overdue${query}`)
        ])
        this.makeups = makeupData?.list || []
        this.leaves = leaveData?.list || []
        this.overdues = overdueData?.list || []
        this.state = 'ready'
      } catch (error) {
        this.state = 'error'
        toast(error?.message || '实习审批数据加载失败')
      } finally { done?.() }
    },
    async onBatch(event) {
      if (this.hasActiveOperation) return
      this.batchIndex = Number(event.detail.value)
      this.context.selectBatch(this.batches[this.batchIndex]?.id)
      await this.load()
    },
    async viewEvidence({ kind, item }) {
      const key = this.recordKey(kind, item.id)
      if (this.isViewing(kind, item.id) || this.isActing(kind, item.id)) return
      if (!item.evidenceFileId) return toast('该申请没有可查看的证明材料')
      this.setKey('viewingKeys', key, true)
      try {
        await openBusinessFile(item.evidenceFileId)
        if (kind === 'makeup') await teacherInternshipMakeupEvidenceViewed(item.id)
        else await teacherInternshipLeaveEvidenceViewed(item.id)
        this.setKey('viewedEvidence', key, true)
        toast('材料已查看，审计留痕已写入')
      } catch (error) {
        toast(error?.message || '材料查看失败，未写入查看留痕')
      } finally { this.setKey('viewingKeys', key, false) }
    },
    review({ kind, item, action }) {
      const key = this.recordKey(kind, item.id)
      const canReview = kind === 'makeup' ? this.canReviewMakeup : this.canReviewLeave
      if (!canReview) return toast('当前身份没有该类审批权限')
      if (this.isActing(kind, item.id) || this.isViewing(kind, item.id)) return
      if (action === 'APPROVE') {
        if (item.evidenceRequired && !item.evidenceFileId) return toast('缺少规则要求的证明材料，不能通过')
        if (item.evidenceFileId && !this.isEvidenceViewed(kind, item)) return toast('请先查看证明材料，再执行通过')
      }
      const reject = action === 'REJECT'
      const label = kind === 'makeup' ? '补卡' : '请假'
      uni.showModal({
        title: `${reject ? '驳回' : '通过'}${label}`,
        editable: true,
        placeholderText: reject ? '驳回原因（不少于5字）' : '审批意见（可选）',
        success: async (result) => {
          if (!result.confirm) return
          const comment = String(result.content || '').trim()
          if (reject && comment.length < 5) return toast('驳回原因不少于5个字')
          this.setKey('actingKeys', key, true)
          try {
            const body = { action, comment, expectedVersion: item.version }
            if (kind === 'makeup') await teacherInternshipMakeupReview(item.id, body)
            else await teacherInternshipLeaveReview(item.id, body)
            toast(reject ? '已驳回' : '已通过')
            await this.load()
          } catch (error) {
            if (String(error?.code || '') === 'DATA_CONFLICT') {
              toast(error?.message || '记录已变化，正在刷新')
              await this.load()
            } else toast(error?.message || `${label}审批失败`)
          } finally { this.setKey('actingKeys', key, false) }
        }
      })
    },
    ackReturn(item) {
      const key = this.recordKey('return', item.id)
      if (!this.canReviewLeave) return toast('当前身份没有销假办结权限')
      if (this.isActing('return', item.id)) return
      uni.showModal({
        title: '确认销假办结', editable: true, placeholderText: '办结说明（不少于2字）',
        success: async (result) => {
          if (!result.confirm) return
          const note = String(result.content || '').trim()
          if (note.length < 2) return toast('办结说明不少于2个字')
          this.setKey('actingKeys', key, true)
          try {
            await realRequest(`/mobile/teacher/internship/context/leaves/${encodeURIComponent(item.id)}/ack-return`, {
              method: 'POST', data: { note, expectedVersion: item.version }
            })
            toast('销假已办结，关联风险已同步处理')
            await this.load()
          } catch (error) {
            if (String(error?.code || '') === 'DATA_CONFLICT') {
              toast(error?.message || '记录已变化，正在刷新')
              await this.load()
            } else toast(error?.message || '销假办结失败')
          } finally { this.setKey('actingKeys', key, false) }
        }
      })
    }
  }
}
</script>

<style scoped>
.tabs { display: flex; background: var(--bg-card); border-bottom: 1px solid var(--border-light); }
.tab { position: relative; flex: 1; padding: 14px 4px 12px; text-align: center; color: var(--text-tertiary); font-size: var(--font-size-sm); }
.tab.on { color: var(--brand-primary); font-weight: var(--font-weight-semibold); }
.underline { position: absolute; left: 34%; right: 34%; bottom: 0; height: 2px; border-radius: 2px; background: var(--brand-primary); }
.badge { display: inline-flex; min-width: 16px; height: 16px; margin-left: 4px; padding: 0 4px; align-items: center; justify-content: center; border-radius: 8px; background: var(--error-500); color: #fff; font-size: 10px; box-sizing: border-box; }
.batch-card { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); }
.muted { color: var(--text-tertiary); font-size: var(--font-size-sm); }
.picker-value { color: var(--brand-primary); font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); text-align: right; }
.item-card { display: flex; flex-direction: column; gap: 10px; }
.title { display: block; color: var(--text-primary); font-size: var(--font-size-md); font-weight: var(--font-weight-semibold); }
.sub { display: block; margin-top: 3px; color: var(--text-tertiary); font-size: var(--font-size-xs); }
.detail { display: flex; gap: 12px; color: var(--text-secondary); font-size: var(--font-size-sm); line-height: 1.55; }
.key { width: 68px; flex: 0 0 68px; color: var(--text-tertiary); }
.approve { margin: 4px 0 0; background: var(--brand-primary); color: #fff; border: 0; }
.approve[disabled] { background: var(--gray-300); color: var(--text-tertiary); }
</style>
