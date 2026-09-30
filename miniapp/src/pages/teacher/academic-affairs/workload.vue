<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" :title="showForm ? '提交工作量申报' : '工作量申报'" :before-back="backToDeclarations" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="d">
        <view class="section-head">
          <text class="section-head__title">我的工作量申报</text>
          <text class="section-head__more" @click="showForm = !showForm">{{ showForm ? '收起' : '+ 新增申报' }}</text>
        </view>

        <view class="card stack-sm" v-if="showForm">
          <text class="t-md t-bold">申报内容</text>
          <view v-if="hasUnknownWrite(writeObjectId)" class="wl__uncertain">本次申报未收到明确回执。已停止重复提交，请下拉刷新并核对申报记录。</view>
          <view class="wl__source"><text>正式任务与已核课时</text><text class="wl__tip">当前未提供任务核算证据。本次填写申报课时，审核结果见申报记录。</text></view>
          <text class="wl__group">工作量类别</text>
          <picker mode="selector" :range="categoryLabels" @change="onCatChange">
            <view class="wl__input wl__picker">{{ categoryLabels[catIndex] }}</view>
          </picker>
          <view class="wl__row">
            <input class="wl__input wl__half" type="digit" v-model="form.hours" placeholder="申报课时（必填）" placeholder-class="wl__ph" />
            <input class="wl__input wl__half" v-model="form.termCode" placeholder="学期（选填）" placeholder-class="wl__ph" />
          </view>
          <textarea class="wl__textarea" v-model="form.description" :maxlength="200"
                    placeholder="工作说明（如：期末监考3场/批阅高数试卷）" placeholder-class="wl__ph" />
          <button class="btn btn-primary" :disabled="!canSubmit || submitting || hasUnknownWrite(writeObjectId)" @click="submit">
            {{ submitting ? '提交中…' : hasUnknownWrite(writeObjectId) ? '等待核对结果' : '提交申报' }}
          </button>
          <text class="wl__tip">申报经教务处审核通过后计入工作量统计（仅供教务参考，非薪酬核算）。</text>
        </view>

        <view class="list-group" v-if="!showForm && d.items && d.items.length">
          <view v-for="r in visibleDeclarations" :key="r.declarationId" class="list-row wl__item">
            <view class="flex-1">
              <text class="t-md">{{ r.categoryLabel }} · {{ r.hours }} 课时<text v-if="r.termCode"> · {{ r.termCode }}</text></text>
              <text class="wl__sub">{{ r.description || '无说明' }}</text>
              <text v-if="r.reviewNote" class="wl__note">审核意见：{{ r.reviewNote }}</text>
            </view>
            <MobileStatusTag :status="r.status" />
          </view>
        </view>
        <MobileGlobalState v-else-if="!showForm" state="empty" title="暂无申报" description="点击右上角新增，申报教学/监考/阅卷等工作量。" />
        <view v-if="!showForm && declarationPageCount > 1" class="wl__pages">
          <button class="btn btn-ghost" :disabled="declarationPageIndex <= 1 || state === 'loading'" @click="load(null, declarationPageIndex - 1)">上一页</button>
          <text>{{ declarationPageIndex }} / {{ declarationPageCount }}</text>
          <button class="btn btn-ghost" :disabled="!declarationHasMore || state === 'loading'" @click="load(null, declarationPageIndex + 1)">下一页</button>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { createSubmitLock, normalizeError } from '@/services/request'
import { useSessionStore } from '@/stores/session'
import { toast } from '@/utils/nav'
import { beginPersistentWrite, clearPersistentWrite, isExplicitWriteRejection, isForbiddenResponse, listPersistentWrites, persistWriteAck, teacherWriteContext } from './write-result'

const submitLock = createSubmitLock(1500)
const CATS = [
  { value: 'TEACHING', label: '教学' }, { value: 'INVIGILATE', label: '监考' },
  { value: 'MARKING', label: '阅卷' }, { value: 'PAPER', label: '出卷' }, { value: 'OTHER', label: '其他' }
]
let workloadCommandSequence = 0

function nextWorkloadCommandKey() {
  workloadCommandSequence += 1
  return `wmp_${Date.now().toString(36)}_${workloadCommandSequence.toString(36)}_${Math.random().toString(36).slice(2, 12)}`
}

