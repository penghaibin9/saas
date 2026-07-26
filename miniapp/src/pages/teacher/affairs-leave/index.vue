<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="学生请假管理" subtitle="审批 · 销假 · 续假 · 逾期处置" show-back />

    <view class="al__tabs">
      <view class="al__tab" :class="{ 'is-on': tab === 'pending' }" @click="switchTab('pending')">
        待审批<text v-if="pending && pending.length" class="al__tab-badge">{{ pending.length }}</text>
        <text v-if="tab === 'pending'" class="al__tab-u" />
      </view>
      <view class="al__tab" :class="{ 'is-on': tab === 'followup' }" @click="switchTab('followup')">
        后续处理<text v-if="followup && followup.length" class="al__tab-badge">{{ followup.length }}</text>
        <text v-if="tab === 'followup'" class="al__tab-u" />
      </view>
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="tab === 'pending'">
        <MobileGlobalState v-if="!pending || !pending.length" state="empty" title="暂无待审批请假"
          description="轮到你审批的请假会出现在这里。" />
        <view class="stack" v-else>
          <view v-for="x in pending" :key="x.id" class="card al">
            <view class="row-between">
              <view class="flex-1">
                <text class="t-md t-bold">{{ x.studentName || '—' }}</text>
                <text class="al__sub">{{ x.studentNo || '' }} · {{ x.className || '' }} · {{ x.leaveTypeLabel }}</text>
              </view>
              <MobileStatusTag :label="x.affairsStatusLabel" type="warning" />
            </view>
            <view class="al__row"><text class="al__row-k">时间</text><text class="flex-1 t-sm">{{ fmt(x.startTime) }} ~ {{ fmt(x.endTime) }}（{{ x.days }}天）</text></view>
            <view class="al__row" v-if="x.reason"><text class="al__row-k">事由</text><text class="flex-1 t-sm">{{ x.reason }}</text></view>
            <view class="al__actions">
              <button v-if="can(x, 'RETURN')" class="al__reject flex-1" :disabled="acting" @click="doReturn(x)">退回</button>
              <button v-if="can(x, 'REJECT')" class="al__reject flex-1" :disabled="acting" @click="doReject(x)">驳回</button>
              <button v-if="can(x, 'APPROVE')" class="al__approve flex-1" :disabled="acting" @click="doApprove(x)">通过</button>
            </view>
          </view>
        </view>
      </view>

      <view class="page-pad" v-if="tab === 'followup'">
        <MobileGlobalState v-if="!followup || !followup.length" state="empty" title="暂无后续处理事项"
          description="已通过/续假中/待销假/逾期的请假会出现在这里。" />
        <view class="stack" v-else>
          <view v-for="x in followup" :key="x.id" class="card al">
            <view class="row-between">
              <view class="flex-1">
                <text class="t-md t-bold">{{ x.studentName || '—' }}</text>
                <text class="al__sub">{{ x.studentNo || '' }} · {{ x.className || '' }} · {{ x.leaveTypeLabel }}</text>
              </view>
              <MobileStatusTag :label="x.affairsStatusLabel" :type="followupTone(x.affairsStatus)" />
            </view>
            <view class="al__row"><text class="al__row-k">时间</text><text class="flex-1 t-sm">{{ fmt(x.startTime) }} ~ {{ fmt(x.endTime) }}（{{ x.days }}天）</text></view>

            <view class="al__actions" v-if="can(x, 'PROXY_CANCEL')">
              <button class="btn btn-ghost flex-1" :disabled="acting" @click="doProxyCancel(x)">代登记销假</button>
            </view>
            <view class="al__actions" v-else-if="can(x, 'CONFIRM_CANCEL')">
              <button class="al__reject flex-1" :disabled="acting" @click="doCancelReturn(x)">销假退回</button>
              <button class="al__approve flex-1" :disabled="acting" @click="doCancelConfirm(x)">确认销假</button>
            </view>
            <view class="al__actions" v-else-if="can(x, 'APPROVE_EXTENSION')">
              <button class="al__reject flex-1" :disabled="acting" @click="doExtension(x, 'REJECT')">续假驳回</button>
              <button class="al__approve flex-1" :disabled="acting" @click="doExtension(x, 'APPROVE')">续假通过</button>
            </view>
            <view class="al__actions" v-else-if="can(x, 'HANDLE_OVERDUE')">
              <button class="btn btn-ghost flex-1" :disabled="acting" @click="doOverdue(x)">逾期处置</button>
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

