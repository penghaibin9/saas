<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="违纪申诉" back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="d">
        <view class="list-group" v-if="(d.items || []).length">
          <view v-for="x in d.items" :key="x.caseId" class="list-row col">
            <view class="row-between">
              <text class="flex-1 t-md">{{ x.discTypeLabel || x.discType || '处分' }}</text>
              <MobileStatusTag :status="x.appealStatus ? appealText(x.appealStatus) : '可申诉'" />
            </view>
            <text v-if="x.effectiveAt" class="hint">生效时间：{{ (x.effectiveAt || '').slice(0, 10) }}</text>
            <text v-if="x.appealReviewOpinion" class="hint">复核意见：{{ x.appealReviewOpinion }}</text>
            <template v-if="x.canAppeal">
              <textarea class="ta" v-model="reasons[x.caseId]" placeholder="申辩理由（≥5字）" />
              <button class="btn" :disabled="busy" @click="appeal(x)">提交申辩</button>
            </template>
            <text v-else-if="x.appealStatus" class="hint">{{ appealText(x.appealStatus) }}</text>
          </view>
        </view>
        <MobileGlobalState v-else state="empty" title="暂无生效处分" description="如有疑问请联系辅导员。" />
        <text v-if="d.detailNote" class="hint foot">{{ d.detailNote }}</text>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { affairsDisciplineAppeal } from '@/services/realApi'

const APPEAL_L = {
  SUBMITTED: '申诉已提交', REVIEWING: '复核中',
  UPHELD: '维持原处分', REVISED: '处分已变更', REVOKED: '处分已撤销'
}

export default {
  data() { return { d: null, state: 'loading', busy: false, reasons: {} } },
  onLoad() { this.load() },
  methods: {
    appealText(s) { return APPEAL_L[s] || s },
    load() {
      this.state = 'loading'
      studentApi.getMyDiscipline().then((d) => { this.d = d; this.state = 'ready' })
        .catch(() => { this.state = 'error' })
    },
    async appeal(x) {
      const reason = (this.reasons[x.caseId] || '').trim()
      if (reason.length < 5) {
        uni.showToast({ title: '申辩理由至少5字', icon: 'none' })
        return
      }
      this.busy = true
      try {
        await affairsDisciplineAppeal({ caseId: x.caseId, reason })
        uni.showToast({ title: '申辩已提交', icon: 'success' })
        this.reasons[x.caseId] = ''
        this.load()
      } catch (e) {
        uni.showToast({ title: (e && e.message) || '提交失败', icon: 'none' })
      } finally {
        this.busy = false
      }
    }
  }
}
</script>

<style scoped>
.col { flex-direction: column; align-items: stretch; gap: 8px; }
.row-between { display: flex; align-items: center; justify-content: space-between; gap: 8px; width: 100%; }
.hint { font-size: 12px; color: #6b7280; }
.foot { display: block; margin-top: 12px; }
.ta { width: 100%; min-height: 72px; border: 1px solid #e5e7eb; border-radius: 8px; padding: 8px; font-size: 13px; box-sizing: border-box; }
.btn { margin-top: 4px; background: #2563eb; color: #fff; border: none; border-radius: 8px; padding: 8px 12px; font-size: 13px; }
</style>
