<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="宿舍待办" subtitle="调宿审批 / 异常处置" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad">
        <view class="seg">
          <button class="seg__btn" :class="{ on: tab === 'transfer' }" @click="tab = 'transfer'">调宿待审 ({{ transfers.length }})</button>
          <button class="seg__btn" :class="{ on: tab === 'exception' }" @click="tab = 'exception'">异常待处置 ({{ exceptions.length }})</button>
        </view>

        <MobileGlobalState v-if="tab === 'transfer' && !transfers.length" state="empty" title="暂无调宿待审" description="有学生调宿进入辅导员/宿管节点时会出现在这里。" />
        <view class="stack" v-else-if="tab === 'transfer'">
          <view v-for="x in transfers" :key="x.transferId" class="card ar">
            <view class="row-between">
              <view class="flex-1"><text class="t-md t-bold">{{ x.realName || '—' }}</text><text class="ar__sub">{{ x.studentNo || '' }} · {{ nodeLabel(x.currentNode || x.status) }}</text></view>
              <MobileStatusTag :label="x.statusLabel || nodeLabel(x.status)" type="warning" />
            </view>
            <view class="ar__route">
              <text class="ar__route-k">原床</text><text class="ar__route-v">{{ x.fromBedLabel || fallbackBed(x, 'from') }}</text>
              <text class="ar__arrow">↓</text>
              <text class="ar__route-k">目标</text><text class="ar__route-v ar__route-target">{{ x.toBedLabel || fallbackBed(x, 'to') }}</text>
            </view>
            <text class="ar__sub" v-if="x.reason">调宿事由：{{ x.reason }}</text>
            <MobileInlineAlert v-if="!x.fromBedLabel || !x.toBedLabel" type="warning" title="床位信息不完整" description="请刷新或联系宿管核对，确认原床和目标床后再审批。" />
            <view class="ar__actions" v-if="can(x, 'REJECT') || can(x, 'APPROVE')">
              <button v-if="can(x, 'REJECT')" class="ar__no flex-1" :disabled="acting" @click="reviewTransfer(x, 'REJECT')">驳回</button>
              <button v-if="can(x, 'APPROVE')" class="ar__ok flex-1" :disabled="acting || !x.fromBedLabel || !x.toBedLabel" @click="reviewTransfer(x, 'APPROVE')">核对后通过</button>
            </view>
            <text v-else class="ar__sub">当前节点暂无可执行动作</text>
          </view>
        </view>

        <MobileGlobalState v-if="tab === 'exception' && !exceptions.length" state="empty" title="暂无宿舍异常" description="查寝异常、夜不归宿等待处置记录会显示在这里。" />
        <view class="stack" v-else-if="tab === 'exception'">
          <view v-for="x in exceptions" :key="x.exceptionId" class="card ar">
            <view class="row-between"><view class="flex-1"><text class="t-md t-bold">{{ x.realName || '房间级异常' }}</text><text class="ar__sub">{{ x.studentNo || '' }} · {{ x.excTypeLabel || x.excType || '异常' }}</text></view><MobileStatusTag :label="x.statusLabel || x.status || '待处置'" type="warning" /></view>
            <text class="ar__sub" v-if="x.buildingName || x.roomNo">位置：{{ [x.buildingName, x.roomNo && (x.roomNo + '室')].filter(Boolean).join(' / ') }}</text>
            <text class="ar__sub" v-if="x.occurredAt || x.createdAt">发生时间：{{ fmt(x.occurredAt || x.createdAt) }}</text>
            <text class="ar__detail" v-if="x.detail">{{ x.detail }}</text>
            <button class="ar__ok" style="margin-top:10px" :disabled="acting" @click="handleException(x)">登记处置</button>
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

