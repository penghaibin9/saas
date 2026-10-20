<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="三方协议办理进度" subtitle="指导教师跟进材料 · 学校管理端终审" show-back />

    <view class="page-pad ac__context">
      <view class="card ac__batch" v-if="batches.length">
        <view class="ac__batch-copy">
          <text class="ac__eyebrow">当前办理批次</text>
          <text class="ac__batch-name">{{ batches[batchIndex]?.name || '请选择批次' }}</text>
        </view>
        <picker class="ac__picker" mode="selector" :range="batchLabels" :value="batchIndex" @change="onBatch">
          <view class="ac__pick-val">切换批次 <text class="ac__arrow">▾</text></view>
        </picker>
      </view>

      <view v-if="batches.length && list" class="card ac__summary">
        <view class="ac__summary-main">
          <text class="ac__summary-label">当前待学校终审</text>
          <view class="ac__summary-value"><text>{{ list.length }}</text><text class="ac__summary-unit">份</text></view>
          <text class="ac__summary-note">{{ summaryConclusion }}</text>
        </view>
        <view class="ac__metrics">
          <view class="ac__metric"><text class="ac__metric-value">{{ missingFileCount }}</text><text class="ac__metric-label">缺扫描件</text></view>
          <view class="ac__metric"><text class="ac__metric-value">{{ studentPendingCount }}</text><text class="ac__metric-label">学生待确认</text></view>
          <view class="ac__metric"><text class="ac__metric-value">{{ enterprisePendingCount }}</text><text class="ac__metric-label">企业待确认</text></view>
        </view>
      </view>

      <MobileInlineAlert type="info" description="本页用于教师跟进材料完整性，不执行学校终审。先处理缺扫描件、学生未确认和企业未确认的协议。" />
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad ac__list" v-if="list">
        <MobileGlobalState v-if="!batches.length" state="empty" title="暂无实习批次"
          description="当前身份的数据范围内没有可查看的岗位实习批次。" />
        <MobileGlobalState v-else-if="!list.length" state="empty" title="当前批次没有待终审协议"
          description="学生与企业确认并上传签署扫描件后，协议会进入学校终审队列。" />
        <view class="stack" v-else>
          <view v-for="a in list" :key="a.id" class="card ac">
            <view class="row-between ac__head">
              <view class="flex-1 ac__identity">
                <text class="t-md t-bold ac__name">{{ a.studentName || '—' }}</text>
                <text class="ac__sub">{{ a.studentNo || '' }}</text>
              </view>
              <MobileStatusTag label="待学校终审" type="warning" />
            </view>

            <view class="ac__business">
              <view class="ac__business-row"><text class="ac__business-key">企业</text><text class="ac__business-value">{{ a.enterpriseName || '—' }}</text></view>
              <view class="ac__business-row"><text class="ac__business-key">岗位</text><text class="ac__business-value">{{ a.positionName || '—' }}</text></view>
            </view>

            <view class="ac__confirms">
              <view class="ac__confirm-item" :class="{ 'is-done': isConfirmed(a.studentConfirmLabel) }">
                <text class="ac__confirm-label">学生确认</text><text class="ac__confirm-value">{{ a.studentConfirmLabel || '待确认' }}</text>
              </view>
              <view class="ac__confirm-item" :class="{ 'is-done': isConfirmed(a.enterpriseConfirmLabel) }">
                <text class="ac__confirm-label">企业确认</text><text class="ac__confirm-value">{{ a.enterpriseConfirmLabel || '待确认' }}</text>
              </view>
              <view class="ac__confirm-item" :class="{ 'is-done': a.hasFile, 'is-danger': !a.hasFile }">
                <text class="ac__confirm-label">签署扫描件</text><text class="ac__confirm-value">{{ a.hasFile ? '已上传' : '未上传' }}</text>
              </view>
            </view>

            <view class="ac__next" :class="{ 'is-ready': a.hasFile }">
              <text class="ac__next-label">下一步</text>
              <text class="ac__next-text">{{ a.hasFile ? '材料已进入学校管理端终审队列，继续关注终审结果。' : '提醒学生或企业补齐签署扫描件，再送学校终审。' }}</text>
            </view>

            <view class="ac__source">
              <text>证据来源：{{ a.sourceLabel || '历史来源未知' }}</text>
              <text>协议版本：v{{ a.version }}</text>
            </view>
          </view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherInternshipAgreements } from '@/services/internshipApi'
import { useInternshipContextStore } from '@/stores/internshipContext'

