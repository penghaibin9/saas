<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="困难认定" back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="d">
        <view class="card" v-if="d.currentLevel"><text class="aid__label">当前认定等级</text><text class="aid__level">{{ d.currentLevel }}</text></view>

        <view class="card">
          <text class="card-title">发起认定申请</text>
          <MobileInlineAlert v-if="batchError" type="warning" title="批次暂不可用" :description="batchError" />
          <view v-else-if="!batches.length" class="hint">当前暂无开放批次，请等待学校发布。</view>
          <template v-else>
            <view class="fld"><text class="lbl">认定批次</text><picker mode="selector" :range="batches" range-key="label" :value="batchIndex" @change="onBatch"><view class="picker">{{ batches[batchIndex].label }}</view></picker></view>
            <view class="fld"><text class="lbl">申请等级</text><picker mode="selector" :range="levels" range-key="label" :value="levelIndex" @change="onLevel"><view class="picker">{{ levels[levelIndex].label }}</view></picker></view>
            <view class="fld"><text class="lbl">家庭年收入（元）</text><input class="inp" type="number" v-model="form.income" placeholder="选填" /></view>
            <view class="fld"><text class="lbl">困难情况说明（≥10字）</text><textarea class="ta" v-model="form.reason" maxlength="500" placeholder="请说明家庭经济困难具体情况" /></view>
            <label class="chk" @click="form.commit = !form.commit"><text class="chk__box">{{ form.commit ? '✓' : '' }}</text><text class="chk__t">已阅读并同意困难认定承诺，系统将记录本人确认、内容哈希与时间</text></label>
            <button class="btn" :disabled="busy" @click="submitApply">提交认定申请</button>
          </template>
        </view>

        <view class="section-head"><text class="section-head__title">申请记录</text></view>
        <view class="list-group" v-if="d.items && d.items.length">
          <view v-for="x in d.items" :key="x.applyId" class="list-row col">
            <view class="row-between">
              <view class="flex-1"><text class="t-md">申请等级：{{ x.applyLevel || '—' }}</text><text class="aid__sub" v-if="x.finalLevel">认定等级：{{ x.finalLevel }}</text><text class="aid__sub aid__return" v-if="x.returnReason">退回意见：{{ x.returnReason }}</text></view>
              <MobileStatusTag :status="x.statusLabel || x.status" />
            </view>
            <button v-if="x.canResubmit" class="btn btn-ghost" :disabled="busy" @click="editReturned(x)">修改后重新提交</button>
            <text v-if="x.hasPendingObjection" class="hint">异议处理中</text>
            <template v-if="x.canObject"><textarea class="ta" v-model="reasons[x.applyId]" placeholder="对公示认定结果有异议（≥5字）" /><button class="btn" :disabled="busy" @click="object(x)">提交公示异议</button></template>
          </view>
        </view>
        <MobileGlobalState v-else state="empty" title="暂无困难认定申请记录" description="开放批次后可在上方直接申请。" />
      </view>
    </MobileGlobalState>

    <view v-if="editVisible" class="aid__mask" @click.self="closeEdit">
      <view class="card aid__sheet">
        <text class="card-title">修改退回的认定申请</text>
        <MobileInlineAlert type="warning" title="请按退回意见修改" :description="editTarget.returnReason || '修改后将重新进入班级评议。'" />
        <view class="fld"><text class="lbl">申请等级</text><picker mode="selector" :range="levels" range-key="label" :value="editLevelIndex" @change="editLevelIndex = Number($event.detail.value)"><view class="picker">{{ levels[editLevelIndex].label }}</view></picker></view>
        <view class="fld"><text class="lbl">家庭年收入（元）</text><input class="inp" type="number" v-model="editForm.income" placeholder="选填" /></view>
        <view class="fld"><text class="lbl">困难情况说明（≥10字）</text><textarea class="ta" v-model="editForm.reason" maxlength="500" /></view>
        <view class="aid__actions"><button class="btn btn-ghost flex-1" :disabled="busy" @click="closeEdit">取消</button><button class="btn flex-1" :disabled="busy" @click="saveAndResubmit">保存并重新提交</button></view>
      </view>
    </view>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { affairsAidObjection } from '@/services/realApi'
import { affairsReturnedApi } from '@/services/affairsReturnedApi'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

const LEVELS = [{ label: '一般困难', value: 'GENERAL' }, { label: '困难', value: 'DIFFICULT' }, { label: '特别困难', value: 'SPECIAL' }]

