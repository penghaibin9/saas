<template>
  <view class="page-wrap lv">
    <MobileGlobalState :state="pageState" @retry="loadList">
      <view class="page-pad stack">
        <view class="card lv__head">
          <text class="card-title">补卡申请</text>
          <text class="lv__hint">对缺卡日期发起补录，需指导教师审批通过后才会记入出勤。</text>
        </view>
        <view v-for="item in list" :key="item.id" class="card lv__item">
          <view class="row-between">
            <text class="lv__range">{{ item.checkinDate }}</text>
            <MobileStatusTag :status="item.status" />
          </view>
          <text class="lv__days">{{ item.makeupTypeLabel || item.makeupType }}</text>
          <text class="lv__reason">{{ item.reason }}</text>
          <button v-if="item.status === 'PENDING'" class="btn btn-ghost lv__withdraw" @click="withdraw(item)">撤回</button>
        </view>
        <MobileInlineAlert v-if="!list.length" type="info" description="暂无补卡申请，可点击下方按钮新建。" />
      </view>
    </MobileGlobalState>
    <MobileSafeAreaBar>
      <button class="btn btn-primary flex-1" @click="openApply">新建补卡申请</button>
    </MobileSafeAreaBar>

    <view v-if="formVisible" class="lv__mask" @click.self="formVisible = false">
      <view class="lv__sheet card">
        <text class="card-title">补卡申请</text>
        <view class="lv__field">
          <text class="lv__label">缺卡日期 <text class="lv__req">*</text></text>
          <picker mode="date" :value="form.checkinDate" @change="onDate">
            <view class="lv__picker">{{ form.checkinDate || '请选择' }}</view>
          </picker>
        </view>
        <view class="lv__field">
          <text class="lv__label">补卡事由 <text class="lv__req">*</text></text>
          <textarea v-model="form.reason" class="lv__textarea" maxlength="300" placeholder="说明缺卡原因（不少于2字）" />
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
      form: { checkinDate: '', reason: '' }
    }
  },
  onLoad() { this.loadList() },
  methods: {
    loadList() {
      this.pageState = 'loading'
      studentApi.getInternshipMakeups().then((rows) => {
        this.list = (rows && rows.items) || rows || []
        this.pageState = 'ready'
      }).catch(() => { this.pageState = 'error' })
    },
    openApply() {
      this.form = { checkinDate: '', reason: '' }
      this.formVisible = true
    },
    onDate(e) { this.form.checkinDate = e.detail.value },
    submit() {
      if (this.submitting) return
      if (!this.form.checkinDate || this.form.reason.trim().length < 2) {
        return toast('请填写缺卡日期与事由（不少于2字）')
      }
      this.submitting = true
      studentApi.applyInternshipMakeup(this.form).then(() => {
        toast('补卡申请已提交')
        this.formVisible = false
        this.loadList()
      }).catch((e) => {
        toast((e && e.message) || '提交失败，请稍后重试')
      }).finally(() => { this.submitting = false })
    },
    withdraw(item) {
      studentApi.withdrawInternshipMakeup(item.id).then(() => {
        toast('已撤回'); this.loadList()
      }).catch((e) => toast((e && e.message) || '撤回失败'))
    }
  }
}
</script>

<style scoped>
.lv__hint { display: block; margin-top: 8rpx; color: var(--t3); font-size: 24rpx; line-height: 1.5; }
.lv__item { margin-bottom: 16rpx; }
.lv__range { font-weight: 600; color: var(--t1); }
.lv__days { display: block; margin-top: 8rpx; color: var(--t3); font-size: 24rpx; }
.lv__reason { display: block; margin-top: 8rpx; color: var(--t2); font-size: 26rpx; line-height: 1.5; }
.lv__withdraw { margin-top: 16rpx; }
.lv__mask { position: fixed; inset: 0; background: rgba(0,0,0,.45); z-index: 99; display: flex; align-items: flex-end; }
.lv__sheet { width: 100%; border-radius: 24rpx 24rpx 0 0; padding: 32rpx; }
.lv__field { margin-top: 24rpx; }
.lv__label { display: block; margin-bottom: 8rpx; color: var(--t2); font-size: 26rpx; }
.lv__req { color: #c0392b; }
.lv__picker, .lv__textarea { background: var(--bg-soft, #f5f6f8); border-radius: 12rpx; padding: 20rpx; }
.lv__textarea { width: 100%; min-height: 160rpx; box-sizing: border-box; }
.lv__actions { display: flex; gap: 16rpx; margin-top: 32rpx; }
</style>
