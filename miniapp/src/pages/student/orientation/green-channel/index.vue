<template>
  <view class="page-wrap">
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="o">
        <!-- 已提交/已处理：只读展示状态 -->
        <view v-if="o.greenChannelStatus !== 'NOT_APPLIED'" class="card gc__status">
          <MobileStatusTag :status="o.greenChannelStatus" />
          <text class="gc__status-tx">{{ statusText }}</text>
        </view>

        <!-- 未申请：可提交表单 -->
        <template v-else>
          <view class="card gc__form">
            <text class="card-title">困难类型</text>
            <view class="gc__types">
              <view
                v-for="t in typeOptions"
                :key="t"
                class="gc__type"
                :class="{ 'is-on': applyType === t }"
                @click="applyType = t"
              >{{ t }}</view>
            </view>

            <view class="gc__field">
              <text class="gc__label">申请金额</text>
              <input class="gc__input" v-model="amount" type="digit" placeholder="请输入申请缓缴/减免金额（元）" placeholder-class="gc__ph" />
            </view>

            <view class="gc__field gc__field--top">
              <text class="gc__label">情况说明</text>
              <textarea class="gc__textarea" v-model="remark" :maxlength="200" placeholder="简述困难情况（选填）" placeholder-class="gc__ph" />
            </view>

            <view class="gc__field">
              <text class="gc__label">证明材料</text>
              <view class="gc__upload" @click="pickFile">
                <text class="gc__upload-icon">！</text>
                <text class="gc__upload-txt">附件上传暂未开放，请携带纸质材料至资助中心窗口</text>
              </view>
            </view>
          </view>

          <MobileInlineAlert type="info" description="提交后由辅导员/资助中心审核，审核结果将通过消息通知你。" />
        </template>
      </view>
    </MobileGlobalState>

    <MobileSafeAreaBar v-if="o && o.greenChannelStatus === 'NOT_APPLIED'">
      <button class="btn btn-primary flex-1" :disabled="submitting" @click="submit">{{ submitting ? '提交中…' : '提交申请' }}</button>
    </MobileSafeAreaBar>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { createSubmitLock, normalizeError } from '@/services/request'
import { toast, back } from '@/utils/nav'

const submitLock = createSubmitLock(1500)
const TYPE_OPTIONS = ['助学贷款', '缓缴学费', '减免学费', '分期缴纳']
const STATUS_TEXT = {
  SUBMITTED: '申请已提交，等待辅导员/资助中心审核。',
  REVIEWING: '申请正在审核中，请耐心等待。',
  APPROVED: '申请已通过，缴费状态已更新为绿色通道。',
  RETURNED: '申请被退回，请补充材料后联系辅导员重新提交。',
  REJECTED: '申请未通过，如有疑问请联系资助中心。',
  WITHDRAWN: '申请已撤回。'
}

export default {
  data() {
    return {
      o: null, state: 'loading', typeOptions: TYPE_OPTIONS,
      applyType: TYPE_OPTIONS[0], amount: '', remark: '', submitting: false
    }
  },
  onLoad() { this.load() },
  computed: {
    statusText() {
      return (this.o && STATUS_TEXT[this.o.greenChannelStatus]) || ''
    }
  },
  methods: {
    load() {
      this.state = 'loading'
      studentApi.getOrientation().then((d) => {
        this.o = d
        this.state = 'ready'
      }).catch(() => { this.state = 'error' })
    },
    pickFile() {
      toast('附件上传暂未开放，请携带纸质材料至资助中心窗口')
    },
    submit() {
      if (this.submitting) return
      this.submitting = true
      submitLock.run(() => studentApi.submitOrientationGreenChannel({
        applyType: this.applyType, applyAmount: Number(this.amount) || 0, remark: this.remark.trim()
      })).then(() => {
        uni.showToast({ title: '提交成功', icon: 'success' })
        setTimeout(() => back(), 700)
      }).catch((e) => {
        if (e && e.code === 'LOCKED') return
        toast(e && e.biz ? normalizeError(e).text : '网络异常，提交未成功，请稍后重试')
      }).finally(() => { this.submitting = false })
    }
  }
}
</script>

<style scoped>
.gc__status { display: flex; align-items: center; gap: var(--space-3); }
.gc__status-tx { flex: 1; font-size: var(--font-size-base); color: var(--text-secondary); line-height: 1.6; }
.gc__types { display: flex; flex-wrap: wrap; gap: var(--space-2); margin: var(--space-3) 0 var(--space-2); }
.gc__type { padding: 8px 16px; border-radius: var(--radius-full); background: var(--gray-100); color: var(--text-secondary); font-size: var(--font-size-sm); }
.gc__type.is-on { background: var(--brand-primary); color: #fff; }
.gc__field { display: flex; align-items: center; min-height: 48px; border-top: 1px solid var(--border-light); margin-top: var(--space-2); padding-top: var(--space-2); }
.gc__field--top { align-items: flex-start; }
.gc__label { width: 80px; flex-shrink: 0; font-size: var(--font-size-base); color: var(--text-secondary); }
.gc__input { flex: 1; font-size: var(--font-size-base); color: var(--text-primary); text-align: right; }
.gc__textarea { flex: 1; min-height: 72px; font-size: var(--font-size-base); color: var(--text-primary); line-height: 1.6; }
.gc__ph { color: var(--text-tertiary); }
.gc__upload { flex: 1; display: flex; align-items: center; gap: var(--space-2); border: 1px dashed var(--border-dark); border-radius: var(--radius-md); padding: var(--space-3); color: var(--text-tertiary); background: var(--gray-50); }
.gc__upload-icon { font-size: var(--font-size-lg); }
.gc__upload-txt { font-size: var(--font-size-sm); }
</style>