export default {
  data() {
    return { d: null, state: 'loading', showForm: false, submitting: false, catIndex: 0, declarationPage: 1,
      form: { hours: '', termCode: '', description: '' }, unknownWrites: {}, writeStorageBlocked: false }
  },
  computed: {
    declarationRows() { return (this.d && this.d.items) || [] },
    declarationPageIndex() { return Math.max(1, Number((this.d && this.d.page) || this.declarationPage || 1)) },
    declarationPageSize() { return Math.max(1, Number((this.d && this.d.pageSize) || 20)) },
    declarationTotal() { return Math.max(0, Number((this.d && this.d.total) || 0)) },
    declarationPageCount() { return Math.max(1, Math.ceil(this.declarationTotal / this.declarationPageSize)) },
    declarationHasMore() { return !!(this.d && this.d.hasMore) },
    visibleDeclarations() { return this.declarationRows },
    categoryLabels() { return CATS.map((c) => c.label) },
    canSubmit() { return Number(this.form.hours) > 0 },
    writeObjectId() { return 'NEW_DECLARATION' }
  },
  onLoad() { this._pageActive = true; this._viewContext = this.contextKey(); this.syncUnknownWrites(); this.load() },
  onShow() {
    this._pageActive = true
    this.syncUnknownWrites()
    const context = this.contextKey()
    if (this._viewContext !== context) {
      this._viewContext = context
      this._submitEpoch = (this._submitEpoch || 0) + 1
      this.submitting = false
      this.showForm = false
      this.catIndex = 0
      this.declarationPage = 1
      this.form = { hours: '', termCode: '', description: '' }
      this.syncUnknownWrites()
      this._needsRefresh = false
      this.load()
      return
    }
    if (this._needsRefresh) { this._needsRefresh = false; this.load() }
  },
  onHide() { this._pageActive = false; this._needsRefresh = true; this._loadEpoch = (this._loadEpoch || 0) + 1 },
  onUnload() { this._pageActive = false; this._loadEpoch = (this._loadEpoch || 0) + 1 },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  onBackPress() { if (!this.showForm) return false; this.backToDeclarations(); return true },
  methods: {
    backToDeclarations() { if (!this.showForm) return true; if (this.submitting) return false; this.showForm = false; return false },
    contextKey() {
      return teacherWriteContext(useSessionStore())
    },
    writeKey(objectId) { return `workload|${String(objectId || '')}` },
    hasUnknownWrite(objectId) { return this.writeStorageBlocked || !!this.unknownWrites[this.writeKey(objectId)] },
    syncUnknownWrites(context = this.contextKey()) { const result = listPersistentWrites(context); this.writeStorageBlocked = !result.ok; this.unknownWrites = result.ok ? Object.fromEntries(result.records.map((row) => [this.writeKey(row.objectId), row])) : {}; return result },
    beginWrite(context, objectId, requestKey) { const result = beginPersistentWrite(context, 'workload', objectId, { requestKey }); this.syncUnknownWrites(); if (!result.ok) toast(result.storageError ? '无法安全保存待核对记录，本次未提交' : '该申报正在等待正式记录核对'); return result.ok },
    ackWrite(context, objectId, ack) { const ok = persistWriteAck(context, 'workload', objectId, ack); this.syncUnknownWrites(); return ok },
    clearWrite(context, objectId) { const ok = clearPersistentWrite(context, 'workload', objectId); this.syncUnknownWrites(); return ok },
    clearPrivateWorkload() {
      this._loadEpoch = (this._loadEpoch || 0) + 1
      this._submitEpoch = (this._submitEpoch || 0) + 1
      this.d = null; this.showForm = false; this.submitting = false; this.declarationPage = 1
      this.catIndex = 0; this.form = { hours: '', termCode: '', description: '' }; this.state = 'error'
    },
    async reconcileWrites(rows, context, epoch) {
      const pending = listPersistentWrites(context)
      if (!pending.ok) { this.syncUnknownWrites(); return }
      for (const record of pending.records.filter((row) => row.action === 'workload')) {
        if (record.state === 'ACK' && record.ackId && rows.some((row) => String(row.declarationId || row.id || '') === record.ackId)) {
          this.clearWrite(record.context, record.objectId)
          continue
        }
        // 旧版本没有命令键时无法安全推断其落单结果，继续保留“待核对”；
        // 新版本按原命令键读取同一教师自己的正式回执，不会重新发起写操作。
        if (!record.requestKey || typeof teacherApi.getWorkloadCommandReceipt !== 'function') continue
        try {
          const receipt = await teacherApi.getWorkloadCommandReceipt(record.requestKey)
          if (!this._pageActive || this._loadEpoch !== epoch || this.contextKey() !== context) return
          const result = receipt && receipt.state === 'SUCCESS' && receipt.result
          const declarationId = String(result && (result.declarationId || result.id) || '')
          if (receipt && receipt.operation === 'WORKLOAD_SUBMIT' && String(receipt.commandKey || '') === record.requestKey && declarationId) {
            this.ackWrite(record.context, record.objectId, { ackId: declarationId, parentId: record.objectId })
            this.clearWrite(record.context, record.objectId)
          }
        } catch (error) {
          if (!this._pageActive || this._loadEpoch !== epoch || this.contextKey() !== context) return
          if (isForbiddenResponse(error)) { this.clearPrivateWorkload(); return }
        }
      }
    },
    async load(done, requestedPage = this.declarationPage) {
      const epoch = (this._loadEpoch || 0) + 1
      this._loadEpoch = epoch
      const context = this.contextKey()
      const page = Math.max(1, Number(requestedPage) || 1)
      this.state = 'loading'
      try {
        const d = await teacherApi.getWorkloadDeclarations({ page, pageSize: 20 })
        if (!this._pageActive || this._loadEpoch !== epoch || this.contextKey() !== context) return
        this.d = d
        this.declarationPage = Math.max(1, Number((d && d.page) || page))
        this.state = 'ready'
        await this.reconcileWrites((d && d.items) || [], context, epoch)
      } catch (error) {
        if (this._pageActive && this._loadEpoch === epoch && this.contextKey() === context) {
          if (isForbiddenResponse(error)) this.clearPrivateWorkload()
          this.state = normalizeError(error).pageState || 'error'
        }
      } finally { if (done) done() }
    },
    onCatChange(e) { this.catIndex = Number(e.detail.value) },
    submit() {
      if (!this.canSubmit || this.submitting || this.hasUnknownWrite(this.writeObjectId)) return
      const commandKey = nextWorkloadCommandKey()
      const body = {
        category: CATS[this.catIndex].value,
        hours: Number(this.form.hours),
        termCode: this.form.termCode.trim() || undefined,
        description: this.form.description.trim() || undefined,
        commandKey
      }
      const context = this.contextKey()
      const objectId = this.writeObjectId
      if (!this.beginWrite(context, objectId, commandKey)) return
      this.submitting = true
      const epoch = (this._submitEpoch || 0) + 1
      this._submitEpoch = epoch
      const snapshot = JSON.stringify([this.catIndex, this.form])
      submitLock.run(() => teacherApi.submitWorkload(body))
        .then(async (ack) => {
          const declarationId = String(ack && (ack.declarationId || ack.id) || '')
          if (declarationId) this.ackWrite(context, objectId, { ackId: declarationId, parentId: objectId })
          if (!this._pageActive || this._submitEpoch !== epoch || this.contextKey() !== context) return
          if (!declarationId) { toast('申报回执缺少单据编号，结果待核实，请勿重复提交'); this.load(null, 1); return }
          this.declarationPage = 1
          const reading = this.load(null, 1)
          const readEpoch = this._loadEpoch
          await reading
          if (!this._pageActive || this._submitEpoch !== epoch || this._loadEpoch !== readEpoch || this.contextKey() !== context) return
          const verified = this.state === 'ready' && !this.hasUnknownWrite(objectId) && this.declarationRows.some(row => String(row.declarationId || row.id || '') === declarationId)
          if (!verified) { toast('已收到申报编号，正式记录尚未核对，请勿重复提交'); return }
          if (JSON.stringify([this.catIndex, this.form]) !== snapshot) {
            toast('原申报已核对，当前新内容已保留')
            return
          }
          uni.showToast({ title: '申报已提交并核对', icon: 'success' })
          this.showForm = false
          this.catIndex = 0
          this.form = { hours: '', termCode: '', description: '' }
        }).catch((e) => {
          if (isExplicitWriteRejection(e)) this.clearWrite(context, objectId)
          if (!this._pageActive || this._submitEpoch !== epoch || this.contextKey() !== context) return
          if (e && e.code === 'LOCKED') return
          if (isForbiddenResponse(e)) { this.clearPrivateWorkload(); return }
          if (isExplicitWriteRejection(e)) toast(normalizeError(e).text)
          else { toast('申报结果未确认，已停止重复提交；请刷新后核对申报记录'); this.load() }
        }).finally(() => { if (this._submitEpoch === epoch && this.contextKey() === context) this.submitting = false })
    }
  }
}
</script>

