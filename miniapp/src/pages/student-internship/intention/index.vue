<template>
  <view class="internship-surface mobile-page mobile-student page-wrap itn">
    <MobileNavBar title="实习意向" show-back :before-back="beforeBack" />
    <MobileGlobalState :state="pageState" :description="error" @retry="load">
      <view class="page-pad stack">
        <view class="card itn__head">
          <text class="card-title">实习意向填报</text>
          <text class="itn__hint">{{ meta.readOnlyReason || '填写城市、行业或岗位偏好，供学校匹配参考。' }}</text>
          <text class="itn__hint">仅供学校匹配参考，不代表申请通过或岗位落实。</text>
          <view v-if="meta.intention" class="itn__status">
            <MobileStatusTag :status="statusTag(meta.intention.status)" :label="meta.intention.statusLabel || '意向状态待核对'" />
            <text class="itn__time">{{ formatDateTime(meta.intention.updatedAt) }} · 第 {{ meta.intention.version }} 版</text>
          </view>
        </view>

        <MobileInlineAlert v-if="error" type="warning" :description="error" />
        <view v-if="conflict" class="card stack">
          <text>原单已变化或上次操作结果待确认，填写内容已保留。</text>
          <button class="mobile-control" :disabled="reading" @click="rereadConflict">读取最新原单</button>
          <template v-if="latest"><text>{{ latest.intention?.statusLabel || '尚无意向' }} · {{ latest.intention?.intentionNote || '未填写说明' }}</text><text v-if="latest.canEdit !== true">{{ latest.readOnlyReason || '原单当前不可编辑，请返回后重新进入查看。' }}</text><button class="mobile-control" :disabled="reading || latest.canEdit !== true" @click="adoptLatest">已核对原单，保留输入继续</button></template>
        </view>
        <text v-if="meta.intention?.status === 'WITHDRAWN' && !newDraft" class="itn__hint">撤回原单保留原内容，可重新提交；需要修改时请重新填写。</text>
        <button v-if="ready && meta.canCreateNew && !newDraft && !conflict" class="mobile-control btn btn-ghost" @click="startNew">重新填写意向</button>

        <view v-if="meta.intention || canEdit || newDraft" class="card stack">
          <view class="itn__field">
            <text class="itn__label">意向城市</text>
            <input v-model="form.preferredCity" class="mobile-input itn__input" placeholder="如：上海、杭州" :disabled="!canEdit" />
          </view>
          <view class="itn__field">
            <text class="itn__label">意向行业</text>
            <input v-model="form.preferredIndustry" class="mobile-input itn__input" placeholder="如：软件、智能制造" :disabled="!canEdit" />
          </view>
          <view class="itn__field">
            <text class="itn__label">意向岗位（可选）</text>
            <picker class="mobile-picker" mode="selector" :range="positionLabels" :value="positionIndex + 1" :disabled="!canEdit" @change="onPositionPick">
              <view class="itn__picker">{{ positionLabel || '从已发布岗位中选择' }}</view>
            </picker>
            <button v-if="positionsMore" class="mobile-control btn btn-ghost" :disabled="reading || submitting" @click="loadMorePositions">继续读取岗位</button>
          </view>
          <view class="itn__field">
            <text class="itn__label">补充说明</text>
            <textarea v-model="form.intentionNote" class="mobile-textarea itn__textarea" maxlength="500"
              placeholder="可说明期望企业类型、通勤距离、特殊要求等" :disabled="!canEdit" />
          </view>
        </view>

        <MobileInlineAlert v-if="!meta.intention && !canEdit" type="info" description="尚未填报实习意向。" />
        <MobileInlineAlert v-if="canEdit && !positions.length" type="info"
          description="暂无可选岗位，可先填写城市/行业意向，待岗位发布后再补充。" />
      </view>
    </MobileGlobalState>

    <MobileSafeAreaBar v-if="ready && (canEdit || canSubmit || canWithdraw)">
      <button v-if="canEdit" class="mobile-control btn btn-ghost flex-1" :disabled="submitting" @click="save">{{ meta.intention?.status === 'SUBMITTED' ? '保存修改' : '保存草稿' }}</button>
      <button v-if="canSubmit" class="mobile-control btn btn-primary flex-1" :disabled="submitting" @click="submit">提交意向</button>
      <button v-if="canWithdraw" class="mobile-control btn btn-ghost flex-1" :disabled="submitting" @click="withdraw">撤回意向</button>
    </MobileSafeAreaBar>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { toast } from '@/utils/nav'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { formatDateTime } from '@/utils/format'

