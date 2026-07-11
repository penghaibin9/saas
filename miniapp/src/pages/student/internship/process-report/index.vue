<template>
  <view class="page-wrap pr">
    <MobileGlobalState :state="pageState" @retry="load">
      <view class="page-pad stack" v-if="loaded">
        <view class="card">
          <text class="card-title">{{ typeLabel }}</text>
          <text class="pr__hint">提交后由指导教师在 PC 端批阅，退回后可修改重交。</text>
        </view>
        <view class="card stack">
          <view v-if="reportType !== 'SUMMARY'" class="pr__field">
            <text class="pr__label">{{ periodLabel }} <text class="pr__req">*</text></text>
            <input v-model="form.periodKey" class="pr__input" :placeholder="periodPlaceholder" />
          </view>
          <view class="pr__field">
            <text class="pr__label">正文 <text class="pr__req">*</text></text>
            <textarea v-model="form.content" class="pr__textarea" maxlength="8000" :placeholder="contentPlaceholder" />
            <text class="pr__count">{{ (form.content || '').length }} 字</text>
          </view>
        </view>
      </view>
    </MobileGlobalState>
    <MobileSafeAreaBar v-if="loaded">
      <button class="btn btn-primary flex-1" :disabled="submitting" @click="submit">{{ submitting ? '提交中…' : '提交' + typeLabel }}</button>
    </MobileSafeAreaBar>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { toast, back } from '@/utils/nav'

const TYPE_LABEL = { DAILY: '日报', MONTHLY: '月报', SUMMARY: '实习总结' }

export default {
  data() {
    return {
      pageState: 'loading', loaded: false, submitting: false,
      reportType: 'DAILY',
      form: { periodKey: '', content: '' }
    }
  },
  computed: {
    typeLabel() { return TYPE_LABEL[this.reportType] || '过程报告' },
    periodLabel() { return this.reportType === 'DAILY' ? '日期' : '月份' },
    periodPlaceholder() {
      return this.reportType === 'DAILY' ? '如 2026-07-10' : '如 2026-07'
    },
    contentPlaceholder() {
      const min = { DAILY: 30, MONTHLY: 100, SUMMARY: 300 }[this.reportType] || 30
      return `请填写${this.typeLabel}正文（至少 ${min} 字）`
    }
  },
  onLoad(q) {
    const t = (q.type || 'daily').toUpperCase()
    this.reportType = t === 'MONTHLY' ? 'MONTHLY' : t === 'SUMMARY' ? 'SUMMARY' : 'DAILY'
    uni.setNavigationBarTitle({ title: '填写' + this.typeLabel })
    if (this.reportType === 'DAILY') {
      const d = new Date()
      this.form.periodKey = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
    } else if (this.reportType === 'MONTHLY') {
      const d = new Date()
      this.form.periodKey = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
    }
    this.loaded = true
    this.pageState = 'ready'
  },
  methods: {
    load() { this.pageState = 'ready' },
    submit() {
      if (this.submitting) return
      this.submitting = true
      studentApi.submitProcessReport({
        reportType: this.reportType,
        periodKey: this.reportType === 'SUMMARY' ? 'FINAL' : this.form.periodKey,
        content: this.form.content
      }).then((res) => {
        toast((res && res.message) || '提交成功')
        setTimeout(() => back(), 600)
      }).catch((e) => {
        toast((e && e.message) || '提交失败')
      }).finally(() => { this.submitting = false })
    }
  }
}
</script>

<style scoped>
.pr__hint { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: var(--space-2); }
.pr__field { display: flex; flex-direction: column; gap: 6px; }
.pr__label { font-size: var(--font-size-sm); color: var(--text-secondary); }
.pr__req { color: var(--danger-500); }
.pr__input { border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: 10px 12px; font-size: var(--font-size-sm); }
.pr__textarea { border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: 10px 12px; min-height: 160px; font-size: var(--font-size-sm); width: 100%; box-sizing: border-box; }
.pr__count { font-size: var(--font-size-xs); color: var(--text-tertiary); text-align: right; }
</style>
