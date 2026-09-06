<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="实习变更审核" subtitle="当前关系、目标关系、审批影响一次看清" show-back />

    <view class="page-pad tc__context">
      <view v-if="batches.length" class="card tc__batch">
        <view><text class="tc__eyebrow">当前审核批次</text><text class="tc__batch-name">{{ batches[batchIndex]?.name || '请选择批次' }}</text></view>
        <picker mode="selector" :range="batchLabels" :value="batchIndex" :disabled="acting" @change="onBatch">
          <view class="tc__picker">切换批次 ▾</view>
        </picker>
      </view>

      <view v-if="lastReceipt" class="card tc__receipt">
        <view class="row-between"><text class="t-bold">✓ {{ lastReceipt.actionLabel }}</text><text>v{{ lastReceipt.version }}</text></view>
        <text>{{ lastReceipt.objectLabel }} · {{ lastReceipt.statusLabel }}</text>
        <text>主记录：{{ lastReceipt.recordStatusLabel }} · {{ lastReceipt.nextStep }}</text>
      </view>
      <view v-if="conflictReceipt" class="card tc__conflict">
        <text class="t-bold">这条申请刚被其他人处理</text>
        <text>{{ conflictReceipt.message }}</text>
        <text v-if="conflictReceipt.comment">已保留意见：{{ conflictReceipt.comment }}</text>
      </view>

      <view v-if="list" class="card tc__summary">
        <view><text class="tc__eyebrow">待审核变更</text><text class="tc__count">{{ list.length }}<text class="tc__count-unit"> 条</text></text></view>
        <text class="tc__summary-note">审批通过会冻结旧关系、作废旧协议，并回退为待重新上岗。</text>
      </view>
      <MobileInlineAlert type="info" description="所有审批都携带申请版本与学生主记录快照；发生冲突会刷新真值并保留你的意见，不会自动重放。" />
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <view v-if="list" class="page-pad tc__list">
        <MobileGlobalState v-if="!batches.length" state="empty" title="暂无实习批次" description="当前身份的数据范围内没有可办理批次。" />
        <MobileGlobalState v-else-if="!list.length" state="empty" title="当前批次没有待审变更" description="学生发起换岗、换单位、自主实习或退岗后会出现在这里。" />
        <view v-else class="stack">
          <view v-for="c in list" :key="c.id" class="card tc">
            <view class="row-between tc__head">
              <view><text class="t-md t-bold">{{ c.studentName || '—' }}</text><text class="tc__sub">{{ c.studentNo }} · 申请 #{{ c.id }}</text></view>
              <MobileStatusTag :label="c.statusLabel" type="warning" />
            </view>
            <view class="tc__type"><text>{{ c.changeTypeLabel }}</text><text>申请 v{{ c.version }} · 主记录快照 v{{ c.recordVersionSnapshot }}</text></view>
            <view class="tc__route">
              <view><text class="tc__route-label">当前关系</text><text class="t-bold">{{ c.currentEnterprise || '未落实单位' }}</text><text>{{ c.currentPosition || '未落实岗位' }}</text></view>
              <text class="tc__arrow">→</text>
              <view class="is-target"><text class="tc__route-label">目标关系</text><text class="t-bold">{{ c.targetEnterpriseName || (c.changeType === 'WITHDRAW_POST' ? '退岗' : '自主实习') }}</text><text>{{ c.targetPositionName || '待重新落实' }}</text></view>
            </view>
            <view class="tc__reason"><text>申请原因</text><text>{{ c.reason }}</text></view>
            <view class="tc__impact">
              <text class="tc__impact-title">通过后的服务端影响</text>
              <view v-for="item in c.impactItems || []" :key="item.label"><text class="t-bold">{{ item.label }}</text><text>{{ item.detail }}</text></view>
            </view>
            <view v-if="canReview" class="tc__actions">
              <button class="tc__reject flex-1" :disabled="acting" @click="review(c, 'REJECT')">驳回补充</button>
              <button class="tc__approve flex-1" :disabled="acting" @click="review(c, 'APPROVE')">确认通过</button>
            </view>
            <MobileInlineAlert v-else type="warning" description="当前身份仅可查看，无实习变更审核权限。" />
          </view>
          <text v-if="loadingMore" class="tc__more">正在加载更多…</text>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherInternshipChanges, teacherInternshipChangeReview } from '@/services/internshipApi'
