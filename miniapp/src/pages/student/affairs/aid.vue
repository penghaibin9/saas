<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="困难认定" back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="d">
        <view class="card" v-if="d.currentLevel">
          <text class="aid__label">当前认定等级</text>
          <text class="aid__level">{{ d.currentLevel }}</text>
        </view>

        <view class="card">
          <text class="card-title">发起认定申请</text>
          <view v-if="!batches.length" class="hint">当前暂无开放批次，请等待学校发布。</view>
          <template v-else>
            <view class="fld">
              <text class="lbl">认定批次</text>
              <picker mode="selector" :range="batches" range-key="label" :value="batchIndex" @change="onBatch">
                <view class="picker">{{ batches[batchIndex].label }}</view>
              </picker>
            </view>
            <view class="fld">
              <text class="lbl">申请等级</text>
              <picker mode="selector" :range="levels" range-key="label" :value="levelIndex" @change="onLevel">
                <view class="picker">{{ levels[levelIndex].label }}</view>
              </picker>
            </view>
            <view class="fld">
              <text class="lbl">家庭年收入(元)</text>
              <input class="inp" type="number" v-model="form.income" placeholder="选填" />
            </view>
            <view class="fld">
              <text class="lbl">困难情况说明（≥10字）</text>
              <textarea class="ta" v-model="form.reason" maxlength="500" placeholder="请说明家庭经济困难具体情况" />
            </view>
            <label class="chk" @click="form.commit = !form.commit">
              <text class="chk__box">{{ form.commit ? '✓' : '' }}</text>
              <text class="chk__t">已阅读并同意困难认定承诺书（电子签）</text>
            </label>
            <button class="btn" :disabled="busy" @click="submitApply">提交认定申请</button>
          </template>
        </view>

        <view class="section-head"><text class="section-head__title">申请记录</text></view>
        <view class="list-group" v-if="d.items && d.items.length">
          <view v-for="x in d.items" :key="x.applyId" class="list-row col">
            <view class="row-between">
              <view class="flex-1">
                <text class="t-md">申请等级：{{ x.applyLevel || '—' }}</text>
                <text class="aid__sub" v-if="x.finalLevel">认定等级：{{ x.finalLevel }}</text>
                <text class="aid__sub" v-if="x.returnReason">意见：{{ x.returnReason }}</text>
              </view>
              <MobileStatusTag :status="x.statusLabel || x.status" />
            </view>
            <text v-if="x.hasPendingObjection" class="hint">异议处理中</text>
            <template v-if="x.canObject">
              <textarea class="ta" v-model="reasons[x.applyId]" placeholder="对公示认定结果有异议（≥5字）" />
              <button class="btn" :disabled="busy" @click="object(x)">提交公示异议</button>
            </template>
          </view>
        </view>
        <MobileGlobalState v-else state="empty" title="暂无困难认定申请记录" description="开放批次后可在上方直接申请。" />
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { affairsAidObjection } from '@/services/realApi'

const LEVELS = [
  { label: '一般困难', value: 'GENERAL' },
  { label: '困难', value: 'DIFFICULT' },
  { label: '特别困难', value: 'SPECIAL' }
]

export default {
  data() {
    return {
      d: null, state: 'loading', busy: false, reasons: {},
      batches: [], batchIndex: 0, levels: LEVELS, levelIndex: 0,
      form: { income: '', reason: '', commit: false }
    }
  },
  onLoad() { this.load() },
  methods: {
    load() {
      this.state = 'loading'
      Promise.all([
        studentApi.getMyAid(),
        studentApi.getAidBatches().catch(() => ({ items: [] }))
      ]).then(([d, b]) => {
        this.d = d
        const items = (b && b.items) || []
        this.batches = items.map((x) => ({
          ...x,
          label: `${x.batchName || x.schoolYear || '认定批次'}（截止 ${(x.applyEnd || '').slice(0, 10) || '不限'}）`
        }))
        this.batchIndex = 0
        this.state = 'ready'
      }).catch(() => { this.state = 'error' })
    },
    onBatch(e) { this.batchIndex = Number(e.detail.value) },
    onLevel(e) { this.levelIndex = Number(e.detail.value) },
    async submitApply() {
      if (!this.batches.length) return
      const reason = (this.form.reason || '').trim()
      if (reason.length < 10) {
        uni.showToast({ title: '说明至少10字', icon: 'none' })
        return
      }
      if (!this.form.commit) {
        uni.showToast({ title: '请勾选承诺书', icon: 'none' })
        return
      }
      this.busy = true
      try {
        await studentApi.applyAid({
          batchId: this.batches[this.batchIndex].batchId,
          applyLevel: this.levels[this.levelIndex].value,
          annualIncome: this.form.income ? Number(this.form.income) : null,
          statement: reason,
          confirm: true
        })
        uni.showToast({ title: '申请已提交', icon: 'success' })
        this.form = { income: '', reason: '', commit: false }
        this.load()
      } catch (e) {
        uni.showToast({ title: (e && e.message) || '提交失败', icon: 'none' })
      } finally {
        this.busy = false
      }
    },
    async object(x) {
      const reason = (this.reasons[x.applyId] || '').trim()
      if (reason.length < 5) {
        uni.showToast({ title: '异议理由至少5字', icon: 'none' })
        return
      }
      this.busy = true
      try {
        await affairsAidObjection({ applyId: x.applyId, reason })
        uni.showToast({ title: '异议已提交', icon: 'success' })
        this.reasons[x.applyId] = ''
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
.aid__label { display: block; font-size: var(--font-size-sm); color: var(--text-tertiary); }
.aid__level { display: block; font-size: 22px; font-weight: 700; color: var(--brand-primary); margin-top: 4px; }
.aid__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.col { flex-direction: column; align-items: stretch; gap: 8px; }
.row-between { display: flex; align-items: center; justify-content: space-between; gap: 8px; width: 100%; }
.hint { font-size: 12px; color: #6b7280; }
.fld { margin-top: 10px; }
.lbl { display: block; font-size: 12px; color: #6b7280; margin-bottom: 4px; }
.picker, .inp, .ta { width: 100%; box-sizing: border-box; border: 1px solid #e5e7eb; border-radius: 8px; padding: 8px; font-size: 13px; background: #fff; }
.ta { min-height: 72px; }
.chk { display: flex; align-items: flex-start; gap: 8px; margin-top: 10px; }
.chk__box { width: 18px; height: 18px; border: 1px solid #94a3b8; border-radius: 4px; text-align: center; line-height: 16px; font-size: 12px; color: #2563eb; flex-shrink: 0; }
.chk__t { font-size: 12px; color: #475569; }
.btn { margin-top: 8px; background: #2563eb; color: #fff; border: none; border-radius: 8px; padding: 8px 12px; font-size: 13px; }
.card-title { display: block; font-weight: 600; margin-bottom: 4px; }
</style>
