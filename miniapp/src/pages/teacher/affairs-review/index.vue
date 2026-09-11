<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" :title="title" subtitle="核对申请材料，及时处理待办" show-back />
    <view v-if="(isAid || isAidObjection || isFunding || isFundingAppeal) && focusId" class="ar__search"><button :disabled="acting" @click="returnToQueue">查看全部待办</button><button :disabled="acting || state === 'loading'" @click="load">{{ state === 'loading' ? '正在刷新…' : '刷新进度' }}</button></view>
    <view v-if="(isAid || isFunding) && !focusId" class="ar__search">
      <input v-model="keyword" confirm-type="search" placeholder="搜索学生姓名或学号" maxlength="100" @confirm="load" />
      <button :disabled="acting" @click="load">搜索</button>
    </view>
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad">
        <view v-if="(isAid || isAidObjection || isFunding || isFundingAppeal) && !focusId" class="ar__queue-head"><text>{{ title }}</text><text>共 {{ total }} 件</text></view>
        <MobileGlobalState v-if="!list.length" state="empty" :title="'暂无' + title" description="有待办时会显示在这里；处理权限与 PC 学工工作台一致。" />
        <view class="stack" v-else>
          <view v-for="x in list" :key="rowKey(x)" class="card ar">
            <view class="row-between">
              <view class="flex-1"><text class="t-md t-bold">{{ x.realName || x.studentName || '—' }}</text><text class="ar__sub">{{ x.studentNo || '' }} · {{ nodeText(x) }}</text></view>
              <MobileStatusTag :label="nodeText(x)" type="warning" />
            </view>
            <view class="ar__row" v-if="!focusId && summary(x)"><text class="ar__k">摘要</text><text class="flex-1 t-sm">{{ summary(x) }}</text></view>
            <view class="ar__row" v-if="!focusId && nodeText(x)"><text class="ar__k">流程节点</text><text class="flex-1 t-sm">{{ nodeText(x) }}</text></view>
            <view class="ar__row" v-if="x.progressHint"><text class="ar__k">办理进度</text><text class="flex-1 t-sm">{{ x.progressHint }}</text></view>
            <view class="ar__row" v-if="!focusId && recommendedActionText(x)"><text class="ar__k">建议动作</text><text class="flex-1 t-sm">{{ recommendedActionText(x) }}</text></view>
            <view class="ar__row" v-if="x.reason && expandedId !== rowKey(x)"><text class="ar__k">理由</text><text class="flex-1 t-sm">{{ x.reason }}</text></view>
            <view class="ar__row" v-if="x.riskLevel"><text class="ar__k">等级</text><text class="flex-1 t-sm">{{ riskLevelText(x.riskLevel) }}</text></view>
            <MobileInlineAlert v-if="!hasVersion(x)" type="warning" title="记录缺少版本号" description="当前记录不能处理，请刷新后重试。" />

            <view class="ar__detail" v-if="expandedId === rowKey(x)">
              <view v-if="detailLoading === rowKey(x)" class="ar__muted">加载详情…</view>
              <view v-else-if="detailMap[rowKey(x)]"><view class="ar__row" v-for="line in detailLines(detailMap[rowKey(x)])" :key="line.k"><text class="ar__k">{{ line.k }}</text><text class="flex-1 t-sm">{{ line.v }}</text></view></view>
              <view v-else class="ar__muted">暂无更多明细</view>
            </view>
            <button v-if="meta.detail || isAppeal" class="btn btn-ghost ar__detail-btn" :disabled="acting" @click="toggleDetail(x)">{{ expandedId === rowKey(x) ? '收起详情' : '查看处理依据' }}</button>
            <MobileFundingEvidence audience="teacher" v-if="kind === 'FUNDING_APPROVAL' && expandedId === rowKey(x) && detailMap[rowKey(x)]" :application-id="String(rowKey(x))" />
            <view v-if="isFunding && expandedId === rowKey(x) && detailMap[rowKey(x)] && (x.status === 'GRANTED' || detailMap[rowKey(x)].disbursements?.length)" class="ar__history">
              <text class="t-md t-bold">发放登记</text>
              <text class="ar__muted">登记结果与学生端同步，实际到账请核对收款；需要登记或更正时由经办老师在 PC 发放台账办理。</text>
              <text v-if="!detailMap[rowKey(x)].disbursements?.length" class="ar__muted">已获资助，学校尚未生成发放记录。</text>
              <view v-for="payment in detailMap[rowKey(x)].disbursements || []" :key="payment.disbursementId" class="ar__event">
                <view class="row-between"><text class="t-bold">{{ payment.statusLabel }}</text><text>{{ paymentAmount(payment.amount) }}</text></view>
                <text v-if="payment.issuedAt" class="ar__sub">登记时间 {{ historyTime(payment.issuedAt) }}</text>
                <text v-if="payment.failReason" class="ar__event-note">{{ payment.failReason }}</text>
              </view>
            </view>
            <template v-if="isAid && expandedId === rowKey(x) && detailMap[rowKey(x)]">
              <button class="btn btn-ghost" @click="openAidMaterials(x)">材料查看与验收</button>
              <view class="ar__history"><text class="t-md t-bold">办理记录</text><text v-if="!detailMap[rowKey(x)].history?.length" class="ar__muted">暂无可核验的历史记录。</text><view v-for="item in detailMap[rowKey(x)].history || []" :key="item.id" class="ar__event"><text class="t-bold">{{ item.title }}</text><text class="ar__sub">{{ historyTime(item.occurredAt) }} · {{ item.operator || '系统' }}</text><text v-if="item.description" class="ar__event-note">{{ item.description }}</text></view></view>
            </template>

            <view class="ar__actions" v-if="kind === 'RISK_HANDLE'">
              <button v-if="canAction(x, 'PROCESS')" class="btn btn-ghost flex-1" :disabled="acting || !hasVersion(x)" @click="doRiskProcess(x)">填写处置</button>
              <button v-if="canAction(x, 'CLOSE')" class="ar__ok flex-1" :disabled="acting || !hasVersion(x)" @click="doRiskClose(x)">关闭</button>
            </view>
            <view class="ar__actions ar__appeal-actions" v-else-if="isAppeal && visibleAppealActions(x).length">
              <button v-for="a in visibleAppealActions(x)" :key="a.value" class="btn flex-1" :class="a.danger ? 'ar__no' : (a.primary ? 'ar__ok' : 'btn-ghost')" :disabled="acting || !hasVersion(x)" @click="reviewAppeal(x, a)">{{ a.label }}</button>
            </view>
            <view class="ar__actions" v-else-if="availableReviewActions(x).length">
              <button v-if="canAction(x, 'REJECT')" class="ar__no flex-1" :disabled="acting || !hasVersion(x)" @click="doReview(x, 'REJECT')">驳回</button>
              <button v-if="kind !== 'AID_ADJUST' && canAction(x, 'RETURN')" class="btn btn-ghost flex-1" :disabled="acting || !hasVersion(x)" @click="doReview(x, 'RETURN')">退回</button>
              <button v-if="canAction(x, 'APPROVE')" class="ar__ok flex-1" :disabled="acting || !hasVersion(x)" @click="doReview(x, 'APPROVE')">{{ kind === 'AID_ADJUST' ? '调整通过' : '审核通过' }}</button>
            </view>
            <text v-else class="ar__muted">当前节点暂无可执行动作</text>
          </view>
        </view>
        <view v-if="(isAid || isAidObjection || isFunding || isFundingAppeal) && !focusId && list.length < total" class="ar__more">
          <text v-if="moreError" class="ar__muted">{{ moreError }}</text>
          <button class="btn btn-ghost" :disabled="loadingMore || acting" @click="loadMore">{{ loadingMore ? '正在加载…' : moreError ? '重试加载' : '加载更多待办' }}</button>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { affairsContractApi } from '@/services/affairsContractApi'
