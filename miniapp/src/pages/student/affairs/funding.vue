<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="奖学金与助学金" back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="d">
        <view class="card">
          <text class="card-title">奖学金 / 助学金申请</text>
          <text class="hint">当前移动端仅开放奖学金和助学金申请；勤工助学、贷款、减免与临时补助由学校按项目另行开放。</text>
          <MobileInlineAlert v-if="batchError" type="warning" title="批次暂不可用" :description="batchError" />
          <view class="seg"><button v-for="t in fundTypes" :key="t.k" class="seg__btn" :class="{ on: fundType === t.k }" @click="fundType = t.k">{{ t.t }}</button></view>
          <view v-if="!batchError && !batchesForType.length" class="hint" style="margin-top:8px">当前暂无开放的{{ fundLabel }}批次。</view>
          <template v-else-if="!batchError">
            <view class="fld"><text class="lbl">申请批次</text><picker mode="selector" :range="batchesForType" range-key="label" :value="batchIndex" @change="onBatch"><view class="picker">{{ batchesForType[batchIndex].label }}</view></picker></view>
            <view class="fld"><text class="lbl">申请理由</text><textarea class="ta" v-model="form.reason" maxlength="500" placeholder="请说明申请理由（≥5字）" /></view>
            <label class="chk" @click="form.commit = !form.commit"><text class="chk__box">{{ form.commit ? '✓' : '' }}</text><text class="chk__t">已阅读并确认诚信承诺，系统将记录本人确认、内容哈希与时间</text></label>
            <button class="btn" :disabled="busy" @click="submitApply">提交{{ fundLabel }}申请</button>
          </template>
        </view>

        <view class="section-head"><text class="section-head__title">我的奖助记录</text></view>
        <view class="list-group" v-if="d.items && d.items.length">
          <view v-for="x in d.items" :key="x.applicationId" class="list-row col">
            <view class="row-between"><text class="flex-1 t-md">{{ typeLabel(x.projectType) }}</text><MobileStatusTag :status="x.statusLabel || x.status" /></view>
            <text v-if="x.returnReason" class="hint warn">退回/驳回：{{ x.returnReason }}</text>
            <button v-if="allows(x, 'EDIT_RETURNED') || allows(x, 'RESUBMIT')" class="btn btn-ghost" :disabled="busy" @click="editReturned(x)">修改后重新提交</button>
            <text v-if="x.hasPendingAppeal" class="hint">申诉处理中，请等待复核</text>
            <template v-if="allows(x, 'SUBMIT_APPEAL')"><textarea class="ta" v-model="reasons[x.applicationId]" placeholder="对公示结果有异议，请填写申诉理由（≥5字）" /><button class="btn" :disabled="busy" @click="appeal(x)">提交公示申诉</button></template>
          </view>
        </view>
        <MobileGlobalState v-else state="empty" title="暂无奖助申请记录" description="开放批次后可在上方申请奖学金/助学金。" />
      </view>
    </MobileGlobalState>

    <view v-if="editVisible" class="fd__mask" @click.self="closeEdit">
      <view class="card fd__sheet">
        <text class="card-title">修改退回的{{ typeLabel(editTarget.projectType) }}申请</text>
        <MobileInlineAlert type="warning" title="请按退回意见修改" :description="editNotice || editTarget.returnReason || '修改后将重新进入辅导员初审。'" />
        <view class="fld"><text class="lbl">申请理由</text><textarea class="ta" v-model="editReason" maxlength="500" placeholder="申请理由（≥5字）" /></view>
        <view class="fd__actions"><button class="btn btn-ghost flex-1" :disabled="busy" @click="closeEdit">取消</button><button class="btn flex-1" :disabled="busy" @click="saveAndResubmit">保存并重新提交</button></view>
      </view>
    </view>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { affairsFundingAppeal } from '@/services/realApi'
import { affairsReturnedApi } from '@/services/affairsReturnedApi'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

