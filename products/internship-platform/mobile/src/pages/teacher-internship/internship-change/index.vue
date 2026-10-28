<template>
  <view class="mobile-page mobile-teacher page-wrap teacher-changes">
    <MobileNavBar variant="teacher" title="实习变更审核" show-back />

    <view class="page-pad tc__context">
      <view v-if="batches.length" class="tc__batch">
        <view><text class="tc__batch-name">{{ batches[batchIndex]?.name || '请选择批次' }}</text></view>
        <picker class="mobile-picker" v-if="batches.length > 1" mode="selector" :range="batchLabels" :value="batchIndex" :disabled="acting" @change="onBatch">
          <view class="tc__picker">切换批次 ▾</view>
        </picker>
      </view>

      <view v-if="lastReceipt" class="card tc__receipt">
        <view class="row-between"><text class="t-bold">✓ {{ lastReceipt.actionLabel }}</text><text>第{{ lastReceipt.version }}版</text></view>
        <text>{{ lastReceipt.objectLabel }} · {{ lastReceipt.statusLabel }}</text>
        <text>主记录：{{ lastReceipt.recordStatusLabel }} · {{ lastReceipt.nextStep }}</text>
      </view>
      <view v-if="conflictReceipt" class="card tc__conflict">
        <text class="t-bold">{{ conflictReceipt.studentName }}的申请未处理完成</text>
        <text>{{ conflictReceipt.message }}</text>
        <text v-if="conflictReceipt.comment">已保留意见：{{ conflictReceipt.comment }}</text>
      </view>

      <view v-if="state === 'ready' && list && total > 0" class="tc__summary">
        <view><text class="tc__eyebrow">{{ currentLabel }}变更</text><text class="tc__count">{{ total }}<text class="tc__count-unit"> 条</text></text></view>
      </view>
      <view class="row-between"><button class="mobile-control" v-for="tab in tabs" :key="tab.value" :disabled="acting" :aria-pressed="reviewStatus === tab.value" @click="setReviewStatus(tab.value)">{{ tab.label }}</button></view>
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <view v-if="list" class="page-pad tc__list">
        <view v-if="focusId" class="card"><text>正在查看待办对应的原变更申请。</text><button class="mobile-control btn btn-ghost" @click="clearFocus">查看本批次全部变更申请</button></view>
        <MobileGlobalState v-if="!batches.length" state="empty" title="暂无实习批次" description="当前身份的数据范围内没有可办理批次。" />
        <MobileGlobalState v-else-if="!list.length" state="empty" :title="'当前批次没有' + currentLabel + '变更'" description="可切换分类查看其他变更。" />
        <view v-else class="stack">
          <view v-for="c in list" :key="c.id" class="card tc">
            <view class="row-between tc__head">
              <view><text class="t-md t-bold">{{ c.studentName || '—' }}</text><text class="tc__sub">{{ c.studentNo }} · 申请 #{{ c.id }}</text></view>
              <MobileStatusTag :label="c.statusLabel" :type="c.status === 'APPROVED' ? 'success' : c.status === 'REJECTED' ? 'danger' : 'warning'" />
            </view>
            <view class="tc__type"><text>{{ c.changeTypeLabel }}</text><text>第 {{ c.version }} 版申请</text></view>
            <view v-if="relationship(c)" class="tc__route">
              <view><text class="tc__route-label">{{ c.status === 'APPROVED' ? '本次变更前' : '当前关系' }}</text><text class="t-bold">{{ relationship(c).before.enterpriseName || '未落实单位' }}</text><text>{{ relationship(c).before.positionName || '未落实岗位' }}</text></view>
              <text class="tc__arrow">→</text>
              <view class="is-target"><text class="tc__route-label">{{ c.status === 'APPROVED' ? '本次变更后' : '目标关系' }}</text><text class="t-bold">{{ relationship(c).after.enterpriseName || '未落实单位' }}</text><text>{{ relationship(c).after.positionName || '待重新落实' }}</text></view>
            </view>
            <template v-if="c.status === 'APPROVED'">
              <MobileInlineAlert v-if="!c.approvedHistory" type="warning" description="历史去向未记录，无法核实本次审批前后去向。" />
              <view v-if="!relationship(c) || c.currentEnterprise !== relationship(c).after.enterpriseName || c.currentPosition !== relationship(c).after.positionName" class="tc__reason"><text>当前实习关系</text><text>{{ c.currentEnterprise || '未落实单位' }} · {{ c.currentPosition || '未落实岗位' }}</text></view>
            </template>
            <button v-if="c.status === 'APPROVED'" class="mobile-control btn btn-ghost" :aria-expanded="expandedNotesId === c.id" @click="expandedNotesId = expandedNotesId === c.id ? '' : c.id">{{ expandedNotesId === c.id ? '收起申请详情' : '查看申请详情' }}</button>
            <template v-if="c.status !== 'APPROVED' || expandedNotesId === c.id"><view class="tc__reason"><text>申请原因</text><text>{{ c.reason }}</text></view>
            <view v-if="c.reviewComment" class="tc__reason"><text>审核意见</text><text>{{ c.reviewComment }}</text></view></template>
            <button class="mobile-control" v-if="canViewStudent" @click="openStudent(c)">查看学生档案</button>
            <view v-if="c.status === 'PENDING'" class="tc__impact">
              <text class="tc__impact-title">通过后的影响</text>
              <text>旧关系将结束，旧协议失效；学生需重新完成上岗核验。</text>
              <view v-for="item in c.impactItems || []" :key="item.label"><text class="t-bold">{{ item.label }}</text><text>{{ item.detail }}</text></view>
            </view>
            <view v-if="canReview && c.status === 'PENDING'" class="tc__actions">
              <button class="mobile-control tc__reject flex-1" :disabled="acting" @click="review(c, 'REJECT')">驳回补充</button>
              <button class="mobile-control tc__approve flex-1" :disabled="acting" @click="review(c, 'APPROVE')">确认通过</button>
            </view>
            <MobileInlineAlert v-else-if="c.status === 'PENDING'" type="warning" description="当前身份仅可查看，无实习变更审核权限。" />
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
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { toast } from '@/utils/nav'

