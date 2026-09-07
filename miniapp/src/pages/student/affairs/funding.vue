<template>
  <view class="page-wrap" :class="{ 'funding-detail-open': detailId }">
    <MobileNavBar variant="brand" title="奖学金与助学金" back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="d">
        <view class="card">
          <text class="card-title">奖学金 / 助学金申请</text>
          <text class="hint">当前移动端仅开放奖学金和助学金申请；勤工助学、贷款、减免与临时补助由学校按项目另行开放。</text>
          <MobileInlineAlert v-if="batchError" type="warning" title="批次暂不可用" :description="batchError" />
          <view class="seg"><button v-for="t in fundTypes" :key="t.k" class="seg__btn" :disabled="busy" :class="{ on: fundType === t.k }" @click="changeType(t.k)">{{ t.t }}</button></view>
          <view class="batch-search"><input class="picker" v-model.trim="batchQuery" maxlength="100" placeholder="按项目名称或学年搜索" confirm-type="search" @confirm="loadBatches()" /><button class="btn btn-ghost" :disabled="batchLoading" @click="loadBatches()">搜索</button></view>
          <view class="batch-meta"><text class="hint">{{ batchLoading ? '正在查找开放批次…' : `已加载 ${allBatches.length} / ${batchTotal} 个匹配批次` }}</text><button v-if="batchError" class="btn btn-ghost" :disabled="batchLoading" @click="loadBatches()">重试</button><button v-else-if="allBatches.length < batchTotal" class="btn btn-ghost" :disabled="batchLoading" @click="loadBatches(true)">加载更多批次</button></view>
          <view v-if="!batchLoading && !batchError && !batchOptions.length" class="hint">没有匹配的开放批次，可修改搜索条件或等待学校发布。</view>
          <template v-if="batchOptions.length">
            <view class="fld"><text class="lbl">申请批次</text><picker mode="selector" :range="batchOptions" range-key="label" :value="batchIndex" :disabled="busy" @change="onBatch"><view class="picker">{{ selectedBatch?.label || '请选择申请批次' }}</view></picker></view>
            <view class="fld"><text class="lbl">申请理由（5–1000字）</text><textarea class="ta" v-model="form.reason" :disabled="busy" maxlength="1000" placeholder="请说明申请理由（5–1000字）" /></view>
            <view class="fld">
              <MobileAttachmentPicker
                label="佐证材料"
                biz-purpose="FUNDING"
                :file-ids="fileIds"
                :max-count="5"
                :max-size-mb="10"
                :disabled="busy"
                @update:fileIds="(ids) => (fileIds = ids)"
                @update:ready="(value) => (attachmentsReady = value)"
                @error="onAttachmentError"
              />
            </view>
            <label class="chk" @click="!busy && (form.commit = !form.commit)"><text class="chk__box">{{ form.commit ? '✓' : '' }}</text><text class="chk__t">本人确认所选批次与申请信息真实</text></label>
            <button class="btn" :disabled="busy || !selectedBatch" @click="submitApply">提交{{ fundLabel }}申请</button>
          </template>
        </view>

        <view class="section-head"><text class="section-head__title">我的奖助记录</text><button class="btn btn-ghost" :disabled="refreshing || busy" @click="load">刷新</button></view>
        <MobileInlineAlert v-if="loadError" type="warning" title="记录刷新失败" :description="loadError" />
        <MobileInlineAlert v-if="focusMissing" type="warning" title="没有找到这条记录"
          description="消息或待办指向的资助申请不在当前列表里，可能已被处理、撤回或超出本页范围。" />
        <view class="list-group" v-if="d.items && d.items.length">
          <view v-for="x in d.items" :key="x.applicationId" :id="'funding-' + x.applicationId" :class="{ 'is-focus': isFocused(x) }" class="list-row col">
            <view class="row-between"><text class="flex-1 t-md">{{ x.projectName || typeLabel(x.projectType) }}</text><MobileStatusTag :status="x.status" :label="x.statusLabel" /></view>
            <text class="hint">{{ x.schoolYear || '学年待核对' }} · {{ typeLabel(x.projectType) }}<template v-if="x.batchId"> · 批次 {{ x.batchId }}</template> · 申请 {{ x.applicationId }}</text>
            <view class="aid__flow" v-if="workflowHint(x)"><text class="aid__k">流程提示：</text><text class="aid__v">{{ workflowHint(x) }}</text></view>
            <text v-if="x.returnReason" class="hint warn">退回/驳回：{{ x.returnReason }}</text>
            <text v-if="x.attachmentCount" class="hint">已附佐证材料 {{ x.attachmentCount }} 份</text>
            <button class="btn btn-ghost" :disabled="busy" @click="detailId = String(x.applicationId)">查看申请详情</button>
            <button class="btn btn-ghost" :disabled="busy" @click="materialId = materialId === x.applicationId ? '' : x.applicationId">{{ materialId === x.applicationId ? '收起材料' : '查看申请材料' }}</button>
            <MobileFundingEvidence v-if="materialId === x.applicationId" :application-id="String(x.applicationId)" />
            <button v-if="allows(x, 'EDIT_RETURNED') || allows(x, 'RESUBMIT')" class="btn btn-ghost" :disabled="busy" @click="editReturned(x)">修改后重新提交</button>
            <text v-if="x.hasPendingAppeal" class="hint">申诉处理中，请等待复核</text>
            <template v-if="allows(x, 'SUBMIT_APPEAL')"><textarea class="ta" v-model="reasons[x.applicationId]" :disabled="busy" maxlength="1000" placeholder="请填写公示申诉理由（5–1000字）" /><button class="btn" :disabled="busy" @click="appeal(x)">提交公示申诉</button></template>
          </view>
        </view>
        <MobileGlobalState v-else state="empty" title="暂无奖助申请记录" description="开放批次后可在上方申请奖学金/助学金。" />
      </view>
    </MobileGlobalState>

    <MobileFundingDetail v-if="detailId" :key="detailId" :application-id="detailId" @close="detailId = ''" @edit="editDetail" />
    <view v-if="editVisible" class="fd__mask" @click.self="closeEdit">
      <view class="card fd__sheet">
        <text class="card-title">修改退回的{{ typeLabel(editTarget.projectType) }}申请</text>
        <MobileInlineAlert type="warning" title="请按退回意见修改" :description="editNotice || editTarget.returnReason || '修改后将重新进入辅导员初审。'" />
        <view class="fld"><text class="lbl">申请理由（5–1000字）</text><textarea class="ta" v-model="editReason" :disabled="busy" maxlength="1000" placeholder="请根据退回意见补充申请理由" /></view>
        <view class="fd__actions"><button class="btn btn-ghost flex-1" :disabled="busy" @click="closeEdit">取消</button><button class="btn flex-1" :disabled="busy" @click="saveAndResubmit">保存并重新提交</button></view>
      </view>
    </view>
  </view>
