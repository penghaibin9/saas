<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="实习申请审核" subtitle="核对去向、材料与学生记录版本" show-back />

    <view class="page-pad ap__context">
      <view class="card ap__batch" v-if="batches.length">
        <view class="ap__batch-copy">
          <text class="ap__eyebrow">当前审核批次</text>
          <text class="ap__batch-name">{{ batches[batchIndex]?.name || '请选择批次' }}</text>
        </view>
        <picker class="ap__picker" mode="selector" :range="batchLabels" :value="batchIndex" :disabled="!!actingId" @change="onBatch">
          <view class="ap__pick-val">切换批次 <text class="ap__arrow">▾</text></view>
        </picker>
      </view>

      <view v-if="batches.length && list" class="card ap__summary">
        <view class="ap__summary-main">
          <text class="ap__summary-label">待审核申请</text>
          <view class="ap__summary-value"><text>{{ list.length }}</text><text>条</text></view>
          <text class="ap__summary-note">{{ summaryConclusion }}</text>
        </view>
        <view class="ap__summary-metrics">
          <view class="ap__metric"><text>{{ assignedCount }}</text><text>学校安排</text></view>
          <view class="ap__metric"><text>{{ selfArrangedCount }}</text><text>自主实习</text></view>
          <view class="ap__metric is-danger"><text>{{ missingEvidenceCount }}</text><text>材料缺失</text></view>
        </view>
      </view>

      <MobileInlineAlert type="warning" description="通过会落实岗位或自主实习去向。请先核对企业、岗位、联系人、证明材料及学生记录版本，再执行审批。" />
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad ap__list" v-if="list">
        <MobileGlobalState v-if="!batches.length" state="empty" title="暂无实习批次"
          description="当前身份的数据范围内没有可审核的岗位实习批次。" />
        <MobileGlobalState v-else-if="!list.length" state="empty" title="当前批次没有待审申请"
          description="学生提交正式实习申请后会出现在这里。" />
        <view class="stack" v-else>
          <view v-for="a in list" :key="a.id" class="card ap">
            <view class="row-between ap__head">
              <view class="flex-1 ap__identity">
                <text class="t-md t-bold">{{ a.studentName || '—' }}</text>
                <text class="ap__sub">{{ a.studentNo || '' }} · {{ a.applicationTypeLabel }}</text>
              </view>
              <MobileStatusTag :label="a.statusLabel" type="warning" />
            </view>

            <view class="ap__business">
              <view class="ap__row"><text class="ap__row-k">企业</text><text class="ap__row-v">{{ a.companyName || '—' }}</text></view>
              <view class="ap__row"><text class="ap__row-k">岗位</text><text class="ap__row-v">{{ a.positionName || '—' }}</text></view>
              <view class="ap__row" v-if="a.workAddress"><text class="ap__row-k">地点</text><text class="ap__row-v">{{ a.workAddress }}</text></view>
              <view class="ap__row" v-if="a.contactName"><text class="ap__row-k">联系人</text><text class="ap__row-v">{{ a.contactName }} {{ a.contactPhone || '' }}</text></view>
            </view>

            <view v-if="a.applicationNote" class="ap__note">
              <text class="ap__section-label">申请说明</text>
              <text class="ap__note-text">{{ a.applicationNote }}</text>
            </view>

            <button v-if="a.evidenceFileId" class="ap__evidence" :disabled="previewingId === a.id" @click="previewEvidence(a)">
              <view class="ap__evidence-copy">
                <text class="ap__evidence-title">自主实习证明材料</text>
                <text class="ap__evidence-hint">点击查看原始文件后再决定是否通过</text>
              </view>
              <text class="ap__evidence-action">{{ previewingId === a.id ? '打开中…' : '查看 ›' }}</text>
            </button>
            <view v-else-if="a.applicationType === 'SELF_ARRANGED'" class="ap__danger">
              <text class="ap__danger-title">缺少自主实习证明材料</text>
              <text class="ap__danger-text">当前申请不能通过，应驳回学生补充材料。</text>
            </view>

            <view class="ap__versions" :class="{ 'has-error': a.recordVersion == null || a.version == null }">
              <view><text>申请版本</text><text>v{{ a.version == null ? '—' : a.version }}</text></view>
              <view><text>学生记录</text><text>{{ a.recordVersion == null ? '版本缺失' : `v${a.recordVersion}` }}</text></view>
              <view><text>提交时间</text><text>{{ fmt(a.submittedAt) }}</text></view>
            </view>

            <view class="ap__next" :class="{ 'is-danger': !canApprove(a) }">
              <text class="ap__next-label">下一步</text>
              <text class="ap__next-text">{{ nextStepText(a) }}</text>
            </view>

            <view class="ap__actions" v-if="canReview">
              <button class="ap__reject flex-1" :disabled="actingId === a.id" @click="review(a, 'REJECT')">驳回修改</button>
              <button class="ap__approve flex-1" :disabled="actingId === a.id || !canApprove(a)" @click="review(a, 'APPROVE')">{{ approveLabel(a) }}</button>
            </view>
            <MobileInlineAlert v-else type="warning" description="当前身份仅可查看，无正式实习申请审核权限。" />
          </view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherInternshipApplications, teacherInternshipApplicationReview } from '@/services/internshipApi'
