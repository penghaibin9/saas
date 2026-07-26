<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" :title="title" subtitle="按数据范围、权限与具体受理人收敛" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad">
        <MobileGlobalState v-if="!list.length" state="empty" :title="'暂无' + title"
          description="有待办时会显示在这里；处理权限与 PC 学工工作台一致。" />
        <view class="stack" v-else>
          <view v-for="x in list" :key="rowKey(x)" class="card ar">
            <view class="row-between">
              <view class="flex-1">
                <text class="t-md t-bold">{{ x.realName || x.studentName || '—' }}</text>
                <text class="ar__sub">{{ x.studentNo || '' }} · {{ x.statusLabel || x.status || '' }}</text>
              </view>
              <MobileStatusTag :label="x.statusLabel || x.status || '待处理'" type="warning" />
            </view>
            <view class="ar__row" v-if="summary(x)">
              <text class="ar__k">摘要</text><text class="flex-1 t-sm">{{ summary(x) }}</text>
            </view>
            <view class="ar__row" v-if="x.reason">
              <text class="ar__k">理由</text><text class="flex-1 t-sm">{{ x.reason }}</text>
            </view>
            <view class="ar__row" v-if="x.riskLevel">
              <text class="ar__k">等级</text><text class="flex-1 t-sm">{{ x.riskLevel }}</text>
            </view>

            <view class="ar__detail" v-if="expandedId === rowKey(x)">
              <view v-if="detailLoading === rowKey(x)" class="ar__muted">加载详情…</view>
              <view v-else-if="detailMap[rowKey(x)]">
                <view class="ar__row" v-for="line in detailLines(detailMap[rowKey(x)])" :key="line.k">
                  <text class="ar__k">{{ line.k }}</text><text class="flex-1 t-sm">{{ line.v }}</text>
                </view>
              </view>
              <view v-else class="ar__muted">暂无更多明细</view>
            </view>
            <button v-if="!isAppeal && meta.detail" class="btn btn-ghost ar__detail-btn" :disabled="acting" @click="toggleDetail(x)">
              {{ expandedId === rowKey(x) ? '收起详情' : '查看详情' }}
            </button>

            <view class="ar__actions" v-if="kind === 'RISK_HANDLE'">
              <button class="btn btn-ghost flex-1" :disabled="acting" @click="doRiskProcess(x)">填写处置</button>
              <button class="ar__ok flex-1" :disabled="acting" @click="doRiskClose(x)">关闭</button>
            </view>
            <view class="ar__actions ar__appeal-actions" v-else-if="isAppeal">
              <button v-for="a in appealActions" :key="a.value" class="btn flex-1"
                :class="a.danger ? 'ar__no' : (a.primary ? 'ar__ok' : 'btn-ghost')"
                :disabled="acting" @click="reviewAppeal(x, a)">{{ a.label }}</button>
            </view>
            <view class="ar__actions" v-else>
              <button class="ar__no flex-1" :disabled="acting" @click="doReview(x, 'REJECT')">驳回</button>
              <button v-if="kind !== 'AID_ADJUST'" class="btn btn-ghost flex-1" :disabled="acting" @click="doReview(x, 'RETURN')">退回</button>
              <button class="ar__ok flex-1" :disabled="acting" @click="doReview(x, 'APPROVE')">通过</button>
            </view>
          </view>
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
  AID_OBJECTION: [
    { label: '异议不成立', value: 'OVERRULED' },
    { label: '异议成立', value: 'SUSTAINED', danger: true }
  ],
  FUNDING_APPEAL: [
    { label: '申诉不成立', value: 'OVERRULED' },
    { label: '申诉成立', value: 'SUSTAINED', danger: true }
  ],
  DISCIPLINE_APPEAL: [
    { label: '维持', value: 'UPHELD' },
    { label: '变更', value: 'REVISED', primary: true },
    { label: '撤销', value: 'REVOKED', danger: true }
  ],
  SECOND_CLASS_APPEAL: [
    { label: '驳回', value: 'REJECT', danger: true },
    { label: '通过', value: 'APPROVE', primary: true }
  ]
}