const conflictCode = (e) => ['DATA_CONFLICT', 'APPROVAL_VERSION_CONFLICT', '409001'].includes(String(e && (e.bizCode || e.code)))

export default {
  data() {
    return {
      expandedNotesId: '', list: null, state: 'loading', acting: false, batches: [], batchId: '', batchIndex: 0,
      page: 1, hasMore: false, loadingMore: false, lastReceipt: null, conflictReceipt: null,
      total: 0, reviewStatus: 'PENDING', requestSeq: 0, reviewSeq: 0, generation: currentSessionGeneration(), hidden: false,
      requestedBatchId: '', focusId: ''
    }
  },
  computed: {
    batchLabels() { return this.batches.map((b) => `${b.name} · ${b.studentCount}人`) },
    canViewStudent() { return useInternshipContextStore().can('internship.student.view') },
    canReview() { return useInternshipContextStore().can('internship.change.review') },
    tabs() { return [{ value: 'PENDING', label: '待审核' }, { value: 'REVIEWED', label: '已审核' }, { value: 'REJECTED', label: '已驳回' }, { value: 'ALL', label: '全部' }] },
    currentLabel() { return this.tabs.find(tab => tab.value === this.reviewStatus)?.label || '全部' }
  },
  onLoad(options = {}) { this.requestedBatchId = String(options.batchId || ''); this.focusId = String(options.changeId || ''); if (this.focusId) this.reviewStatus = 'ALL'; return this.load() },
  onShow() { const refresh = this.hidden || this.generation !== currentSessionGeneration(); this.hidden = false; if (refresh) return this.load() },
  onHide() { this.expandedNotesId = ''; this.hidden = true; this.requestSeq++; this.reviewSeq++; this.acting = false },
  onUnload() { this.hidden = true; this.requestSeq++; this.reviewSeq++; this.acting = false },
  onReachBottom() { this.loadMore() },
  onPullDownRefresh() { this.load(() => uni.stopPullDownRefresh()) },
  methods: {
    relationship(c) {
      if (c.status === 'APPROVED') return c.approvedHistory || null
      return { before:{enterpriseName:c.currentEnterprise,positionName:c.currentPosition},
        after:{enterpriseName:c.targetEnterpriseName || (c.changeType === 'WITHDRAW_POST' ? '退岗' : '自主实习'),positionName:c.targetPositionName} }
    },
    clearFocus() { this.focusId = ''; this.reviewStatus = 'PENDING'; return this.load() },
    current(seq, generation, batchId = this.batchId, status = this.reviewStatus) { return !this.hidden && seq === this.requestSeq && generation === currentSessionGeneration() && String(batchId) === String(this.batchId) && status === this.reviewStatus },
    openStudent(item) { if (this.canViewStudent && item.internId) uni.navigateTo({ url: '/pages/teacher-internship/internship-students/detail?id=' + encodeURIComponent(item.internId) + '&batchId=' + encodeURIComponent(this.batchId) }) },
    async setReviewStatus(status) { if (this.acting || status === this.reviewStatus) return; this.reviewStatus = status; await this.load() },
    async load(done) {
      this.expandedNotesId = ''
      const changed = this.generation !== currentSessionGeneration()
      const seq = ++this.requestSeq, generation = this.generation = currentSessionGeneration()
      if (changed) { this.lastReceipt = null; this.conflictReceipt = null; this.reviewSeq++; this.acting = false; this.batches = []; this.batchId = ''; this.batchIndex = 0 }
      this.list = null; this.total = 0; this.loadingMore = false
      this.state = 'loading'; this.page = 1; this.hasMore = false
      try {
        const context = useInternshipContextStore()
        context.restore()
        await context.load(true)
        if (this.hidden || seq !== this.requestSeq || generation !== currentSessionGeneration()) return
        if ((this.focusId && (!/^[1-9]\d*$/.test(this.focusId) || !this.requestedBatchId)) || (this.requestedBatchId && !/^[1-9]\d*$/.test(this.requestedBatchId))) throw new Error('待办定位信息不完整，请返回待办重新进入')
        if (this.requestedBatchId && !context.selectBatch(this.requestedBatchId)) throw new Error('当前身份无权处理该待办所属批次，请返回待办刷新核对')
        this.batches = context.batches || []
        if (String(this.batchId) !== String(context.selectedBatchId || '')) { this.lastReceipt = null; this.conflictReceipt = null }
        this.batchId = context.selectedBatchId || ''
        this.batchIndex = Math.max(0, this.batches.findIndex((b) => String(b.id) === String(this.batchId)))
        if (!this.batchId) { this.list = []; this.state = 'ready'; return }
        const batchId = this.batchId, status = this.reviewStatus
        const data = await teacherInternshipChanges(batchId, 1, 20, status, this.focusId)
        if (!this.current(seq, generation, batchId, status)) return
        this.list = (data && (data.items || data.list)) || []
        this.total = Number(data?.total ?? this.list.length)
        this.hasMore = !!data?.hasMore
        this.state = 'ready'
      } catch (e) {
        if (!this.current(seq, generation)) return
        this.list = []; this.state = 'error'
      } finally { if (typeof done === 'function') done() }
    },
    async onBatch(e) {
      if (this.acting) return
      this.focusId = ''; this.requestedBatchId = ''
      this.batchIndex = Number(e.detail.value)
      const context = useInternshipContextStore()
      context.selectBatch(this.batches[this.batchIndex]?.id)
      this.batchId = context.selectedBatchId
      this.conflictReceipt = null
      this.lastReceipt = null
      await this.load()
    },
    async loadMore() {
      if (!this.batchId || !this.hasMore || this.loadingMore || this.state !== 'ready') return
      const selected = this.batchId
      const seq = this.requestSeq, generation = currentSessionGeneration(), status = this.reviewStatus
      this.loadingMore = true
      try {
        const next = this.page + 1
        const data = await teacherInternshipChanges(selected, next, 20, status, this.focusId)
        if (!this.current(seq, generation, selected, status)) return
        this.list = [...(this.list || []), ...(data?.items || [])]
        this.page = next; this.hasMore = !!data?.hasMore
      } catch (e) { if (this.current(seq, generation, selected, status)) toast('后续变更读取失败，已加载申请保留') }
      finally { if (this.current(seq, generation, selected, status)) this.loadingMore = false }
    },
    review(c, action, initialComment = '') {
      if (!this.canReview || this.acting || this.state !== 'ready' || c.status !== 'PENDING') return
      const seq = this.requestSeq, generation = currentSessionGeneration(), batchId = this.batchId, status = this.reviewStatus
      const snapshot = { ...c }
      const operation = ++this.reviewSeq
      const release = () => { if (operation === this.reviewSeq) this.acting = false }
      const draft = { id: c.id, batchId, action, studentName: c.studentName || '当前学生' }
      const reject = action === 'REJECT'
      this.acting = true
      uni.showModal({
        title: reject ? '驳回变更' : '通过变更', editable: true,
        placeholderText: reject ? '请填写驳回原因（至少 5 字）' : '可填写审核意见',
        content: initialComment || (this.conflictReceipt?.id === c.id && this.conflictReceipt.batchId === batchId && this.conflictReceipt.action === action ? this.conflictReceipt.comment : '') || '',
        success: async (result) => {
          if (!result.confirm) { release(); return }
          const comment = (result.content || '').trim()
          if (operation !== this.reviewSeq || !this.current(seq, generation, batchId, status)) { release(); return }
          if (reject && comment.length < 5) { release(); this.conflictReceipt = { ...draft, message: '驳回原因至少 5 个字，请补充后重新确认', comment }; return }
          this.acting = true; this.conflictReceipt = null
          try {
            const receipt = await teacherInternshipChangeReview(snapshot.id, batchId, {
              action, comment, expectedVersion: snapshot.version,
              recordExpectedVersion: snapshot.recordVersionSnapshot
            })
            if (!this.current(seq, generation, batchId, status)) return
            this.lastReceipt = {
              actionLabel: reject ? '变更申请已驳回' : '变更审批已通过',
              objectLabel: `${c.studentName} · ${c.changeTypeLabel}`,
              statusLabel: receipt.statusLabel || (reject ? '已驳回' : '已通过'), version: receipt.version,
              recordStatusLabel: receipt.recordStatusLabel || c.recordStatusLabel,
              nextStep: receipt.nextStep || '继续处理下一条申请'
            }
            toast(reject ? '已驳回并留下回执' : '已通过并进入重新上岗流程')
            await this.load()
          } catch (e) {
            if (!this.current(seq, generation, batchId, status)) return
            if (conflictCode(e)) {
              const message = (e && e.message) || '申请或学生主记录版本已变化'
              await this.load()
              if (operation !== this.reviewSeq || this.hidden || generation !== currentSessionGeneration() || String(batchId) !== String(this.batchId) || status !== this.reviewStatus) return
              this.conflictReceipt = { ...draft, message, comment }
              toast('已刷新最新状态，你的意见仍保留')
            } else { this.conflictReceipt = { ...draft, message: '审核未完成，请重新核对后提交，意见已保留', comment }; toast('审核失败，意见已保留') }
          } finally { release() }
        },
        fail: release
      })
    }
  }
}
</script>

