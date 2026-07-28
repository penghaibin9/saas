<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="过程报告批阅" subtitle="先读正文，再通过或退回修改" show-back />

    <view class="page-pad pr__context">
      <view class="card pr__batch" v-if="batches.length">
        <view class="pr__batch-copy">
          <text class="pr__eyebrow">当前批阅批次</text>
          <text class="pr__batch-name">{{ batches[batchIndex]?.name || '请选择批次' }}</text>
        </view>
        <picker class="pr__picker" mode="selector" :range="batchLabels" :value="batchIndex" :disabled="!!actingId" @change="onBatch">
          <view class="pr__pick-val">切换批次 <text class="pr__arrow">▾</text></view>
        </picker>
      </view>

      <view v-if="batches.length && list" class="card pr__summary">
        <view class="pr__summary-main">
          <text class="pr__summary-label">待批阅报告</text>
          <view class="pr__summary-value"><text>{{ list.length }}</text><text>篇</text></view>
          <text class="pr__summary-note">{{ summaryConclusion }}</text>
        </view>
        <view class="pr__summary-metrics">
          <view class="pr__metric"><text>{{ dailyCount }}</text><text>日报</text></view>
          <view class="pr__metric"><text>{{ monthlyCount }}</text><text>月报</text></view>
          <view class="pr__metric"><text>{{ summaryCount }}</text><text>总结</text></view>
        </view>
      </view>

      <MobileInlineAlert type="info" description="点击学生卡片展开完整正文。退回时写清具体修改要求；所有操作仍按当前报告版本提交。" />
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad pr__list" v-if="list">
        <MobileGlobalState v-if="!batches.length" state="empty" title="暂无实习批次"
          description="当前身份的数据范围内没有可办理的岗位实习批次。" />
        <MobileGlobalState v-else-if="!list.length" state="empty" title="当前批次没有待批阅报告"
          description="学生提交日报、月报或实习总结后会出现在这里。" />
        <view class="stack" v-else>
          <view v-for="r in list" :key="r.id" class="card pr" :class="{ 'is-expanded': expanded === r.id }">
            <view class="row-between pr__head" @click="toggle(r)">
              <view class="flex-1 pr__identity">
                <text class="t-md t-bold">{{ r.studentName || '—' }}</text>
                <text class="pr__sub">{{ r.studentNo || '' }} · {{ r.reportTypeLabel }}</text>
              </view>
              <view class="pr__head-right">
                <MobileStatusTag :label="r.statusLabel" type="warning" />
                <text class="pr__chevron">{{ expanded === r.id ? '收起 ▲' : '展开正文 ▼' }}</text>
              </view>
            </view>

            <view class="pr__brief">
              <view><text>报告周期</text><text>{{ r.periodKey || '—' }}</text></view>
              <view><text>正文长度</text><text>{{ r.wordCount || 0 }} 字</text></view>
              <view><text>数据版本</text><text>v{{ r.version }}</text></view>
            </view>

            <template v-if="expanded === r.id">
              <view v-if="loadingDetail === r.id" class="pr__loading"><text class="t-sm t-tertiary">正在加载正文…</text></view>
              <template v-else-if="detail[r.id]">
                <view class="pr__meta">
                  <text>企业：{{ detail[r.id].enterpriseName || '—' }}</text>
                  <text>提交：{{ fmt(detail[r.id].submitAt) }}</text>
                </view>
                <view class="pr__content">
                  <text class="pr__content-label">报告正文</text>
                  <text class="pr__content-text">{{ detail[r.id].content || '（无正文）' }}</text>
                </view>
                <view class="pr__next">
                  <text class="pr__next-label">批阅重点</text>
                  <text class="pr__next-text">核对内容是否真实、完整、与当前实习阶段相符；退回意见应让学生能直接修改。</text>
                </view>
                <view class="pr__actions" v-if="canReview">
                  <button class="pr__reject flex-1" :disabled="actingId === r.id" @click.stop="review(r, 'RETURN')">退回修改</button>
                  <button class="pr__approve flex-1" :disabled="actingId === r.id" @click.stop="review(r, 'APPROVE')">通过报告</button>
                </view>
                <MobileInlineAlert v-else type="warning" description="当前身份仅可查看，无过程报告批阅权限。" />
              </template>
            </template>
          </view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import {
  teacherInternshipProcessReports,
  teacherInternshipProcessReportDetail,
  teacherInternshipProcessReportReview
} from '@/services/internshipApi'
import { useInternshipContextStore } from '@/stores/internshipContext'
import { toast } from '@/utils/nav'