<style scoped>
.wl__pages { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin: 16px 0; }
.btn.btn-primary { background: var(--teacher-600); border-color: var(--teacher-600); color: #fff; }
.btn.btn-ghost { color: var(--teacher-700); border-color: var(--teacher-200); }
.btn[disabled] { opacity: .5; }
.wl__source { display: flex; flex-direction: column; gap: 8px; padding: 12px; background: var(--teacher-50); border-radius: 12px; font-size: 14px; }
.wl__uncertain { padding: 10px 12px; border-radius: 10px; background: var(--warning-50); color: var(--warning-700); font-size: 13px; line-height: 1.5; }
.wl__group { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); font-weight: 600; margin-top: var(--space-1); }
.wl__input { width: 100%; min-height: var(--touch-target-min); font-size: var(--font-size-base); color: var(--text-primary); border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: 0 var(--space-3); box-sizing: border-box; }
.wl__picker { line-height: var(--touch-target-min); }
.wl__row { display: flex; gap: var(--space-2); }
.wl__half { flex: 1; }
.wl__textarea { width: 100%; min-height: 60px; font-size: var(--font-size-base); color: var(--text-primary); border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: var(--space-2); box-sizing: border-box; }
.wl__ph { color: var(--text-tertiary); }
.wl__tip { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.wl__item { align-items: flex-start; }
.wl__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.wl__note { display: block; font-size: var(--font-size-xs); color: var(--text-secondary); margin-top: 4px; }
</style>
