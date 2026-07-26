<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="实习风险处置" subtitle="受理、持续跟进并形成办结留痕" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad ir__page" v-if="list">
        <view class="card ir__summary">
          <view class="ir__summary-main">
            <text class="ir__summary-label">当前风险待办</text>
            <view class="ir__summary-value"><text>{{ list.length }}</text><text>条</text></view>
            <text class="ir__summary-note">{{ summaryConclusion }}</text>
          </view>
          <view class="ir__summary-metrics">
            <view class="ir__metric is-danger"><text>{{ pendingCount }}</text><text>待受理</text></view>
            <view class="ir__metric is-warning"><text>{{ processingCount }}</text><text>处理中</text></view>
            <view class="ir__metric"><text>{{ highRiskCount }}</text><text>高风险</text></view>
          </view>
        </view>

        <MobileInlineAlert type="warning" description="优先受理高风险和学生主动求助事项；处理中风险应持续记录跟进事实，确认问题解决后再办结关闭。" />

        <MobileGlobalState v-if="!list.length" state="empty" title="暂无待办风险"
          description="学生求助、超期未销假、打卡转风险等会出现在这里；本页不替代学工危机处置。" />
        <view class="stack" v-else>
          <view v-for="r in list" :key="r.id" class="card ir" :class="riskClass(r)">
            <view class="row-between ir__head">
              <view class="flex-1 ir__identity">
                <text class="t-md t-bold">{{ r.studentName || '—' }}</text>
                <text class="ir__sub">{{ r.studentNo || '' }}</text>
              </view>
              <MobileStatusTag :label="r.statusLabel || r.status" :type="r.status === 'PENDING_HANDLE' ? 'warning' : 'default'" />
            </view>

            <view class="ir__risk-title">
              <view class="ir__level" :class="riskClass(r)">{{ r.riskLevelLabel || r.riskLevel || '风险' }}</view>
              <view class="flex-1 ir__title-copy">
                <text class="ir__title-label">风险事项</text>
                <text class="ir__title-text">{{ r.riskTitle || r.riskCode || '未命名风险' }}</text>
              </view>
            </view>

            <view class="ir__detail">
              <text class="ir__detail-label">最新情况</text>
              <text class="ir__detail-text">{{ r.lastFollowNote || '暂无跟进说明，请受理后补充处置事实。' }}</text>
            </view>

            <view class="ir__next" :class="{ 'is-danger': r.status === 'PENDING_HANDLE' }">
              <text class="ir__next-label">下一步</text>
              <text class="ir__next-text">{{ nextStepText(r) }}</text>
            </view>

            <view class="ir__actions" v-if="r.status === 'PENDING_HANDLE'">
              <button class="btn btn-primary flex-1" :disabled="acting" @click="doHandle(r)">受理并开始处置</button>
            </view>
            <view class="ir__actions" v-else-if="r.status === 'PROCESSING'">
              <button class="btn btn-ghost flex-1" :disabled="acting" @click="doFollow(r)">补充跟进</button>
              <button class="btn btn-primary flex-1" :disabled="acting" @click="doClose(r)">确认解决并关闭</button>
            </view>
          </view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { toast } from '@/utils/nav'

export default {
  data() { return { list: null, state: 'loading', acting: false } },
  computed: {
    pendingCount() { return (this.list || []).filter((item) => item.status === 'PENDING_HANDLE').length },
    processingCount() { return (this.list || []).filter((item) => item.status === 'PROCESSING').length },
    highRiskCount() { return (this.list || []).filter((item) => ['HIGH', 'CRITICAL'].includes(String(item.riskLevel || '').toUpperCase())).length },
    summaryConclusion() {
      if (!this.list?.length) return '当前没有需要处置的岗位实习风险。'
      if (this.highRiskCount) return `有 ${this.highRiskCount} 条高风险事项，应优先核实和处置。`
      if (this.pendingCount) return `${this.pendingCount} 条风险尚未受理。`
      return '当前风险均已受理，请持续记录跟进并及时办结。'
    }
  },
  onLoad() { this.load() },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  methods: {
    riskClass(r) {
      const level = String(r.riskLevel || '').toUpperCase()
      return level === 'CRITICAL' ? 'is-critical' : level === 'HIGH' ? 'is-high' : level === 'MEDIUM' ? 'is-medium' : 'is-low'
    },
    nextStepText(r) {
      if (r.status === 'PENDING_HANDLE') return '填写受理意见，确认责任人已开始核实和处置。'
      if (r.status === 'PROCESSING') return '继续补充真实跟进记录；问题解决后填写关闭说明。'
      return '查看风险状态和历史跟进，确认是否仍有未闭环事项。'
    },
    load(done) {
      this.state = 'loading'
      teacherApi.getInternshipRisks().then((d) => {
        this.list = (d && d.list) || []
        this.state = 'ready'
      }).catch(() => { this.state = 'error' }).finally(() => { if (done) done() })
    },
    doHandle(r) {
      uni.showModal({
        title: '受理风险', editable: true, placeholderText: '受理意见（不少于 5 字）',
        success: (res) => {
          if (!res.confirm) return
          const comment = String(res.content || '').trim()
          if (comment.length < 5) return toast('受理意见不少于 5 字')
          this.acting = true
          teacherApi.handleInternshipRisk(r.id, { comment }).then(() => {
            toast('已受理'); this.load()
          }).catch((e) => toast((e && e.message) || '受理失败')).finally(() => { this.acting = false })
        }
      })
    },
    doFollow(r) {
      uni.showModal({
        title: '跟进记录', editable: true, placeholderText: '跟进说明',
        success: (res) => {
          if (!res.confirm) return
          const note = String(res.content || '').trim()
          if (note.length < 2) return toast('跟进说明必填')
          this.acting = true
          teacherApi.followInternshipRisk(r.id, note).then(() => {
            toast('已跟进'); this.load()
          }).catch((e) => toast((e && e.message) || '跟进失败')).finally(() => { this.acting = false })
        }
      })
    },
    doClose(r) {
      uni.showModal({
        title: '办结关闭', editable: true, placeholderText: '关闭说明（不少于 5 字）',
        success: (res) => {
          if (!res.confirm) return
          const comment = String(res.content || '').trim()
          if (comment.length < 5) return toast('关闭说明不少于 5 字')
          this.acting = true
          teacherApi.closeInternshipRisk(r.id, { result: 'RESOLVED', comment }).then(() => {
            toast('已关闭'); this.load()
          }).catch((e) => toast((e && e.message) || '关闭失败')).finally(() => { this.acting = false })
        }
      })
    }
  }
}
</script>

