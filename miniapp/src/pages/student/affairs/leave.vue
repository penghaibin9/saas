<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="我的请假" back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="items">
        <MobileGlobalState v-if="!items.length" state="empty" title="暂无请假记录" description="发起请假后记录会显示在这里。" />
        <view class="list-group" v-else>
          <view v-for="x in items" :key="x.leaveId" class="list-row lv__row">
            <view class="flex-1">
              <text class="t-md">{{ typeText(x.leaveType) }}</text>
              <text class="lv__time">{{ (x.startTime || '').slice(0, 10) }} 至 {{ (x.endTime || '').slice(0, 10) }} · {{ x.days }} 天</text>
              <text class="lv__reason" v-if="x.reason">{{ x.reason }}</text>
              <text class="lv__reason" v-if="x.returnReason || x.rejectReason">意见：{{ x.returnReason || x.rejectReason }}</text>
            </view>
            <MobileStatusTag :label="statusText(x.status)" :type="badgeType(x.status)" />
            <button
              v-if="x.canResubmit"
              class="btn btn-ghost lv__resubmit"
              @click="resubmit(x)"
            >重新提交</button>
            <button
              v-if="x.canCancel"
              class="btn btn-ghost lv__resubmit"
              @click="cancelLeave(x)"
            >申请销假</button>
            <button
              v-if="x.canExtend"
              class="btn btn-ghost lv__resubmit"
              @click="openExtend(x)"
            >申请续假</button>
          </view>
        </view>
      </view>
    </MobileGlobalState>

    <MobileSafeAreaBar>
      <button class="btn btn-primary flex-1" @click="openApply">新建请假</button>
    </MobileSafeAreaBar>

    <view v-if="formVisible" class="lv__mask" @click.self="formVisible = false">
      <view class="lv__sheet card">
        <text class="card-title">请假申请</text>
        <view class="lv__field">
          <text class="lv__label">请假类型 <text class="lv__req">*</text></text>
          <picker mode="selector" :range="typeOptions" range-key="label" :value="typeIndex" @change="onType">
            <view class="lv__picker">{{ typeOptions[typeIndex].label }}</view>
          </picker>
        </view>
        <view class="lv__field">
          <text class="lv__label">开始日期 <text class="lv__req">*</text></text>
          <picker mode="date" :value="form.startTime" @change="onStart">
            <view class="lv__picker">{{ form.startTime || '请选择' }}</view>
          </picker>
        </view>
        <view class="lv__field">
          <text class="lv__label">结束日期 <text class="lv__req">*</text></text>
          <picker mode="date" :value="form.endTime" @change="onEnd">
            <view class="lv__picker">{{ form.endTime || '请选择' }}</view>
          </picker>
        </view>
        <view class="lv__field">
          <text class="lv__label">请假事由 <text class="lv__req">*</text></text>
          <textarea v-model="form.reason" class="lv__textarea" maxlength="300" placeholder="说明请假原因（不少于5字）" />
        </view>
        <view class="lv__actions">
          <button class="btn btn-ghost flex-1" :disabled="submitting" @click="formVisible = false">取消</button>
          <button class="btn btn-primary flex-1" :disabled="submitting" @click="submit">{{ submitting ? '提交中…' : '提交申请' }}</button>
        </view>
      </view>
    </view>

    <view v-if="extendVisible" class="lv__mask" @click.self="extendVisible = false">
      <view class="lv__sheet card">
        <text class="card-title">续假申请</text>
        <text class="lv__time">原结束：{{ (extendTarget.endTime || '').slice(0, 10) || '—' }}</text>
        <view class="lv__field">
          <text class="lv__label">新结束日期 <text class="lv__req">*</text></text>
          <picker mode="date" :value="extendForm.newEndTime" @change="onExtendEnd">
            <view class="lv__picker">{{ extendForm.newEndTime || '请选择' }}</view>
          </picker>
        </view>
        <view class="lv__field">
          <text class="lv__label">续假事由 <text class="lv__req">*</text></text>
          <textarea v-model="extendForm.reason" class="lv__textarea" maxlength="300" placeholder="说明续假原因（不少于5字）" />
        </view>
        <view class="lv__actions">
          <button class="btn btn-ghost flex-1" :disabled="submitting" @click="extendVisible = false">取消</button>
          <button class="btn btn-primary flex-1" :disabled="submitting" @click="submitExtend">{{ submitting ? '提交中…' : '提交续假' }}</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { createSubmitLock, normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

const submitLock = createSubmitLock(1500)
const TYPE = { SICK: '病假', PERSONAL: '事假', GOOUT: '外出', OTHER: '其他' }
const STATUS = {
  COUNSELOR_REVIEW: '辅导员审批', COLLEGE_REVIEW: '学院审批', STUDENT_AFFAIRS_REVIEW: '学工处审批',
  APPROVED: '已通过', REJECTED: '已驳回', RETURNED: '已退回', WAIT_CANCEL_LEAVE: '待销假', CLOSED: '已销假',
  OVERDUE: '已逾期', EXTENSION_REVIEW: '续假审批中', PENDING_REVIEW: '待审批'
}

export default {
  data() {
    return {
      items: null,
      state: 'loading',
      formVisible: false,
      extendVisible: false,
      extendTarget: {},
      extendForm: { newEndTime: '', reason: '' },
      submitting: false,
      typeIndex: 0,
      typeOptions: [
        { label: '事假', value: 'PERSONAL' },
        { label: '病假', value: 'SICK' },
        { label: '外出', value: 'GOOUT' }
      ],
      form: { startTime: '', endTime: '', reason: '' }
    }
  },
  onLoad() { this.load() },
  methods: {
    load() {
      this.state = 'loading'
      studentApi.getMyLeaves().then((d) => {
        this.items = (d && d.items) || []
        this.state = 'ready'
      }).catch(() => { this.state = 'error' })
    },
    openApply() {
      const d = new Date()
      const pad = (n) => (n < 10 ? '0' + n : '' + n)
      const today = d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate())
      this.typeIndex = 0
      this.form = { startTime: today, endTime: today, reason: '' }
      this.formVisible = true
    },
    openExtend(item) {
      const end = (item.endTime || '').slice(0, 10)
      this.extendTarget = item
      this.extendForm = { newEndTime: end, reason: '' }
      this.extendVisible = true
    },
    onType(e) { this.typeIndex = Number(e.detail.value) },
    onStart(e) { this.form.startTime = e.detail.value },
    onEnd(e) { this.form.endTime = e.detail.value },
    onExtendEnd(e) { this.extendForm.newEndTime = e.detail.value },
    submit() {
      if (this.submitting || !submitLock.acquire()) return
      if (!this.form.startTime || !this.form.endTime || this.form.reason.trim().length < 5) {
        submitLock.release()
        return toast('请填写起止日期与事由（不少于5字）')
      }
      this.submitting = true
      studentApi.submitServiceApply({
        serviceKey: 'LEAVE',
        leaveType: this.typeOptions[this.typeIndex].value,
        startTime: this.form.startTime,
        endTime: this.form.endTime,
        reason: this.form.reason.trim()
      }).then(() => {
        toast('请假已提交，等待辅导员审批')
        this.formVisible = false
        this.load()
      }).catch((e) => {
        const n = normalizeError(e)
        toast(n.text || (e && e.message) || '提交失败')
      }).finally(() => {
        this.submitting = false
        submitLock.release()
      })
    },
    submitExtend() {
      if (this.submitting || !submitLock.acquire()) return
      if (!this.extendForm.newEndTime || this.extendForm.reason.trim().length < 5) {
        submitLock.release()
        return toast('请填写新结束日期与续假事由（不少于5字）')
      }
      this.submitting = true
      studentApi.extendLeave(this.extendTarget.leaveId, {
        newEndTime: this.extendForm.newEndTime,
        reason: this.extendForm.reason.trim()
      }).then(() => {
        toast('续假已提交，等待辅导员审批')
        this.extendVisible = false
        this.load()
      }).catch((e) => {
        const n = normalizeError(e)
        toast(n.text || (e && e.message) || '续假失败')
      }).finally(() => {
        this.submitting = false
        submitLock.release()
      })
    },
    typeText(t) { return TYPE[t] || t },
    statusText(s) { return STATUS[s] || s },
    badgeType(s) {
      if (['APPROVED', 'CLOSED'].includes(s)) return 'success'
      if (['REJECTED', 'OVERDUE'].includes(s)) return 'danger'
      return 'warning'
    },
    resubmit(item) {
      if (this.submitting || !submitLock.acquire()) return
      this.submitting = true
      studentApi.resubmitLeave(item.leaveId, {
        reason: (item.reason || '') + '（已按退回意见补充说明）'
      }).then(() => {
        toast('已重新提交，等待辅导员审批')
        this.load()
      }).catch((e) => {
        const n = normalizeError(e)
        toast(n.text || (e && e.message) || '重新提交失败')
      }).finally(() => {
        this.submitting = false
        submitLock.release()
      })
    },
    cancelLeave(item) {
      if (this.submitting || !submitLock.acquire()) return
      this.submitting = true
      studentApi.cancelLeave(item.leaveId, { proofNote: '学生本人申请销假' }).then(() => {
        toast('销假已提交，等待辅导员确认')
        this.load()
      }).catch((e) => {
        const n = normalizeError(e)
        toast(n.text || (e && e.message) || '销假失败')
      }).finally(() => {
        this.submitting = false
        submitLock.release()
      })
    }
  }
}
</script>

<style scoped>
.lv__row { align-items: flex-start; }
.lv__time { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin-top: 2px; }
.lv__reason { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 4px; }
.lv__mask {
  position: fixed; inset: 0; background: rgba(15, 23, 42, 0.45);
  display: flex; align-items: flex-end; z-index: 1000;
}
.lv__sheet { width: 100%; border-radius: 16px 16px 0 0; padding: 16px; }
.lv__field { margin-top: 12px; }
.lv__label { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin-bottom: 6px; }
.lv__req { color: #dc2626; }
.lv__picker, .lv__textarea {
  width: 100%; box-sizing: border-box; border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 8px; padding: 10px 12px; background: #fff; font-size: var(--font-size-md);
}
.lv__textarea { min-height: 88px; }
.lv__actions { display: flex; gap: 12px; margin-top: 16px; }
.lv__resubmit { margin-top: 8px; font-size: var(--font-size-sm); }
</style>
