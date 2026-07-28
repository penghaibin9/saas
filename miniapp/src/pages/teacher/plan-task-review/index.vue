<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="实习计划任务确认" subtitle="查看完成说明与凭证后确认" show-back />

    <view class="page-pad pt__context">
      <view class="card pt__batch" v-if="batches.length">
        <view class="pt__batch-copy">
          <text class="pt__eyebrow">当前确认批次</text>
          <text class="pt__batch-name">{{ batches[batchIndex]?.name || '请选择批次' }}</text>
        </view>
        <picker class="pt__picker" mode="selector" :range="batchLabels" :value="batchIndex" :disabled="!!actingId" @change="onBatch">
          <view class="pt__pick-val">切换批次 <text class="pt__arrow">▾</text></view>
        </picker>
      </view>

      <view v-if="batches.length && list" class="card pt__summary">
        <view class="pt__summary-main">
          <text class="pt__summary-label">待确认任务</text>
          <view class="pt__summary-value"><text>{{ list.length }}</text><text>项</text></view>
          <text class="pt__summary-note">{{ summaryConclusion }}</text>
        </view>
        <view class="pt__summary-metrics">
          <view class="pt__metric"><text>{{ evidenceCount }}</text><text>有凭证</text></view>
          <view class="pt__metric is-warning"><text>{{ missingEvidenceCount }}</text><text>无凭证</text></view>
        </view>
      </view>

      <MobileInlineAlert type="info" description="先阅读学生完成说明，再按任务要求查看凭证。退回时写清可执行修改意见，避免学生反复重交。" />
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad pt__list" v-if="list">
        <MobileGlobalState v-if="!batches.length" state="empty" title="暂无实习批次"
          description="当前身份的数据范围内没有可办理的岗位实习批次。" />
        <MobileGlobalState v-else-if="!list.length" state="empty" title="当前批次没有待确认任务"
          description="学生提交任务完成情况后会出现在这里。" />
        <view class="stack" v-else>
          <view v-for="p in list" :key="p.id" class="card pt">
            <view class="row-between pt__head">
              <view class="flex-1 pt__identity">
                <text class="t-md t-bold">{{ p.studentName || '—' }}</text>
                <text class="pt__sub">{{ p.studentNo || '' }}</text>
              </view>
              <MobileStatusTag :label="p.statusLabel" type="warning" />
            </view>

            <view class="pt__task-title">
              <text class="pt__task-no">{{ p.taskSortOrder }}</text>
              <view class="flex-1 pt__task-copy">
                <text class="pt__task-label">计划任务</text>
                <text class="pt__task-name">{{ p.taskName || '未命名任务' }}</text>
              </view>
            </view>

            <view class="pt__note">
              <text class="pt__section-label">学生完成说明</text>
              <text class="pt__note-text">{{ p.studentNote || '学生未填写完成说明' }}</text>
            </view>

            <button v-if="p.evidenceFileId" class="pt__evidence" :disabled="previewingId === p.id" @click="previewEvidence(p)">
              <view class="pt__evidence-copy">
                <text class="pt__evidence-title">学生完成凭证</text>
                <text class="pt__evidence-hint">打开原始文件，核对是否满足任务要求</text>
              </view>
              <text class="pt__evidence-action">{{ previewingId === p.id ? '打开中…' : '查看 ›' }}</text>
            </button>
            <view v-else class="pt__missing">
              <text class="pt__missing-title">未上传完成凭证</text>
              <text class="pt__missing-text">请结合任务本身是否要求附件，谨慎确认。</text>
            </view>

            <view class="pt__meta">
              <text>提交时间 {{ fmt(p.submittedAt) }}</text>
              <text>数据版本 v{{ p.version }}</text>
            </view>

            <view class="pt__next">
              <text class="pt__next-label">下一步</text>
              <text class="pt__next-text">{{ p.evidenceFileId ? '查看凭证并核对说明，确认完成或退回修改。' : '核对任务要求；需要凭证时应退回补充。' }}</text>
            </view>

            <view class="pt__actions" v-if="canReview">
              <button class="pt__reject flex-1" :disabled="actingId === p.id" @click="review(p, 'REJECT')">退回修改</button>
              <button class="pt__approve flex-1" :disabled="actingId === p.id" @click="review(p, 'APPROVE')">确认完成</button>
            </view>
            <MobileInlineAlert v-else type="warning" description="当前身份仅可查看，无任务确认权限。" />
          </view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherInternshipPlanTasks, teacherInternshipPlanTaskReview } from '@/services/internshipApi'
import { openBusinessFile } from '@/services/fileApi'
import { useInternshipContextStore } from '@/stores/internshipContext'
import { toast } from '@/utils/nav'

