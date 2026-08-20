<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="学生请假管理" subtitle="审批 · 销假 · 续假 · 逾期处置" show-back />

    <view class="al__tabs">
      <view class="al__tab" :class="{ 'is-on': tab === 'pending' }" @click="switchTab('pending')">待审批<text v-if="pending && pending.length" class="al__tab-badge">{{ pending.length }}</text><text v-if="tab === 'pending'" class="al__tab-u" /></view>
      <view class="al__tab" :class="{ 'is-on': tab === 'followup' }" @click="switchTab('followup')">后续处理<text v-if="followup && followup.length" class="al__tab-badge">{{ followup.length }}</text><text v-if="tab === 'followup'" class="al__tab-u" /></view>
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="tab === 'pending'">
        <view v-if="sequentialItems.length > 1" class="al__queue-bar">
          <text class="al__queue-note">逐条处理 {{ sequentialItems.length }} 条待审批</text>
          <text class="al__queue-toggle" @click="sequentialMode ? stopSequential() : startSequential()">{{ sequentialMode ? '退出连续处理' : '连续处理' }}</text>
        </view>

        <MobileGlobalState v-if="!pending || !pending.length" state="empty" title="暂无待审批请假" description="轮到你审批的请假会出现在这里。" />

        <MobileSequentialQueue
          v-else-if="sequentialMode"
          title="请假连续审批"
          :items="sequentialItems"
          :current-index="sequentialIndex"
          :loading="acting"
          :conflict="sequentialConflict"
          @open="openSequentialItem"
          @next="nextSequential"
        >
          <template #default="{ item: x, blocked }">
            <view class="al al__queue-item">
              <view class="row-between"><view class="flex-1"><text class="t-md t-bold">{{ x.studentName || '—' }}</text><text class="al__sub">{{ x.studentNo || '' }} · {{ x.className || '' }} · {{ x.leaveTypeLabel }}</text></view><MobileStatusTag :label="x.affairsStatusLabel" type="warning" /></view>
              <view class="al__row"><text class="al__row-k">时间</text><text class="flex-1 t-sm">{{ fmt(x.startTime) }} ~ {{ fmt(x.endTime) }}（{{ x.days }}天）</text></view>
              <view class="al__row" v-if="x.reason"><text class="al__row-k">事由</text><text class="flex-1 t-sm">{{ x.reason }}</text></view>
              <MobileInlineAlert v-if="!hasVersion(x)" type="warning" title="记录缺少版本号" description="请刷新后再处理，禁止使用旧数据审批。" />
              <view class="al__actions">
                <button v-if="can(x, 'RETURN')" class="al__reject flex-1" :disabled="blocked || !hasVersion(x)" @click="doReturn(x)">退回</button>
                <button v-if="can(x, 'REJECT')" class="al__reject flex-1" :disabled="blocked || !hasVersion(x)" @click="doReject(x)">驳回</button>
                <button v-if="can(x, 'APPROVE')" class="al__approve flex-1" :disabled="blocked || !hasVersion(x)" @click="doApprove(x)">核对后通过</button>
              </view>
              <button v-if="sequentialConflict" class="btn btn-ghost" @click="restartSequential">已刷新，重新开始当前队列</button>
            </view>
          </template>
        </MobileSequentialQueue>

        <view class="stack" v-else-if="pending && pending.length">
          <view v-for="x in pending" :key="x.id" class="card al">
            <view class="row-between"><view class="flex-1"><text class="t-md t-bold">{{ x.studentName || '—' }}</text><text class="al__sub">{{ x.studentNo || '' }} · {{ x.className || '' }} · {{ x.leaveTypeLabel }}</text></view><MobileStatusTag :label="x.affairsStatusLabel" type="warning" /></view>
            <view class="al__row"><text class="al__row-k">时间</text><text class="flex-1 t-sm">{{ fmt(x.startTime) }} ~ {{ fmt(x.endTime) }}（{{ x.days }}天）</text></view>
            <view class="al__row" v-if="x.reason"><text class="al__row-k">事由</text><text class="flex-1 t-sm">{{ x.reason }}</text></view>
            <MobileInlineAlert v-if="!hasVersion(x)" type="warning" title="记录缺少版本号" description="请刷新后再处理，禁止使用旧数据审批。" />
            <view class="al__actions">
              <button v-if="can(x, 'RETURN')" class="al__reject flex-1" :disabled="acting || !hasVersion(x)" @click="doReturn(x)">退回</button>
              <button v-if="can(x, 'REJECT')" class="al__reject flex-1" :disabled="acting || !hasVersion(x)" @click="doReject(x)">驳回</button>
              <button v-if="can(x, 'APPROVE')" class="al__approve flex-1" :disabled="acting || !hasVersion(x)" @click="doApprove(x)">核对后通过</button>
            </view>
          </view>
        </view>
      </view>

      <view class="page-pad" v-if="tab === 'followup'">
        <MobileGlobalState v-if="!followup || !followup.length" state="empty" title="暂无后续处理事项" description="已通过/续假中/待销假/逾期的请假会出现在这里。" />
        <view class="stack" v-else>
          <view v-for="x in followup" :key="x.id" class="card al">
            <view class="row-between"><view class="flex-1"><text class="t-md t-bold">{{ x.studentName || '—' }}</text><text class="al__sub">{{ x.studentNo || '' }} · {{ x.className || '' }} · {{ x.leaveTypeLabel }}</text></view><MobileStatusTag :label="x.affairsStatusLabel" :type="followupTone(x.affairsStatus)" /></view>
            <view class="al__row"><text class="al__row-k">时间</text><text class="flex-1 t-sm">{{ fmt(x.startTime) }} ~ {{ fmt(x.endTime) }}（{{ x.days }}天）</text></view>
            <MobileInlineAlert v-if="!hasVersion(x)" type="warning" title="记录缺少版本号" description="请刷新后再处理。" />
            <view class="al__actions" v-if="can(x, 'PROXY_CANCEL')"><button class="btn btn-ghost flex-1" :disabled="acting || !hasVersion(x)" @click="doProxyCancel(x)">代登记销假</button></view>
            <view class="al__actions" v-else-if="can(x, 'CONFIRM_CANCEL')"><button class="al__reject flex-1" :disabled="acting || !hasVersion(x)" @click="doCancelReturn(x)">销假退回</button><button class="al__approve flex-1" :disabled="acting || !hasVersion(x)" @click="doCancelConfirm(x)">确认销假</button></view>
            <view class="al__actions" v-else-if="can(x, 'APPROVE_EXTENSION')"><button class="al__reject flex-1" :disabled="acting || !hasVersion(x)" @click="doExtension(x, 'REJECT')">续假驳回</button><button class="al__approve flex-1" :disabled="acting || !hasVersion(x)" @click="doExtension(x, 'APPROVE')">续假通过</button></view>
            <view class="al__actions" v-else-if="can(x, 'HANDLE_OVERDUE')"><button class="btn btn-ghost flex-1" :disabled="acting || !hasVersion(x)" @click="doOverdue(x)">逾期处置</button></view>
          </view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import MobileSequentialQueue from '@/components/teacher/MobileSequentialQueue.vue'