export default {
  data() { return { state: 'loading', acting: false, tab: 'transfer', transfers: [], exceptions: [] } },
  onLoad(q) { if (q && q.tab === 'exception') this.tab = 'exception'; this.load() },
  onShow() { if (this.state === 'ready') this.load() },
  methods: {
    fmt(v) { return (v || '').slice(0, 16).replace('T', ' ') },
    nodeLabel(v) { return ({ COUNSELOR_REVIEW: '辅导员审核', DORM_MANAGER_REVIEW: '宿管审核', EXECUTED: '已执行', REJECTED: '已驳回' })[v] || v || '待审' },
    fallbackBed(x, side) {
      const prefix = side === 'from' ? 'from' : 'to'
      const parts = [x[prefix + 'BuildingName'], x[prefix + 'RoomNo'] && (x[prefix + 'RoomNo'] + '室'), x[prefix + 'BedNo'] && (x[prefix + 'BedNo'] + '床')].filter(Boolean)
      return parts.join(' / ') || (x[prefix + 'BedId'] ? `床位 #${x[prefix + 'BedId']}` : '未记录')
    },
    can(x, action) {
      return Array.isArray(x.allowedActions) ? x.allowedActions.includes(action) : ['COUNSELOR_REVIEW', 'DORM_MANAGER_REVIEW', 'SUBMITTED'].includes(x.status)
    },
    load() {
      this.state = 'loading'
      teacherApi.getAffairsDormPending().then((d) => { this.transfers = (d && d.transfers) || []; this.exceptions = (d && d.exceptions) || []; this.state = 'ready' })
        .catch((e) => { this.state = 'error'; this.showError(e, '宿舍待办加载失败') })
    },
    showError(e, fallback) { const n = normalizeError(e); toast(n.text || (e && e.message) || fallback); if (n.kind === 'conflict') this.load(); return n },
    versionOf(x) { if (x.version === undefined || x.version === null || x.version === '') { toast('记录缺少版本号，请刷新后重试'); this.load(); return null }; return x.version },
    promptText({ title, placeholder, initial = '', min = 5, invalid, submit }) {
      uni.showModal({ title, editable: true, placeholderText: placeholder, content: initial, success: (r) => {
        if (!r.confirm) return
        const value = (r.content || '').trim(); if (value.length < min) return toast(invalid)
        submit(value)
      } })
    },
    reviewTransfer(x, action, previous = '') {
      if (this.acting || !this.can(x, action)) return
      const run = (reason) => {
        const version = this.versionOf(x); if (version === null) return
        this.acting = true
        affairsContractApi.reviewDormTransfer(x.transferId, action, reason, version).then(() => { toast(action === 'APPROVE' ? '已通过' : '已驳回'); this.load() })
          .catch((e) => { const n = this.showError(e, '调宿处理失败'); if (n.kind !== 'conflict' && action === 'REJECT') setTimeout(() => this.reviewTransfer(x, action, reason), 0) })
          .finally(() => { this.acting = false })
      }
      if (action === 'REJECT') {
        this.promptText({ title: '驳回调宿', placeholder: '驳回原因不少于5字', initial: previous, invalid: '驳回原因至少5字', submit: run })
        return
      }
      uni.showModal({
        title: '确认通过调宿',
        content: `${x.realName || '该学生'}\n${x.fromBedLabel || this.fallbackBed(x, 'from')}\n→ ${x.toBedLabel || this.fallbackBed(x, 'to')}\n\n确认床位、学生和审批节点无误后再通过。`,
        confirmText: '确认通过',
        success: (r) => { if (r.confirm) run('') }
      })
    },
    handleException(x, previous = '') {
      if (this.acting) return
      this.promptText({
        title: '处置说明', placeholder: '处置说明不少于5字', initial: previous, invalid: '处置说明至少5字',
        submit: (note) => {
          const version = this.versionOf(x); if (version === null) return
          this.acting = true
          affairsContractApi.handleDormException(x.exceptionId, note, version).then(() => { toast('已处置'); this.load() })
            .catch((e) => { const n = this.showError(e, '异常处置失败'); if (n.kind !== 'conflict') setTimeout(() => this.handleException(x, note), 0) })
            .finally(() => { this.acting = false })
        }
      })
    }
  }
}
</script>

<style scoped>
.seg { display: flex; gap: 8px; margin-bottom: 12px; }
.seg__btn { flex: 1; font-size: 13px; background: #f1f5f9; color: #334155; border: none; border-radius: 8px; padding: 8px; }
.seg__btn.on { background: #2563eb; color: #fff; }
.ar { margin-bottom: 10px; }
.row-between { display: flex; justify-content: space-between; gap: 8px; }
.ar__sub { display: block; font-size: 12px; color: #64748b; margin-top: 4px; }
.ar__detail { display: block; margin-top: 8px; padding: 8px; background: #f8fafc; border-radius: 8px; font-size: 13px; line-height: 1.6; }
.ar__route { margin-top: 10px; padding: 10px; background: #f8fafc; border-radius: 8px; display: grid; grid-template-columns: 44px 1fr; gap: 5px 8px; }
.ar__route-k { font-size: 12px; color: #64748b; }
.ar__route-v { font-size: 13px; color: #334155; font-weight: 600; }
.ar__route-target { color: #166534; }
.ar__arrow { grid-column: 2; color: #94a3b8; }
.ar__actions { display: flex; gap: 8px; margin-top: 10px; }
.ar__ok { background: #16a34a; color: #fff; border: none; border-radius: 8px; padding: 8px; font-size: 13px; }
.ar__no { background: #fee2e2; color: #b91c1c; border: none; border-radius: 8px; padding: 8px; font-size: 13px; }
</style>
