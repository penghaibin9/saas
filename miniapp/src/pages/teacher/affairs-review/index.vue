<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" :title="title" subtitle="按数据范围、权限与指派人收敛" show-back />
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
            <view class="ar__row" v-if="x.title || x.topic || x.applyLevel">
              <text class="ar__k">摘要</text>
              <text class="flex-1 t-sm">{{ x.title || x.topic || ('申请等级 ' + (x.applyLevel || '')) }}</text>
            </view>
            <view class="ar__row" v-if="x.riskLevel">
              <text class="ar__k">等级</text>
              <text class="flex-1 t-sm">{{ x.riskLevel }}</text>
            </view>

            <view class="ar__detail" v-if="expandedId === rowKey(x)">
              <view v-if="detailLoading === rowKey(x)" class="ar__muted">加载详情…</view>
              <view v-else-if="detailMap[rowKey(x)]">
                <view class="ar__row" v-for="line in detailLines(detailMap[rowKey(x)])" :key="line.k">
                  <text class="ar__k">{{ line.k }}</text>
                  <text class="flex-1 t-sm">{{ line.v }}</text>
                </view>
              </view>
              <view v-else class="ar__muted">暂无更多明细</view>
            </view>
            <button class="btn btn-ghost ar__detail-btn" :disabled="acting" @click="toggleDetail(x)">
              {{ expandedId === rowKey(x) ? '收起详情' : '查看详情' }}
            </button>

            <view class="ar__actions" v-if="kind === 'RISK_HANDLE'">
              <button class="btn btn-ghost flex-1" :disabled="acting" @click="doRiskProcess(x)">填写处置</button>
              <button class="ar__ok flex-1" :disabled="acting" @click="doRiskClose(x)">关闭</button>
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
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

const META = {
  AID_APPROVAL: { title: '困难认定待审', load: 'getAffairsAidPending', detail: 'getAffairsAidDetail' },
  AID_ADJUST: { title: '困难等级调整', load: 'getAffairsAidPending', detail: 'getAffairsAidDetail' },
  FUNDING_APPROVAL: { title: '奖助待审', load: 'getAffairsFundingPending', detail: 'getAffairsFundingDetail' },
  DISCIPLINE_APPROVAL: { title: '处分待审', load: 'getAffairsDisciplinePending', detail: 'getAffairsDisciplineDetail' },
  DISCIPLINE_REMOVE: { title: '处分解除待审', load: 'getAffairsDisciplinePending', detail: 'getAffairsDisciplineDetail' },
  RISK_HANDLE: { title: '风险待处置', load: 'getAffairsRiskPending', detail: 'getAffairsRiskDetail' }
}
const ACTION_LABEL = { APPROVE: '已通过', REJECT: '已驳回', RETURN: '已退回' }