import { affairsAppealApi } from '@/services/affairsAppealApi'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

const META = {
  AID_APPROVAL: { title: '困难认定待审', load: 'getAffairsAidPending', detail: 'getAffairsAidDetail' },
  AID_ADJUST: { title: '困难等级调整', load: 'getAffairsAidPending', detail: 'getAffairsAidDetail' },
  FUNDING_APPROVAL: { title: '奖助待审', load: 'getAffairsFundingPending', detail: 'getAffairsFundingDetail' },
  DISCIPLINE_APPROVAL: { title: '处分待审', load: 'getAffairsDisciplinePending', detail: 'getAffairsDisciplineDetail' },
  DISCIPLINE_REMOVE: { title: '处分解除待审', load: 'getAffairsDisciplinePending', detail: 'getAffairsDisciplineDetail' },
  RISK_HANDLE: { title: '风险待处置', load: 'getAffairsRiskPending', detail: 'getAffairsRiskDetail' },
  AID_OBJECTION_REVIEW: { title: '困难认定异议复核', appealKind: 'AID_OBJECTION' },
  FUNDING_APPEAL_REVIEW: { title: '资助公示申诉复核', appealKind: 'FUNDING_APPEAL' },
  DISCIPLINE_APPEAL_REVIEW: { title: '处分申诉复核', appealKind: 'DISCIPLINE_APPEAL' },
  SECOND_CLASS_APPEAL_REVIEW: { title: '第二课堂积分申诉', appealKind: 'SECOND_CLASS_APPEAL' }
}
const APPEAL_ACTIONS = {
  AID_OBJECTION: [{ label: '异议不成立', value: 'OVERRULED' }, { label: '异议成立', value: 'SUSTAINED', danger: true }],
  FUNDING_APPEAL: [{ label: '不成立 · 维持公示', value: 'OVERRULED' }, { label: '成立 · 驳回申请', value: 'SUSTAINED', danger: true }],
  DISCIPLINE_APPEAL: [{ label: '维持', value: 'UPHELD' }, { label: '变更', value: 'REVISED', primary: true }, { label: '撤销', value: 'REVOKED', danger: true }],
  SECOND_CLASS_APPEAL: [{ label: '驳回', value: 'REJECT', danger: true }, { label: '通过', value: 'APPROVE', primary: true }]
}
const DISC_TYPES = [
  { label: '警告', value: 'WARNING' }, { label: '严重警告', value: 'SERIOUS_WARNING' },
  { label: '记过', value: 'DEMERIT' }, { label: '留校察看', value: 'PROBATION' },
  { label: '开除学籍', value: 'EXPEL' }
]
const HIGH_RISK_KINDS = new Set([
  'AID_APPROVAL', 'AID_ADJUST', 'FUNDING_APPROVAL', 'DISCIPLINE_APPROVAL',
  'DISCIPLINE_REMOVE', 'RISK_HANDLE', 'AID_OBJECTION_REVIEW',
  'FUNDING_APPEAL_REVIEW', 'DISCIPLINE_APPEAL_REVIEW', 'SECOND_CLASS_APPEAL_REVIEW'
])