export default {
  data() {
    return {
      d: null, state: 'loading', busy: false, reasons: {}, batches: [], batchIndex: 0, batchError: '',
      levels: LEVELS, levelIndex: 0, form: { income: '', reason: '', commit: false },
      editVisible: false, editTarget: {}, editLevelIndex: 0, editForm: { income: '', reason: '' }
    }
  },
  onLoad() { this.load() },
  methods: {
    showError(e, fallback) { toast(normalizeError(e).text || (e && e.message) || fallback) },
    load() {
      this.state = 'loading'; this.batchError = ''
      Promise.all([studentApi.getMyAid(), studentApi.getAidBatches().catch((e) => ({ __error: normalizeError(e).text || '开放批次加载失败' }))]).then(([d, b]) => {
        this.d = d
        if (b && b.__error) { this.batchError = b.__error; this.batches = [] }
        else this.batches = ((b && b.items) || []).map((x) => ({ ...x, label: `${x.batchName || x.schoolYear || '认定批次'}（截止 ${(x.applyEnd || '').slice(0, 10) || '不限'}）` }))
        this.batchIndex = 0; this.state = 'ready'
      }).catch((e) => { this.state = 'error'; this.showError(e, '困难认定加载失败') })
    },
    onBatch(e) { this.batchIndex = Number(e.detail.value) }, onLevel(e) { this.levelIndex = Number(e.detail.value) },
    async submitApply() {
      if (!this.batches.length || this.busy) return
      const reason = (this.form.reason || '').trim()
      if (reason.length < 10) return toast('说明至少10字')
      if (!this.form.commit) return toast('请勾选本人确认承诺')
      this.busy = true
      try {
        await studentApi.applyAid({ batchId: this.batches[this.batchIndex].batchId, applyLevel: this.levels[this.levelIndex].value, annualIncome: this.form.income ? Number(this.form.income) : null, statement: reason, confirm: true })
        toast('申请已提交'); this.form = { income: '', reason: '', commit: false }; this.load()
      } catch (e) { this.showError(e, '提交失败') } finally { this.busy = false }
    },
    async editReturned(x) {
      if (this.busy) return
      this.busy = true
      try {
        const d = await affairsReturnedApi.getAid(x.applyId)
        this.editTarget = { ...x, ...d }
        const idx = LEVELS.findIndex((o) => o.value === d.applyLevel)
        this.editLevelIndex = idx >= 0 ? idx : 0
        this.editForm = { income: d.annualIncome == null ? '' : String(d.annualIncome), reason: d.statement || '' }
        this.editVisible = true
      } catch (e) { this.showError(e, '退回申请加载失败') } finally { this.busy = false }
    },
    closeEdit() { if (!this.busy) this.editVisible = false },
    async saveAndResubmit() {
      if (this.busy) return
      const reason = this.editForm.reason.trim()
      if (reason.length < 10) return toast('说明至少10字')
      this.busy = true
      try {
        const updated = await affairsReturnedApi.updateAid(this.editTarget.applyId, { applyLevel: LEVELS[this.editLevelIndex].value, annualIncome: this.editForm.income ? Number(this.editForm.income) : null, statement: reason, version: this.editTarget.version })
        await affairsReturnedApi.resubmitAid(this.editTarget.applyId, updated.version)
        toast('已修改并重新提交'); this.editVisible = false; this.load()
      } catch (e) { this.showError(e, '重新提交失败') } finally { this.busy = false }
    },
    async object(x) {
      const reason = (this.reasons[x.applyId] || '').trim(); if (reason.length < 5) return toast('异议理由至少5字')
      this.busy = true
      try { await affairsAidObjection({ applyId: x.applyId, reason }); toast('异议已提交'); this.reasons[x.applyId] = ''; this.load() }
      catch (e) { this.showError(e, '提交失败') } finally { this.busy = false }
    }
  }
}
</script>

<style scoped>
.aid__label { display: block; font-size: var(--font-size-sm); color: var(--text-tertiary); }.aid__level { display: block; font-size: 22px; font-weight: 700; color: var(--brand-primary); margin-top: 4px; }.aid__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }.aid__return { color: #dc2626; }.col { flex-direction: column; align-items: stretch; gap: 8px; }.row-between { display: flex; align-items: center; justify-content: space-between; gap: 8px; width: 100%; }.hint { font-size: 12px; color: #6b7280; }.fld { margin-top: 10px; }.lbl { display: block; font-size: 12px; color: #6b7280; margin-bottom: 4px; }.picker, .inp, .ta { width: 100%; box-sizing: border-box; border: 1px solid #e5e7eb; border-radius: 8px; padding: 8px; font-size: 13px; background: #fff; }.ta { min-height: 72px; }.chk { display: flex; align-items: flex-start; gap: 8px; margin-top: 10px; }.chk__box { width: 18px; height: 18px; border: 1px solid #94a3b8; border-radius: 4px; text-align: center; line-height: 16px; font-size: 12px; color: #2563eb; flex-shrink: 0; }.chk__t { font-size: 12px; color: #475569; }.btn { margin-top: 8px; background: #2563eb; color: #fff; border: none; border-radius: 8px; padding: 8px 12px; font-size: 13px; }.card-title { display: block; font-weight: 600; margin-bottom: 4px; }.aid__mask { position: fixed; inset: 0; z-index: 1000; background: rgba(15,23,42,.5); display: flex; align-items: flex-end; }.aid__sheet { width: 100%; border-radius: 18px 18px 0 0; padding: 18px; max-height: 88vh; overflow-y: auto; }.aid__actions { display: flex; gap: 10px; margin-top: 12px; }
</style>
