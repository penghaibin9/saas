<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="我的教材" back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="d">
        <view class="card tb__sum">
          <view class="tb__sum-item"><text class="tb__sum-num">{{ fmt(d.fees.totalDue) }}</text><text class="tb__sum-lb">应缴(元)</text></view>
          <view class="tb__sum-item"><text class="tb__sum-num">{{ fmt(d.fees.totalPaid) }}</text><text class="tb__sum-lb">已缴</text></view>
          <view class="tb__sum-item"><text class="tb__sum-num tb__unpaid">{{ fmt(d.fees.unpaid) }}</text><text class="tb__sum-lb">待缴</text></view>
        </view>

        <view class="section-head"><text class="section-head__title">教材领用</text></view>
        <view class="list-group" v-if="d.distributions && d.distributions.length">
          <view v-for="r in d.distributions" :key="r.recordId" class="list-row tb__item">
            <view class="flex-1">
              <text class="t-md">{{ r.textbookName }}<text v-if="r.qty > 1"> ×{{ r.qty }}</text></text>
              <text class="tb__sub">{{ statusText(r.status) }}<text v-if="r.receivedAt"> · {{ r.receivedAt }}</text></text>
            </view>
            <button v-if="canSign(r)" class="btn btn-sm btn-primary" :disabled="signing === r.recordId" @click="sign(r)">
              {{ signing === r.recordId ? '签收中…' : '签收' }}
            </button>
            <MobileStatusTag v-else :status="r.status" />
          </view>
        </view>
        <MobileGlobalState v-else state="empty" title="暂无教材记录" description="学校完成教材征订发放后，这里出现你的领用与费用。" />

        <view class="section-head" v-if="d.fees.items && d.fees.items.length"><text class="section-head__title">教材费用明细</text></view>
        <view class="list-group" v-if="d.fees.items && d.fees.items.length">
          <view v-for="f in d.fees.items" :key="f.feeId" class="list-row tb__item">
            <view class="flex-1">
              <text class="t-md">{{ f.textbookName }}</text>
              <text class="tb__sub">应缴 {{ fmt(f.amount) }} 元 · 已缴 {{ fmt(f.paidAmount) }} 元</text>
            </view>
            <MobileStatusTag :status="f.status" />
          </view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { createSubmitLock, normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

const signLock = createSubmitLock(1500)
const DIST_STATUS = { PENDING: '待签收', RECEIVED: '已领取', EXCLUDED: '非在籍(不发放)' }

export default {
  data() {
    return { d: null, state: 'loading', signing: '' }
  },
  onLoad() { this.load() },
  methods: {
    fmt(v) { return (Number(v) || 0).toFixed(2) },
    statusText(s) { return DIST_STATUS[s] || s },
    canSign(r) { return r.status === 'PENDING' },
    load() {
      this.state = 'loading'
      studentApi.getMyTextbook().then((d) => { this.d = d; this.state = 'ready' })
        .catch(() => { this.state = 'error' })
    },
    sign(r) {
      if (this.signing) return
      this.signing = r.recordId
      signLock.run(() => studentApi.signTextbook(r.recordId))
        .then(() => { uni.showToast({ title: '签收成功', icon: 'success' }); this.load() })
        .catch((e) => {
          if (e && e.code === 'LOCKED') return
          toast(e && e.biz ? normalizeError(e).text : '签收失败，请稍后重试')
        }).finally(() => { this.signing = '' })
    }
  }
}
</script>

<style scoped>
.tb__sum { display: flex; justify-content: space-around; padding: var(--space-3) 0; }
.tb__sum-item { display: flex; flex-direction: column; align-items: center; gap: 4px; }
.tb__sum-num { font-size: var(--font-size-lg); font-weight: 600; color: var(--text-primary); }
.tb__unpaid { color: var(--danger-600); }
.tb__sum-lb { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.tb__item { align-items: center; }
.tb__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.btn-sm { height: 32px; line-height: 32px; padding: 0 var(--space-3); font-size: var(--font-size-sm); }
</style>