</template>

<script>
import { hasFocusRow, isFocusRow, readFocusId, scrollToFocus } from '@/utils/listFocus.mjs'
import { studentApi } from '@/services/studentApi'
import { affairsFundingAppeal } from '@/services/realApi'
import { affairsReturnedApi } from '@/services/affairsReturnedApi'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

export default {
  data() {
    return { focusId: '', focusMissing: false,
      d: null, state: 'loading', busy: false, reasons: {}, batchError: '',
      selectedBatch: null, batchQuery: '', batchTotal: 0, batchPage: 0, batchLoading: false,
      batchSeq: 0, batchAppliedQuery: '', loadSeq: 0, loadError: '', refreshing: false,
      fundTypes: [{ k: 'SCHOLARSHIP', t: '奖学金' }, { k: 'GRANT', t: '助学金' }], fundType: 'SCHOLARSHIP',
      allBatches: [], form: { reason: '', commit: false },
      editVisible: false, editTarget: {}, editReason: '', editNotice: '',
      // V3 §8.1：fileIds 只是 TEMP_PRIVATE 标识；正式绑定由服务端在业务事务里完成。
      fileIds: [], attachmentsReady: true, materialId: '', detailId: ''
    }
  },
  computed: {
    fundLabel() { const hit = this.fundTypes.find((x) => x.k === this.fundType); return (hit && hit.t) || '奖助' },
    batchOptions() { return this.selectedBatch && !this.allBatches.some(x => x.batchId === this.selectedBatch.batchId) ? [this.selectedBatch, ...this.allBatches] : this.allBatches },
    batchIndex() { return Math.max(0, this.batchOptions.findIndex(x => x.batchId === this.selectedBatch?.batchId)) }
  },
  // V3 §4.4 LIST_FOCUS：待办/消息深链带 recordId 进来时必须定位到那条记录。
  onLoad(query) { this.focusId = readFocusId(query); this.detailId = this.focusId; this.load() },
  onUnload() { this.loadSeq++; this.batchSeq++ },
  onBackPress() { if (this.detailId) { this.detailId = ''; return true } return false },
  methods: {
    editDetail(item) { this.detailId = ''; return this.editReturned(item) },
    isFocused(row) { return isFocusRow(row, this.focusId, ['applicationId']) },
    hasAnyAction(item, actions) {
      const list = Array.isArray(item && item.allowedActions) ? item.allowedActions : []
      return actions.some((name) => list.includes(name))
    },
    workflowHint(item) {
      const status = item.statusLabel || item.status || '处理中'
      if (this.hasAnyAction(item, ['EDIT_RETURNED', 'RESUBMIT'])) return `当前在「${status}」。建议先根据退回意见修改后，点击“修改后重新提交”。`
      if (item.hasPendingAppeal) return `当前在「${status}」。申诉已提交，请等待复核处理。`
      if (this.hasAnyAction(item, ['SUBMIT_APPEAL'])) return `当前在「${status}」。公示结果可提交申诉（5–1000字）。`
      if (item.status === 'GRANTED') return '已获得资助资格，实际发放情况以学校发放记录为准。'
      if (['REJECTED', 'CANCELLED', 'ARCHIVED'].includes(item.status)) return `当前为「${status}」，本次申请流程已结束。`
      return `当前在「${status}」。请等待负责本次评审的老师处理，结果会同步到申请记录。`
    },
    applyFocus() {
      if (!this.focusId) return
      const rows = (this.d && this.d.items) || []
      this.focusMissing = !hasFocusRow(rows, this.focusId, ['applicationId'])
      if (this.focusMissing) return
      this.$nextTick(() => scrollToFocus('#funding-', this.focusId))
    },
    allows(item, action) { return Array.isArray(item && item.allowedActions) && item.allowedActions.includes(action) },
    typeLabel(t) { return ({ SCHOLARSHIP: '奖学金', GRANT: '助学金', WORK_STUDY: '勤工助学', LOAN: '助学贷款', TUITION_REDUCTION: '学费减免', TEMPORARY_AID: '临时补助' })[t] || t || '奖助' },
    showError(e, fallback) { const n = normalizeError(e); toast(n.text || (e && e.message) || fallback); return n },
    async load() {
      const seq = ++this.loadSeq
      if (!this.d) this.state = 'loading'
      this.refreshing = true; this.loadError = ''
      try {
        const [d] = await Promise.all([studentApi.getMyFunding(), this.loadBatches()])
        if (seq !== this.loadSeq) return
        this.d = d; this.state = 'ready'; this.applyFocus()
      } catch (e) {
        if (seq !== this.loadSeq) return
        this.state = this.d ? 'ready' : 'error'; this.loadError = '仍保留上次记录，请重试获取最新进度。'; this.showError(e, '奖助信息加载失败')
      } finally { if (seq === this.loadSeq) this.refreshing = false }
    },
    async loadBatches(more = false) {
      if (more && this.batchLoading) return
      const seq = ++this.batchSeq
      const page = more ? this.batchPage + 1 : 1
      const keyword = more ? this.batchAppliedQuery : this.batchQuery.trim()
      this.batchLoading = true; this.batchError = ''
      try {
        const data = await studentApi.getFundingBatches({ page, pageSize: 20, keyword, projectType: this.fundType })
        if (seq !== this.batchSeq) return
        const rows = (data?.items || []).map(x => ({ ...x, label: `${x.batchName || x.schoolYear || '批次'}（截止 ${(x.applyEnd || '').slice(0, 10) || '不限'}）` }))
        this.allBatches = more ? [...new Map([...this.allBatches, ...rows].map(x => [x.batchId, x])).values()] : rows
        this.batchTotal = data?.total ?? rows.length; this.batchPage = page; this.batchAppliedQuery = keyword
      } catch {
        if (seq === this.batchSeq) this.batchError = '批次查找失败，已选批次和填写内容已保留，请重试。'
      } finally { if (seq === this.batchSeq) this.batchLoading = false }
    },
    changeType(type) {
      if (this.busy || type === this.fundType) return
      this.fundType = type; this.selectedBatch = null; this.form.commit = false
      this.allBatches = []; this.batchTotal = 0; this.batchPage = 0
      return this.loadBatches()
    },
    onBatch(e) { if (!this.busy) { this.selectedBatch = this.batchOptions[Number(e.detail.value)] || null; this.form.commit = false } },
    onAttachmentError(message) { if (message && typeof message === 'object') this.showError(message, '附件处理失败'); else toast(message || '附件处理失败') },
    async submitApply() {
      if (!this.selectedBatch || this.busy) return
      const reason = (this.form.reason || '').trim(); if (reason.length < 5 || reason.length > 1000) return toast('申请理由需5–1000字'); if (!this.form.commit) return toast('请勾选本人确认承诺')
      // 还有附件在扫描或被拒绝时不允许提交（readyForBusiness=false）。
      if (!this.attachmentsReady) return toast('附件仍在安全扫描或不可用，请稍候再提交')
      this.busy = true
      try {
        await studentApi.applyFunding({
          batchId: this.selectedBatch.batchId,
          statement: reason, confirm: true, fileIds: this.fileIds
        })
        toast('申请已提交')
        // 一批临时文件只能绑一次业务，提交成功后清空，避免再被附到第二笔申请上。
        this.form = { reason: '', commit: false }; this.fileIds = []; this.attachmentsReady = true
        this.load()
      }
      catch (e) { this.showError(e, '提交失败') } finally { this.busy = false }
    },
    async editReturned(x) {
      if (this.busy) return; this.busy = true
      try { const d = await affairsReturnedApi.getFunding(x.applicationId); this.editTarget = { ...x, ...d }; this.editReason = d.statement || ''; this.editNotice = ''; this.editVisible = true }
      catch (e) { this.showError(e, '退回申请加载失败') } finally { this.busy = false }
    },
    closeEdit() { if (!this.busy) { this.editVisible = false; this.editNotice = '' } },
    async saveAndResubmit() {
      if (this.busy) return
      const reason = this.editReason.trim(); if (reason.length < 5 || reason.length > 1000) return toast('申请理由需5–1000字')
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
        toast('已修改并重新提交'); this.editVisible = false; this.editNotice = ''; this.detailId = String(this.editTarget.applicationId); this.load()
      } catch (e) { this.showError(e, '保存修改失败') } finally { this.busy = false }
    },
    async appeal(x) {
      if (this.busy) return
      const reason = (this.reasons[x.applicationId] || '').trim(); if (reason.length < 5 || reason.length > 1000) return toast('申诉理由需5–1000字')
      this.busy = true
      try { await affairsFundingAppeal({ applicationId: x.applicationId, reason }); toast('申诉已提交'); this.reasons[x.applicationId] = ''; this.load() }
      catch (e) { this.showError(e, '提交失败') } finally { this.busy = false }
    }
  }
}
</script>

