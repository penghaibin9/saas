<template>
  <view class="mobile-page mobile-teacher page-wrap">
    <MobileNavBar variant="teacher" title="实习风险" show-back :fallback-url="'/pages/teacher-internship/index?batchId=' + batchId" />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad ir__page" v-if="list">
        <view class="ir__context row-between">
          <text>{{ context.selectedBatch?.name || '当前批次' }}</text>
          <picker class="mobile-picker" v-if="context.batches.length > 1" :range="context.batches.map(x => x.name)" :disabled="acting" @change="onBatch"><view class="ir__switch">切换批次 ▾</view></picker>
        </view>
        <MobileSegmented :items="[{label:'待受理',key:'PENDING_HANDLE'},{label:'处理中',key:'PROCESSING'},{label:'全部',key:''}]" :model-value="status" @update:model-value="changeStatus" />
        <text v-if="list.length" class="ir__sub">共 {{ total }} 条 · {{ pendingCount || processingCount ? '高风险事项优先处理' : '当前页均为已办记录' }}</text>
        <MobileInlineAlert v-if="conflictText" type="warning" :description="conflictText" />

        <view v-if="lastReceipt" class="card ir__receipt">
          <view class="row-between"><text class="t-bold">✓ 操作回执 · {{ lastReceipt.action }}</text><text>第{{ lastReceipt.version ?? '—' }}版</text></view>
          <text>{{ lastReceipt.object }}</text>
          <text class="ir__sub">{{ lastReceipt.status }}</text>
          <text class="ir__sub">下一步：{{ lastReceipt.nextStep }}</text>
        </view>

        <MobileGlobalState v-if="!list.length" state="empty" title="当前分类没有风险记录" description="可切换分类查看。" />
        <view class="stack" v-else>
          <view v-for="r in list" :key="r.id" class="card ir" :class="riskClass(r)">
            <view class="row-between ir__head">
              <view class="flex-1 ir__identity">
                <text class="t-md t-bold">{{ r.studentName || '—' }}</text>
                <text class="ir__sub">{{ r.studentNo || '' }}</text>
              </view>
              <MobileStatusTag :label="riskStatusLabel(r.status, r.statusLabel)" :type="r.status === 'PENDING_HANDLE' ? 'warning' : 'default'" />
            </view>

            <view class="ir__risk-title">
              <view class="ir__level" :class="riskClass(r)">{{ riskLevelLabel(r.riskLevel, r.riskLevelLabel) }}</view>
              <view class="flex-1 ir__title-copy">
                <text class="ir__title-label">风险事项</text>
                <text class="ir__title-text">{{ r.riskTitle || '实习风险事项' }}</text>
              </view>
            </view>

            <view class="ir__detail">
              <text class="ir__detail-label">来源 · {{ sourceText(r) }}</text>
              <text class="ir__detail-text">{{ r.latestEvent || r.lastFollowNote || '暂无跟进说明，请受理后补充处置事实。' }}</text>
            </view>

            <view class="ir__next" :class="{ 'is-danger': r.status === 'PENDING_HANDLE' }">
              <text class="ir__next-label">{{ ['CLOSED','RESOLVED'].includes(r.status) ? '结案结果' : '下一步' }}</text>
              <text class="ir__next-text">{{ ['CLOSED','RESOLVED'].includes(r.status) ? nextStepText(r) : r.currentAction || nextStepText(r) }}</text>
            </view>
            <view v-if="!['CLOSED','RESOLVED'].includes(r.status) && r.closeBlockers && r.closeBlockers.length" class="ir__blocked">
              <text>关闭条件未满足</text><text>{{ r.closeBlockers.join('；') }}</text>
            </view>

            <view class="ir__actions" v-if="canHandle && r.status === 'PENDING_HANDLE'">
              <button class="mobile-control btn btn-primary flex-1" :disabled="acting" @click="doHandle(r)">受理并开始处置</button>
            </view>
            <view class="ir__actions" v-else-if="canHandle && r.status === 'PROCESSING'">
              <button class="mobile-control btn btn-ghost flex-1" :disabled="acting" @click="doFollow(r)">补充跟进</button>
              <button v-if="r.closeAllowed !== false" class="mobile-control btn btn-primary flex-1" :disabled="acting" @click="doClose(r)">确认解决并关闭</button>
            </view>
          </view>
        </view>
        <view v-if="total > pageSize" class="row-between ir__pager"><button class="mobile-control btn btn-ghost" :disabled="page <= 1 || acting" @click="loadPage(page - 1)">上一页</button><text>{{ page }} / {{ Math.ceil(total / pageSize) }}</text><button class="mobile-control btn btn-ghost" :disabled="page * pageSize >= total || acting" @click="loadPage(page + 1)">下一页</button></view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'
