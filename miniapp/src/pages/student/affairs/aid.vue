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
            <view class="grid2">
              <view class="fld"><text class="lbl">家庭成员数 <text class="req">*</text></text><input class="inp" type="number" v-model="form.memberCount" placeholder="1-30人" /></view>
              <view class="fld"><text class="lbl">家庭年收入（元）</text><input class="inp" type="digit" v-model="form.income" placeholder="选填，不得为负数" /></view>
            </view>
            <view class="fld"><text class="lbl">家庭债务（元）</text><input class="inp" type="digit" v-model="form.debt" placeholder="选填，不得为负数" /></view>
            <view class="fld"><text class="lbl">特殊情况标签</text><input class="inp" v-model="form.specialTags" maxlength="200" placeholder="低保、孤残、重大疾病等，用逗号分隔" /></view>
            <view class="fld"><text class="lbl">困难情况说明（10-500字） <text class="req">*</text></text><textarea class="ta" v-model="form.reason" maxlength="500" placeholder="请客观说明家庭经济困难具体情况" /></view>
            <text class="counter">{{ (form.reason || '').trim().length }}/500</text>
            <label class="chk" @click="form.commit = !form.commit"><text class="chk__box">{{ form.commit ? '✓' : '' }}</text><text class="chk__t">已阅读并同意困难认定承诺，系统将记录本人确认、内容哈希与时间</text></label>
            <button class="btn" :disabled="busy || !canSubmit" @click="submitApply">提交认定申请</button>
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
            <template v-if="x.canObject"><textarea class="ta" maxlength="500" v-model="reasons[x.applyId]" placeholder="对公示认定结果有异议（5-500字）" /><button class="btn" :disabled="busy || (reasons[x.applyId] || '').trim().length < 5" @click="object(x)">提交公示异议</button></template>
          </view>
        </view>
        <MobileGlobalState v-else state="empty" title="暂无困难认定申请记录" description="开放批次后可在上方直接申请。" />
      </view>
    </MobileGlobalState>

    <view v-if="editVisible" class="aid__mask" @click.self="closeEdit">
      <view class="card aid__sheet">
        <text class="card-title">修改退回的认定申请</text>
        <MobileInlineAlert type="warning" title="请按退回意见修改" :description="editNotice || editTarget.returnReason || '修改后将重新进入班级评议。'" />
        <view class="fld"><text class="lbl">申请等级</text><picker mode="selector" :range="levels" range-key="label" :value="editLevelIndex" @change="editLevelIndex = Number($event.detail.value)"><view class="picker">{{ levels[editLevelIndex].label }}</view></picker></view>
        <view class="grid2">
          <view class="fld"><text class="lbl">家庭成员数 <text class="req">*</text></text><input class="inp" type="number" v-model="editForm.memberCount" placeholder="1-30人" /></view>
          <view class="fld"><text class="lbl">家庭年收入（元）</text><input class="inp" type="digit" v-model="editForm.income" placeholder="选填，不得为负数" /></view>
        </view>
        <view class="fld"><text class="lbl">家庭债务（元）</text><input class="inp" type="digit" v-model="editForm.debt" placeholder="选填，不得为负数" /></view>
        <view class="fld"><text class="lbl">特殊情况标签</text><input class="inp" v-model="editForm.specialTags" maxlength="200" placeholder="用逗号分隔" /></view>
        <view class="fld"><text class="lbl">困难情况说明（10-500字）</text><textarea class="ta" v-model="editForm.reason" maxlength="500" /></view>
        <text class="counter">{{ (editForm.reason || '').trim().length }}/500</text>
        <view class="aid__actions"><button class="btn btn-ghost flex-1" :disabled="busy" @click="closeEdit">取消</button><button class="btn flex-1" :disabled="busy || !canSaveEdit" @click="saveAndResubmit">保存并重新提交</button></view>
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
const blankForm = () => ({ memberCount: '', income: '', debt: '', specialTags: '', reason: '', commit: false })
const blankEditForm = () => ({ memberCount: '', income: '', debt: '', specialTags: '', reason: '' })