export default {
  data() {
    return { kind: 'AID_APPROVAL', list: [], state: 'loading', acting: false, expandedId: '', detailMap: {}, detailLoading: '' }
  },
  computed: {
    meta() { return META[this.kind] || { title: '学工待办' } },
    title() { return this.meta.title },
    isAppeal() { return !!this.meta.appealKind },
    appealActions() { return APPEAL_ACTIONS[this.meta.appealKind] || [] }
  },
  onLoad(q) { this.kind = (q && q.type) || 'AID_APPROVAL'; this.load() },
  methods: {
    rowKey(x) { return String(x.objectionId || x.appealId || x.applyId || x.applicationId || x.caseId || x.riskId || x.id || '') },
    summary(x) { return x.title || x.topic || x.statement || x.applyLevel || x.claimCreditType || x.discTypeLabel || '' },
    load() {
      this.state = 'loading'; this.expandedId = ''; this.detailMap = {}
      const task = this.isAppeal
        ? affairsAppealApi.getPending(this.meta.appealKind)
        : (this.meta.load && teacherApi[this.meta.load] ? teacherApi[this.meta.load]() : Promise.reject(new Error('未配置待办接口')))
      task.then((d) => {
        let rows = (d && (d.items || d.list)) || []
        if (this.kind === 'AID_ADJUST') rows = rows.filter((x) => x.status === 'ADJUST_REVIEW')
        if (this.kind === 'AID_APPROVAL') rows = rows.filter((x) => x.status !== 'ADJUST_REVIEW')
        if (this.kind === 'DISCIPLINE_REMOVE') rows = rows.filter((x) => x.status === 'REMOVE_REVIEW')
        if (this.kind === 'DISCIPLINE_APPROVAL') rows = rows.filter((x) => x.status !== 'REMOVE_REVIEW')
        this.list = rows; this.state = 'ready'
      }).catch((e) => { this.state = 'error'; this._err(e, '加载') })
    },
    detailLines(d) {
      const pairs = [
        ['事由', d.reason || d.statement || d.applyReason || d.topic || d.title],
        ['等级', d.applyLevel || d.suggestLevel || d.level || d.riskLevel || d.discTypeLabel || d.discType],
        ['节点', d.statusLabel || d.status], ['退回原因', d.returnReason],
        ['说明', d.remark || d.note || d.content || d.description], ['学院', d.collegeName], ['班级', d.className]
      ]
      return pairs.filter(([, v]) => v != null && String(v).trim() !== '').map(([k, v]) => ({ k, v: String(v) }))
    },
    loadDetail(x) {
      const id = this.rowKey(x)
      if (!id || !this.meta.detail || !teacherApi[this.meta.detail]) return Promise.resolve(x)
      if (this.detailMap[id]) return Promise.resolve({ ...x, ...this.detailMap[id] })
      this.detailLoading = id
      return teacherApi[this.meta.detail](id).then((d) => {
        this.detailMap = { ...this.detailMap, [id]: d || {} }
        return { ...x, ...(d || {}) }
      }).finally(() => { this.detailLoading = '' })
    },
    toggleDetail(x) {
      const id = this.rowKey(x)
      if (!id) return
      if (this.expandedId === id) { this.expandedId = ''; return }
      this.expandedId = id
      this.loadDetail(x).catch((e) => { this._err(e, '详情加载'); this.expandedId = '' })
    },
    _err(e, label) {
      const n = normalizeError(e)
      toast(n.text || (e && e.message) || label + '失败')
      if (n.kind === 'conflict') this.load()
    },
    versionOf(entity) {
      const value = entity && entity.version
      if (value === undefined || value === null || value === '') {
        toast('记录缺少版本号，请刷新后再处理'); this.load(); return null
      }
      return value
    },
    reviewRequest(id, action, reason, entity) {
      const version = this.versionOf(entity)
      if (version === null) return Promise.reject(new Error('缺少版本号'))
      if (['AID_APPROVAL', 'AID_ADJUST'].includes(this.kind)) return affairsContractApi.reviewAid(id, action, reason, entity.suggestLevel || entity.applyLevel, version)
      if (this.kind === 'FUNDING_APPROVAL') return affairsContractApi.reviewFunding(id, action, reason, version)
      return affairsContractApi.reviewDiscipline(id, action, reason, version)
    },
    doReview(x, action) {
      const id = this.rowKey(x); if (!id || this.acting) return
      const needReason = ['REJECT', 'RETURN'].includes(action)
      const run = (reason) => {
        if (needReason && reason.trim().length < 5) return toast('原因不少于5字')
        this.acting = true
        this.loadDetail(x).then((entity) => this.reviewRequest(id, action, reason, entity))
          .then(() => { toast('已处理'); this.load() }).catch((e) => this._err(e, '审批'))
          .finally(() => { this.acting = false })
      }
      if (needReason) uni.showModal({ title: action === 'RETURN' ? '退回原因' : '驳回原因', editable: true, placeholderText: '不少于5字', success: (r) => { if (r.confirm) run((r.content || '').trim()) } })
      else run('')
    },
    reviewAppeal(x, action) {
      const id = this.rowKey(x); const version = this.versionOf(x)
      if (!id || version === null || this.acting) return
      uni.showModal({
        title: action.label, editable: true, placeholderText: '填写复核意见（不少于5字）',
        success: (r) => {
          if (!r.confirm) return
          const opinion = (r.content || '').trim(); if (opinion.length < 5) return toast('复核意见至少5字')
          const payload = this.meta.appealKind === 'SECOND_CLASS_APPEAL'
            ? { action: action.value, opinion, version }
            : { result: action.value, opinion, version }
          this.acting = true
          affairsAppealApi.review(this.meta.appealKind, id, payload).then(() => { toast('复核完成'); this.load() })
            .catch((e) => this._err(e, '复核')).finally(() => { this.acting = false })
        }
      })
    },
    doRiskProcess(x) {
      const id = x.riskId || x.id
      uni.showModal({ title: '处置内容', editable: true, placeholderText: '不少于5字', success: (r) => {
        if (!r.confirm) return; const content = (r.content || '').trim(); if (content.length < 5) return toast('处置内容不少于5字')
        this.acting = true; this.loadDetail(x).then((entity) => {
          const version = this.versionOf(entity); if (version === null) throw new Error('缺少版本号')
          return affairsContractApi.processRisk(id, content, version)
        }).then(() => { toast('已记录'); this.load() }).catch((e) => this._err(e, '处置')).finally(() => { this.acting = false })
      } })
    },
    doRiskClose(x) {
      const id = x.riskId || x.id
      uni.showModal({ title: '关闭结论', editable: true, placeholderText: '不少于5字', success: (r) => {
        if (!r.confirm) return; const conclusion = (r.content || '').trim(); if (conclusion.length < 5) return toast('关闭结论不少于5字')
        this.acting = true; this.loadDetail(x).then((entity) => {
          const version = this.versionOf(entity); if (version === null) throw new Error('缺少版本号')
          return affairsContractApi.closeRisk(id, conclusion, version)
        }).then(() => { toast('已关闭'); this.load() }).catch((e) => this._err(e, '关闭')).finally(() => { this.acting = false })
      } })
    }
  }
}
</script>

<style scoped>
.ar { padding: var(--space-4); }
.ar__sub { display: block; margin-top: 4px; color: var(--text-tertiary); font-size: 12px; }
.ar__row { display: flex; gap: 8px; margin-top: 8px; }
.ar__k { width: 56px; color: var(--text-tertiary); font-size: 12px; flex-shrink: 0; }
.ar__detail { margin-top: 8px; padding: 8px; background: rgba(0,0,0,0.03); border-radius: 8px; }
.ar__detail-btn { margin-top: 8px; font-size: 13px; }
.ar__muted { color: var(--text-tertiary); font-size: 12px; }
.ar__actions { display: flex; gap: 8px; margin-top: 12px; }
.ar__appeal-actions { flex-wrap: wrap; }
.ar__ok { background: var(--brand-primary); color: #fff; border-radius: 8px; font-size: 14px; }
.ar__no { background: #fee2e2; color: #b91c1c; border-radius: 8px; font-size: 14px; }
</style>