const OVERDUE_TYPES = [
  { key: 'CONTACT', label: '联系学生' }, { key: 'TO_HOME_SCHOOL', label: '转家校联系' },
  { key: 'CLOSE', label: '处置完毕关闭' }
]

export default {
  data() { return { tab: 'pending', pending: null, followup: null, state: 'loading', acting: false } },
  onLoad() { this.load() },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  methods: {
    fmt(v) { return (v || '').slice(0, 16).replace('T', ' ') },
    can(x, action) {
      return Array.isArray(x.allowedActions) && x.allowedActions.includes(action)
    },
    followupTone(s) {
      return s === 'OVERDUE' ? 'danger' : s === 'WAIT_CANCEL_LEAVE' ? 'warning' : 'default'
    },
    switchTab(t) {
      if (this.tab === t) return
      this.tab = t
      if ((t === 'pending' && !this.pending) || (t === 'followup' && !this.followup)) this.load()
    },
    load(done) {
      this.state = 'loading'
      Promise.all([
        teacherApi.getAffairsLeavePending(),
        teacherApi.getAffairsLeaveFollowup()
      ]).then(([p, f]) => {
        this.pending = (p && p.list) || []
        this.followup = (f && f.list) || []
        this.state = 'ready'
      }).catch((e) => {
        this.state = 'error'
        this._err(e, '加载')
      }).finally(() => { if (done) done() })
    },
    _err(e, label) {
      const n = normalizeError(e)
      toast(n.text || (e && e.message) || label + '失败，请重试')
      if (n.kind === 'conflict') this.load()
    },
    run(task, successText, label) {
      if (this.acting) return
      this.acting = true
      task().then(() => {
        toast(successText)
        this.load()
      }).catch((e) => this._err(e, label))
        .finally(() => { this.acting = false })
    },
    doApprove(x) {
      uni.showModal({
        title: '通过请假', editable: true, placeholderText: '可填写审批意见（可选）', content: '',
        success: (r) => {
          if (!r.confirm) return
          this.run(() => affairsContractApi.approveLeave(x.id, r.content || '', x.version), '已通过', '审批')
        }
      })
    },
    doReject(x) {
      uni.showModal({
        title: '驳回请假', editable: true, placeholderText: '请填写驳回原因（≥5 字）', content: '',
        success: (r) => {
          if (!r.confirm) return
          const reason = (r.content || '').trim()
          if (reason.length < 5) return toast('驳回原因至少 5 个字')
          this.run(() => affairsContractApi.rejectLeave(x.id, reason, x.version), '已驳回', '驳回')
        }
      })
    },
    doReturn(x) {
      uni.showModal({
        title: '退回申请人修改', editable: true, placeholderText: '请明确填写需要修改的内容（≥5 字）', content: '',
        success: (r) => {
          if (!r.confirm) return
          const reason = (r.content || '').trim()
          if (reason.length < 5) return toast('退回原因至少 5 个字')
          this.run(() => affairsContractApi.returnLeave(x.id, reason, x.version), '已退回申请人修改', '退回')
        }
      })
    },
    doCancelConfirm(x) {
      uni.showModal({
        title: '确认销假', editable: true, placeholderText: '可填写备注（可选）', content: '',
        success: (r) => {
          if (!r.confirm) return
          this.run(
            () => affairsContractApi.confirmCancelLeave(x.id, 'CONFIRM', { note: r.content || '' }, x.version),
            '已确认销假', '销假确认'
          )
        }
      })
    },
    doCancelReturn(x) {
      uni.showModal({
        title: '销假退回', editable: true, placeholderText: '请填写退回原因（≥5 字）', content: '',
        success: (r) => {
          if (!r.confirm) return
          const reason = (r.content || '').trim()
          if (reason.length < 5) return toast('退回原因至少 5 个字')
          this.run(
            () => affairsContractApi.confirmCancelLeave(x.id, 'RETURN', { reason }, x.version),
            '销假申请已退回', '销假退回'
          )
        }
      })
    },
    doProxyCancel(x) {
      uni.showModal({
        title: '代登记销假', editable: true,
        placeholderText: '填写实际返校时间，如 2026-03-05 08:30', content: '',
        success: (r) => {
          if (!r.confirm) return
          const value = (r.content || '').trim()
          if (!value) return toast('请填写实际返校时间')
          this.run(
            () => affairsContractApi.proxyCancelLeave(x.id, value, '', x.version),
            '已代登记销假', '代登记销假'
          )
        }
      })
    },
    doExtension(x, action) {
      const reject = action === 'REJECT'
      uni.showModal({
        title: reject ? '续假驳回' : '续假通过',
        editable: reject, placeholderText: reject ? '请填写驳回原因（≥5 字）' : '',
        content: reject ? '' : '确认通过该续假申请？',
        success: (r) => {
          if (!r.confirm) return
          const reason = (r.content || '').trim()
          if (reject && reason.length < 5) return toast('驳回原因至少 5 个字')
          this.run(
            () => affairsContractApi.reviewLeaveExtension(x.id, action, reason, x.version),
            reject ? '已驳回' : '已通过', '续假审批'
          )
        }
      })
    },
    doOverdue(x) {
      uni.showActionSheet({
        itemList: OVERDUE_TYPES.map((t) => t.label),
        success: (res) => {
          const type = OVERDUE_TYPES[res.tapIndex]
          uni.showModal({
            title: type.label, editable: true, placeholderText: '请填写处置说明（≥5 字）', content: '',
            success: (r) => {
              if (!r.confirm) return
              const note = (r.content || '').trim()
              if (note.length < 5) return toast('处置说明至少 5 个字')
              this.run(
                () => affairsContractApi.handleLeaveOverdue(x.id, type.key, note, x.version),
                '已登记', '逾期处置'
              )
            }
          })
        }
      })
    }
  }
}
</script>