import { useInternshipContextStore } from '@/stores/internshipContext'
import { toast } from '@/utils/nav'

const conflictCode = (e) => ['DATA_CONFLICT', 'APPROVAL_VERSION_CONFLICT', '409001'].includes(String(e && (e.bizCode || e.code)))

export default {
  data() {
    return {
      list: null, state: 'loading', acting: false, batches: [], batchId: '', batchIndex: 0,
      page: 1, hasMore: false, loadingMore: false, lastReceipt: null, conflictReceipt: null
    }
  },
  computed: {
    batchLabels() { return this.batches.map((b) => `${b.name} · ${b.status} · ${b.studentCount}人`) },
    canReview() { return useInternshipContextStore().can('internship.change.review') }
  },
  onLoad() { this.load() },
  onReachBottom() { this.loadMore() },
  onPullDownRefresh() { this.load(() => uni.stopPullDownRefresh()) },
  methods: {
    async load(done) {
      this.state = 'loading'; this.page = 1; this.hasMore = false
      try {
        const context = useInternshipContextStore()
        context.restore()
        await context.load(true)
        this.batches = context.batches || []
        this.batchId = context.selectedBatchId || ''
        this.batchIndex = Math.max(0, this.batches.findIndex((b) => String(b.id) === String(this.batchId)))
        if (!this.batchId) { this.list = []; this.state = 'ready'; return }
        const data = await teacherInternshipChanges(this.batchId, 1, 20)
        this.list = (data && (data.items || data.list)) || []
        this.hasMore = !!data?.hasMore
        this.state = 'ready'
      } catch (e) {
        this.list = []; this.state = 'error'
      } finally { if (done) done() }
    },
    async onBatch(e) {
      this.batchIndex = Number(e.detail.value)
      const context = useInternshipContextStore()
      context.selectBatch(this.batches[this.batchIndex]?.id)
      this.batchId = context.selectedBatchId
      this.conflictReceipt = null
      await this.load()
    },
    async loadMore() {
      if (!this.batchId || !this.hasMore || this.loadingMore || this.state !== 'ready') return
      const selected = this.batchId
      this.loadingMore = true
      try {
        const next = this.page + 1
        const data = await teacherInternshipChanges(selected, next, 20)
        if (selected !== this.batchId) return
        this.list = [...(this.list || []), ...(data?.items || [])]
        this.page = next; this.hasMore = !!data?.hasMore
      } finally { this.loadingMore = false }
    },
    review(c, action, initialComment = '') {
      if (!this.canReview || this.acting) return
      const reject = action === 'REJECT'
      uni.showModal({
        title: reject ? '驳回变更' : '通过变更', editable: true,
        placeholderText: reject ? '请填写驳回原因（至少 5 字）' : '可填写审核意见',
        content: initialComment,
        success: async (result) => {
          if (!result.confirm) return
          const comment = (result.content || '').trim()
          if (reject && comment.length < 5) { toast('驳回原因至少 5 个字'); return }
          this.acting = true; this.conflictReceipt = null
          try {
            const receipt = await teacherInternshipChangeReview(c.id, this.batchId, {
              action, comment, expectedVersion: c.version,
              recordExpectedVersion: c.recordVersionSnapshot
            })
            this.lastReceipt = {
              actionLabel: reject ? '变更申请已驳回' : '变更审批已通过',
              objectLabel: `${c.studentName} · ${c.changeTypeLabel}`,
              statusLabel: receipt.statusLabel || receipt.status, version: receipt.version,
              recordStatusLabel: receipt.recordStatusLabel || c.recordStatusLabel,
              nextStep: receipt.nextStep || '继续处理下一条申请'
            }
            toast(reject ? '已驳回并留下回执' : '已通过并进入重新上岗流程')
            await this.load()
          } catch (e) {
            if (conflictCode(e)) {
              const message = (e && e.message) || '申请或学生主记录版本已变化'
              await this.load()
              const latest = (this.list || []).find((item) => String(item.id) === String(c.id))
              this.conflictReceipt = { message, comment }
              toast('已刷新最新状态，你的意见仍保留')
              if (latest && latest.status === 'PENDING') this.$nextTick(() => this.review(latest, action, comment))
            } else toast((e && e.message) || '审核失败，请重试')
          } finally { this.acting = false }
        }
      })
    }
  }
}
</script>