export default {
  data() {
    return {
      kind: 'AID_APPROVAL', list: [], state: 'loading', acting: false,
      expandedId: '', detailMap: {}, detailLoading: ''
    }
  },
  computed: {
    title() { return (META[this.kind] && META[this.kind].title) || '学工待办' }
  },
  onLoad(q) {
    this.kind = (q && q.type) || 'AID_APPROVAL'
    this.load()
  },
  methods: {
    rowKey(x) {
      return String(x.applyId || x.applicationId || x.caseId || x.riskId || x.id || '')
    },
    load() {
      const m = META[this.kind]
      if (!m || !teacherApi[m.load]) { this.state = 'error'; return }
      this.state = 'loading'
      this.expandedId = ''
      this.detailMap = {}
      teacherApi[m.load]().then((d) => {
        let rows = (d && d.list) || []
        if (this.kind === 'AID_ADJUST') rows = rows.filter((x) => x.status === 'ADJUST_REVIEW')
        if (this.kind === 'AID_APPROVAL') rows = rows.filter((x) => x.status !== 'ADJUST_REVIEW')
        if (this.kind === 'DISCIPLINE_REMOVE') rows = rows.filter((x) => x.status === 'REMOVE_REVIEW')
        if (this.kind === 'DISCIPLINE_APPROVAL') rows = rows.filter((x) => x.status !== 'REMOVE_REVIEW')
        this.list = rows
        this.state = 'ready'
      }).catch((e) => {
        this.state = 'error'
        this._err(e, '加载')
      })
    },
    detailLines(d) {
      if (!d || typeof d !== 'object') return []
      const pairs = [
        ['事由', d.reason || d.statement || d.applyReason || d.topic || d.title],
        ['等级', d.applyLevel || d.suggestLevel || d.level || d.riskLevel || d.discTypeLabel || d.discType],
        ['节点', d.statusLabel || d.status],
        ['退回原因', d.returnReason],
        ['说明', d.remark || d.note || d.content || d.description],
        ['学院', d.collegeName],
        ['班级', d.className]
      ]
      return pairs.filter(([, v]) => v != null && String(v).trim() !== '').map(([k, v]) => ({ k, v: String(v) }))
    },
    loadDetail(x) {
      const id = this.rowKey(x)
      const m = META[this.kind]
      if (!id || !m || !m.detail || !teacherApi[m.detail]) return Promise.resolve(x)
      if (this.detailMap[id]) return Promise.resolve({ ...x, ...this.detailMap[id] })
      this.detailLoading = id
      return teacherApi[m.detail](id).then((d) => {
        this.detailMap = { ...this.detailMap, [id]: d || {} }
        return { ...x, ...(d || {}) }
      }).finally(() => { this.detailLoading = '' })
    },
    toggleDetail(x) {
      const id = this.rowKey(x)
      if (!id) return
      if (this.expandedId === id) { this.expandedId = ''; return }
      this.expandedId = id
      this.loadDetail(x).catch((e) => {
        this._err(e, '详情加载')
        this.expandedId = ''
      })
    },
    _err(e, label) {
      const n = normalizeError(e)
      toast(n.text || (e && e.message) || label + '失败')
      if (n.kind === 'conflict') this.load()
    },
    versionOf(entity) {
      const value = entity && entity.version
      if (value === undefined || value === null || value === '') {
        toast('记录缺少版本号，请刷新后再处理')
        this.load()
        return null
      }
      return value
    },
    reviewRequest(id, action, reason, entity) {
      const version = this.versionOf(entity)
      if (version === null) return Promise.reject({ message: '缺少版本号' })
      if (this.kind === 'AID_APPROVAL' || this.kind === 'AID_ADJUST') {
        return affairsContractApi.reviewAid(id, action, reason, entity.suggestLevel || entity.applyLevel, version)
      }
      if (this.kind === 'FUNDING_APPROVAL') {
        return affairsContractApi.reviewFunding(id, action, reason, version)
      }
      return affairsContractApi.reviewDiscipline(id, action, reason, version)
    },
    doReview(x, action) {
      const id = this.rowKey(x)
      if (!id || this.acting) return
      const needReason = action === 'REJECT' || action === 'RETURN'
      const run = (reason) => {
        if (needReason && (!reason || reason.trim().length < 5)) {
          toast((action === 'RETURN' ? '退回' : '驳回') + '原因不少于 5 字')
          return
        }
        this.acting = true
        this.loadDetail(x)
          .then((entity) => this.reviewRequest(id, action, reason || '', entity))
          .then(() => { toast(ACTION_LABEL[action] || '已处理'); this.load() })
          .catch((e) => this._err(e, '审批'))
          .finally(() => { this.acting = false })
      }
      if (needReason) {
        uni.showModal({
          title: action === 'RETURN' ? '退回原因' : '驳回原因',
          editable: true, placeholderText: '不少于 5 字',
          success: (r) => { if (r.confirm) run(r.content || '') }
        })
      } else run('')
    },
    doRiskProcess(x) {
      const id = x.riskId || x.id
      uni.showModal({
        title: '处置内容', editable: true, placeholderText: '不少于 5 字',
        success: (r) => {
          if (!r.confirm) return
          const content = (r.content || '').trim()
          if (content.length < 5) return toast('处置内容不少于 5 字')
          this.acting = true
          this.loadDetail(x).then((entity) => {
            const version = this.versionOf(entity)
            if (version === null) throw { message: '缺少版本号' }
            return affairsContractApi.processRisk(id, content, version)
          }).then(() => { toast('已记录'); this.load() })
            .catch((e) => this._err(e, '处置'))
            .finally(() => { this.acting = false })
        }
      })
    },
    doRiskClose(x) {
      const id = x.riskId || x.id
      uni.showModal({
        title: '关闭结论', editable: true, placeholderText: '不少于 5 字',
        success: (r) => {
          if (!r.confirm) return
          const conclusion = (r.content || '').trim()
          if (conclusion.length < 5) return toast('关闭结论不少于 5 字')
          this.acting = true
          this.loadDetail(x).then((entity) => {
            const version = this.versionOf(entity)
            if (version === null) throw { message: '缺少版本号' }
            return affairsContractApi.closeRisk(id, conclusion, version)
          }).then(() => { toast('已关闭'); this.load() })
            .catch((e) => this._err(e, '关闭'))
            .finally(() => { this.acting = false })
        }
      })
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
.ar__ok { background: var(--brand-primary); color: #fff; border-radius: 8px; font-size: 14px; }
.ar__no { background: #fee2e2; color: #b91c1c; border-radius: 8px; font-size: 14px; }
</style>
