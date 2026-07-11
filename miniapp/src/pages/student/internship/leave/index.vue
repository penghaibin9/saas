<template>
  <view class="page-wrap lv">
    <MobileGlobalState :state="pageState" @retry="loadList">
      <view class="page-pad stack">
        <view class="card lv__head">
          <text class="card-title">实习请假</text>
          <text class="lv__hint">请假需指导教师审批，审批期间请勿离岗。</text>
        </view>
        <view v-for="item in list" :key="item.id" class="card lv__item">
          <view class="row-between">
            <text class="lv__range">{{ item.startDate }} ~ {{ item.endDate }}</text>
            <MobileStatusTag :status="item.status" />
          </view>
          <text class="lv__days">{{ item.days }} 天 · {{ item.leaveTypeLabel || item.leaveType }}</text>
          <text class="lv__reason">{{ item.reason }}</text>
          <button v-if="item.status === 'PENDING'" class="btn btn-ghost lv__withdraw" @click="withdraw(item)">撤回</button>
        </view>
        <MobileInlineAlert v-if="!list.length" type="info" description="暂无请假记录，可点击下方按钮新建申请。" />
      </view>
    </MobileGlobalState>
    <MobileSafeAreaBar>
      <button class="btn btn-primary flex-1" @click="openApply">新建请假申请</button>
    </MobileSafeAreaBar>

    <view v-if="formVisible" class="lv__mask" @click.self="formVisible = false">
      <view class="lv__sheet card">
        <text class="card-title">请假申请</text>
        <view class="lv__field">
          <text class="lv__label">开始日期 <text class="lv__req">*</text></text>
          <picker mode="date" :value="form.startDate" @change="onStart">
            <view class="lv__picker">{{ form.startDate || '请选择' }}</view>
          </picker>
        </view>
        <view class="lv__field">
          <text class="lv__label">结束日期 <text class="lv__req">*</text></text>
          <picker mode="date" :value="form.endDate" @change="onEnd">
            <view class="lv__picker">{{ form.endDate || '请选择' }}</view>
          </picker>
        </view>
        <view class="lv__field">
          <text class="lv__label">请假事由 <text class="lv__req">*</text></text>
          <textarea v-model="form.reason" class="lv__textarea" maxlength="300" placeholder="说明请假原因（不少于2字）" />
        </view>
        <view class="lv__actions">
          <button class="btn btn-ghost flex-1" :disabled="submitting" @click="formVisible = false">取消</button>
          <button class="btn btn-primary flex-1" :disabled="submitting" @click="submit">{{ submitting ? '提交中…' : '提交申请' }}</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { toast } from '@/utils/nav'

export default {
  data() {
    return {
      list: [], pageState: 'loading', formVisible: false, submitting: false,
      form: { startDate: '', endDate: '', reason: '' }
    }
  },
  onLoad() { this.loadList() },
  methods: {
    loadList() {
      this.pageState = 'loading'
      studentApi.getInternshipLeaves().then((rows) => {
        this.list = rows || []
        this.pageState = 'ready'
      }).catch(() => { this.pageState = 'error' })
    },
    openApply() {
      this.form = { startDate: '', endDate: '', reason: '' }
      this.formVisible = true
    },
    onStart(e) { this.form.startDate = e.detail.value },
    onEnd(e) { this.form.endDate = e.detail.value },
    submit() {
      if (this.submitting) return
      if (!this.form.startDate || !this.form.endDate || this.form.reason.trim().length < 2) {
        return toast('请填写起止日期与事由（不少于2字）')
      }
      this.submitting = true
      studentApi.applyInternshipLeave(this.form).then(() => {
        toast('请假申请已提交')
        this.formVisible = false
        this.loadList()
      }).catch((e) => {
        toast((e && e.message) || '提交失败，请稍后重试')
      }).finally(() => { this.submitting = false })
    },
    withdraw(item) {
      uni.showModal({
        title: '撤回请假',
        content: '确认撤回该待审批请假申请？',
        success: (r) => {
          if (!r.confirm) return
          studentApi.withdrawInternshipLeave(item.id).then(() => {
            toast('已撤回')
            this.loadList()
          }).catch((e) => toast((e && e.message) || '撤回失败'))
        }
      })
    }
  }
}
</script>

<style scoped>
.lv__hint { display: block; margin-top: 6px; font-size: var(--font-size-sm); color: var(--text-secondary); }
.lv__item { margin-bottom: 10px; }
.lv__range { font-weight: var(--font-weight-medium); }
.lv__days { display: block; margin-top: 4px; font-size: var(--font-size-sm); color: var(--text-secondary); }
.lv__reason { display: block; margin-top: 6px; font-size: var(--font-size-sm); color: var(--text-primary); }
.lv__withdraw { margin-top: 10px; }
.lv__mask { position: fixed; inset: 0; background: rgba(0,0,0,.45); z-index: 100; display: flex; align-items: flex-end; }
.lv__sheet { width: 100%; border-radius: 16px 16px 0 0; padding: 16px; box-sizing: border-box; }
.lv__field { margin-top: 12px; }
.lv__label { display: block; font-size: var(--font-size-sm); margin-bottom: 6px; }
.lv__req { color: var(--danger-600); }
.lv__picker { padding: 10px 12px; background: var(--gray-50); border-radius: var(--radius-md); font-size: var(--font-size-sm); }
.lv__textarea { width: 100%; min-height: 80px; padding: 10px; box-sizing: border-box; border: 1px solid var(--border-base); border-radius: var(--radius-md); font-size: var(--font-size-sm); }
.lv__actions { display: flex; gap: 10px; margin-top: 16px; }
</style>