import { openBusinessFile } from '@/services/fileApi'
import { useInternshipContextStore } from '@/stores/internshipContext'
import { toast } from '@/utils/nav'

export default {
  data() {
    return { list: null, state: 'loading', actingId: '', previewingId: '', batches: [], batchId: '', batchIndex: 0 }
  },
  computed: {
    batchLabels() { return this.batches.map((b) => `${b.name} · ${b.status} · ${b.studentCount}人`) },
    canReview() { return useInternshipContextStore().can('internship.application.review') },
    selfArrangedCount() { return (this.list || []).filter((item) => item.applicationType === 'SELF_ARRANGED').length },
    assignedCount() { return (this.list || []).length - this.selfArrangedCount },
    missingEvidenceCount() { return (this.list || []).filter((item) => item.applicationType === 'SELF_ARRANGED' && !item.evidenceFileId).length },
    summaryConclusion() {
      if (!this.list?.length) return '当前没有需要审核的正式实习申请。'
      if (this.missingEvidenceCount) return `优先驳回 ${this.missingEvidenceCount} 条缺少自主实习证明的申请。`
      return '材料与版本信息齐全，可逐条核对企业和岗位后审批。'
    }
  },
  onLoad() { this.load() },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  methods: {
    fmt(value) { return value ? String(value).slice(0, 16).replace('T', ' ') : '—' },
    approveLabel(a) { return a.applicationType === 'SELF_ARRANGED' ? '通过并确认自主实习' : '通过并落实岗位' },
    canApprove(a) {
      const evidenceOk = a.applicationType !== 'SELF_ARRANGED' || !!a.evidenceFileId
      return evidenceOk && a.recordVersion != null && a.version != null
    },
    nextStepText(a) {
      if (a.applicationType === 'SELF_ARRANGED' && !a.evidenceFileId) return '驳回学生补充自主实习证明材料。'
      if (a.recordVersion == null || a.version == null) return '刷新页面获取最新申请与学生记录版本。'
      return a.applicationType === 'SELF_ARRANGED' ? '查看证明材料，核实企业信息后确认自主实习。' : '核对企业与岗位信息后，通过并落实岗位。'
    },
    async load(done) {
      this.state = 'loading'
      try {
        const context = useInternshipContextStore()
        context.restore()
        await context.load(true)
        this.batches = context.batches || []
        this.batchId = context.selectedBatchId || ''
        this.batchIndex = Math.max(0, this.batches.findIndex((b) => String(b.id) === String(this.batchId)))
        if (!this.batchId) { this.list = []; this.state = 'ready'; return }
        const data = await teacherInternshipApplications(this.batchId)
        this.list = (data && data.list) || []
        this.state = 'ready'
      } catch (e) {
        this.list = []
        this.state = 'error'
        toast((e && e.message) || '实习申请加载失败')
      } finally { if (done) done() }
    },
    async onBatch(e) {
      if (this.actingId) return
      this.batchIndex = Number(e.detail.value)
      const batch = this.batches[this.batchIndex]
      const context = useInternshipContextStore()
      context.selectBatch(batch && batch.id)
      this.batchId = context.selectedBatchId
      await this.load()
    },
    async previewEvidence(item) {
      if (!item.evidenceFileId || this.previewingId) return
      this.previewingId = item.id
      try { await openBusinessFile(item.evidenceFileId) }
      catch (e) { toast((e && e.message) || '证明材料打开失败') }
      finally { this.previewingId = '' }
    },
    review(a, action) {
      if (!this.canReview || this.actingId) return
      if (action === 'APPROVE' && !this.canApprove(a)) {
        toast(a.applicationType === 'SELF_ARRANGED' && !a.evidenceFileId
          ? '自主实习证明材料缺失，不能通过'
          : '申请或学生记录版本缺失，请刷新后再试')
        return
      }
      const reject = action === 'REJECT'
      uni.showModal({
        title: reject ? '驳回申请' : this.approveLabel(a),
        editable: true,
        placeholderText: reject ? '请填写具体驳回原因（至少5字）' : '可填写审核意见',
        content: '',
        success: async (r) => {
          if (!r.confirm) return
          const comment = (r.content || '').trim()
          if (reject && comment.length < 5) { toast('驳回原因至少5个字'); return }
          this.actingId = a.id
          try {
            await teacherInternshipApplicationReview(a.id, {
              action,
              comment,
              expectedVersion: a.version,
              recordExpectedVersion: a.recordVersion,
              batchId: this.batchId
            })
            toast(reject ? '已驳回学生修改' : (a.applicationType === 'SELF_ARRANGED' ? '已确认自主实习去向' : '已通过并落实岗位'))
            await this.load()
          } catch (e) {
            if (String(e && e.code) === 'DATA_CONFLICT') {
              toast((e && e.message) || '申请或学生记录已变化，正在刷新')
              await this.load()
            } else toast((e && e.message) || '申请审核失败，请重试')
          } finally { this.actingId = '' }
        }
      })
    }
  }
}
</script>