<style scoped>
.tc__count-unit{font-size:var(--font-size-sm);font-weight:400;color:var(--text-secondary)}.tc__route-label{font-size:10px!important;color:var(--text-tertiary)!important}
.tc__context,.tc__list{display:flex;flex-direction:column;gap:var(--space-3)}.tc__batch{display:flex;align-items:center;justify-content:space-between;gap:var(--space-3);padding:var(--space-3)}.tc__batch>view{min-width:0;display:flex;flex-direction:column;gap:3px}.tc__eyebrow{font-size:var(--font-size-xs);color:var(--text-tertiary)}.tc__batch-name{font-size:var(--font-size-md);font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.tc__picker{color:var(--teacher-700);font-size:var(--font-size-sm)}.tc__receipt,.tc__conflict{display:flex;flex-direction:column;gap:6px;padding:var(--space-3);font-size:var(--font-size-xs);line-height:1.5}.tc__receipt{border-color:var(--success-300,#86efac);background:var(--success-50,#f0fdf4)}.tc__conflict{border-color:var(--warning-300,#fcd34d);background:var(--warning-50,#fffbeb)}.tc__summary{display:flex;align-items:center;justify-content:space-between;gap:var(--space-3);padding:var(--space-3)}.tc__summary>view{display:flex;flex-direction:column;gap:3px}.tc__count{font-size:32px;font-weight:700;color:var(--teacher-700)}.tc__count small{font-size:var(--font-size-sm);font-weight:400;color:var(--text-secondary)}.tc__summary-note{max-width:65%;font-size:var(--font-size-xs);line-height:1.55;color:var(--text-secondary)}.tc{display:flex;flex-direction:column;gap:var(--space-3);padding:var(--space-3)}.tc__head{align-items:flex-start}.tc__sub{display:block;margin-top:3px;font-size:var(--font-size-xs);color:var(--text-tertiary)}.tc__type{display:flex;justify-content:space-between;gap:10px;padding:8px 10px;border-radius:var(--radius-md);background:var(--teacher-50,#eff6ff);font-size:var(--font-size-xs)}.tc__type text:first-child{font-weight:700;color:var(--teacher-700)}.tc__route{display:grid;grid-template-columns:1fr auto 1fr;align-items:stretch;gap:8px}.tc__route>view{display:flex;min-width:0;flex-direction:column;gap:5px;padding:10px;border:1px solid var(--border-light);border-radius:var(--radius-md);background:var(--gray-50)}.tc__route .is-target{border-color:var(--teacher-200,#bfdbfe);background:var(--teacher-50,#eff6ff)}.tc__route small{font-size:10px;color:var(--text-tertiary)}.tc__route b,.tc__route text{font-size:var(--font-size-xs);line-height:1.45;word-break:break-word}.tc__arrow{align-self:center;color:var(--teacher-600);font-size:20px}.tc__reason{display:flex;flex-direction:column;gap:5px;padding:9px 11px;border-radius:var(--radius-md);background:var(--gray-50);font-size:var(--font-size-xs);line-height:1.55}.tc__reason text:first-child,.tc__impact-title{font-weight:700;color:var(--text-secondary)}.tc__impact{display:flex;flex-direction:column;gap:7px;padding:10px 11px;border-radius:var(--radius-md);background:var(--warning-50,#fffbeb)}.tc__impact>view{display:grid;grid-template-columns:64px 1fr;gap:7px;font-size:var(--font-size-xs);line-height:1.5}.tc__impact>view text{color:var(--text-secondary)}.tc__actions{display:flex;gap:var(--space-2)}.tc__reject,.tc__approve{min-height:var(--touch-target-min);border-radius:var(--radius-md);font-size:var(--font-size-md)}.tc__reject{border:1px solid var(--danger-500);background:var(--bg-card);color:var(--danger-600)}.tc__approve{border:none;background:var(--teacher-600);color:#fff}.tc__reject::after,.tc__approve::after{border:none}.tc__more{text-align:center;color:var(--text-tertiary);font-size:var(--font-size-xs)}@media(max-width:360px){.tc__summary{align-items:flex-start;flex-direction:column}.tc__summary-note{max-width:none}.tc__route{grid-template-columns:1fr}.tc__arrow{transform:rotate(90deg)}}
.teacher-changes .tc__context,.teacher-changes .tc__list{width:100%;max-width:760px;margin:0 auto;box-sizing:border-box}.teacher-changes .card{border-radius:8px;box-shadow:none}.teacher-changes button,.tc__picker{min-height:44px;font-size:15px}.tc__batch{padding:4px 0 12px;border-bottom:1px solid var(--border-light)}.tc__batch-name{font-size:15px;line-height:22px;margin-top:0;overflow-wrap:anywhere}.tc__picker{display:flex;align-items:center;white-space:nowrap}.tc__sub,.tc__type,.tc__route-label,.tc__reason,.tc__impact,.tc__summary,.tc__receipt,.tc__conflict{font-size:14px;line-height:22px}.tc__type{flex-wrap:wrap}.tc__impact-title{font-size:15px}.tc__summary{padding:0;background:transparent}.tc__count{font-size:24px}
</style>