export default {
  data() {
    return {
      list: null, state: 'loading', actingId: '', previewingId: '', batches: [],
      batchId: '', batchIndex: 0, page: 1, hasMore: false, loadingMore: false
    }
  },
  computed: {
    batchLabels() { return this.batches.map((b) => `${b.name} · ${b.status} · ${b.studentCount}人`) },
    canReview() { return useInternshipContextStore().can('internship.task.review') },
    evidenceCount() { return (this.list || []).filter((item) => item.evidenceFileId).length },
    missingEvidenceCount() { return (this.list || []).length - this.evidenceCount },
    summaryConclusion() {
      if (!this.list?.length) return '当前没有需要确认的计划任务。'
      if (this.missingEvidenceCount) return `${this.missingEvidenceCount} 项未上传凭证，需结合任务要求重点核对。`
      return '全部待办均附带凭证，可按提交顺序逐项确认。'
    }
  },
  onLoad() { this.load() },
  onReachBottom() { this.loadMore() },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  methods: {
    fmt(value) { return value ? String(value).slice(0, 16).replace('T', ' ') : '—' },
    async load(done) {
      this.state = 'loading'
      this.page = 1
      this.hasMore = false
      try {
        const context = useInternshipContextStore()
        context.restore()
        await context.load(true)
        this.batches = context.batches || []
        this.batchId = context.selectedBatchId || ''
        this.batchIndex = Math.max(0, this.batches.findIndex((b) => String(b.id) === String(this.batchId)))
        if (!this.batchId) { this.list = []; this.state = 'ready'; return }
        const data = await teacherInternshipPlanTasks(this.batchId, 1, 20)
        this.list = (data && (data.items || data.list)) || []
        this.hasMore = !!data?.hasMore
        this.state = 'ready'
      } catch (e) {
        this.list = []
        this.state = 'error'
        toast((e && e.message) || '计划任务加载失败')
      } finally { if (done) done() }
    },
    async onBatch(e) {
      if (this.actingId) return
      this.batchIndex = Number(e.detail.value)
      const batch = this.batches[this.batchIndex]
      const context = useInternshipContextStore()
      context.selectBatch(batch && batch.id)
      this.batchId = context.selectedBatchId
      this.list = []
      await this.load()
    },
    async loadMore() {
      if (!this.batchId || !this.hasMore || this.loadingMore || this.state !== 'ready') return
      const selectedBatch = this.batchId
      this.loadingMore = true
      try {
        const nextPage = this.page + 1
        const data = await teacherInternshipPlanTasks(selectedBatch, nextPage, 20)
        if (selectedBatch !== this.batchId) return
        this.list = [...(this.list || []), ...(data?.items || [])]
        this.page = nextPage
        this.hasMore = !!data?.hasMore
      } finally { this.loadingMore = false }
    },
    async previewEvidence(item) {
      if (!item.evidenceFileId || this.previewingId) return
      this.previewingId = item.id
      try { await openBusinessFile(item.evidenceFileId) }
      catch (e) { toast((e && e.message) || '凭证打开失败') }
      finally { this.previewingId = '' }
    },
    review(p, action) {
      if (!this.canReview || this.actingId || this.state !== 'ready') return
      const reject = action === 'REJECT'
      uni.showModal({
        title: reject ? '退回任务' : '确认完成',
        editable: true,
        placeholderText: reject ? '请填写具体退回原因（至少5字）' : '可填写确认意见',
        content: '',
        success: async (r) => {
          if (!r.confirm) return
          const comment = (r.content || '').trim()
          if (reject && comment.length < 5) { toast('退回原因至少5个字'); return }
          this.actingId = p.id
          try {
            await teacherInternshipPlanTaskReview(p.id, this.batchId, {
              action, comment, expectedVersion: p.version, batchId: this.batchId
            })
            toast(reject ? '已退回学生修改' : '已确认任务完成')
            await this.load()
          } catch (e) {
            if (String(e && e.code) === 'DATA_CONFLICT') {
              toast((e && e.message) || '任务已被其他人处理，正在刷新')
              await this.load()
            } else toast((e && e.message) || '任务处理失败，请重试')
          } finally { this.actingId = '' }
        }
      })
    }
  }
}
</script>