import { useInternshipContextStore } from '@/stores/internshipContext'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'

export default {
  data() { return { requestedBatchId: '', list: null, state: 'loading', acting: false, lastReceipt: null, conflictText: '', drafts: {}, batchId: '', status: 'PENDING_HANDLE', page: 1, pageSize: 20, total: 0, sequence: 0, hidden: false } },
  computed: {
    context() { return useInternshipContextStore() },
    canHandle() { return this.context.can('internship.risk.handle') },
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
  onLoad(query = {}) { this.requestedBatchId = String(query.batchId || ''); this.load() },
  onShow() { if (this.hidden || this.state !== 'loading') { this.hidden = false; this.load() } },
  onHide() { this.hidden = true; this.sequence++; this.list = null },
  onUnload() { this.sequence++ },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  methods: {
    captureRiskScope() { return { sequence: this.sequence, batchId: this.batchId, generation: currentSessionGeneration() } },
    isRiskScopeCurrent(scope) { return scope.sequence === this.sequence && scope.batchId === this.batchId && scope.batchId === this.context.selectedBatchId && scope.generation === currentSessionGeneration() },
    riskStatusLabel(value, label) {
      return ({ PENDING_HANDLE: '待受理', PROCESSING: '处理中', RESOLVED: '已化解', CLOSED: '已关闭' })[value] || (label && /[一-鿿]/.test(label) ? label : '状态待确认')
    },
    riskLevelLabel(value, label) {
      return ({ LOW: '低风险', MEDIUM: '中风险', HIGH: '高风险', CRITICAL: '重大风险' })[value] || (label && /[一-鿿]/.test(label) ? label : '风险等级待确认')
    },
    riskClass(r) {
      const level = String(r.riskLevel || '').toUpperCase()
      return level === 'CRITICAL' ? 'is-critical' : level === 'HIGH' ? 'is-high' : level === 'MEDIUM' ? 'is-medium' : 'is-low'
    },
    nextStepText(r) {
      if (r.status === 'CLOSED') return '本条风险已关闭，可查看原单和历史处置记录。'
      if (r.status === 'RESOLVED') return '本条风险已化解，可查看原单和历史处置记录。'
      if (r.status === 'PENDING_HANDLE') return '填写受理意见，确认责任人已开始核实和处置。'
      if (r.status === 'PROCESSING') return '继续补充真实跟进记录；问题解决后填写关闭说明。'
      return '查看风险状态和历史跟进，确认是否仍有未闭环事项。'
    },
    sourceText(r) {
      const value = r.sourceType || r.sourceModule
      return ({ CHECKIN: '打卡异常', LEAVE: '请假与销假', REPORT: '周报异常', INSURANCE: '保险异常', AGREEMENT: '协议异常', PLACEMENT: '岗位安排', INCIDENT: '实习事件', COMPLAINT: '实习投诉', MANUAL: '人工登记', INTERNSHIP: '实习管理' })[value] || (value && /[一-鿿]/.test(value) ? value : '来源待核对')
    },
    setReceipt(result, r, action) {
      const data = result || {}
      this.lastReceipt = {
        action, object: `${r.studentName || '学生'} · ${r.riskTitle || '实习风险事项'}`,
        version: data.version, status: this.riskStatusLabel(data.status, data.statusLabel) || '已提交',
        nextStep: data.nextStep || (data.status === 'CLOSED' ? '生成监管证据包或处理下一条' : '继续当前责任链')
      }
      this.conflictText = ''
      delete this.drafts[r.id]
    },
    handleWriteError(error, r, kind, text) {
      if (normalizeError(error).kind === 'conflict') {
        this.drafts[r.id] = { kind, text }
        this.conflictText = `“${text}”已保留；风险事实或版本已变化，已刷新最新状态，请核对后手动重新提交。`
        this.load()
      }
      toast((error && error.message) || '操作失败')
    },
    async load(done) {
      const sequence = ++this.sequence
      const generation = currentSessionGeneration()
      this.state = 'loading'; this.list = null
      try {
        this.context.restore(); await this.context.load(true)
        if (sequence !== this.sequence || generation !== currentSessionGeneration()) return
        if (this.requestedBatchId) {
          if (!this.context.selectBatch(this.requestedBatchId)) throw { httpStatus: 403, message: '当前批次不在授权范围' }
          this.requestedBatchId = ''
        }
        this.batchId = this.context.selectedBatchId || ''
        if (!this.context.can('internship.risk.view')) { this.state = 'forbidden'; return }
        if (!this.batchId) { this.total = 0; this.list = []; this.state = 'ready'; return }
        const d = await teacherApi.getInternshipRisks({ batchId: this.batchId, page: this.page, pageSize: this.pageSize, status: this.status })
        if (sequence !== this.sequence || generation !== currentSessionGeneration() || this.batchId !== this.context.selectedBatchId) return
        this.list = d?.items || d?.list || []; this.total = d?.total ?? this.list.length
        this.state = 'ready'
      } catch(e) { if (sequence === this.sequence && generation === currentSessionGeneration()) this.state = normalizeError(e).pageState || 'error' }
      finally { if (typeof done === 'function') done() }
    },
    loadPage(page) { if (this.acting) return; this.page = page; return this.load() },
    changeStatus(status) { if (this.acting) return; this.status = status; this.page = 1; return this.load() },
    onBatch(e) {
      if (this.acting) return
      this.context.selectBatch(this.context.batches[Number(e.detail.value)]?.id)
      this.page = 1; this.drafts = {}; this.lastReceipt = null; this.conflictText = ''; return this.load()
    },
    doHandle(r) {
      if (this.acting || !this.canHandle || this.state !== 'ready' || r.status !== 'PENDING_HANDLE') return
      const scope = this.captureRiskScope()
      uni.showModal({
        title: '受理风险', editable: true, placeholderText: '受理意见（不少于 5 字）',
        content: this.drafts[r.id]?.kind === 'handle' ? this.drafts[r.id].text : '',
        success: (res) => {
          if (!res.confirm || !this.isRiskScopeCurrent(scope) || this.state !== 'ready' || !this.canHandle) return
          const comment = String(res.content || '').trim()
          if (comment.length < 5) return toast('受理意见不少于 5 字')
          this.acting = true
          teacherApi.handleInternshipRisk(r.id, { comment, expectedVersion: r.version }).then((result) => {
            if (!this.isRiskScopeCurrent(scope)) return
            this.setReceipt(result, r, '受理风险'); toast('已受理'); this.load()
          }).catch((e) => { if (this.isRiskScopeCurrent(scope)) this.handleWriteError(e, r, 'handle', comment) }).finally(() => { this.acting = false })
        }
      })
    },
    doFollow(r) {
      if (this.acting || !this.canHandle || this.state !== 'ready' || r.status !== 'PROCESSING') return
      const scope = this.captureRiskScope()
      uni.showModal({
        title: '跟进记录', editable: true, placeholderText: '跟进说明',
        content: this.drafts[r.id]?.kind === 'follow' ? this.drafts[r.id].text : '',
        success: (res) => {
          if (!res.confirm || !this.isRiskScopeCurrent(scope) || this.state !== 'ready' || !this.canHandle) return
          const note = String(res.content || '').trim()
          if (note.length < 2) return toast('跟进说明必填')
          this.acting = true
          teacherApi.followInternshipRisk(r.id, { note, expectedVersion: r.version }).then((result) => {
            if (!this.isRiskScopeCurrent(scope)) return
            this.setReceipt(result, r, '补充跟进'); toast('已跟进'); this.load()
          }).catch((e) => { if (this.isRiskScopeCurrent(scope)) this.handleWriteError(e, r, 'follow', note) }).finally(() => { this.acting = false })
        }
      })
    },
    doClose(r) {
      if (this.acting || !this.canHandle || this.state !== 'ready' || r.status !== 'PROCESSING' || r.closeAllowed === false) return
      const scope = this.captureRiskScope()
      uni.showModal({
        title: '办结关闭', editable: true, placeholderText: '关闭说明（不少于 5 字）',
        content: this.drafts[r.id]?.kind === 'close' ? this.drafts[r.id].text : '',
        success: (res) => {
          if (!res.confirm || !this.isRiskScopeCurrent(scope) || this.state !== 'ready' || !this.canHandle) return
          const comment = String(res.content || '').trim()
          if (comment.length < 5) return toast('关闭说明不少于 5 字')
          this.acting = true
          teacherApi.closeInternshipRisk(r.id, { result: 'RESOLVED', comment, expectedVersion: r.version }).then((result) => {
            if (!this.isRiskScopeCurrent(scope)) return
            this.setReceipt(result, r, '关闭风险'); toast('已关闭'); this.load()
          }).catch((e) => { if (this.isRiskScopeCurrent(scope)) this.handleWriteError(e, r, 'close', comment) }).finally(() => { this.acting = false })
        }
      })
    }
  }
}
</script>

<style scoped>
.ir__receipt{display:flex;flex-direction:column;gap:6px;padding:var(--space-3);border:1px solid var(--success-200,#a7f3d0);background:var(--success-50,#ecfdf5)}.ir__blocked{display:flex;flex-direction:column;gap:4px;padding:10px 12px;border-radius:var(--radius-md);background:var(--danger-50,#fef2f2);color:var(--danger-700,#b91c1c);font-size:var(--font-size-xs)}
.ir__page{display:flex;flex-direction:column;gap:var(--space-3)}.ir__summary{display:flex;align-items:stretch;gap:var(--space-3);padding:var(--space-3)}.ir__summary-main{flex:1;min-width:0}.ir__summary-label{display:block;font-size:var(--font-size-xs);color:var(--text-tertiary)}.ir__summary-value{display:flex;align-items:baseline;gap:4px;margin-top:4px}.ir__summary-value text:first-child{font-size:34px;line-height:1;font-weight:700;color:var(--danger-600)}.ir__summary-value text:last-child{font-size:var(--font-size-sm);color:var(--text-secondary)}.ir__summary-note{display:block;margin-top:8px;font-size:var(--font-size-xs);line-height:1.5;color:var(--text-secondary)}.ir__summary-metrics{width:50%;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));background:var(--gray-50);border-radius:var(--radius-md);overflow:hidden}.ir__metric{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;padding:10px 3px;border-left:1px solid var(--border-light);text-align:center}.ir__metric:first-child{border-left:0}.ir__metric text:first-child{font-size:var(--font-size-lg);font-weight:700;color:var(--text-primary)}.ir__metric.is-danger text:first-child{color:var(--danger-600)}.ir__metric.is-warning text:first-child{color:var(--warning-700)}.ir__metric text:last-child{font-size:10px;line-height:1.25;color:var(--text-tertiary)}.ir{display:flex;flex-direction:column;gap:var(--space-3);padding:var(--space-3);border-left:4px solid var(--border-light)}.ir.is-critical,.ir.is-high{border-left-color:var(--danger-500)}.ir.is-medium{border-left-color:var(--warning-500)}.ir.is-low{border-left-color:var(--teacher-300,#93c5fd)}.ir__head{align-items:flex-start}.ir__identity{min-width:0}.ir__sub{display:block;margin-top:4px;font-size:var(--font-size-xs);color:var(--text-tertiary)}.ir__risk-title{display:flex;align-items:center;gap:10px;padding:var(--space-2) var(--space-3);background:var(--gray-50);border-radius:var(--radius-md)}.ir__level{flex-shrink:0;padding:5px 9px;border-radius:var(--radius-full);background:var(--teacher-50,#eff6ff);color:var(--teacher-700);font-size:var(--font-size-xs);font-weight:600}.ir__level.is-critical,.ir__level.is-high{background:var(--danger-50);color:var(--danger-700)}.ir__level.is-medium{background:var(--warning-50,#fff7ed);color:var(--warning-800,#9a3412)}.ir__title-copy{min-width:0}.ir__title-label{display:block;font-size:10px;color:var(--text-tertiary)}.ir__title-text{display:block;margin-top:3px;font-size:var(--font-size-sm);font-weight:600;line-height:1.45;color:var(--text-primary);word-break:break-word}.ir__detail{padding:var(--space-2) var(--space-3);border:1px solid var(--border-light);border-radius:var(--radius-md)}.ir__detail-label{display:block;font-size:var(--font-size-xs);font-weight:600;color:var(--text-secondary)}.ir__detail-text{display:block;margin-top:5px;font-size:var(--font-size-sm);line-height:1.6;color:var(--text-primary);white-space:pre-wrap;word-break:break-word}.ir__next{display:flex;gap:10px;padding:10px 12px;border-radius:var(--radius-md);background:var(--teacher-50,#eff6ff)}.ir__next.is-danger{background:var(--warning-50,#fff7ed)}.ir__next-label{flex-shrink:0;font-size:var(--font-size-xs);font-weight:600;color:var(--text-secondary)}.ir__next-text{font-size:var(--font-size-xs);line-height:1.5;color:var(--text-secondary)}.ir__actions{display:flex;gap:8px}.ir__actions .btn{min-height:var(--touch-target-min)}@media(max-width:360px){.ir__summary{flex-direction:column}.ir__summary-metrics{width:100%}.ir__risk-title{align-items:flex-start}}
</style>
<style scoped>
.ir__context{gap:12px;font-size:14px;line-height:1.5}.ir__context>text{min-width:0;overflow-wrap:anywhere}.ir__switch{min-height:44px;display:flex;align-items:center;color:var(--teacher-700);white-space:nowrap}.ir__detail-text{font-size:15px}.ir__sub,.ir__next-text,.ir__next-label,.ir__level{font-size:14px}.ir__actions .btn,.ir__pager .btn{min-height:44px;font-size:14px}.ir__pager{gap:12px;font-size:14px}.ir__page :deep(.mseg__item){min-height:44px;font-size:14px}.ir__page :deep(.mseg__item.is-active){background:var(--teacher-600);border-color:var(--teacher-600)}
</style>