export default {
  data() {
    return {
      list: null, state: 'loading', batches: [], batchId: '', batchIndex: 0,
      page: 1, hasMore: false, loadingMore: false
    }
  },
  onLoad() { this.load() },
  onReachBottom() { this.loadMore() },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  computed: {
    batchLabels() { return this.batches.map((b) => `${b.name} · ${b.status} · ${b.studentCount}人`) },
    missingFileCount() { return (this.list || []).filter((item) => !item.hasFile).length },
    studentPendingCount() { return (this.list || []).filter((item) => !this.isConfirmed(item.studentConfirmLabel)).length },
    enterprisePendingCount() { return (this.list || []).filter((item) => !this.isConfirmed(item.enterpriseConfirmLabel)).length },
    summaryConclusion() {
      if (!this.list?.length) return '当前没有需要教师跟进的协议。'
      if (this.missingFileCount) return `优先催办 ${this.missingFileCount} 份缺少签署扫描件的协议。`
      if (this.studentPendingCount || this.enterprisePendingCount) return '扫描件已齐，继续跟进学生与企业确认。'
      return '材料与双方确认已齐，等待学校管理端终审。'
    }
  },
  methods: {
    isConfirmed(label) {
      return ['已确认', '已签署', '已完成', '有效'].some((text) => String(label || '').includes(text))
    },
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
        const data = await teacherInternshipAgreements(this.batchId, 1, 20)
        this.list = (data && (data.items || data.list)) || []
        this.hasMore = !!data?.hasMore
        this.state = 'ready'
      } catch (e) {
        this.list = []
        this.state = 'error'
      } finally { if (done) done() }
    },
    async onBatch(e) {
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
        const data = await teacherInternshipAgreements(selectedBatch, nextPage, 20)
        if (selectedBatch !== this.batchId) return
        this.list = [...(this.list || []), ...(data?.items || [])]
        this.page = nextPage
        this.hasMore = !!data?.hasMore
      } finally { this.loadingMore = false }
    }
  }
}
</script>

<style scoped>
.ac__context{display:flex;flex-direction:column;gap:var(--space-3)}.ac__batch{display:flex;align-items:center;justify-content:space-between;gap:var(--space-3);padding:var(--space-3)}.ac__batch-copy{min-width:0;display:flex;flex-direction:column;gap:3px}.ac__eyebrow{font-size:var(--font-size-xs);color:var(--text-tertiary)}.ac__batch-name{font-size:var(--font-size-md);font-weight:var(--font-weight-semibold);color:var(--text-primary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.ac__picker{flex-shrink:0}.ac__pick-val{color:var(--teacher-700);font-size:var(--font-size-sm);white-space:nowrap}.ac__arrow{margin-left:4px;color:var(--text-tertiary)}.ac__summary{display:flex;align-items:stretch;gap:var(--space-3);padding:var(--space-3)}.ac__summary-main{flex:1;min-width:0}.ac__summary-label{display:block;font-size:var(--font-size-xs);color:var(--text-tertiary)}.ac__summary-value{display:flex;align-items:baseline;gap:4px;margin-top:3px}.ac__summary-value>text:first-child{font-size:34px;line-height:1;font-weight:700;color:var(--teacher-700)}.ac__summary-unit{font-size:var(--font-size-sm);color:var(--text-secondary)}.ac__summary-note{display:block;margin-top:7px;font-size:var(--font-size-xs);line-height:1.5;color:var(--text-secondary)}.ac__metrics{width:46%;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));background:var(--gray-50);border-radius:var(--radius-md);overflow:hidden}.ac__metric{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;padding:10px 4px;border-left:1px solid var(--border-light);text-align:center}.ac__metric:first-child{border-left:0}.ac__metric-value{font-size:var(--font-size-lg);font-weight:700;color:var(--text-primary)}.ac__metric-label{font-size:10px;line-height:1.3;color:var(--text-tertiary)}.ac__list{padding-top:0}.ac{display:flex;flex-direction:column;gap:var(--space-3);padding:var(--space-3)}.ac__head{align-items:flex-start}.ac__identity{min-width:0}.ac__name{display:block}.ac__sub{display:block;font-size:var(--font-size-xs);color:var(--text-tertiary);margin-top:3px}.ac__business{padding:var(--space-2) var(--space-3);background:var(--gray-50);border-radius:var(--radius-md);display:flex;flex-direction:column;gap:7px}.ac__business-row{display:flex;gap:12px;min-width:0}.ac__business-key{width:36px;flex-shrink:0;font-size:var(--font-size-xs);color:var(--text-tertiary)}.ac__business-value{min-width:0;font-size:var(--font-size-sm);color:var(--text-primary);word-break:break-word}.ac__confirms{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.ac__confirm-item{min-width:0;padding:9px 8px;border:1px solid var(--border-light);border-radius:var(--radius-md);background:var(--bg-card);display:flex;flex-direction:column;gap:4px}.ac__confirm-item.is-done{border-color:var(--success-200,#bbf7d0);background:var(--success-50)}.ac__confirm-item.is-danger{border-color:var(--danger-200,#fecaca);background:var(--danger-50)}.ac__confirm-label{font-size:10px;color:var(--text-tertiary)}.ac__confirm-value{font-size:var(--font-size-xs);font-weight:600;color:var(--text-primary);word-break:break-word}.ac__next{display:flex;gap:10px;padding:10px 12px;border-radius:var(--radius-md);background:var(--warning-50,#fff7ed)}.ac__next.is-ready{background:var(--success-50)}.ac__next-label{flex-shrink:0;font-size:var(--font-size-xs);font-weight:600;color:var(--text-secondary)}.ac__next-text{font-size:var(--font-size-xs);line-height:1.5;color:var(--text-secondary)}.ac__source{display:flex;flex-wrap:wrap;justify-content:space-between;gap:6px 12px;font-size:var(--font-size-xs);color:var(--text-tertiary);word-break:break-word}@media(max-width:360px){.ac__summary{flex-direction:column}.ac__metrics{width:100%}.ac__confirms{grid-template-columns:1fr}.ac__batch{align-items:flex-start}.ac__pick-val{padding-top:4px}}
</style>