<style scoped>
.tc__count-unit{font-size:var(--font-size-sm);font-weight:400;color:var(--text-secondary)}.tc__route-label{font-size:10px!important;color:var(--text-tertiary)!important}
.tc__context,.tc__list{display:flex;flex-direction:column;gap:var(--space-3)}.tc__batch{display:flex;align-items:center;justify-content:space-between;gap:var(--space-3);padding:var(--space-3)}.tc__batch>view{min-width:0;display:flex;flex-direction:column;gap:3px}.tc__eyebrow{font-size:var(--font-size-xs);color:var(--text-tertiary)}.tc__batch-name{font-size:var(--font-size-md);font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.tc__picker{color:var(--teacher-700);font-size:var(--font-size-sm)}.tc__receipt,.tc__conflict{display:flex;flex-direction:column;gap:6px;padding:var(--space-3);font-size:var(--font-size-xs);line-height:1.5}.tc__receipt{border-color:var(--success-300,#86efac);background:var(--success-50,#f0fdf4)}.tc__conflict{border-color:var(--warning-300,#fcd34d);background:var(--warning-50,#fffbeb)}.tc__summary{display:flex;align-items:center;justify-content:space-between;gap:var(--space-3);padding:var(--space-3)}.tc__summary>view{display:flex;flex-direction:column;gap:3px}.tc__count{font-size:32px;font-weight:700;color:var(--teacher-700)}.tc__count small{font-size:var(--font-size-sm);font-weight:400;color:var(--text-secondary)}.tc__summary-note{max-width:65%;font-size:var(--font-size-xs);line-height:1.55;color:var(--text-secondary)}.tc{display:flex;flex-direction:column;gap:var(--space-3);padding:var(--space-3)}.tc__head{align-items:flex-start}.tc__sub{display:block;margin-top:3px;font-size:var(--font-size-xs);color:var(--text-tertiary)}.tc__type{display:flex;justify-content:space-between;gap:10px;padding:8px 10px;border-radius:var(--radius-md);background:var(--teacher-50,#eff6ff);font-size:var(--font-size-xs)}.tc__type text:first-child{font-weight:700;color:var(--teacher-700)}.tc__route{display:grid;grid-template-columns:1fr auto 1fr;align-items:stretch;gap:8px}.tc__route>view{display:flex;min-width:0;flex-direction:column;gap:5px;padding:10px;border:1px solid var(--border-light);border-radius:var(--radius-md);background:var(--gray-50)}.tc__route .is-target{border-color:var(--teacher-200,#bfdbfe);background:var(--teacher-50,#eff6ff)}.tc__route small{font-size:10px;color:var(--text-tertiary)}.tc__route b,.tc__route text{font-size:var(--font-size-xs);line-height:1.45;word-break:break-word}.tc__arrow{align-self:center;color:var(--teacher-600);font-size:20px}.tc__reason{display:flex;flex-direction:column;gap:5px;padding:9px 11px;border-radius:var(--radius-md);background:var(--gray-50);font-size:var(--font-size-xs);line-height:1.55}.tc__reason text:first-child,.tc__impact-title{font-weight:700;color:var(--text-secondary)}.tc__impact{display:flex;flex-direction:column;gap:7px;padding:10px 11px;border-radius:var(--radius-md);background:var(--warning-50,#fffbeb)}.tc__impact>view{display:grid;grid-template-columns:64px 1fr;gap:7px;font-size:var(--font-size-xs);line-height:1.5}.tc__impact>view text{color:var(--text-secondary)}.tc__actions{display:flex;gap:var(--space-2)}.tc__reject,.tc__approve{min-height:var(--touch-target-min);border-radius:var(--radius-md);font-size:var(--font-size-md)}.tc__reject{border:1px solid var(--danger-500);background:var(--bg-card);color:var(--danger-600)}.tc__approve{border:none;background:var(--teacher-600);color:#fff}.tc__reject::after,.tc__approve::after{border:none}.tc__more{text-align:center;color:var(--text-tertiary);font-size:var(--font-size-xs)}@media(max-width:360px){.tc__summary{align-items:flex-start;flex-direction:column}.tc__summary-note{max-width:none}.tc__route{grid-template-columns:1fr}.tc__arrow{transform:rotate(90deg)}}
</style>