export default {
  data() {
    return {
      d: null, state: 'loading', busy: false, reasons: {}, batchError: '',
      fundTypes: [{ k: 'SCHOLARSHIP', t: '奖学金' }, { k: 'GRANT', t: '助学金' }], fundType: 'SCHOLARSHIP',
      allBatches: [], batchIndex: 0, form: { reason: '', commit: false },
      editVisible: false, editTarget: {}, editReason: '', editNotice: ''
    }
  },
  computed: {
    fundLabel() { const hit = this.fundTypes.find((x) => x.k === this.fundType); return (hit && hit.t) || '奖助' },
    batchesForType() { return (this.allBatches || []).filter((b) => b.projectType === this.fundType).map((b) => ({ ...b, label: `${b.batchName || b.schoolYear || '批次'}（截止 ${(b.applyEnd || '').slice(0, 10) || '不限'}）` })) }
  },
  watch: { fundType() { this.batchIndex = 0 }, batchesForType() { if (this.batchIndex >= this.batchesForType.length) this.batchIndex = 0 } },
  onLoad() { this.load() },
  methods: {
    allows(item, action) { return Array.isArray(item && item.allowedActions) && item.allowedActions.includes(action) },
    typeLabel(t) { return ({ SCHOLARSHIP: '奖学金', GRANT: '助学金', WORK_STUDY: '勤工助学', LOAN: '助学贷款', TUITION_REDUCTION: '学费减免', TEMPORARY_AID: '临时补助' })[t] || t || '奖助' },
    showError(e, fallback) { const n = normalizeError(e); toast(n.text || (e && e.message) || fallback); return n },
    load() {
      this.state = 'loading'; this.batchError = ''
      Promise.all([studentApi.getMyFunding(), studentApi.getFundingBatches().catch((e) => ({ __error: normalizeError(e).text || '开放批次加载失败' }))]).then(([d, b]) => {
        this.d = d
        if (b && b.__error) { this.batchError = b.__error; this.allBatches = [] } else this.allBatches = (b && b.items) || []
        this.state = 'ready'
      }).catch((e) => { this.state = 'error'; this.showError(e, '奖助信息加载失败') })
    },
    onBatch(e) { this.batchIndex = Number(e.detail.value) },
    async submitApply() {
      if (!this.batchesForType.length || this.busy) return
      const reason = (this.form.reason || '').trim(); if (reason.length < 5) return toast('理由至少5字'); if (!this.form.commit) return toast('请勾选本人确认承诺')
      this.busy = true
      try { await studentApi.applyFunding({ batchId: this.batchesForType[this.batchIndex].batchId, statement: reason, confirm: true }); toast('申请已提交'); this.form = { reason: '', commit: false }; this.load() }
      catch (e) { this.showError(e, '提交失败') } finally { this.busy = false }
    },
    async editReturned(x) {
      if (this.busy) return; this.busy = true
      try { const d = await affairsReturnedApi.getFunding(x.applicationId); this.editTarget = { ...x, ...d }; this.editReason = d.statement || ''; this.editNotice = ''; this.editVisible = true }
      catch (e) { this.showError(e, '退回申请加载失败') } finally { this.busy = false }
    },
    closeEdit() { if (!this.busy) { this.editVisible = false; this.editNotice = '' } },
    async saveAndResubmit() {
      const reason = this.editReason.trim(); if (reason.length < 5) return toast('申请理由至少5字')
      this.busy = true
      try {
        const updated = await affairsReturnedApi.updateFunding(this.editTarget.applicationId, { statement: reason, version: this.editTarget.version })
        this.editTarget = { ...this.editTarget, ...(updated || {}), version: updated.version }
        try {
          await affairsReturnedApi.resubmitFunding(this.editTarget.applicationId, this.editTarget.version)
        } catch (e) {
          this.editNotice = `修改已保存，但重新提交失败：${normalizeError(e).text || e.message || '请重试'}`
          this.showError(e, '重新提交失败')
          return
        }
        toast('已修改并重新提交'); this.editVisible = false; this.editNotice = ''; this.load()
      } catch (e) { this.showError(e, '保存修改失败') } finally { this.busy = false }
    },
    async appeal(x) {
      const reason = (this.reasons[x.applicationId] || '').trim(); if (reason.length < 5) return toast('申诉理由至少5字')
      this.busy = true
      try { await affairsFundingAppeal({ applicationId: x.applicationId, reason }); toast('申诉已提交'); this.reasons[x.applicationId] = ''; this.load() }
      catch (e) { this.showError(e, '提交失败') } finally { this.busy = false }
    }
  }
}
</script>

<style scoped>
.col { flex-direction: column; align-items: stretch; gap: 8px; }.row-between { display: flex; align-items: center; justify-content: space-between; gap: 8px; width: 100%; }.hint { font-size: 12px; color: #6b7280; display: block; }.hint.warn { color: #b45309; }.seg { display: flex; gap: 8px; margin-top: 10px; }.seg__btn { flex: 1; font-size: 13px; background: #f1f5f9; color: #334155; border: none; border-radius: 8px; padding: 8px; }.seg__btn.on { background: #2563eb; color: #fff; }.fld { margin-top: 10px; }.lbl { display: block; font-size: 12px; color: #6b7280; margin-bottom: 4px; }.picker, .ta { width: 100%; box-sizing: border-box; border: 1px solid #e5e7eb; border-radius: 8px; padding: 8px; font-size: 13px; background: #fff; }.ta { min-height: 72px; }.chk { display: flex; align-items: flex-start; gap: 8px; margin-top: 10px; }.chk__box { width: 18px; height: 18px; border: 1px solid #94a3b8; border-radius: 4px; text-align: center; line-height: 16px; font-size: 12px; color: #2563eb; flex-shrink: 0; }.chk__t { font-size: 12px; color: #475569; }.btn { margin-top: 8px; background: #2563eb; color: #fff; border: none; border-radius: 8px; padding: 8px 12px; font-size: 13px; }.card-title { display: block; font-weight: 600; margin-bottom: 4px; }.fd__mask { position: fixed; inset: 0; z-index: 1000; background: rgba(15,23,42,.5); display: flex; align-items: flex-end; }.fd__sheet { width: 100%; border-radius: 18px 18px 0 0; padding: 18px; }.fd__actions { display: flex; gap: 10px; margin-top: 12px; }
</style>