import { teacherApi } from '@/services/teacherApi'
import { affairsContractApi } from '@/services/affairsContractApi'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

const OVERDUE_TYPES = [
  { key: 'CONTACT', label: '联系学生' }, { key: 'TO_HOME_SCHOOL', label: '转家校联系' },
  { key: 'CLOSE', label: '处置完毕关闭' }
]

export default {
  components: { MobileSequentialQueue },
  data() {
    return {
      tab: 'pending', pending: null, followup: null, state: 'loading', acting: false,
      sequentialMode: false, sequentialIndex: 0, sequentialConflict: false
    }
  },
  computed: {
    sequentialItems() {
      return (this.pending || []).filter((x) => ['APPROVE', 'REJECT', 'RETURN'].some((action) => this.can(x, action)))
    },
    sequentialCurrent() { return this.sequentialItems[this.sequentialIndex] || null }
  },
  onLoad() { this.load() },
  onPullDownRefresh() { if (this.state === 'loading') { uni.stopPullDownRefresh(); return }; this.load(() => uni.stopPullDownRefresh()) },
  methods: {
    fmt(v) { return (v || '').slice(0, 16).replace('T', ' ') },
    hasVersion(x) { return x && x.version !== undefined && x.version !== null && x.version !== '' },
    can(x, action) { return Array.isArray(x && x.allowedActions) && x.allowedActions.includes(action) },
    followupTone(s) { return s === 'OVERDUE' ? 'danger' : s === 'WAIT_CANCEL_LEAVE' ? 'warning' : 'default' },
    switchTab(t) {
      if (this.tab === t) return
      this.stopSequential()
      this.tab = t
      if ((t === 'pending' && !this.pending) || (t === 'followup' && !this.followup)) this.load()
    },
    startSequential() {
      if (!this.sequentialItems.length) return
      this.sequentialMode = true
      this.sequentialIndex = 0
      this.sequentialConflict = false
    },
    stopSequential() {
      this.sequentialMode = false
      this.sequentialIndex = 0
      this.sequentialConflict = false
    },
    restartSequential() {
      this.sequentialConflict = false
      this.sequentialIndex = Math.max(0, Math.min(this.sequentialIndex, this.sequentialItems.length - 1))
    },
    openSequentialItem(x) {
      if (!x) return
      toast(`${x.studentName || '当前学生'} · ${x.leaveTypeLabel || '请假申请'}`)
    },
    nextSequential() {
      if (this.sequentialConflict || this.acting) return
      if (this.sequentialIndex < this.sequentialItems.length - 1) this.sequentialIndex += 1
    },
    load(done) {
      this.state = 'loading'
      const currentId = this.sequentialCurrent && String(this.sequentialCurrent.id)
      const request = Promise.all([teacherApi.getAffairsLeavePending(), teacherApi.getAffairsLeaveFollowup()]).then(([p, f]) => {
        this.pending = (p && p.list) || []
        this.followup = (f && f.list) || []
        if (this.sequentialMode && currentId) {
          const found = this.sequentialItems.findIndex((x) => String(x.id) === currentId)
          if (found >= 0) this.sequentialIndex = found
          else this.sequentialIndex = Math.max(0, Math.min(this.sequentialIndex, this.sequentialItems.length - 1))
          if (!this.sequentialItems.length) this.stopSequential()
        }
        this.state = 'ready'
        return { pending: this.pending, followup: this.followup }
      }).catch((e) => {
        this.state = 'error'
        this._err(e, '加载')
        throw e
      }).finally(() => { if (done) done() })
      return request
    },
    _err(e, label) {
      const n = normalizeError(e)
      toast(n.text || (e && e.message) || label + '失败，请重试')
      return n
    },
    afterSequentialSuccess(processedId, oldIndex) {
      if (!this.sequentialMode) return
      if (!this.sequentialItems.length) return this.stopSequential()
      const stillThere = this.sequentialItems.findIndex((x) => String(x.id) === String(processedId))
      if (stillThere >= 0) this.sequentialIndex = Math.min(stillThere + 1, this.sequentialItems.length - 1)
      else this.sequentialIndex = Math.max(0, Math.min(oldIndex, this.sequentialItems.length - 1))
    },
    run(task, successText, label, retry, sequentialId = null) {
      if (this.acting) return
      const queueId = sequentialId || (this.sequentialMode && this.sequentialCurrent ? this.sequentialCurrent.id : null)
      const oldIndex = this.sequentialIndex
      this.acting = true
      return task().then(() => {
        toast(successText)
        return this.load().then(() => this.afterSequentialSuccess(queueId, oldIndex))
      }).catch((e) => {
        const n = this._err(e, label)
        if (n.kind !== 'conflict') {
          if (retry) setTimeout(retry, 0)
          return
        }
        if (this.sequentialMode) this.sequentialConflict = true
        return this.load().catch(() => {})
      }).finally(() => { this.acting = false })
    },
    promptText({ title, placeholder, initial = '', required = false, max = 300, submit }) {
      uni.showModal({ title, editable: true, placeholderText: placeholder, content: initial, success: (r) => {
        if (!r.confirm) return
        const value = (r.content || '').trim()
        if (required && value.length < 5) return toast('处理意见至少5个字')
        if (value.length > max) return toast(`处理意见不能超过${max}字`)
        submit(value)
      } })
    },
    parseReturnAt(value) {
      const raw = String(value || '').trim().replace('T', ' ')
      const m = raw.match(/^(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})$/)
      if (!m) return { error: '实际返校时间格式应为 YYYY-MM-DD HH:mm' }
      const [year, month, day, hour, minute] = m.slice(1).map(Number)
      const dt = new Date(year, month - 1, day, hour, minute, 0, 0)
      if (dt.getFullYear() !== year || dt.getMonth() !== month - 1 || dt.getDate() !== day || dt.getHours() !== hour || dt.getMinutes() !== minute) return { error: '实际返校时间不是有效日期时间' }
      if (dt.getTime() > Date.now() + 60 * 1000) return { error: '实际返校时间不能晚于当前时间' }
      return { value: `${m[1]}-${m[2]}-${m[3]} ${m[4]}:${m[5]}` }
    },
    doApprove(x, initial = '') {
      this.promptText({ title: '通过请假', placeholder: '可填写审批意见（可选）', initial, submit: (opinion) => {
        uni.showModal({ title: '确认通过请假', content: `${x.studentName || '该学生'}\n${this.fmt(x.startTime)} 至 ${this.fmt(x.endTime)}\n\n确认请假时间、事由和审批节点无误。`, confirmText: '确认通过', success: (r) => { if (r.confirm) this.run(() => affairsContractApi.approveLeave(x.id, opinion, x.version), '已通过', '审批', () => this.doApprove(x, opinion), x.id) } })
      } })
    },
    doReject(x, initial = '') { this.promptText({ title: '驳回请假', placeholder: '请填写驳回原因（≥5字）', initial, required: true, submit: (reason) => this.run(() => affairsContractApi.rejectLeave(x.id, reason, x.version), '已驳回', '驳回', () => this.doReject(x, reason), x.id) }) },
    doReturn(x, initial = '') { this.promptText({ title: '退回申请人修改', placeholder: '请明确填写需要修改的内容（≥5字）', initial, required: true, submit: (reason) => this.run(() => affairsContractApi.returnLeave(x.id, reason, x.version), '已退回申请人修改', '退回', () => this.doReturn(x, reason), x.id) }) },
    doCancelConfirm(x, initial = '') {
      this.promptText({ title: '确认销假', placeholder: '可填写备注（可选）', initial, submit: (note) => {
        uni.showModal({ title: '确认学生已返校', content: `${x.studentName || '该学生'}的销假将被确认并办结，请确认返校事实已核实。`, confirmText: '确认销假', success: (r) => { if (r.confirm) this.run(() => affairsContractApi.confirmCancelLeave(x.id, 'CONFIRM', { note }, x.version), '已确认销假', '销假确认', () => this.doCancelConfirm(x, note)) } })
      } })
    },
    doCancelReturn(x, initial = '') { this.promptText({ title: '销假退回', placeholder: '请填写退回原因（≥5字）', initial, required: true, submit: (reason) => this.run(() => affairsContractApi.confirmCancelLeave(x.id, 'RETURN', { reason }, x.version), '销假申请已退回', '销假退回', () => this.doCancelReturn(x, reason)) }) },
    doProxyCancel(x, initial = '') {
      this.promptText({
        title: '代登记销假', placeholder: '实际返校时间：2026-03-05 08:30', initial,
        submit: (value) => {
          const parsed = this.parseReturnAt(value)
          if (parsed.error) return toast(parsed.error)
          uni.showModal({ title: '确认代登记销假', content: `${x.studentName || '该学生'}\n实际返校：${parsed.value}\n\n请确认已核实返校事实，代登记将写入审计。`, confirmText: '确认登记', success: (r) => {
            if (r.confirm) this.run(() => affairsContractApi.proxyCancelLeave(x.id, parsed.value, '辅导员核实后代登记销假', x.version), '已代登记销假', '代登记销假', () => this.doProxyCancel(x, parsed.value))
          } })
        }
      })
    },
    doExtension(x, action, initial = '') {
      const reject = action === 'REJECT'
      if (!reject) {
        uni.showModal({ title: '续假通过', content: `${x.studentName || '该学生'}\n请确认续假日期与理由已核对。`, confirmText: '确认通过', success: (r) => { if (r.confirm) this.run(() => affairsContractApi.reviewLeaveExtension(x.id, action, '', x.version), '已通过', '续假审批') } })
        return
      }
      this.promptText({ title: '续假驳回', placeholder: '请填写驳回原因（≥5字）', initial, required: true, submit: (reason) => this.run(() => affairsContractApi.reviewLeaveExtension(x.id, action, reason, x.version), '已驳回', '续假审批', () => this.doExtension(x, action, reason)) })
    },
    doOverdue(x, selectedIndex = null, initial = '') {
      const prompt = (type) => this.promptText({ title: type.label, placeholder: '请填写处置说明（≥5字）', initial, required: true, submit: (note) => this.run(() => affairsContractApi.handleLeaveOverdue(x.id, type.key, note, x.version), '已登记', '逾期处置', () => this.doOverdue(x, OVERDUE_TYPES.indexOf(type), note)) })
      if (selectedIndex !== null && OVERDUE_TYPES[selectedIndex]) return prompt(OVERDUE_TYPES[selectedIndex])
      uni.showActionSheet({ itemList: OVERDUE_TYPES.map((t) => t.label), success: (res) => prompt(OVERDUE_TYPES[res.tapIndex]) })
    }
  }
}
</script>