export default {
  data() {
    return {
      d: null, state: 'loading', busy: false, reasons: {}, batches: [], batchIndex: 0, batchError: '',
      levels: LEVELS, levelIndex: 0, form: blankForm(),
      editVisible: false, editTarget: {}, editLevelIndex: 0, editForm: blankEditForm(), editNotice: ''
    }
  },
  computed: {
    canSubmit() { return this.form.commit && this.validAidForm(this.form) },
    canSaveEdit() { return this.validAidForm(this.editForm) }
  },
  onLoad() { this.load() },
  methods: {
    showError(e, fallback) { const n = normalizeError(e); toast(n.text || (e && e.message) || fallback); return n },
    numberOrNull(value) {
      if (value === '' || value === null || value === undefined) return null
      const n = Number(value)
      return Number.isFinite(n) ? n : NaN
    },
    tags(value) { return String(value || '').split(/[,，]/).map((x) => x.trim()).filter(Boolean) },
    validAidForm(form) {
      const count = Number(form.memberCount)
      const income = this.numberOrNull(form.income)
      const debt = this.numberOrNull(form.debt)
      return Number.isInteger(count) && count >= 1 && count <= 30 &&
        (income === null || (Number.isFinite(income) && income >= 0)) &&
        (debt === null || (Number.isFinite(debt) && debt >= 0)) &&
        (form.reason || '').trim().length >= 10 && (form.reason || '').trim().length <= 500
    },
    validate(form) {
      const count = Number(form.memberCount)
      if (!Number.isInteger(count) || count < 1 || count > 30) return '家庭成员数应为1-30人的整数'
      for (const [label, value] of [['家庭年收入', form.income], ['家庭债务', form.debt]]) {
        const n = this.numberOrNull(value)
        if (Number.isNaN(n) || (n !== null && n < 0)) return `${label}格式不正确，且不得为负数`
      }
      const reason = (form.reason || '').trim()
      if (reason.length < 10 || reason.length > 500) return '困难情况说明需10-500字'
      return ''
    },
    payload(form) {
      return {
        memberCount: Number(form.memberCount),
        annualIncome: this.numberOrNull(form.income),
        debt: this.numberOrNull(form.debt),
        specialTags: this.tags(form.specialTags),
        statement: (form.reason || '').trim()
      }
    },
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
      const error = this.validate(this.form); if (error) return toast(error)
      if (!this.form.commit) return toast('请勾选本人确认承诺')
      this.busy = true
      try {
        await studentApi.applyAid({ batchId: this.batches[this.batchIndex].batchId, applyLevel: this.levels[this.levelIndex].value, ...this.payload(this.form), confirm: true })
        toast('申请已提交'); this.form = blankForm(); this.load()
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
        this.editForm = {
          memberCount: d.memberCount == null ? '' : String(d.memberCount),
          income: d.annualIncome == null ? '' : String(d.annualIncome),
          debt: d.debt == null ? '' : String(d.debt),
          specialTags: Array.isArray(d.specialTags) ? d.specialTags.join('，') : '',
          reason: d.statement || ''
        }
        this.editNotice = ''
        this.editVisible = true
      } catch (e) { this.showError(e, '退回申请加载失败') } finally { this.busy = false }
    },
    closeEdit() { if (!this.busy) { this.editVisible = false; this.editNotice = '' } },
    async saveAndResubmit() {
      if (this.busy) return
      const error = this.validate(this.editForm); if (error) return toast(error)
      this.busy = true
      try {
        const updated = await affairsReturnedApi.updateAid(this.editTarget.applyId, { applyLevel: LEVELS[this.editLevelIndex].value, ...this.payload(this.editForm), version: this.editTarget.version })
        this.editTarget = { ...this.editTarget, ...(updated || {}), version: updated.version }
        try {
          await affairsReturnedApi.resubmitAid(this.editTarget.applyId, this.editTarget.version)
        } catch (e) {
          this.editNotice = `修改已保存，但重新提交失败：${normalizeError(e).text || e.message || '请重试'}`
          this.showError(e, '重新提交失败')
          return
        }
        toast('已修改并重新提交'); this.editVisible = false; this.editNotice = ''; this.load()
      } catch (e) { this.showError(e, '保存修改失败') } finally { this.busy = false }
    },
    async object(x) {
      const reason = (this.reasons[x.applyId] || '').trim(); if (reason.length < 5 || reason.length > 500) return toast('异议理由需5-500字')
      this.busy = true
      try { await affairsAidObjection({ applyId: x.applyId, reason }); toast('异议已提交'); this.reasons[x.applyId] = ''; this.load() }
      catch (e) { this.showError(e, '提交失败') } finally { this.busy = false }
    }
  }
}
</script>

<style scoped>
.aid__label { display: block; font-size: var(--font-size-sm); color: var(--text-tertiary); }.aid__level { display: block; font-size: 22px; font-weight: 700; color: var(--brand-primary); margin-top: 4px; }.aid__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }.aid__return { color: #dc2626; }.col { flex-direction: column; align-items: stretch; gap: 8px; }.row-between { display: flex; align-items: center; justify-content: space-between; gap: 8px; width: 100%; }.hint { font-size: 12px; color: #6b7280; }.fld { margin-top: 10px; }.lbl { display: block; font-size: 12px; color: #6b7280; margin-bottom: 4px; }.picker, .inp, .ta { width: 100%; box-sizing: border-box; border: 1px solid #e5e7eb; border-radius: 8px; padding: 8px; font-size: 13px; background: #fff; }.ta { min-height: 72px; }.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }.req { color: #dc2626; }.counter { display: block; text-align: right; margin-top: 3px; font-size: 11px; color: #94a3b8; }.chk { display: flex; align-items: flex-start; gap: 8px; margin-top: 10px; }.chk__box { width: 18px; height: 18px; border: 1px solid #94a3b8; border-radius: 4px; text-align: center; line-height: 16px; font-size: 12px; color: #2563eb; flex-shrink: 0; }.chk__t { font-size: 12px; color: #475569; }.btn { margin-top: 8px; background: #2563eb; color: #fff; border: none; border-radius: 8px; padding: 8px 12px; font-size: 13px; }.card-title { display: block; font-weight: 600; margin-bottom: 4px; }.aid__mask { position: fixed; inset: 0; z-index: 1000; background: rgba(15,23,42,.5); display: flex; align-items: flex-end; }.aid__sheet { width: 100%; border-radius: 18px 18px 0 0; padding: 18px; max-height: 88vh; overflow-y: auto; }.aid__actions { display: flex; gap: 10px; margin-top: 12px; }
</style>
