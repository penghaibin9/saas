<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="奖助申请" back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="d">
        <view class="list-group" v-if="d.items.length">
          <view v-for="x in d.items" :key="x.applicationId" class="list-row col">
            <view class="row-between">
              <text class="flex-1 t-md">{{ typeLabel(x.projectType) }}</text>
              <MobileStatusTag :status="x.statusLabel || x.status" />
            </view>
            <text v-if="x.returnReason" class="hint warn">退回/驳回：{{ x.returnReason }}</text>
            <text v-if="x.hasPendingAppeal" class="hint">申诉处理中，请等待复核</text>
            <template v-if="x.canAppeal">
              <textarea class="ta" v-model="reasons[x.applicationId]" placeholder="对公示结果有异议，请填写申诉理由（≥5字）" />
              <button class="btn" :disabled="busy" @click="appeal(x)">提交公示申诉</button>
            </template>
          </view>
        </view>
        <MobileGlobalState v-else state="empty" title="暂无奖助申请记录" description="如需申请请联系辅导员或关注学院通知。" />
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { affairsFundingAppeal } from '@/services/realApi'

export default {
  data() { return { d: null, state: 'loading', busy: false, reasons: {} } },
  onLoad() { this.load() },
  methods: {
    typeLabel(t) {
      return ({ SCHOLARSHIP: '奖学金', GRANT: '助学金', WORK_STUDY: '勤工助学', LOAN: '助学贷款', SUBSIDY: '困难补助' })[t] || t || '奖助'
    },
    load() {
      this.state = 'loading'
      studentApi.getMyFunding().then((d) => { this.d = d; this.state = 'ready' })
        .catch(() => { this.state = 'error' })
    },
    async appeal(x) {
      const reason = (this.reasons[x.applicationId] || '').trim()
      if (reason.length < 5) {
        uni.showToast({ title: '申诉理由至少5字', icon: 'none' })
        return
      }
      this.busy = true
      try {
        await affairsFundingAppeal({ applicationId: x.applicationId, reason })
        uni.showToast({ title: '申诉已提交', icon: 'success' })
        this.reasons[x.applicationId] = ''
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
.hint.warn { color: #b45309; }
.ta { width: 100%; min-height: 72px; border: 1px solid #e5e7eb; border-radius: 8px; padding: 8px; font-size: 13px; box-sizing: border-box; }
.btn { margin-top: 4px; background: #2563eb; color: #fff; border: none; border-radius: 8px; padding: 8px 12px; font-size: 13px; }
</style>
