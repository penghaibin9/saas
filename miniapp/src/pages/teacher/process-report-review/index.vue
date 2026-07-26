<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="过程报告批阅" subtitle="按批次批阅日报 · 月报 · 实习总结" show-back />

    <view class="page-pad">
      <view class="card pr__batch" v-if="batches.length">
        <text class="pr__label">实习批次</text>
        <picker class="pr__picker" mode="selector" :range="batchLabels" :value="batchIndex" @change="onBatch">
          <view class="pr__pick-val">{{ batchLabels[batchIndex] || '请选择批次' }}<text class="pr__arrow">▾</text></view>
        </picker>
      </view>
      <MobileInlineAlert type="info" description="报告正文展开后再批阅；退回必须写明可执行修改意见。所有操作携带报告版本，避免覆盖他人处理结果。" />
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="list">
        <MobileGlobalState v-if="!batches.length" state="empty" title="暂无实习批次"
          description="当前身份的数据范围内没有可办理的岗位实习批次。" />
        <MobileGlobalState v-else-if="!list.length" state="empty" title="暂无待批阅报告"
          description="当前批次学生提交日报、月报或实习总结后会出现在这里。" />
        <view class="stack" v-else>
          <view v-for="r in list" :key="r.id" class="card pr">
            <view class="row-between" @click="toggle(r)">
              <view class="flex-1">
                <text class="t-md t-bold">{{ r.studentName || '—' }}</text>
                <text class="pr__sub">{{ r.studentNo || '' }} · {{ r.reportTypeLabel }} · {{ r.periodKey || '—' }} · {{ r.wordCount || 0 }}字</text>
              </view>
              <MobileStatusTag :label="r.statusLabel" type="warning" />
            </view>

            <template v-if="expanded === r.id">
              <view v-if="loadingDetail === r.id" class="pr__loading"><text class="t-sm t-tertiary">正在加载正文…</text></view>
              <template v-else-if="detail[r.id]">
                <view class="pr__meta">
                  <text>企业：{{ detail[r.id].enterpriseName || '—' }}</text>
                  <text>提交：{{ fmt(detail[r.id].submitAt) }}</text>
                </view>
                <view class="pr__content"><text class="pr__content-text">{{ detail[r.id].content || '（无正文）' }}</text></view>
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
      batches: [], batchId: '', batchIndex: 0
    }
  },
  computed: {
    batchLabels() { return this.batches.map((b) => `${b.name} · ${b.status} · ${b.studentCount}人`) },
    canReview() { return useInternshipContextStore().can('internship.report.review') }
  },
  onLoad() { this.load() },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  methods: {
    fmt(value) { return value ? String(value).slice(0, 16).replace('T', ' ') : '—' },
    async load(done) {
      this.state = 'loading'
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
        const data = await teacherInternshipProcessReports(this.batchId)
        this.list = (data && data.list) || []
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
      await this.load()
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
      if (!this.canReview || this.actingId) return
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
            await teacherInternshipProcessReportReview(r.id, {
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
.pr__batch { display:flex;align-items:center;min-height:48px;margin-bottom:var(--space-3);padding:0 var(--space-3); }
.pr__label { width:88px;flex-shrink:0;font-size:var(--font-size-base);color:var(--text-secondary); }
.pr__picker { flex:1; }
.pr__pick-val { text-align:right;color:var(--text-primary);font-size:var(--font-size-base); }
.pr__arrow { margin-left:4px;color:var(--text-tertiary); }
.pr { display:flex;flex-direction:column;gap:var(--space-2); }
.pr__sub { display:block;font-size:var(--font-size-xs);color:var(--text-tertiary);margin-top:2px; }
.pr__loading { padding:var(--space-3) 0;text-align:center; }
.pr__meta { display:flex;flex-wrap:wrap;gap:12px;font-size:var(--font-size-xs);color:var(--text-tertiary); }
.pr__content { background:var(--gray-50);border-radius:var(--radius-md);padding:var(--space-3);max-height:420px;overflow:auto; }
.pr__content-text { font-size:var(--font-size-sm);color:var(--text-primary);line-height:1.7;white-space:pre-wrap; }
.pr__actions { display:flex;gap:var(--space-2); }
.pr__reject,.pr__approve { min-height:var(--touch-target-min);border-radius:var(--radius-md);font-size:var(--font-size-md); }
.pr__reject { border:1px solid var(--danger-500);background:var(--bg-card);color:var(--danger-600); }
.pr__approve { border:none;background:var(--teacher-600);color:#fff; }
.pr__reject::after,.pr__approve::after { border:none; }
</style>