<style scoped>
.ap__context{display:flex;flex-direction:column;gap:var(--space-3)}.ap__batch{display:flex;align-items:center;justify-content:space-between;gap:var(--space-3);padding:var(--space-3)}.ap__batch-copy{min-width:0;display:flex;flex-direction:column;gap:3px}.ap__eyebrow{font-size:var(--font-size-xs);color:var(--text-tertiary)}.ap__batch-name{font-size:var(--font-size-md);font-weight:600;color:var(--text-primary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.ap__picker{flex-shrink:0}.ap__pick-val{color:var(--teacher-700);font-size:var(--font-size-sm);white-space:nowrap}.ap__arrow{margin-left:4px;color:var(--text-tertiary)}.ap__summary{display:flex;align-items:stretch;gap:var(--space-3);padding:var(--space-3)}.ap__summary-main{flex:1;min-width:0}.ap__summary-label{display:block;font-size:var(--font-size-xs);color:var(--text-tertiary)}.ap__summary-value{display:flex;align-items:baseline;gap:4px;margin-top:4px}.ap__summary-value text:first-child{font-size:34px;line-height:1;font-weight:700;color:var(--teacher-700)}.ap__summary-value text:last-child{font-size:var(--font-size-sm);color:var(--text-secondary)}.ap__summary-note{display:block;margin-top:8px;font-size:var(--font-size-xs);line-height:1.5;color:var(--text-secondary)}.ap__summary-metrics{width:48%;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));background:var(--gray-50);border-radius:var(--radius-md);overflow:hidden}.ap__metric{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;padding:10px 4px;border-left:1px solid var(--border-light);text-align:center}.ap__metric:first-child{border-left:0}.ap__metric text:first-child{font-size:var(--font-size-lg);font-weight:700;color:var(--text-primary)}.ap__metric.is-danger text:first-child{color:var(--danger-600)}.ap__metric text:last-child{font-size:10px;line-height:1.3;color:var(--text-tertiary)}.ap__list{padding-top:0}.ap{display:flex;flex-direction:column;gap:var(--space-3);padding:var(--space-3)}.ap__head{align-items:flex-start}.ap__identity{min-width:0}.ap__sub{display:block;font-size:var(--font-size-xs);color:var(--text-tertiary);margin-top:3px;word-break:break-word}.ap__business{display:flex;flex-direction:column;gap:8px;padding:var(--space-2) var(--space-3);background:var(--gray-50);border-radius:var(--radius-md)}.ap__row{display:flex;gap:var(--space-3);min-width:0}.ap__row-k{font-size:var(--font-size-xs);color:var(--text-tertiary);width:42px;flex-shrink:0}.ap__row-v{min-width:0;flex:1;font-size:var(--font-size-sm);line-height:1.5;color:var(--text-primary);word-break:break-word}.ap__note{padding:var(--space-2) var(--space-3);border:1px solid var(--border-light);border-radius:var(--radius-md)}.ap__section-label{display:block;font-size:var(--font-size-xs);font-weight:600;color:var(--text-secondary)}.ap__note-text{display:block;margin-top:5px;font-size:var(--font-size-sm);line-height:1.6;color:var(--text-primary);white-space:pre-wrap;word-break:break-word}.ap__evidence{display:flex;align-items:center;justify-content:space-between;gap:var(--space-3);min-height:58px;padding:10px var(--space-3);border:1px solid var(--success-300,#86efac);border-radius:var(--radius-md);background:var(--success-50);text-align:left}.ap__evidence::after{border:none}.ap__evidence-copy{min-width:0}.ap__evidence-title{display:block;font-size:var(--font-size-sm);font-weight:600;color:var(--success-800,#166534)}.ap__evidence-hint{display:block;margin-top:3px;font-size:var(--font-size-xs);color:var(--success-700)}.ap__evidence-action{flex-shrink:0;font-size:var(--font-size-sm);color:var(--success-700)}.ap__danger{padding:var(--space-2) var(--space-3);border:1px solid var(--danger-200,#fecaca);border-radius:var(--radius-md);background:var(--danger-50)}.ap__danger-title{display:block;font-size:var(--font-size-sm);font-weight:600;color:var(--danger-700)}.ap__danger-text{display:block;margin-top:3px;font-size:var(--font-size-xs);line-height:1.5;color:var(--danger-600)}.ap__versions{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;padding:var(--space-2);border-radius:var(--radius-md);background:var(--gray-50)}.ap__versions.has-error{background:var(--warning-50,#fff7ed)}.ap__versions>view{min-width:0;display:flex;flex-direction:column;gap:3px}.ap__versions>view text:first-child{font-size:10px;color:var(--text-tertiary)}.ap__versions>view text:last-child{font-size:var(--font-size-xs);font-weight:600;color:var(--text-primary);word-break:break-word}.ap__next{display:flex;gap:10px;padding:10px 12px;border-radius:var(--radius-md);background:var(--teacher-50,#eff6ff)}.ap__next.is-danger{background:var(--warning-50,#fff7ed)}.ap__next-label{flex-shrink:0;font-size:var(--font-size-xs);font-weight:600;color:var(--text-secondary)}.ap__next-text{font-size:var(--font-size-xs);line-height:1.5;color:var(--text-secondary)}.ap__actions{display:flex;gap:var(--space-2)}.ap__reject,.ap__approve{min-height:var(--touch-target-min);border-radius:var(--radius-md);font-size:var(--font-size-md)}.ap__reject{border:1px solid var(--danger-500);background:var(--bg-card);color:var(--danger-600)}.ap__approve{border:none;background:var(--teacher-600);color:#fff}.ap__approve[disabled],.ap__reject[disabled],.ap__evidence[disabled]{opacity:.45}.ap__reject::after,.ap__approve::after{border:none}@media(max-width:360px){.ap__summary{flex-direction:column}.ap__summary-metrics{width:100%}.ap__versions{grid-template-columns:1fr}.ap__batch{align-items:flex-start}}
</style>