<style scoped>
.al__tabs { display: flex; gap: var(--space-6); padding: var(--space-3) var(--page-padding-mobile) 0; background: var(--bg-card); }.al__tab { position: relative; font-size: var(--font-size-base); color: var(--text-tertiary); font-weight: var(--font-weight-medium); padding-bottom: var(--space-3); }.al__tab.is-on { color: var(--text-primary); font-weight: var(--font-weight-semibold); }.al__tab-u { position: absolute; left: 50%; bottom: 0; transform: translateX(-50%); width: 22px; height: 3px; border-radius: 2px; background: var(--teacher-600); }.al__tab-badge { margin-left: 4px; font-size: 10px; color: #fff; background: var(--danger-500); padding: 1px 5px; border-radius: var(--radius-full); }.al { display: flex; flex-direction: column; gap: var(--space-2); }.al__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }.al__row { display: flex; gap: var(--space-3); }.al__row-k { font-size: var(--font-size-sm); color: var(--text-tertiary); width: 40px; flex-shrink: 0; }.al__actions { display: flex; gap: var(--space-2); margin-top: var(--space-1); }.al__reject { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); border: 1px solid var(--danger-500); background: var(--bg-card); color: var(--danger-600); }.al__reject::after { border: none; }.al__approve { min-height:var(--touch-target-min); border-radius:var(--radius-md); font-size:var(--font-size-md); border:0; background:var(--teacher-600); color:#fff; }.al__approve::after { border:none; }.al__queue-bar{display:flex;align-items:center;justify-content:space-between;gap:var(--space-2);margin-bottom:var(--space-3)}.al__queue-note{font-size:var(--font-size-sm);color:var(--text-secondary)}.al__queue-toggle{flex-shrink:0;font-size:var(--font-size-sm);color:var(--teacher-700)}.al__queue-item{padding:0}
</style>