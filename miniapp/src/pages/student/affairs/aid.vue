<template>
  <view class="page-wrap" :class="{ 'aid-detail-open': detailVisible }">
    <MobileNavBar variant="brand" title="困难认定" show-back :before-back="beforeBack" />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="d">
        <view class="card aid__overview">
          <view><text class="aid__label">我的困难认定</text><text class="aid__level">{{ d.currentLevelLabel || '尚未认定' }}</text><text class="hint">申请、审核与结果和电脑端同步</text></view>
          <button class="btn btn-ghost" :disabled="busy || refreshing" @click="load">{{ refreshing ? '刷新中' : '刷新进度' }}</button>
        </view>
        <MobileInlineAlert v-if="loadError" type="warning" title="进度刷新失败" :description="loadError" />
        <view class="aid__entry"><text class="hint">按学校开放的批次申请</text><button class="btn" :disabled="busy" @click="formVisible = !formVisible">{{ formVisible ? '收起申请' : '发起申请' }}</button></view>

        <view class="card" v-show="formVisible">
          <text class="card-title">发起认定申请</text>
          <view class="aid__batch-search"><input class="inp" v-model.trim="batchQuery" maxlength="100" placeholder="按批次名称或学年搜索" confirm-type="search" @confirm="loadBatches()" /><button class="btn btn-ghost" :disabled="batchLoading" @click="loadBatches()">搜索</button></view>
          <MobileInlineAlert v-if="batchError" type="warning" title="批次暂不可用" :description="batchError" />
          <view class="aid__batch-meta"><text class="hint">{{ batchLoading ? '正在查找开放批次…' : `已加载 ${batches.length} / ${batchTotal} 个匹配批次` }}</text><button v-if="batchError" class="btn btn-ghost" :disabled="batchLoading" @click="loadBatches()">重试</button><button v-else-if="batches.length < batchTotal" class="btn btn-ghost" :disabled="batchLoading" @click="loadBatches(true)">加载更多批次</button></view>
          <view v-if="!batchLoading && !batchError && !batchOptions.length" class="hint">没有匹配的开放批次，可修改搜索条件或等待学校发布。</view>
          <template v-if="batchOptions.length">
            <view class="fld"><text class="lbl">认定批次</text><picker mode="selector" :range="batchOptions" range-key="label" :value="batchIndex" @change="onBatch"><view class="picker">{{ selectedBatch?.label || '请选择认定批次' }}</view></picker></view>
            <view class="fld"><text class="lbl">申请等级</text><picker mode="selector" :range="levels" range-key="label" :value="levelIndex" @change="onLevel"><view class="picker">{{ levels[levelIndex].label }}</view></picker></view>
            <view class="grid2">
              <view class="fld"><text class="lbl">家庭成员数 <text class="req">*</text></text><input class="inp" type="number" v-model="form.memberCount" placeholder="1-30人" /></view>
              <view class="fld"><text class="lbl">家庭年收入（元）</text><input class="inp" type="digit" v-model="form.income" placeholder="选填，不得为负数" /></view>
            </view>
            <view class="fld"><text class="lbl">家庭债务（元）</text><input class="inp" type="digit" v-model="form.debt" placeholder="选填，不得为负数" /></view>
            <view class="fld"><text class="lbl">特殊情况标签</text><input class="inp" v-model="form.specialTags" maxlength="200" placeholder="低保、孤残、重大疾病等，用逗号分隔" /></view>
            <view class="fld"><text class="lbl">困难情况说明（10-500字） <text class="req">*</text></text><textarea class="ta" v-model="form.reason" maxlength="500" placeholder="请客观说明家庭经济困难具体情况" /></view>
            <text class="counter">{{ (form.reason || '').trim().length }}/500</text>
            <label class="chk" @click="form.commit = !form.commit"><text class="chk__box">{{ form.commit ? '✓' : '' }}</text><text class="chk__t">本人确认填写的信息真实、完整，并提交学校审核。</text></label>
            <button class="btn" :disabled="busy || !canSubmit" @click="submitApply">提交认定申请</button>
          </template>
        </view>

        <view class="section-head"><text class="section-head__title">我的申请 · {{ (d.items || []).length }}</text></view>
        <MobileInlineAlert v-if="focusMissing" type="warning" title="没有找到这条记录"
          description="消息或待办指向的困难认定申请不在当前列表里，可能已被处理、撤回或超出本页范围。" />
        <view class="list-group" v-if="d.items && d.items.length">
          <view v-for="x in d.items" :key="x.applyId" :id="'aid-' + x.applyId" :class="{ 'is-focus': isFocused(x) }" class="list-row col">
            <view class="row-between">
              <view class="flex-1"><text class="t-md">申请等级：{{ x.applyLevelLabel || levelLabel(x.applyLevel) }}</text><text class="aid__sub" v-if="x.finalLevel">{{ x.status === 'PUBLICITY' ? '拟认定等级' : '认定等级' }}：{{ x.finalLevelLabel || levelLabel(x.finalLevel) }}</text><text class="aid__sub aid__return" v-if="x.returnReason">处理意见：{{ x.returnReason }}</text></view>
              <MobileStatusTag :status="x.status" :label="x.statusLabel" />
            </view>
            <view class="aid__flow" v-if="workflowHint(x)"><text class="aid__k">流程提示：</text><text class="aid__v">{{ workflowHint(x) }}</text></view>
            <button class="btn btn-ghost" :disabled="busy" @click="openDetail(x)">查看申请详情</button>
            <button v-if="allows(x, 'EDIT_RETURNED') || allows(x, 'RESUBMIT')" class="btn btn-ghost" :disabled="busy" @click="editReturned(x)">修改后重新提交</button>
            <text v-if="x.hasPendingObjection" class="hint">异议处理中</text>
            <template v-if="allows(x, 'SUBMIT_OBJECTION')"><button class="btn btn-ghost" @click="objectionId = objectionId === x.applyId ? '' : x.applyId">{{ objectionId === x.applyId ? '收起异议' : '对公示结果有异议' }}</button><template v-if="objectionId === x.applyId"><textarea class="ta" maxlength="500" v-model="reasons[x.applyId]" placeholder="对公示认定结果有异议（5-500字）" /><button class="btn" :disabled="busy || (reasons[x.applyId] || '').trim().length < 5" @click="object(x)">提交公示异议</button></template></template>
          </view>
        </view>
        <MobileGlobalState v-else state="empty" title="暂无困难认定申请记录" description="点击“发起申请”，查看学校开放批次并填写家庭情况。" />
      </view>
    </MobileGlobalState>

    <view v-if="detailVisible" class="aid__detail">
      <view class="aid__detail-head"><button class="btn btn-ghost" @click="closeDetail">返回记录</button><text class="card-title">申请详情</text><button class="btn btn-ghost" :disabled="detailState === 'loading'" @click="openDetail({ applyId: detailId })">刷新</button></view>
      <scroll-view scroll-y class="aid__detail-scroll">
        <MobileGlobalState :state="detailState" @retry="openDetail({ applyId: detailId })">
          <view v-if="detail" class="page-pad stack">
            <view class="card"><text class="card-title">{{ detail.batchName }}</text><text class="aid__sub">{{ detail.schoolYear }} · 申请编号 {{ detail.applyId }}</text><MobileStatusTag :status="detail.status" :label="detail.statusLabel" /><view class="aid__flow"><text>{{ detail.progressHint }}</text></view><MobileInlineAlert v-if="detail.returnReason" type="warning" title="处理意见" :description="detail.returnReason" /></view>
            <view class="card"><text class="card-title">认定信息</text><view class="aid__fact"><text>申请等级</text><text>{{ detail.applyLevelLabel }}</text></view><view v-if="detail.finalLevel" class="aid__fact"><text>{{ detail.status === 'PUBLICITY' ? '拟认定等级' : '认定等级' }}</text><text>{{ detail.finalLevelLabel }}</text></view><view v-if="detail.createdAt" class="aid__fact"><text>创建时间</text><text>{{ displayTime(detail.createdAt) }}</text></view><view v-if="detail.publicityEnd" class="aid__fact"><text>公示截止</text><text>{{ displayTime(detail.publicityEnd) }}</text></view><view v-if="detail.resultAt" class="aid__fact"><text>认定时间</text><text>{{ displayTime(detail.resultAt) }}</text></view></view>
            <view class="card"><text class="card-title">我提交的家庭情况</text><view class="aid__fact"><text>家庭成员</text><text>{{ detail.memberCount == null ? '未填写' : detail.memberCount + ' 人' }}</text></view><view class="aid__fact"><text>家庭年收入</text><text>{{ amount(detail.annualIncome) }}</text></view><view class="aid__fact"><text>家庭债务</text><text>{{ amount(detail.debt) }}</text></view><view class="aid__fact"><text>特殊情况</text><text>{{ (detail.specialTags || []).join('、') || '未填写' }}</text></view><text class="lbl">困难情况说明</text><text class="aid__statement">{{ detail.statement || '未填写' }}</text></view>
            <view v-if="detail.status === 'PUBLICITY'" class="aid__flow"><text>{{ detail.hasPendingObjection ? '异议复核完成后，学校才能确认认定结果。' : detail.publicityHint }}</text></view>
            <view v-if="detail.adjustment" class="card"><text class="card-title">等级调整审核中</text><view class="aid__flow"><text>{{ detail.adjustment.fromLabel }} → {{ detail.adjustment.targetLabel }}</text></view><text class="aid__sub">这是申请调整的目标，审核完成前仍以当前认定等级为准。</text></view>
            <view v-if="detail.objectionResults && detail.objectionResults.length" class="card"><text class="card-title">公示异议与复核</text><view v-for="item in detail.objectionResults" :key="item.objectionId" class="aid__result"><text class="card-title">{{ item.resultLabel || item.statusLabel }}</text><text v-if="item.reviewedAt" class="aid__sub">{{ displayTime(item.reviewedAt) }}</text><text class="aid__statement">{{ item.reviewOpinion || '已进入复核，完成后在这里查看结论。' }}</text></view></view>
            <view class="card"><text class="card-title">申请材料</text><text class="hint">查看这份申请的补交要求、文件版本与验收结果。</text><button class="btn btn-ghost" @click="openMaterials">材料查看与补交</button></view>
            <view class="card aid__history"><text class="card-title">办理记录</text><text v-if="!detail.history || !detail.history.length" class="hint">暂无可核验的历史记录。</text><view v-for="item in detail.history || []" :key="item.id" class="aid__event"><text class="card-title">{{ item.title }}</text><text class="aid__sub">{{ item.occurredAt ? displayTime(item.occurredAt) : '时间未记录' }}</text><text v-if="item.description" class="aid__statement">{{ item.description }}</text></view></view>
            <button v-if="allows(detail, 'EDIT_RETURNED')" class="btn" :disabled="busy" @click="editReturned(detail)">按意见补正并重提</button>
          </view>
        </MobileGlobalState>
      </scroll-view>
    </view>
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
import { hasFocusRow, isFocusRow, readFocusId, scrollToFocus } from '@/utils/listFocus.mjs'
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
    return { focusId: '', focusMissing: false,
      d: null, state: 'loading', busy: false, reasons: {}, batches: [], selectedBatch: null, batchError: '',
      batchQuery: '', batchAppliedQuery: '', batchPage: 0, batchTotal: 0, batchLoading: false, batchSeq: 0,
      levels: LEVELS, levelIndex: 0, form: blankForm(), formVisible: false, objectionId: '',
      refreshing: false, loadError: '', loadSeq: 0,
      detailVisible: false, detailId: '', detail: null, detailState: 'loading', detailSeq: 0,
      editVisible: false, editTarget: {}, editLevelIndex: 0, editForm: blankEditForm(), editNotice: ''
    }
  },
  computed: {
    batchOptions() { return this.selectedBatch && !this.batches.some(x => x.batchId === this.selectedBatch.batchId) ? [this.selectedBatch, ...this.batches] : this.batches },
    batchIndex() { return Math.max(0, this.batchOptions.findIndex(x => x.batchId === this.selectedBatch?.batchId)) },
    canSubmit() { return !!this.selectedBatch && this.form.commit && this.validAidForm(this.form) },
    canSaveEdit() { return this.validAidForm(this.editForm) }
  },
  // V3 §4.4 LIST_FOCUS：待办/消息深链带 recordId 进来时必须定位到那条记录。
  onLoad(query) { this.focusId = readFocusId(query); this.load() },
  onUnload() { this.loadSeq++; this.batchSeq++; this.detailSeq++ },
  methods: {
    openMaterials() { uni.navigateTo({ url: '/pages/student/affairs/index?bizType=AID&bizId=' + encodeURIComponent(this.detailId) }) },
    displayTime(value) { return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '未记录' },
    amount(value) { return value == null || value === '' ? '未填写' : `${Number(value).toLocaleString('zh-CN')} 元` },
    async beforeBack() {
      if (this.busy) return false
      if (this.editVisible) { this.closeEdit(); return false }
      if (this.detailVisible) { this.closeDetail(); return false }
      if (Object.entries(this.form).some(([key, value]) => key !== 'commit' && value !== '') || Object.values(this.reasons).some(Boolean)) {
        return new Promise(resolve => uni.showModal({ title: '离开困难认定？', content: '未提交的填写内容将丢失。', confirmText: '离开', success: r => resolve(r.confirm), fail: () => resolve(false) }))
      }
      return true
    },
    async openDetail(row) {
      const seq = ++this.detailSeq
      this.detailId = row.applyId; this.detail = null; this.detailVisible = true; this.detailState = 'loading'
      try {
        const detail = await affairsReturnedApi.getAidDetail(row.applyId)
        if (seq !== this.detailSeq) return
        this.detail = detail; this.detailState = 'ready'
        if (this.d) this.d.items = (this.d.items || []).map(item => String(item.applyId) === String(detail.applyId) ? {
          ...item, status: detail.status, statusLabel: detail.statusLabel, progressHint: detail.progressHint,
          applyLevel: detail.applyLevel, applyLevelLabel: detail.applyLevelLabel,
          finalLevel: detail.finalLevel, finalLevelLabel: detail.finalLevelLabel,
          returnReason: detail.returnReason, allowedActions: detail.allowedActions,
          hasPendingObjection: detail.hasPendingObjection
        } : item)
        // 当前认定可能来自另一批次，刷新权威概览，不能用打开的历史单推算页头等级。
        await this.load()
      } catch (e) { if (seq === this.detailSeq) { this.detailState = 'error'; this.showError(e, '详情加载失败') } }
    },
    closeDetail() { this.detailSeq++; this.detailVisible = false; this.detail = null },
    isFocused(row) { return isFocusRow(row, this.focusId, ['applyId']) },
    workflowHint(item) {
      return item.progressHint || '请刷新查看最新办理进度。'
    },
    levelLabel(value) { return LEVELS.find(x => x.value === value)?.label || '等级待确认' },
    applyFocus() {
      if (!this.focusId) return
      const rows = (this.d && this.d.items) || []
      this.focusMissing = !hasFocusRow(rows, this.focusId, ['applyId'])
      if (this.focusMissing) return
      this.$nextTick(() => scrollToFocus('#aid-', this.focusId))
    },
    allows(item, action) { return Array.isArray(item && item.allowedActions) && item.allowedActions.includes(action) },
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
    async load() {
      const seq = ++this.loadSeq
      if (!this.d) this.state = 'loading'
      this.refreshing = true; this.loadError = ''
      try {
        const [d] = await Promise.all([studentApi.getMyAid(), this.loadBatches()])
        if (seq !== this.loadSeq) return
        this.d = d
        this.state = 'ready'; this.applyFocus()
      } catch (e) {
        if (seq !== this.loadSeq) return
        this.state = this.d ? 'ready' : 'error'; this.loadError = '仍保留上次记录，请重试获取最新进度。'; this.showError(e, '困难认定加载失败')
      } finally { if (seq === this.loadSeq) this.refreshing = false }
    },
    async loadBatches(more = false) {
      if (more && this.batchLoading) return
      const seq = ++this.batchSeq
      const page = more ? this.batchPage + 1 : 1
      const keyword = more ? this.batchAppliedQuery : this.batchQuery.trim()
      this.batchLoading = true; this.batchError = ''
      try {
        const data = await studentApi.getAidBatches({ page, pageSize: 20, keyword })
        if (seq !== this.batchSeq) return
        const rows = (data?.items || []).map(x => ({ ...x, label: `${x.batchName || x.schoolYear || '认定批次'}（截止 ${(x.applyEnd || '').slice(0, 10) || '不限'}）` }))
        this.batches = more ? [...new Map([...this.batches, ...rows].map(x => [x.batchId, x])).values()] : rows
        this.batchTotal = data?.total ?? rows.length; this.batchPage = page; this.batchAppliedQuery = keyword
      } catch {
        if (seq === this.batchSeq) this.batchError = '批次查找失败，已选批次和填写内容已保留，请重试。'
      } finally { if (seq === this.batchSeq) this.batchLoading = false }
    },
    onBatch(e) { this.selectedBatch = this.batchOptions[Number(e.detail.value)] || null }, onLevel(e) { this.levelIndex = Number(e.detail.value) },
    async submitApply() {
      if (!this.selectedBatch || this.busy) return
      const error = this.validate(this.form); if (error) return toast(error)
      if (!this.form.commit) return toast('请勾选本人确认承诺')
      this.busy = true
      try {
        await studentApi.applyAid({ batchId: this.selectedBatch.batchId, applyLevel: this.levels[this.levelIndex].value, ...this.payload(this.form), confirm: true })
        toast('申请已提交'); this.form = blankForm(); this.formVisible = false; await this.load()
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
    closeEdit() {
      if (this.busy) return
      uni.showModal({ title: '关闭补正？', content: this.editNotice || '尚未保存的修改会丢失。', confirmText: '关闭', success: r => { if (r.confirm) { this.editVisible = false; this.editNotice = '' } } })
    },
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
        toast('已修改并重新提交'); this.editVisible = false; this.editNotice = ''; await this.load()
        if (this.detailVisible) await this.openDetail(this.editTarget)
      } catch (e) { this.showError(e, '保存修改失败') } finally { this.busy = false }
    },
    async object(x) {
      if (this.busy) return
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
.is-focus { outline: 2px solid var(--brand-primary); outline-offset: 2px; border-radius: var(--radius-md); }.aid__flow { display: flex; gap: 6px; align-items: flex-start; padding: 8px; border-radius: 8px; background: rgba(59, 130, 246, 0.08); margin-top: 8px; }.aid__k { font-size: 12px; color: #1e3a8a; line-height: 1.35; }.aid__v { font-size: 12px; color: var(--text-primary); line-height: 1.35; flex: 1; }
</style>

<style scoped>
.aid__batch-search, .aid__batch-meta { display: flex; gap: 10px; align-items: center; margin-top: 12px; }
.aid__batch-search .inp { flex: 1; min-width: 0; }
.aid__batch-search .btn, .aid__batch-meta .btn { flex-shrink: 0; margin: 0; }
.aid__batch-meta { justify-content: space-between; flex-wrap: wrap; }
.aid__overview, .aid__entry, .aid__detail-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.aid__result { padding: 12px 0; border-bottom: 1px solid var(--border-base); }
.aid__event { padding: 8px 0 18px 16px; margin-left: 4px; border-left: 2px solid var(--brand-primary); }.aid__event:last-child { padding-bottom: 4px; }.aid__event .aid__statement { margin-top: 6px; }
.aid__overview .btn, .aid__entry .btn { flex-shrink: 0; margin: 0; }
.aid__level { font-size: 24px; margin: 6px 0; }
.hint, .lbl, .aid__sub, .chk__t { font-size: 14px; line-height: 1.6; color: var(--text-secondary); }
.btn { min-height: 44px; font-size: 14px; line-height: 1.6; background: var(--brand-primary); }
.btn-ghost { background: var(--bg-card); color: var(--brand-primary); border: 1px solid var(--border-color, #d8e0e7); }
.inp, .picker, .ta { min-height: 44px; font-size: 15px; color: var(--text-primary); background: var(--bg-card); border-color: var(--border-color, #d8e0e7); }
.ta { min-height: 112px; line-height: 1.6; }
.aid__flow { font-size: 14px; line-height: 1.6; background: var(--bg-page); padding: 12px; }
.aid__k { display: none; }.aid__v { font-size: 14px; line-height: 1.6; }
.aid__mask { z-index: 90; }
.aid__sheet { box-sizing: border-box; padding-bottom: calc(18px + env(safe-area-inset-bottom)); }
.aid-detail-open { height: 100vh; overflow: hidden; box-sizing: border-box; padding-bottom: 0; }
.aid__detail { position: fixed; inset: 0; z-index: 80; display: flex; flex-direction: column; overflow: hidden; box-sizing: border-box; background: var(--bg-page); padding-top: env(safe-area-inset-top); }
.aid__detail-head { padding: 8px 12px; background: var(--bg-card); border-bottom: 1px solid var(--border-color, #d8e0e7); }
.aid__detail-head .btn { margin: 0; }.aid__detail-head .card-title { margin: 0; }
.aid__detail-scroll { height: 0; flex: 1; }.aid__detail-scroll .stack { padding-bottom: calc(24px + env(safe-area-inset-bottom)); }
.aid__fact { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; padding: 10px 0; font-size: 14px; line-height: 1.6; border-bottom: 1px solid var(--border-color, #d8e0e7); }
.aid__fact > text:first-child { flex-shrink: 0; color: var(--text-secondary); }.aid__fact > text:last-child { text-align: right; overflow-wrap: anywhere; }
.aid__statement { display: block; font-size: 15px; line-height: 1.8; white-space: pre-wrap; overflow-wrap: anywhere; }.aid__detail .lbl { margin-top: 14px; }
</style>