<style scoped>
.pt__context{display:flex;flex-direction:column;gap:var(--space-3)}.pt__batch{display:flex;align-items:center;justify-content:space-between;gap:var(--space-3);padding:var(--space-3)}.pt__batch-copy{min-width:0;display:flex;flex-direction:column;gap:3px}.pt__eyebrow{font-size:var(--font-size-xs);color:var(--text-tertiary)}.pt__batch-name{font-size:var(--font-size-md);font-weight:600;color:var(--text-primary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.pt__picker{flex-shrink:0}.pt__pick-val{color:var(--teacher-700);font-size:var(--font-size-sm);white-space:nowrap}.pt__arrow{margin-left:4px;color:var(--text-tertiary)}.pt__summary{display:flex;align-items:stretch;gap:var(--space-3);padding:var(--space-3)}.pt__summary-main{flex:1;min-width:0}.pt__summary-label{display:block;font-size:var(--font-size-xs);color:var(--text-tertiary)}.pt__summary-value{display:flex;align-items:baseline;gap:4px;margin-top:4px}.pt__summary-value text:first-child{font-size:34px;line-height:1;font-weight:700;color:var(--teacher-700)}.pt__summary-value text:last-child{font-size:var(--font-size-sm);color:var(--text-secondary)}.pt__summary-note{display:block;margin-top:8px;font-size:var(--font-size-xs);line-height:1.5;color:var(--text-secondary)}.pt__summary-metrics{width:42%;display:grid;grid-template-columns:1fr 1fr;background:var(--gray-50);border-radius:var(--radius-md);overflow:hidden}.pt__metric{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;padding:10px 5px;border-left:1px solid var(--border-light)}.pt__metric:first-child{border-left:0}.pt__metric text:first-child{font-size:var(--font-size-lg);font-weight:700;color:var(--success-700)}.pt__metric.is-warning text:first-child{color:var(--warning-700)}.pt__metric text:last-child{font-size:10px;color:var(--text-tertiary)}.pt__list{padding-top:0}.pt{display:flex;flex-direction:column;gap:var(--space-3);padding:var(--space-3)}.pt__head{align-items:flex-start}.pt__identity{min-width:0}.pt__sub{display:block;font-size:var(--font-size-xs);color:var(--text-tertiary);margin-top:3px}.pt__task-title{display:flex;align-items:center;gap:10px;padding:var(--space-2) var(--space-3);background:var(--teacher-50,#eff6ff);border-radius:var(--radius-md)}.pt__task-no{display:flex;align-items:center;justify-content:center;width:28px;height:28px;flex-shrink:0;border-radius:50%;background:var(--teacher-600);color:#fff;font-size:var(--font-size-sm);font-weight:700}.pt__task-copy{min-width:0}.pt__task-label{display:block;font-size:10px;color:var(--text-tertiary)}.pt__task-name{display:block;margin-top:2px;font-size:var(--font-size-sm);font-weight:600;color:var(--text-primary);word-break:break-word}.pt__note{padding:var(--space-2) var(--space-3);border:1px solid var(--border-light);border-radius:var(--radius-md)}.pt__section-label{display:block;font-size:var(--font-size-xs);font-weight:600;color:var(--text-secondary)}.pt__note-text{display:block;margin-top:5px;font-size:var(--font-size-sm);line-height:1.6;color:var(--text-primary);white-space:pre-wrap;word-break:break-word}.pt__evidence{display:flex;align-items:center;justify-content:space-between;gap:var(--space-3);min-height:58px;padding:10px var(--space-3);border:1px solid var(--success-300,#86efac);border-radius:var(--radius-md);background:var(--success-50);text-align:left}.pt__evidence::after{border:none}.pt__evidence-copy{min-width:0}.pt__evidence-title{display:block;font-size:var(--font-size-sm);font-weight:600;color:var(--success-800,#166534)}.pt__evidence-hint{display:block;margin-top:3px;font-size:var(--font-size-xs);color:var(--success-700)}.pt__evidence-action{flex-shrink:0;font-size:var(--font-size-sm);color:var(--success-700)}.pt__missing{padding:var(--space-2) var(--space-3);border:1px solid var(--warning-200,#fed7aa);border-radius:var(--radius-md);background:var(--warning-50,#fff7ed)}.pt__missing-title{display:block;font-size:var(--font-size-sm);font-weight:600;color:var(--warning-800,#9a3412)}.pt__missing-text{display:block;margin-top:3px;font-size:var(--font-size-xs);line-height:1.5;color:var(--warning-700)}.pt__meta{display:flex;flex-wrap:wrap;justify-content:space-between;gap:5px 12px;font-size:var(--font-size-xs);color:var(--text-tertiary)}.pt__next{display:flex;gap:10px;padding:10px 12px;border-radius:var(--radius-md);background:var(--gray-50)}.pt__next-label{flex-shrink:0;font-size:var(--font-size-xs);font-weight:600;color:var(--text-secondary)}.pt__next-text{font-size:var(--font-size-xs);line-height:1.5;color:var(--text-secondary)}.pt__actions{display:flex;gap:var(--space-2)}.pt__reject,.pt__approve{min-height:var(--touch-target-min);border-radius:var(--radius-md);font-size:var(--font-size-md)}.pt__reject{border:1px solid var(--danger-500);background:var(--bg-card);color:var(--danger-600)}.pt__approve{border:none;background:var(--teacher-600);color:#fff}.pt__reject::after,.pt__approve::after{border:none}.pt__reject[disabled],.pt__approve[disabled],.pt__evidence[disabled]{opacity:.55}@media(max-width:360px){.pt__summary{flex-direction:column}.pt__summary-metrics{width:100%}.pt__batch{align-items:flex-start}}
</style>