export default {
  data() {
    return {
      list: null, state: 'loading', expanded: '', detail: {}, loadingDetail: '', actingId: '',
      batches: [], batchId: '', batchIndex: 0, page: 1, hasMore: false, loadingMore: false
    }
  },
  computed: {
    batchLabels() { return this.batches.map((b) => `${b.name} · ${b.status} · ${b.studentCount}人`) },
    canReview() { return useInternshipContextStore().can('internship.report.review') },
    dailyCount() { return (this.list || []).filter((item) => String(item.reportType || item.reportTypeLabel || '').includes('DAILY') || String(item.reportTypeLabel || '').includes('日报')).length },
    monthlyCount() { return (this.list || []).filter((item) => String(item.reportType || item.reportTypeLabel || '').includes('MONTH') || String(item.reportTypeLabel || '').includes('月报')).length },
    summaryCount() { return Math.max(0, (this.list || []).length - this.dailyCount - this.monthlyCount) },
    summaryConclusion() {
      if (!this.list?.length) return '当前没有需要批阅的过程报告。'
      const shortCount = this.list.filter((item) => Number(item.wordCount || 0) < 100).length
      if (shortCount) return `${shortCount} 篇正文较短，展开后重点核对完整性。`
      return '按提交顺序展开正文，批阅后通过或给出明确修改意见。'
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
        this.expanded = ''
        this.detail = {}
        if (!this.batchId) { this.list = []; this.state = 'ready'; return }
        const data = await teacherInternshipProcessReports(this.batchId, 1, 20)
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
        const data = await teacherInternshipProcessReports(selectedBatch, nextPage, 20)
        if (selectedBatch !== this.batchId) return
        this.list = [...(this.list || []), ...(data?.items || [])]
        this.page = nextPage
        this.hasMore = !!data?.hasMore
      } finally { this.loadingMore = false }
    },
    async toggle(r) {
      if (this.expanded === r.id) { this.expanded = ''; return }
      this.expanded = r.id
      if (this.detail[r.id]) return
      this.loadingDetail = r.id
      try {
        const data = await teacherInternshipProcessReportDetail(r.id)
        this.detail = { ...this.detail, [r.id]: data }
      } catch (e) {
        toast((e && e.message) || '报告正文加载失败')
        this.expanded = ''
      } finally { this.loadingDetail = '' }
    },
    review(r, action) {
      if (!this.canReview || this.actingId || this.state !== 'ready') return
      const reject = action === 'RETURN'
      uni.showModal({
        title: reject ? '退回报告' : '通过报告',
        editable: true,
        placeholderText: reject ? '请填写具体修改要求（至少5字）' : '可填写批阅意见',
        content: '',
        success: async (m) => {
          if (!m.confirm) return
          const comment = (m.content || '').trim()
          if (reject && comment.length < 5) { toast('退回原因至少5个字'); return }
          this.actingId = r.id
          try {
            await teacherInternshipProcessReportReview(r.id, this.batchId, {
              action, comment, expectedVersion: r.version, batchId: this.batchId
            })
            toast(reject ? '已退回学生修改' : '报告已通过')
            await this.load()
          } catch (e) {
            if (String(e && e.code) === 'DATA_CONFLICT') {
              toast((e && e.message) || '报告已被其他人处理，正在刷新')
              await this.load()
            } else toast((e && e.message) || '报告批阅失败，请重试')
          } finally { this.actingId = '' }
        }
      })
    }
  }
}
</script>