export default {
  data() { return { kind: 'AID_APPROVAL', focusId: '', list: [], state: 'loading', acting: false, expandedId: '', detailMap: {}, detailLoading: '', keyword: '', appliedKeyword: '', page: 1, total: 0, loadingMore: false, moreError: '', requestSeq: 0 } },
  computed: {
    meta() { return META[this.kind] || { title: '学工待办' } }, title() { return this.focusId && this.isFunding ? '奖助申请办理' : this.isAid && this.focusId ? '困难认定办理' : this.meta.title },
    isAid() { return ['AID_APPROVAL', 'AID_ADJUST'].includes(this.kind) },
    isFunding() { return this.kind === 'FUNDING_APPROVAL' },
    isAidObjection() { return this.kind === 'AID_OBJECTION_REVIEW' },
    isFundingAppeal() { return this.kind === 'FUNDING_APPEAL_REVIEW' },
    isAppeal() { return !!this.meta.appealKind }, appealActions() { return APPEAL_ACTIONS[this.meta.appealKind] || [] }
  },
  onLoad(q) { this.kind = (q && q.type) || 'AID_APPROVAL'; this.focusId = (this.isAid || this.isAidObjection || this.isFunding || this.isFundingAppeal) ? String(q?.recordId || '') : ''; this.load() },
  methods: {
    historyTime(value) { return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '时间未记录' },
    paymentAmount(value) { return value == null || value === '' ? '金额尚未登记' : /^\d+(\.\d+)?$/.test(String(value)) ? `¥${Number(value).toFixed(2)}` : '金额按权限隐藏' },
    openAidMaterials(row) { uni.navigateTo({ url: '/pages/teacher/affairs/index?bizType=AID&bizId=' + encodeURIComponent(row.applyId) }) },
    rowKey(x) { return String(x.objectionId || x.appealId || x.applyId || x.applicationId || x.caseId || x.riskId || x.id || '') },
    summary(x) { return x.title || x.topic || x.statement || x.applyLevelLabel || x.claimCreditType || x.discTypeLabel || '' },
    nodeText(x) {
      const value = x.status
      return x.statusLabel || ({ PENDING: '待处理', PENDING_REVIEW: '待审核', PROCESSING: '处理中', APPROVED: '已通过', RETURNED: '已退回', REJECTED: '已驳回', CLOSED: '已关闭' })[value] || (value ? `状态待确认（${value}）` : '待处理')
    },
    riskLevelText(value) {
      return ({ LOW: '低风险', MEDIUM: '中风险', HIGH: '高风险', CRITICAL: '重大风险' })[value] || (value && /[一-鿿]/.test(value) ? value : value ? `等级待确认（${value}）` : '等级待确认')
    },
    actionLabel(action) {
      if (action === 'APPROVE') return '通过'
      if (action === 'RETURN') return '退回'
      if (action === 'REJECT') return '驳回'
      if (action === 'PROCESS') return '填写处置'
      if (action === 'CLOSE') return '关闭'
      return action
    },
    recommendedActionText(x) {
      const next = []
      if (this.kind === 'RISK_HANDLE') {
        if (this.canAction(x, 'PROCESS')) next.push('填写处置')
        if (this.canAction(x, 'CLOSE')) next.push('关闭')
      } else if (this.isAppeal) {
        this.visibleAppealActions(x).forEach((action) => { if (action.label) next.push(action.label) })
      } else {
        this.availableReviewActions(x).forEach((action) => next.push(this.actionLabel(action)))
      }
      if (!next.length) return '当前节点暂无可执行动作'
      if (next.length === 1) return next[0]
      return next.join(' / ')
    },
    hasVersion(x) { return x && x.version !== undefined && x.version !== null && x.version !== '' },
    fallbackActions() {
      if (HIGH_RISK_KINDS.has(this.kind)) return []
      return ['APPROVE', 'RETURN', 'REJECT']
    },
    canAction(x, action) {
      const list = Array.isArray(x.allowedActions) ? x.allowedActions : this.fallbackActions()
      if (this.kind === 'DISCIPLINE_REMOVE' && ['APPROVE', 'REJECT'].includes(action)) {
        return list.includes(`REMOVE_${action}`)
      }
      return list.includes(action)
    },
    visibleAppealActions(x) {
      if (!Array.isArray(x && x.allowedActions)) return []
      if (x.allowedActions.includes('REVIEW')) return this.appealActions
      return this.appealActions.filter((action) => x.allowedActions.includes(action.value))
    },
    availableReviewActions(x) { return ['APPROVE', 'RETURN', 'REJECT'].filter((a) => this.canAction(x, a)) },
    load() {
      return (this.isAid || this.isAidObjection || this.isFunding || this.isFundingAppeal) && this.focusId ? this.loadFocusedAid() : this.loadQueue(false)
    },
    returnToQueue() { this.focusId = ''; this.keyword = ''; return this.load() },
    loadFocusedAid() {
      const requestId = ++this.requestSeq
      this.state = 'loading'; this.detailMap = {}; this.expandedId = ''; this.loadingMore = false
      const request = this.isFundingAppeal ? affairsAppealApi.getFundingAppealDetail(this.focusId) : this.isFunding ? teacherApi.getAffairsFundingDetail(this.focusId) : this.isAidObjection ? affairsAppealApi.getAidObjectionDetail(this.focusId) : teacherApi.getAffairsAidDetail(this.focusId)
      return request.then(detail => {
        if (requestId !== this.requestSeq) return
        if (!detail || this.rowKey(detail) !== this.focusId) throw new Error('该申请暂不可查看，请返回待办列表核对')
        if (detail.status === 'ADJUST_REVIEW') this.kind = 'AID_ADJUST'
        this.list = [detail]; this.total = 1; this.page = 1
        this.detailMap = { [this.focusId]: detail }; this.expandedId = this.focusId; this.state = 'ready'
      }).catch(error => {
        if (requestId !== this.requestSeq) return
        this.list = []; this.total = 0; this.state = 'error'; this._err(error, '申请加载')
      })
    },
    loadMore() {
      if (this.state === 'loading' || this.loadingMore || this.list.length >= this.total) return
      return this.loadQueue(true)
    },
    loadQueue(append) {
      const requestId = ++this.requestSeq
      const page = append ? this.page + 1 : 1
      if (append) this.loadingMore = true
      else { this.state = 'loading'; this.expandedId = ''; this.detailMap = {}; this.appliedKeyword = this.keyword.trim() }
      this.moreError = ''
      const params = (this.isAid || this.isFunding) ? { page, pageSize: 20, ...(this.isAid ? { kind: this.kind } : {}), keyword: this.appliedKeyword } : undefined
      const task = this.isAppeal ? affairsAppealApi.getPending(this.meta.appealKind, (this.isAidObjection || this.isFundingAppeal) ? { page, pageSize: 20 } : {}) : (this.meta.load && teacherApi[this.meta.load] ? teacherApi[this.meta.load](params) : Promise.reject(new Error('未配置待办接口')))
      return task.then((d) => {
        if (requestId !== this.requestSeq) return
        let rows = (d && (d.items || d.list)) || []
        if (this.kind === 'DISCIPLINE_REMOVE') rows = rows.filter((x) => x.status === 'REMOVE_REVIEW')
        if (this.kind === 'DISCIPLINE_APPROVAL') rows = rows.filter((x) => x.status !== 'REMOVE_REVIEW')
        const previous = new Set(append ? this.list.map(this.rowKey) : [])
        this.list = append ? [...this.list, ...rows.filter(row => !previous.has(this.rowKey(row)))] : rows
        this.page = page; this.total = Number(d?.total ?? rows.length); this.state = 'ready'
      }).catch((e) => {
        if (requestId !== this.requestSeq) return
        if (append) this.moreError = '后续待办暂未加载，已显示的记录仍保留。'
        else this.state = 'error'
        this._err(e, '加载')
      }).finally(() => { if (requestId === this.requestSeq) this.loadingMore = false })
    },
    detailLines(d) {
      const pairs = [
        ['资助类型', this.isFunding ? ({ SCHOLARSHIP: '奖学金', GRANT: '助学金' }[d.projectType] || '类型待确认') : ''],
        ['标准金额（元）', this.isFunding ? (d.requestedAmount ?? d.amount) : ''],
        ['批准金额（元）', this.isFunding ? d.approvedAmount : ''],
        ['原申请编号', this.isFundingAppeal ? d.applicationId : ''],
        ['申诉人', this.isFundingAppeal ? (d.appellantName || '匿名') : ''],
        ['事由', d.reason || d.statement || d.applyReason || d.topic || d.title],
        [d.applyLevelLabel ? '申请等级' : '当前等级', d.applyLevelLabel || d.level || d.riskLevel || d.discTypeLabel || d.discType],
        ['认定等级', d.finalLevel ? d.finalLevelLabel : ''],
        ['公示截止', d.publicityEnd ? this.historyTime(d.publicityEnd) : ''],
        ['公示进度', d.status === 'PUBLICITY' ? (d.hasPendingObjection ? '有异议待复核，暂不能确认认定结果' : d.publicityHint) : ''],
        ['申请调整', d.adjustment ? `${d.adjustment.fromLabel} → ${d.adjustment.targetLabel}（待审核）` : ''],
        ['调整原因', d.adjustment?.reason],
        ['主张类型', d.claimCreditType], ['主张数值', d.claimValue], ['申诉类型', d.appealType],
        ['节点', this.nodeText(d)], ['退回原因', d.returnReason], ['复核结论', d.resultLabel], ['复核意见', d.reviewOpinion],
        ['说明', d.remark || d.note || d.content || d.description], ['学院', d.collegeName], ['班级', d.className],
        ['提交时间', (d.createdAt || d.submittedAt) ? this.historyTime(d.createdAt || d.submittedAt) : '']
      ]
      return pairs.filter(([, v]) => v !== undefined && v !== null && String(v).trim() !== '').map(([k, v]) => ({ k, v: String(v) }))
    },
    loadDetail(x) {
      const id = this.rowKey(x)
      if (!id) return Promise.resolve(x)
      if (this.detailMap[id]) return Promise.resolve({ ...x, ...this.detailMap[id] })
      if (this.isAppeal || !this.meta.detail || !teacherApi[this.meta.detail]) { this.detailMap = { ...this.detailMap, [id]: x }; return Promise.resolve(x) }
      this.detailLoading = id
      return teacherApi[this.meta.detail](id).then((d) => { this.detailMap = { ...this.detailMap, [id]: d || {} }; return { ...x, ...(d || {}) } }).finally(() => { this.detailLoading = '' })
    },
    toggleDetail(x) {
      const id = this.rowKey(x); if (!id) return
      if (this.expandedId === id) { this.expandedId = ''; return }
      this.expandedId = id; this.loadDetail(x).catch((e) => { this._err(e, '详情加载'); this.expandedId = '' })
    },
    _err(e, label) { const n = normalizeError(e); toast(n.text || (e && e.message) || label + '失败'); if (n.kind === 'conflict') this.load(); return n },
    versionOf(entity) { const value = entity && entity.version; if (value === undefined || value === null || value === '') { toast('记录缺少版本号，请刷新后再处理'); this.load(); return null }; return value },
    visibleVersion(row, detail) {
      const visible = this.versionOf(row); if (visible === null) throw new Error('缺少版本号')
      const latest = detail && detail.version
      if (latest !== undefined && latest !== null && latest !== '' && String(latest) !== String(visible)) { toast('记录已被他人修改，请刷新后重新查看并确认'); this.load(); const error = new Error('记录版本已变化'); error.kind = 'conflict'; throw error }
      return visible
    },
    reviewRequest(id, action, reason, row, detail, selectedLevel = '') {
      const version = this.visibleVersion(row, detail)
      const level = selectedLevel || (detail && (detail.suggestLevel || detail.applyLevel)) || row.suggestLevel || row.applyLevel
      if (['AID_APPROVAL', 'AID_ADJUST'].includes(this.kind)) return affairsContractApi.reviewAid(id, action, reason, level, version)
      if (this.kind === 'FUNDING_APPROVAL') return affairsContractApi.reviewFunding(id, action, reason, version)
      return affairsContractApi.reviewDiscipline(id, action, reason, version)
    },
    promptText({ title, initial = '', invalid, submit }) {
      uni.showModal({ title, editable: true, placeholderText: '不少于5字', content: initial, success: (r) => { if (!r.confirm) return; const value = (r.content || '').trim(); if (value.length < 5) return toast(invalid); submit(value) } })
    },
    promptOptionalText({ title, initial = '', placeholderText = '可留空', submit }) {
      uni.showModal({ title, editable: true, placeholderText, content: initial, success: (r) => { if (!r.confirm) return; submit((r.content || '').trim()) } })
    },
    doReview(x, action, previous = '') {
      const id = this.rowKey(x); if (!id || this.acting || !this.canAction(x, action)) return
      if (this.kind === 'AID_ADJUST' && action === 'APPROVE') return this.chooseAdjustLevel(x)
      const needReason = ['REJECT', 'RETURN'].includes(action)
      const run = (reason) => {
        this.acting = true
        this.loadDetail(x).then((detail) => this.reviewRequest(id, action, reason, x, detail)).then(() => { toast('已处理'); this.load() })
          .catch((e) => { const n = this._err(e, '审批'); if (n.kind !== 'conflict' && needReason) setTimeout(() => this.doReview(x, action, reason), 0) }).finally(() => { this.acting = false })
      }
      if (needReason) return this.promptText({ title: action === 'RETURN' ? '退回原因' : '驳回原因', initial: previous, invalid: '原因不少于5字', submit: run })
      uni.showModal({ title: '确认审批通过', content: `${x.realName || x.studentName || '该学生'}\n${this.summary(x) || '请先查看处理依据'}\n\n确认材料、节点和数据范围无误后再通过。`, confirmText: '确认通过', success: (r) => { if (r.confirm) run('') } })
    },
    chooseAdjustLevel(x) {
      if (this.acting) return
      this.acting = true
      return this.loadDetail(x).then((detail) => {
        this.visibleVersion(x, detail)
        const adjustment = detail.adjustment
        if (!adjustment || !this.canAction(detail, 'APPROVE')) throw new Error('当前调整不可审批，请刷新查看最新状态')
        return new Promise((resolve, reject) => uni.showModal({ title: '确认困难等级调整', content: `${detail.realName || '该学生'}\n${adjustment.fromLabel} → ${adjustment.targetLabel}\n\n${adjustment.reason || '请核对已提交的调整依据。'}\n\n通过后按上述申请目标更新认定等级。`, confirmText: '确认通过', success: (c) => {
          if (!c.confirm) { resolve(); return }
          this.reviewRequest(this.rowKey(x), 'APPROVE', '', x, detail, adjustment.targetLevel)
            .then(() => { toast('调整已通过'); return this.load() })
            .then(resolve, reject)
        }, fail: reject }))
      }).catch((e) => this._err(e, '调整审批')).finally(() => { this.acting = false })
    },
    reviewAppeal(x, action, previous = '', revisedDiscType = '', revisedReason = '', revisedDocNo = null) {
      const id = this.rowKey(x); const version = this.versionOf(x)
      if (!id || version === null || this.acting) return
      if (!this.visibleAppealActions(x).some((candidate) => candidate.value === action.value)) return
      if (this.meta.appealKind === 'DISCIPLINE_APPEAL' && action.value === 'REVISED') {
        if (!revisedDiscType) {
          const options = DISC_TYPES.filter((item) => item.value !== x.discType)
          uni.showActionSheet({ itemList: options.map((item) => item.label), success: (r) => {
            const selected = options[r.tapIndex]
            if (selected) this.reviewAppeal(x, action, previous, selected.value, revisedReason, revisedDocNo)
          } })
          return
        }
        if (!revisedReason) {
          this.promptText({
            title: '变更后的处分事实',
            initial: '',
            invalid: '变更后的处分事实至少5字',
            submit: (value) => this.reviewAppeal(x, action, previous, revisedDiscType, value, revisedDocNo)
          })
          return
        }
        if (revisedDocNo === null) {
          this.promptOptionalText({
            title: '变更后的文号',
            placeholderText: '可留空；留空表示新决定无文号',
            submit: (value) => this.reviewAppeal(x, action, previous, revisedDiscType, revisedReason, value)
          })
          return
        }
      }
      this.promptText({ title: action.label, initial: previous, invalid: '复核意见至少5字', submit: (opinion) => {
        const payload = this.meta.appealKind === 'SECOND_CLASS_APPEAL'
          ? { action: action.value, opinion, version }
          : {
              result: action.value,
              opinion,
              version,
              ...(revisedDiscType ? { revisedDiscType, revisedReason, revisedDocNo: revisedDocNo || '' } : {})
            }
        this.acting = true
        affairsAppealApi.review(this.meta.appealKind, id, payload).then(() => { toast('复核完成'); this.load() })
          .catch((e) => {
            const n = this._err(e, '复核')
            if (n.kind !== 'conflict') setTimeout(() => this.reviewAppeal(x, action, opinion, revisedDiscType, revisedReason, revisedDocNo), 0)
          }).finally(() => { this.acting = false })
      } })
    },
    doRiskProcess(x, previous = '') {
      if (!this.canAction(x, 'PROCESS')) return
      const id = x.riskId || x.id
      this.promptText({ title: '处置内容', initial: previous, invalid: '处置内容不少于5字', submit: (content) => {
        this.acting = true
        this.loadDetail(x).then((detail) => affairsContractApi.processRisk(id, content, this.visibleVersion(x, detail))).then(() => { toast('已记录'); this.load() })
          .catch((e) => { const n = this._err(e, '处置'); if (n.kind !== 'conflict') setTimeout(() => this.doRiskProcess(x, content), 0) }).finally(() => { this.acting = false })
      } })
    },
    doRiskClose(x, previous = '') {
      if (!this.canAction(x, 'CLOSE')) return
      const id = x.riskId || x.id
      this.promptText({ title: '关闭结论', initial: previous, invalid: '关闭结论不少于5字', submit: (conclusion) => {
        uni.showModal({ title: '确认关闭风险', content: `关闭结论：${conclusion}\n\n确认已完成必要处置并具备关闭依据。`, confirmText: '确认关闭', success: (r) => {
          if (!r.confirm) return
          this.acting = true
          this.loadDetail(x).then((detail) => affairsContractApi.closeRisk(id, conclusion, this.visibleVersion(x, detail))).then(() => { toast('已关闭'); this.load() })
            .catch((e) => { const n = this._err(e, '关闭'); if (n.kind !== 'conflict') setTimeout(() => this.doRiskClose(x, conclusion), 0) }).finally(() => { this.acting = false })
        } })
      } })
    }
  }
}
</script>

