<template>
  <view class="page-wrap ins">
    <MobileGlobalState :state="pageState" @retry="load">
      <view class="page-pad stack">
        <view class="card">
          <text class="card-title">实习保险</text>
          <text v-if="info" class="ins__status">{{ info.statusLabel }}</text>
        </view>
        <view class="card stack">
          <view class="ins__field"><text class="ins__label">承保单位 *</text><input v-model="form.insurerName" class="ins__input" /></view>
          <view class="ins__field"><text class="ins__label">保单号 *</text><input v-model="form.policyNo" class="ins__input" /></view>
          <view class="ins__field"><text class="ins__label">险种</text><input v-model="form.coverageType" class="ins__input" placeholder="如 实习责任险" /></view>
          <view class="ins__field"><text class="ins__label">生效日期</text><input v-model="form.effectiveDate" class="ins__input" placeholder="YYYY-MM-DD" /></view>
          <view class="ins__field"><text class="ins__label">到期日期</text><input v-model="form.expiryDate" class="ins__input" placeholder="YYYY-MM-DD" /></view>
        </view>
      </view>
    </MobileGlobalState>
    <MobileSafeAreaBar>
      <button class="btn btn-primary flex-1" :disabled="submitting || info && info.status === 'VERIFIED'" @click="submit">
        {{ submitting ? '提交中…' : (info && info.status === 'VERIFIED' ? '已核验' : '提交保险信息') }}
      </button>
    </MobileSafeAreaBar>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { toast, back } from '@/utils/nav'
export default {
  data() {
    return {
      pageState: 'loading', submitting: false, info: null,
      form: { insurerName: '', policyNo: '', coverageType: '', effectiveDate: '', expiryDate: '' }
    }
  },
  onLoad() { this.load() },
  methods: {
    load() {
      this.pageState = 'loading'
      studentApi.getInternshipInsurance().then((d) => {
        this.info = d
        if (d && d.policyNo) {
          this.form = {
            insurerName: d.insurerName || '', policyNo: d.policyNo || '',
            coverageType: d.coverageType || '', effectiveDate: d.effectiveDate || '', expiryDate: d.expiryDate || ''
          }
        }
        this.pageState = 'ready'
      }).catch(() => { this.pageState = 'error' })
    },
    submit() {
      if (this.submitting) return
      this.submitting = true
      studentApi.submitInternshipInsurance(this.form).then(() => {
        toast('已提交，待学校核验')
        setTimeout(() => back(), 600)
      }).catch((e) => toast((e && e.message) || '提交失败')).finally(() => { this.submitting = false })
    }
  }
}
</script>

<style scoped>
.ins__status { display: block; margin-top: 6px; font-size: var(--font-size-sm); color: var(--text-secondary); }
.ins__field { margin-bottom: 12px; }
.ins__label { display: block; font-size: var(--font-size-sm); margin-bottom: 4px; }
.ins__input { border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: 10px 12px; font-size: var(--font-size-sm); }
</style>