const blank = () => ({ preferredCity: '', preferredIndustry: '', preferredPositionId: '', intentionNote: '' })

export default {
  data() {
    return {
      pageState: 'loading', submitting: false, reading: false, error: '', requestedBatchId: '', context: {},
      meta: { intention: null, canEdit: false, canSubmit: false, canWithdraw: false }, form: blank(),
      positions: [], positionIndex: -1, positionsPage: 1, positionsMore: false,
      generation: currentSessionGeneration(), hidden: false, sequence: 0, pausedLoad: false,
      conflict: false, latest: null, newDraft: false, baseline: ''
    }
  },
  computed: {
    ready() { return this.pageState === 'ready' && !this.hidden && !this.submitting && !this.reading && this.generation === currentSessionGeneration() },
    canEdit() { return this.ready && !this.conflict && (this.meta.canEdit === true || (this.newDraft && this.meta.canCreateNew === true)) },
    canSubmit() { return this.ready && !this.conflict && (this.meta.canSubmit === true || (this.canEdit && (!this.meta.intention || this.newDraft))) },
    canWithdraw() { return this.ready && !this.conflict && !this.newDraft && this.meta.canWithdraw === true },
    positionLabels() { return ['暂不指定岗位', ...this.positions.map((p) => `${p.companyName} · ${p.title}（余${p.remaining}）${p.canSelect === false ? ' · 暂不可选' : ''}`)] },
    positionLabel() {
      if (this.positionIndex < 0) return this.form.preferredPositionId ? (this.meta.intention?.preferredPositionTitle || '原意向岗位（请核对当前目录）') : ''
      const p = this.positions[this.positionIndex]
      return p ? `${p.companyName} · ${p.title}` : ''
    }
  },
  onLoad(options = {}) { this.requestedBatchId = String(options.batchId || ''); this.load() },
  onHide() { if (this.submitting) { this.conflict = true; this.error = '上次操作结果待确认，请读取原单核对' }; this.pausedLoad = this.pageState === 'loading'; this.hidden = true; this.sequence++; this.submitting = false; this.reading = false },
  onUnload() { this.hidden = true; this.sequence++ },
  onShow() {
    this.hidden = false
    if (this.generation !== currentSessionGeneration()) {
      this.sequence++; this.generation = currentSessionGeneration(); this.context = {}; this.requestedBatchId = ''
      this.form = blank(); this.baseline = ''; this.meta = {}; this.positions = []; this.conflict = false; this.latest = null; this.newDraft = false; this.load()
    } else if (this.pausedLoad) { this.pausedLoad = false; this.load() }
  },
  methods: {
    formatDateTime,
    capture() { return { sequence: this.sequence, generation: currentSessionGeneration(), batch: this.context.batchId, record: this.context.internshipId } },
    current(t) { return !this.hidden && t.sequence === this.sequence && t.generation === currentSessionGeneration() && t.batch === this.context.batchId && t.record === this.context.internshipId },
    beforeBack() { if (this.submitting || this.reading) return false; if (!this.baseline || JSON.stringify(this.form) === this.baseline) return true; return new Promise(resolve => uni.showModal({ title: '尚有未保存内容', content: '离开后本次输入不会保存，是否离开？', success: result => resolve(!!result.confirm), fail: () => resolve(false) })) },
    startNew() { if (!this.ready || !this.meta.canCreateNew || this.conflict) return; this.newDraft = true; this.fillForm(this.meta.intention) },
    statusTag(st) {
      if (st === 'SUBMITTED') return 'COMPLETED'
      if (st === 'DRAFT') return 'PENDING'
      return 'DEFAULT'
    },
    fillForm(it) {
      if (!it) {
        this.form = { preferredCity: '', preferredIndustry: '', preferredPositionId: '', intentionNote: '' }
        this.positionIndex = -1
        return
      }
      this.form = {
        preferredCity: it.preferredCity || '',
        preferredIndustry: it.preferredIndustry || '',
        preferredPositionId: it.preferredPositionId || '',
        intentionNote: it.intentionNote || ''
      }
      const idx = this.positions.findIndex((p) => p.id === it.preferredPositionId)
      this.positionIndex = idx >= 0 ? idx : -1
      this.baseline = JSON.stringify(this.form)
    },
    async load() {
      if (this.conflict) return this.rereadConflict()
      const sequence = ++this.sequence, generation = currentSessionGeneration(), requested = this.requestedBatchId
      const current = () => !this.hidden && sequence === this.sequence && generation === currentSessionGeneration() && requested === this.requestedBatchId
      this.pageState = 'loading'; this.error = ''
      try {
        const dashboard = await studentApi.getInternship(requested)
        if (!current()) return
        const batchId = String(dashboard?.batchId || ''), internshipId = String(dashboard?.recordId || '')
        if (!batchId || !internshipId) { this.pageState = 'empty'; return }
        const d = await studentApi.getInternshipIntention(batchId, internshipId, 1)
        if (!current()) return
        if (String(d?.batchId) !== batchId || String(d?.internshipId) !== internshipId) throw Error('意向不属于当前实习记录，请重新读取')
        if (!d || !d.hasData) {
          this.pageState = 'empty'
          return
        }
        this.context = { batchId, internshipId }; this.meta = d; this.newDraft = false
        this.positions = d.positions || []
        this.positionsPage = d.positionsPage || 1; this.positionsMore = !!d.positionsHasMore; this.fillForm(d.intention); this.baseline = JSON.stringify(this.form)
        this.pageState = 'ready'
      } catch (error) { if (current()) { this.pageState = 'error'; this.error = error?.message || '意向读取失败，请重试' } }
    },
    async loadMorePositions() {
      if (!this.ready || !this.positionsMore) return
      const t = this.capture(), page = this.positionsPage + 1; this.reading = true
      try {
        const d = await studentApi.getInternshipIntention(t.batch, t.record, page)
        if (!this.current(t)) return
        if (String(d.batchId) !== t.batch || String(d.internshipId) !== t.record || d.positionsPage !== page) throw Error('岗位目录读取结果不一致')
        this.positions = [...this.positions, ...(d.positions || []).filter(row => !this.positions.some(item => String(item.id) === String(row.id)))]; this.positionsPage = page; this.positionsMore = !!d.positionsHasMore
      } catch (error) { if (this.current(t)) this.error = error?.message || '后续岗位读取失败，原选择保留' }
      finally { if (this.current(t)) this.reading = false }
    },
    onPositionPick(e) {
      if (!this.canEdit) return
      const i = Number(e.detail.value) - 1
      if (i >= 0 && this.positions[i]?.canSelect !== true) return toast('当前岗位暂不可选')
      this.positionIndex = i
      const p = this.positions[i]
      this.form.preferredPositionId = p ? p.id : ''
      if (p && p.workLocation && !this.form.preferredCity) {
        this.form.preferredCity = p.workLocation
      }
    },
    bodyPayload() {
      const original = this.meta.intention
      return { ...this.form, ...this.context, id: this.newDraft ? undefined : original?.id, expectedVersion: this.newDraft ? undefined : original?.version,
        ...(this.newDraft ? { newAfterWithdraw: true, previousIntentionId: original.id, previousExpectedVersion: original.version } : {}) }
    },
    async save() {
      if (!this.canEdit) return
      if (!this.form.preferredCity.trim() && !this.form.preferredIndustry.trim() && !this.form.intentionNote.trim()) {
        return toast('请至少填写城市、行业或补充说明中的一项')
      }
      return this.write('SAVE')
    },
    async submit() { if (!this.canSubmit) return; return this.write('SUBMIT') },
    async write(action) {
      const t = this.capture(), body = this.bodyPayload(), saveFirst = action === 'SUBMIT' && this.canEdit
      this.submitting = true; this.error = ''
      try {
        let result
        if (action === 'SAVE' || saveFirst) {
          result = await studentApi.saveInternshipIntention(body)
          if (!this.current(t)) return
          this.acceptWrite(result)
        }
        if (action === 'SUBMIT') {
          result = await studentApi.submitInternshipIntention({ ...this.context, id: this.meta.intention.id, expectedVersion: this.meta.intention.version })
          if (!this.current(t)) return
          this.acceptWrite(result)
        } else if (action === 'WITHDRAW') {
          result = await studentApi.withdrawInternshipIntention(body)
          if (!this.current(t)) return
          this.acceptWrite(result)
        }
        toast(action === 'SUBMIT' ? '意向已提交' : action === 'WITHDRAW' ? '意向已撤回' : '意向已保存')
      } catch (error) { if (this.current(t)) { this.error = error?.message || '操作未完成，输入已保留'; if (!error?.biz || [error?.bizCode,error?.code].includes('DATA_CONFLICT') || error?.httpStatus === 409 || error?.code === 'NETWORK') this.conflict = true } }
      finally { if (this.current(t)) this.submitting = false }
    },
    acceptWrite(result) {
      if (String(result?.batchId) !== this.context.batchId || String(result?.internshipId) !== this.context.internshipId || !result.intention?.id || !Number.isInteger(result.intention.version)) throw Error('意向回执不完整，请重新读取核对')
      this.meta = { ...this.meta, ...result }; this.newDraft = false; this.baseline = JSON.stringify(this.form)
    },
    async rereadConflict() {
      if (!this.conflict || this.reading || this.hidden || this.generation !== currentSessionGeneration()) return
      const t = this.capture(); this.reading = true; this.latest = null
      try { const d = await studentApi.getInternshipIntention(t.batch,t.record,1); if (!this.current(t)) return; if (String(d.batchId) !== t.batch || String(d.internshipId) !== t.record) throw Error('原单上下文不一致'); this.latest = d }
      catch (error) { if (this.current(t)) this.error = error?.message || '原单读取失败，输入已保留' }
      finally { if (this.current(t)) this.reading = false }
    },
    adoptLatest() {
      if (!this.ready || !this.latest || this.latest.canEdit !== true || (this.meta.intention && String(this.latest.intention?.id) !== String(this.meta.intention.id))) return
      this.meta = this.latest; this.latest = null; this.conflict = false; this.newDraft = false; this.error = ''
    },
    withdraw() {
      if (!this.canWithdraw) return
      const t = this.capture()
      uni.showModal({
        title: '撤回意向',
        content: '撤回后原内容保留，需要修改可重新填写。确认撤回？',
        success: (r) => {
          if (!r.confirm || !this.current(t) || !this.canWithdraw) return
          return this.write('WITHDRAW')
        }
      })
    }
  }
}
</script>

<style scoped>
.itn__hint { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin-top: 6px; }
.itn__status { display: flex; align-items: center; gap: var(--space-2); margin-top: var(--space-3); }
.itn__time { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.itn__field { display: flex; flex-direction: column; gap: 6px; margin-bottom: var(--space-3); }
.itn__label { font-size: var(--font-size-sm); color: var(--text-secondary); }
.itn__input, .itn__picker { padding: 10px 12px; border: 1px solid var(--border-base); border-radius: var(--radius-md); font-size: var(--font-size-base); background: #fff; }
.itn__textarea { min-height: 88px; padding: 10px 12px; border: 1px solid var(--border-base); border-radius: var(--radius-md); font-size: var(--font-size-base); width: 100%; box-sizing: border-box; }
</style>