<style scoped>
.ir__page{display:flex;flex-direction:column;gap:var(--space-3)}.ir__summary{display:flex;align-items:stretch;gap:var(--space-3);padding:var(--space-3)}.ir__summary-main{flex:1;min-width:0}.ir__summary-label{display:block;font-size:var(--font-size-xs);color:var(--text-tertiary)}.ir__summary-value{display:flex;align-items:baseline;gap:4px;margin-top:4px}.ir__summary-value text:first-child{font-size:34px;line-height:1;font-weight:700;color:var(--danger-600)}.ir__summary-value text:last-child{font-size:var(--font-size-sm);color:var(--text-secondary)}.ir__summary-note{display:block;margin-top:8px;font-size:var(--font-size-xs);line-height:1.5;color:var(--text-secondary)}.ir__summary-metrics{width:50%;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));background:var(--gray-50);border-radius:var(--radius-md);overflow:hidden}.ir__metric{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;padding:10px 3px;border-left:1px solid var(--border-light);text-align:center}.ir__metric:first-child{border-left:0}.ir__metric text:first-child{font-size:var(--font-size-lg);font-weight:700;color:var(--text-primary)}.ir__metric.is-danger text:first-child{color:var(--danger-600)}.ir__metric.is-warning text:first-child{color:var(--warning-700)}.ir__metric text:last-child{font-size:10px;line-height:1.25;color:var(--text-tertiary)}.ir{display:flex;flex-direction:column;gap:var(--space-3);padding:var(--space-3);border-left:4px solid var(--border-light)}.ir.is-critical,.ir.is-high{border-left-color:var(--danger-500)}.ir.is-medium{border-left-color:var(--warning-500)}.ir.is-low{border-left-color:var(--teacher-300,#93c5fd)}.ir__head{align-items:flex-start}.ir__identity{min-width:0}.ir__sub{display:block;margin-top:4px;font-size:var(--font-size-xs);color:var(--text-tertiary)}.ir__risk-title{display:flex;align-items:center;gap:10px;padding:var(--space-2) var(--space-3);background:var(--gray-50);border-radius:var(--radius-md)}.ir__level{flex-shrink:0;padding:5px 9px;border-radius:var(--radius-full);background:var(--teacher-50,#eff6ff);color:var(--teacher-700);font-size:var(--font-size-xs);font-weight:600}.ir__level.is-critical,.ir__level.is-high{background:var(--danger-50);color:var(--danger-700)}.ir__level.is-medium{background:var(--warning-50,#fff7ed);color:var(--warning-800,#9a3412)}.ir__title-copy{min-width:0}.ir__title-label{display:block;font-size:10px;color:var(--text-tertiary)}.ir__title-text{display:block;margin-top:3px;font-size:var(--font-size-sm);font-weight:600;line-height:1.45;color:var(--text-primary);word-break:break-word}.ir__detail{padding:var(--space-2) var(--space-3);border:1px solid var(--border-light);border-radius:var(--radius-md)}.ir__detail-label{display:block;font-size:var(--font-size-xs);font-weight:600;color:var(--text-secondary)}.ir__detail-text{display:block;margin-top:5px;font-size:var(--font-size-sm);line-height:1.6;color:var(--text-primary);white-space:pre-wrap;word-break:break-word}.ir__next{display:flex;gap:10px;padding:10px 12px;border-radius:var(--radius-md);background:var(--teacher-50,#eff6ff)}.ir__next.is-danger{background:var(--warning-50,#fff7ed)}.ir__next-label{flex-shrink:0;font-size:var(--font-size-xs);font-weight:600;color:var(--text-secondary)}.ir__next-text{font-size:var(--font-size-xs);line-height:1.5;color:var(--text-secondary)}.ir__actions{display:flex;gap:8px}.ir__actions .btn{min-height:var(--touch-target-min)}@media(max-width:360px){.ir__summary{flex-direction:column}.ir__summary-metrics{width:100%}.ir__risk-title{align-items:flex-start}}
</style>