<style scoped>
.al__tabs { display: flex; gap: var(--space-6); padding: var(--space-3) var(--page-padding-mobile) 0; background: var(--bg-card); }
.al__tab { position: relative; font-size: var(--font-size-base); color: var(--text-tertiary); font-weight: var(--font-weight-medium); padding-bottom: var(--space-3); }
.al__tab.is-on { color: var(--text-primary); font-weight: var(--font-weight-semibold); }
.al__tab-u { position: absolute; left: 50%; bottom: 0; transform: translateX(-50%); width: 22px; height: 3px; border-radius: 2px; background: var(--teacher-600); }
.al__tab-badge { margin-left: 4px; font-size: 10px; color: #fff; background: var(--danger-500); padding: 1px 5px; border-radius: var(--radius-full); }
.al { display: flex; flex-direction: column; gap: var(--space-2); }
.al__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.al__row { display: flex; gap: var(--space-3); }
.al__row-k { font-size: var(--font-size-sm); color: var(--text-tertiary); width: 40px; flex-shrink: 0; }
.al__actions { display: flex; gap: var(--space-2); margin-top: var(--space-1); }
.al__reject { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); border: 1px solid var(--danger-500); background: var(--bg-card); color: var(--danger-600); }
.al__reject::after { border: none; }
.al__approve { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); border: none; background: var(--teacher-600); color: #fff; }
.al__approve::after { border: none; }
</style>
