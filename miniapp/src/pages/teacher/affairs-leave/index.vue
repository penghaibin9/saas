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
      <!-- 待审批 -->
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
              <button class="al__reject flex-1" :disabled="acting" @click="doReturn(x)">退回</button>
              <button class="al__reject flex-1" :disabled="acting" @click="doReject(x)">驳回</button>
              <button class="al__approve flex-1" :disabled="acting" @click="doApprove(x)">通过</button>
            </view>
          </view>
        </view>
      </view>

      <!-- 后续处理 -->
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

            <view class="al__actions" v-if="x.affairsStatus === 'APPROVED'">
              <button class="btn btn-ghost flex-1" :disabled="acting" @click="doProxyCancel(x)">代登记销假</button>
            </view>
            <view class="al__actions" v-else-if="x.affairsStatus === 'WAIT_CANCEL_LEAVE'">
              <button class="al__reject flex-1" :disabled="acting" @click="doCancelReturn(x)">销假退回</button>
              <button class="al__approve flex-1" :disabled="acting" @click="doCancelConfirm(x)">确认销假</button>
            </view>
            <view class="al__actions" v-else-if="x.affairsStatus === 'EXTENSION_REVIEW'">
              <button class="al__reject flex-1" :disabled="acting" @click="doExtension(x, 'REJECT')">续假驳回</button>
              <button class="al__approve flex-1" :disabled="acting" @click="doExtension(x, 'APPROVE')">续假通过</button>
            </view>
            <view class="al__actions" v-else-if="x.affairsStatus === 'OVERDUE'">
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
        teacherApi.getAffairsLeavePending().catch(() => ({ list: [] })),
        teacherApi.getAffairsLeaveFollowup().catch(() => ({ list: [] }))
      ]).then(([p, f]) => {
        this.pending = (p && p.list) || []
        this.followup = (f && f.list) || []
        this.state = 'ready'
      }).catch(() => { this.state = 'error' }).finally(() => { if (done) done() })
    },
    _err(e, label) {
      const code = e && String(e.code)
      if (code === 'APPROVAL_VERSION_CONFLICT' || code === 'DATA_CONFLICT') { toast((e && e.message) || '状态已变化，正在刷新'); this.load() }
      else if (code && code.startsWith('403')) toast((e && e.message) || '无权处理该记录')
      else toast((e && e.message) || label + '失败，请重试')
    },
    doApprove(x) {
      if (this.acting) return
      uni.showModal({
        title: '通过请假', editable: true, placeholderText: '可填写审批意见（可选）', content: '',
        success: (r) => {
          if (!r.confirm) return
          this.acting = true
          teacherApi.approveAffairsLeave(x.id, r.content || '')
            .then(() => { toast('已通过'); this.load() })
            .catch((e) => this._err(e, '审批'))
            .finally(() => { this.acting = false })
        }
      })
    },
    doReject(x) {
      if (this.acting) return
      uni.showModal({
        title: '驳回请假', editable: true, placeholderText: '请填写驳回原因（≥5 字）', content: '',
        success: (r) => {
          if (!r.confirm) return
          const reason = (r.content || '').trim()
          if (reason.length < 5) { toast('驳回原因至少 5 个字'); return }
          this.acting = true
          teacherApi.rejectAffairsLeave(x.id, reason)
            .then(() => { toast('已驳回'); this.load() })
            .catch((e) => this._err(e, '驳回'))
            .finally(() => { this.acting = false })
        }
      })
    },
    doReturn(x) {
      if (this.acting) return
      uni.showModal({
        title: '退回申请人重提', editable: true, placeholderText: '请填写退回原因（≥5 字）', content: '',
        success: (r) => {
          if (!r.confirm) return
          const reason = (r.content || '').trim()
          if (reason.length < 5) { toast('退回原因至少 5 个字'); return }
          this.acting = true
          teacherApi.returnAffairsLeave(x.id, reason)
            .then(() => { toast('已退回'); this.load() })
            .catch((e) => this._err(e, '退回'))
            .finally(() => { this.acting = false })
        }
      })
    },
    doCancelConfirm(x) {
      if (this.acting) return
      uni.showModal({
        title: '确认销假', editable: true, placeholderText: '可填写备注（可选）', content: '',
        success: (r) => {
          if (!r.confirm) return
          this.acting = true
          teacherApi.cancelConfirmAffairsLeave(x.id, 'CONFIRM', { note: r.content || '' })
            .then(() => { toast('已确认销假'); this.load() })
            .catch((e) => this._err(e, '销假确认'))
            .finally(() => { this.acting = false })
        }
      })
    },
    doCancelReturn(x) {
      if (this.acting) return
      uni.showModal({
        title: '销假退回', editable: true, placeholderText: '请填写退回原因（≥5 字，如返校证明与实际不符）', content: '',
        success: (r) => {
          if (!r.confirm) return
          const reason = (r.content || '').trim()
          if (reason.length < 5) { toast('退回原因至少 5 个字'); return }
          this.acting = true
          teacherApi.cancelConfirmAffairsLeave(x.id, 'RETURN', { reason })
            .then(() => { toast('已退回'); this.load() })
            .catch((e) => this._err(e, '销假退回'))
            .finally(() => { this.acting = false })
        }
      })
    },
    doProxyCancel(x) {
      if (this.acting) return
      uni.showModal({
        title: '代登记销假', editable: true,
        placeholderText: '请填写实际返校时间（如 2026-03-05 08:30），可附备注', content: '',
        success: (r) => {
          if (!r.confirm) return
          const v = (r.content || '').trim()
          if (!v) { toast('请填写实际返校时间'); return }
          this.acting = true
          teacherApi.proxyCancelAffairsLeave(x.id, v, '')
            .then(() => { toast('已登记'); this.load() })
            .catch((e) => this._err(e, '代登记销假'))
            .finally(() => { this.acting = false })
        }
      })
    },
    doExtension(x, action) {
      if (this.acting) return
      const reject = action === 'REJECT'
      uni.showModal({
        title: reject ? '续假驳回' : '续假通过',
        editable: reject, placeholderText: reject ? '请填写驳回原因（≥5 字）' : '',
        content: reject ? '' : '确认通过该续假申请？',
        success: (r) => {
          if (!r.confirm) return
          const reason = (r.content || '').trim()
          if (reject && reason.length < 5) { toast('驳回原因至少 5 个字'); return }
          this.acting = true
          teacherApi.extensionApproveAffairsLeave(x.id, action, reason)
            .then(() => { toast(reject ? '已驳回' : '已通过'); this.load() })
            .catch((e) => this._err(e, '续假审批'))
            .finally(() => { this.acting = false })
        }
      })
    },
    doOverdue(x) {
      if (this.acting) return
      uni.showActionSheet({
        itemList: OVERDUE_TYPES.map((t) => t.label),
        success: (res) => {
          const type = OVERDUE_TYPES[res.tapIndex]
          uni.showModal({
            title: type.label, editable: true, placeholderText: '请填写处置说明（≥5 字）', content: '',
            success: (r) => {
              if (!r.confirm) return
              const note = (r.content || '').trim()
              if (note.length < 5) { toast('处置说明至少 5 个字'); return }
              this.acting = true
              teacherApi.overdueHandleAffairsLeave(x.id, type.key, note)
                .then(() => { toast('已登记'); this.load() })
                .catch((e) => this._err(e, '逾期处置'))
                .finally(() => { this.acting = false })
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