<style scoped>
.pr__context{display:flex;flex-direction:column;gap:var(--space-3)}.pr__batch{display:flex;align-items:center;justify-content:space-between;gap:var(--space-3);padding:var(--space-3)}.pr__batch-copy{min-width:0;display:flex;flex-direction:column;gap:3px}.pr__eyebrow{font-size:var(--font-size-xs);color:var(--text-tertiary)}.pr__batch-name{font-size:var(--font-size-md);font-weight:600;color:var(--text-primary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.pr__picker{flex-shrink:0}.pr__pick-val{color:var(--teacher-700);font-size:var(--font-size-sm);white-space:nowrap}.pr__arrow{margin-left:4px;color:var(--text-tertiary)}.pr__summary{display:flex;align-items:stretch;gap:var(--space-3);padding:var(--space-3)}.pr__summary-main{flex:1;min-width:0}.pr__summary-label{display:block;font-size:var(--font-size-xs);color:var(--text-tertiary)}.pr__summary-value{display:flex;align-items:baseline;gap:4px;margin-top:4px}.pr__summary-value text:first-child{font-size:34px;line-height:1;font-weight:700;color:var(--teacher-700)}.pr__summary-value text:last-child{font-size:var(--font-size-sm);color:var(--text-secondary)}.pr__summary-note{display:block;margin-top:8px;font-size:var(--font-size-xs);line-height:1.5;color:var(--text-secondary)}.pr__summary-metrics{width:48%;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));background:var(--gray-50);border-radius:var(--radius-md);overflow:hidden}.pr__metric{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;padding:10px 4px;border-left:1px solid var(--border-light)}.pr__metric:first-child{border-left:0}.pr__metric text:first-child{font-size:var(--font-size-lg);font-weight:700;color:var(--text-primary)}.pr__metric text:last-child{font-size:10px;color:var(--text-tertiary)}.pr__list{padding-top:0}.pr{display:flex;flex-direction:column;gap:var(--space-3);padding:var(--space-3)}.pr.is-expanded{border-color:var(--teacher-200,#bfdbfe)}.pr__head{align-items:flex-start}.pr__identity{min-width:0}.pr__sub{display:block;font-size:var(--font-size-xs);color:var(--text-tertiary);margin-top:3px}.pr__head-right{flex-shrink:0;display:flex;flex-direction:column;align-items:flex-end;gap:6px}.pr__chevron{font-size:10px;color:var(--teacher-700)}.pr__brief{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;padding:var(--space-2);background:var(--gray-50);border-radius:var(--radius-md)}.pr__brief>view{min-width:0;display:flex;flex-direction:column;gap:3px}.pr__brief text:first-child{font-size:10px;color:var(--text-tertiary)}.pr__brief text:last-child{font-size:var(--font-size-xs);font-weight:600;color:var(--text-primary);word-break:break-word}.pr__loading{padding:var(--space-4) 0;text-align:center}.pr__meta{display:flex;flex-wrap:wrap;justify-content:space-between;gap:6px 12px;font-size:var(--font-size-xs);color:var(--text-tertiary)}.pr__content{background:var(--gray-50);border-radius:var(--radius-md);padding:var(--space-3);max-height:420px;overflow:auto}.pr__content-label{display:block;margin-bottom:7px;font-size:var(--font-size-xs);font-weight:600;color:var(--text-secondary)}.pr__content-text{font-size:var(--font-size-sm);color:var(--text-primary);line-height:1.75;white-space:pre-wrap;word-break:break-word}.pr__next{display:flex;gap:10px;padding:10px 12px;border-radius:var(--radius-md);background:var(--teacher-50,#eff6ff)}.pr__next-label{flex-shrink:0;font-size:var(--font-size-xs);font-weight:600;color:var(--text-secondary)}.pr__next-text{font-size:var(--font-size-xs);line-height:1.5;color:var(--text-secondary)}.pr__actions{display:flex;gap:var(--space-2)}.pr__reject,.pr__approve{min-height:var(--touch-target-min);border-radius:var(--radius-md);font-size:var(--font-size-md)}.pr__reject{border:1px solid var(--danger-500);background:var(--bg-card);color:var(--danger-600)}.pr__approve{border:none;background:var(--teacher-600);color:#fff}.pr__reject::after,.pr__approve::after{border:none}.pr__reject[disabled],.pr__approve[disabled]{opacity:.55}@media(max-width:360px){.pr__summary{flex-direction:column}.pr__summary-metrics{width:100%}.pr__brief{grid-template-columns:1fr}.pr__batch{align-items:flex-start}}
</style>