<style scoped>
.ar__history { margin-top: 20px; }.ar__event { padding: 8px 0 18px 16px; margin: 12px 0 0 4px; border-left: 2px solid var(--brand-primary); }.ar__event-note { display: block; font-size: 14px; line-height: 1.7; margin-top: 6px; white-space: pre-wrap; }
.ar__search { display: flex; align-items: center; gap: 12px; padding: 12px 16px 0; }
.ar__search input { flex: 1; min-width: 0; height: 44px; padding: 0 14px; border-radius: 12px; background: var(--surface-card, #fff); color: var(--text-primary); font-size: 14px; }
.ar__search button { margin: 0; padding: 0 16px; height: 44px; line-height: 44px; border-radius: 12px; background: var(--brand-primary); color: #fff; font-size: 14px; }
.ar__queue-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding-bottom: 12px; color: var(--text-secondary); font-size: 13px; }
.ar__queue-head text:first-child { color: var(--text-primary); font-weight: 600; }
.ar__more { display: flex; flex-direction: column; align-items: center; gap: 12px; padding: 20px 0 calc(16px + env(safe-area-inset-bottom)); }
.ar__more button { min-height: 44px; min-width: 180px; }
.ar__actions button { display: flex; align-items: center; justify-content: center; min-width: 0; min-height: 44px; padding: 8px; font-size: 14px; line-height: 20px; white-space: nowrap; }
.ar { padding: var(--space-4); }.ar__sub { display: block; margin-top: 4px; color: var(--text-tertiary); font-size: 12px; }.ar__row { display: flex; gap: 8px; margin-top: 8px; }.ar__k { width: 80px; color: var(--text-tertiary); font-size: 12px; flex-shrink: 0; }.ar__detail { margin-top: 8px; padding: 8px; background: rgba(0,0,0,0.03); border-radius: 8px; }.ar__detail-btn { margin-top: 8px; font-size: 13px; }.ar__muted { display: block; color: var(--text-tertiary); font-size: 12px; margin-top: 8px; }.ar__actions { display: flex; gap: 8px; margin-top: 12px; }.ar__appeal-actions { flex-wrap: wrap; }.ar__ok { background: var(--brand-primary); color: #fff; border-radius: 8px; font-size: 14px; }.ar__no { background: #fee2e2; color: #b91c1c; border-radius: 8px; font-size: 14px; }
</style>
