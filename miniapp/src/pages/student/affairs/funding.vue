<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="奖助申请" back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="d">
        <view class="card">
          <text class="card-title">奖学金 / 助学金申请</text>
          <text class="hint">勤工助学、助学贷款、临时补助请到学校 PC 端学工中心办理（与门户一致）。</text>
          <view class="seg">
            <button
              v-for="t in fundTypes"
              :key="t.k"
              class="seg__btn"
              :class="{ on: fundType === t.k }"
              @click="fundType = t.k"
            >{{ t.t }}</button>
          </view>
          <view v-if="!batchesForType.length" class="hint" style="margin-top:8px">当前暂无开放的{{ fundLabel }}批次。</view>
          <template v-else>
            <view class="fld">
              <text class="lbl">申请批次</text>
              <picker mode="selector" :range="batchesForType" range-key="label" :value="batchIndex" @change="onBatch">
                <view class="picker">{{ batchesForType[batchIndex].label }}</view>
              </picker>
            </view>
            <view class="fld">
              <text class="lbl">申请理由</text>
              <textarea class="ta" v-model="form.reason" maxlength="300" placeholder="请说明申请理由（≥5字）" />
            </view>
            <label class="chk" @click="form.commit = !form.commit">
              <text class="chk__box">{{ form.commit ? '✓' : '' }}</text>
              <text class="chk__t">电子签署诚信承诺书</text>
            </label>
            <button class="btn" :disabled="busy" @click="submitApply">提交{{ fundLabel }}申请</button>
          </template>
        </view>

        <view class="section-head"><text class="section-head__title">我的奖助记录</text></view>
        <view class="list-group" v-if="d.items && d.items.length">
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
        <MobileGlobalState v-else state="empty" title="暂无奖助申请记录" description="开放批次后可在上方申请奖学金/助学金。" />
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { affairsFundingAppeal } from '@/services/realApi'

export default {
  data() {
    return {
      d: null, state: 'loading', busy: false, reasons: {},
      fundTypes: [{ k: 'SCHOLARSHIP', t: '奖学金' }, { k: 'GRANT', t: '助学金' }],
      fundType: 'SCHOLARSHIP',
      allBatches: [], batchIndex: 0,
      form: { reason: '', commit: false }
    }
  },
  computed: {
    fundLabel() {
      const hit = this.fundTypes.find((x) => x.k === this.fundType)
      return (hit && hit.t) || '奖助'
    },
    batchesForType() {
      return (this.allBatches || [])
        .filter((b) => b.projectType === this.fundType)
        .map((b) => ({
          ...b,
          label: `${b.batchName || b.schoolYear || '批次'}（截止 ${(b.applyEnd || '').slice(0, 10) || '不限'}）`
        }))
    }
  },
  watch: {
    fundType() { this.batchIndex = 0 },
    batchesForType() { if (this.batchIndex >= this.batchesForType.length) this.batchIndex = 0 }
  },
  onLoad() { this.load() },
  methods: {
    typeLabel(t) {
      return ({ SCHOLARSHIP: '奖学金', GRANT: '助学金', WORK_STUDY: '勤工助学', LOAN: '助学贷款', SUBSIDY: '困难补助' })[t] || t || '奖助'
    },
    load() {
      this.state = 'loading'
      Promise.all([
        studentApi.getMyFunding(),
        studentApi.getFundingBatches().catch(() => ({ items: [] }))
      ]).then(([d, b]) => {
        this.d = d
        this.allBatches = (b && b.items) || []
        this.state = 'ready'
      }).catch(() => { this.state = 'error' })
    },
    onBatch(e) { this.batchIndex = Number(e.detail.value) },
    async submitApply() {
      if (!this.batchesForType.length) return
      const reason = (this.form.reason || '').trim()
      if (reason.length < 5) {
        uni.showToast({ title: '理由至少5字', icon: 'none' })
        return
      }
      if (!this.form.commit) {
        uni.showToast({ title: '请勾选承诺书', icon: 'none' })
        return
      }
      this.busy = true
      try {
        await studentApi.applyFunding({
          batchId: this.batchesForType[this.batchIndex].batchId,
          statement: reason,
          confirm: true
        })
        uni.showToast({ title: '申请已提交', icon: 'success' })
        this.form = { reason: '', commit: false }
        this.load()
      } catch (e) {
        uni.showToast({ title: (e && e.message) || '提交失败', icon: 'none' })
      } finally {
        this.busy = false
      }
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
.hint { font-size: 12px; color: #6b7280; display: block; }
.hint.warn { color: #b45309; }
.seg { display: flex; gap: 8px; margin-top: 10px; }
.seg__btn { flex: 1; font-size: 13px; background: #f1f5f9; color: #334155; border: none; border-radius: 8px; padding: 8px; }
.seg__btn.on { background: #2563eb; color: #fff; }
.fld { margin-top: 10px; }
.lbl { display: block; font-size: 12px; color: #6b7280; margin-bottom: 4px; }
.picker, .ta { width: 100%; box-sizing: border-box; border: 1px solid #e5e7eb; border-radius: 8px; padding: 8px; font-size: 13px; background: #fff; }
.ta { min-height: 72px; }
.chk { display: flex; align-items: flex-start; gap: 8px; margin-top: 10px; }
.chk__box { width: 18px; height: 18px; border: 1px solid #94a3b8; border-radius: 4px; text-align: center; line-height: 16px; font-size: 12px; color: #2563eb; flex-shrink: 0; }
.chk__t { font-size: 12px; color: #475569; }
.btn { margin-top: 8px; background: #2563eb; color: #fff; border: none; border-radius: 8px; padding: 8px 12px; font-size: 13px; }
.card-title { display: block; font-weight: 600; margin-bottom: 4px; }
</style>