<style scoped>
.funding-detail-open { height:100vh; overflow:hidden; box-sizing:border-box; padding-bottom:0; }
.batch-search, .batch-meta { display: flex; align-items: center; gap: 8px; margin-top: 10px; }
.batch-search input { flex: 1; min-width: 0; height: 38px; }
.batch-search .btn, .batch-meta .btn { flex-shrink: 0; margin: 0; }
.batch-meta { flex-wrap: wrap; justify-content: space-between; }
.col { flex-direction: column; align-items: stretch; gap: 8px; }.row-between { display: flex; align-items: center; justify-content: space-between; gap: 8px; width: 100%; }.hint { font-size: 12px; color: #6b7280; display: block; }.hint.warn { color: #b45309; }.seg { display: flex; gap: 8px; margin-top: 10px; }.seg__btn { flex: 1; font-size: 13px; background: #f1f5f9; color: #334155; border: none; border-radius: 8px; padding: 8px; }.seg__btn.on { background: #2563eb; color: #fff; }.fld { margin-top: 10px; }.lbl { display: block; font-size: 12px; color: #6b7280; margin-bottom: 4px; }.picker, .ta { width: 100%; box-sizing: border-box; border: 1px solid #e5e7eb; border-radius: 8px; padding: 8px; font-size: 13px; background: #fff; }.ta { min-height: 72px; }.chk { display: flex; align-items: flex-start; gap: 8px; margin-top: 10px; }.chk__box { width: 18px; height: 18px; border: 1px solid #94a3b8; border-radius: 4px; text-align: center; line-height: 16px; font-size: 12px; color: #2563eb; flex-shrink: 0; }
.chk__t { font-size: 12px; color: #475569; }.btn { margin-top: 8px; background: #2563eb; color: #fff; border: none; border-radius: 8px; padding: 8px 12px; font-size: 13px; }.card-title { display: block; font-weight: 600; margin-bottom: 4px; }.fd__mask { position: fixed; inset: 0; z-index: 1000; background: rgba(15,23,42,.5); display: flex; align-items: flex-end; }.fd__sheet { width: 100%; border-radius: 18px 18px 0 0; padding: 18px; }.fd__actions { display: flex; gap: 10px; margin-top: 12px; }
.is-focus { outline: 2px solid var(--brand-primary); outline-offset: 2px; border-radius: var(--radius-md); }
.aid__flow { display: flex; gap: 6px; align-items: flex-start; padding: 8px; border-radius: 8px; background: rgba(59, 130, 246, 0.08); margin-top: 8px; }
.aid__k { font-size: 12px; color: #1e3a8a; line-height: 1.35; }
.aid__v { font-size: 12px; color: var(--text-primary); line-height: 1.35; flex: 1; }
</style>
