<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" :title="detailId ? '预警跟进' : '学业预警待处理'" subtitle="学业预警" :before-back="backToWarnings" show-back />

    <view class="aw__filter" v-if="!detailId && list">
      <view class="aw__chip" :class="{ 'is-on': levelFilter === 'all' }" @click="setLevel('all')">全部</view>
      <view v-for="lv in levelOptions" :key="lv.key" class="aw__chip" :class="{ 'is-on': levelFilter === lv.key }" @click="setLevel(lv.key)">{{ lv.label }}</view>
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="list">
        <button v-if="detailId" class="btn btn-ghost aw__back" :disabled="!!actingId" @click="backToWarnings">‹ 返回预警列表</button>
        <MobileGlobalState v-if="!list.length" state="empty" title="暂无待处理预警"
          description="学生触发学业预警后会出现在这里，可关闭或升级为风险。" />
        <MobileGlobalState v-else-if="!filteredList.length" state="empty" title="当前筛选无预警" description="可切换上方预警等级查看其他记录。" />
        <view class="stack" v-else>
          <view v-for="w in displayedWarnings" :key="w.id || w.warningId" class="card aw" :class="{ 'is-target': isTarget(w) }">
            <text v-if="isTarget(w)" class="aw__target">从工作台直达的预警</text>
            <view class="row-between">
              <view class="flex-1">
                <view class="row" style="gap:6px;">
                  <text class="t-md t-bold">{{ w.studentName || w.name || '—' }}</text>
                  <MobileStatusTag :label="w.levelLabel || w.level" :type="levelTone(w.level)" />
                </view>
                <text class="aw__sub">{{ w.className || '' }} · {{ w.typeLabel || w.type }}</text>
              </view>
              <text class="aw__time">{{ (w.triggerTime || '').slice(5, 16) }}</text>
            </view>
            <view class="aw__reason" v-if="w.reason"><text class="flex-1 t-sm">{{ w.reason }}</text></view>
            <view class="aw__meta">
              <text class="aw__meta-item" v-if="w.deadline">处理时限 {{ w.deadline }}</text>
              <text class="aw__meta-item" v-if="w.remindCount">已催办 {{ w.remindCount }} 次</text>
              <text class="aw__meta-item aw__meta-status">{{ w.statusLabel || w.status }}</text>
            </view>
            <template v-if="detailId">
              <view class="aw__evidence"><text>预警编号 {{ warningId(w) }}</text><text>责任人 {{ w.owner || '未提供' }}</text></view>
              <view v-if="hasAnyUnknownWrite(w)" class="aw__uncertain">存在未取得明确回执的操作。已停止该对象继续写入，只会读取正式记录核对。</view>
              <view class="aw__followup">
                <text class="t-md t-bold">追加跟进记录</text>
                <text v-if="detailState === 'loading'" class="aw__unavailable">正在读取正式跟进记录…</text>
                <view v-else-if="detailState === 'error'" class="aw__detail-error"><text>跟进记录读取失败</text><button class="btn btn-ghost" @click="loadDetail(warningId(w))">重新读取</button></view>
                <view v-else-if="detail && detail.interventions && detail.interventions.length" class="aw__history">
                  <view v-for="i in detail.interventions" :key="i.id || i.interventionId" class="aw__history-item">
                    <view class="row-between"><text class="t-sm t-bold">{{ i.wayLabel || wayLabel(i.way) }}</text><text class="aw__time">{{ i.time || '' }}</text></view>
                    <text class="t-sm">{{ i.content }}</text>
                    <text v-if="i.result" class="aw__sub">结果：{{ i.result }}</text>
                    <text v-if="i.nextPlan" class="aw__sub">下一步：{{ i.nextPlan }}</text>
                    <text class="aw__sub">{{ i.operator || '操作人未提供' }}</text>
                  </view>
                </view>
                <text v-else-if="detailState === 'ready'" class="aw__unavailable">暂无跟进记录</text>
                <view v-if="followAck" class="aw__receipt">
                  <text>已收到跟进编号 {{ followAck.interventionId }}</text>
                  <text>正在等待详情返回该编号；只读核对不会重复提交。</text>
                  <button class="btn btn-ghost" :disabled="detailState === 'loading'" @click="verifyFollowup">只读核对记录</button>
                </view>
                <picker mode="selector" :range="wayLabels" :value="followWayIndex" :disabled="followSubmitting || !!followAck || hasAnyUnknownWrite(w)" @change="onWayChange">
                  <view class="aw__input">跟进方式：{{ wayLabels[followWayIndex] }}<text>▾</text></view>
                </picker>
                <textarea v-model="followForm.content" :disabled="followSubmitting || !!followAck || hasAnyUnknownWrite(w)" maxlength="1000" placeholder="记录本次沟通过程与学生情况，至少 5 个字" class="aw__note" />
                <input v-model="followForm.result" :disabled="followSubmitting || !!followAck || hasAnyUnknownWrite(w)" maxlength="200" placeholder="跟进结果（选填）" class="aw__input" />
                <input v-model="followForm.nextPlan" :disabled="followSubmitting || !!followAck || hasAnyUnknownWrite(w)" maxlength="200" placeholder="下一步计划（选填）" class="aw__input" />
                <button class="btn btn-primary" :disabled="followSubmitting || !!followAck || hasAnyUnknownWrite(w) || followForm.content.trim().length < 5" @click="submitFollowup(w)">{{ followSubmitting ? '提交中…' : followAck ? '等待核对记录' : '保存跟进记录' }}</button>
              </view>
            </template>
            <button v-else class="btn btn-primary" @click="openWarning(w)">查看预警并跟进 ›</button>
            <view class="aw__actions" v-if="detailId && (w.status === 'PENDING_HANDLE' || w.status === 'PROCESSING' || w.status === 'ACTIVE')">
              <button class="aw__escalate flex-1" :disabled="actingId === warningId(w) || followSubmitting || hasAnyUnknownWrite(w)" @click="handle(w, 'ESCALATE')">升级为风险</button>
              <button class="aw__close flex-1" :disabled="actingId === warningId(w) || followSubmitting || hasAnyUnknownWrite(w)" @click="handle(w, 'CLOSE')">关闭预警</button>
            </view>
          </view>
        </view>
        <view v-if="!detailId && queueTotal > 20" class="aw__pages">
          <button class="btn btn-ghost" :disabled="queuePageIndex === 0 || state === 'loading'" @click="changeQueuePage(queuePageIndex - 1)">上一组</button>
          <text>{{ queuePageIndex + 1 }} / {{ Math.ceil(queueTotal / 20) }}</text>
          <button class="btn btn-ghost" :disabled="!queueHasMore || state === 'loading'" @click="changeQueuePage(queuePageIndex + 1)">下一组</button>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { useSessionStore } from '@/stores/session'
import { toast } from '@/utils/nav'
import { beginPersistentWrite, clearPersistentWrite, isExplicitWriteRejection, isForbiddenResponse, listPersistentWrites, persistWriteAck, teacherWriteContext } from '../academic-affairs/write-result'

const LEVELS = [{ key: 'HIGH', label: '高' }, { key: 'MEDIUM', label: '中' }, { key: 'LOW', label: '低' }]
const WAYS = [{ key: 'TALK', label: '当面谈话' }, { key: 'PHONE', label: '电话联系' }, { key: 'FAMILY', label: '家校联系' }, { key: 'PLAN', label: '帮扶计划' }]

export default {
  data() {
    return {
      list: null, state: 'loading', actingId: '', levelFilter: 'all', targetWarningId: '', detailId: '', queuePage: 0, queueTotal: 0, queueHasMore: false, unknownWrites: {}, writeStorageBlocked: false, writeAccessDenied: false,
      detail: null, detailState: 'idle', followWayIndex: 0, followSubmitting: false, followAck: null,
      followForm: { content: '', result: '', nextPlan: '' }
    }
  },
  onLoad(options = {}) {
    this._pageActive = true
    this.syncUnknownWrites()
    this.targetWarningId = String(options.id || options.warningId || '')
    this.load()
  },
  onShow() {
    this._pageActive = true
    this.syncUnknownWrites()
    if (this._needsRefresh) {
      this._needsRefresh = false
      const detailId = this.detailId
      this.load()
      if (detailId) this.loadDetail(detailId)
    }
  },
  onHide() { this._pageActive = false; this._needsRefresh = true; this._loadEpoch = (this._loadEpoch || 0) + 1; this._detailEpoch = (this._detailEpoch || 0) + 1 },
  onUnload() { this._pageActive = false; this._loadEpoch = (this._loadEpoch || 0) + 1; this._detailEpoch = (this._detailEpoch || 0) + 1 },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  computed: {
    queuePageIndex() { return this.queuePage },
    displayedWarnings() { return this.detailId ? (this.list || []).filter((row) => this.warningId(row) === this.detailId) : (this.list || []) },
    levelOptions() { return LEVELS },
    filteredList() { return this.list || [] },
    wayLabels() { return WAYS.map((way) => way.label) }
  },
  onBackPress() { if (!this.detailId) return false; this.backToWarnings(); return true },
  methods: {
    setLevel(level) { if (this.levelFilter === level) return; this.levelFilter = level; this.queuePage = 0; this.load() },
    changeQueuePage(page) { if (page < 0 || this.state === 'loading') return; this.queuePage = page; this.load() },
    openWarning(row) { if (this.actingId || this.followSubmitting) return; this.detailId = this.warningId(row); this.loadDetail(this.detailId) },
    backToWarnings() { if (!this.detailId) return true; if (this.actingId || this.followSubmitting) return false; this.detailId = ''; this.targetWarningId = ''; this.detail = null; this.detailState = 'idle'; this.load(); return false },
    contextKey() {
      return teacherWriteContext(useSessionStore())
    },
    warningId(item) { return String((item && (item.warningId || item.id)) || '') },
    unknownKey(item, action) { return `${action}|${this.warningId(item)}` },
    hasUnknownWrite(item, action) { return this.writeStorageBlocked || this.writeAccessDenied || !!this.unknownWrites[this.unknownKey(item, action)] },
    hasAnyUnknownWrite(item) { return ['FOLLOWUP', 'CLOSE', 'ESCALATE'].some((action) => this.hasUnknownWrite(item, action)) },
    syncUnknownWrites(context = this.contextKey()) {
      const result = listPersistentWrites(context)
      this.writeStorageBlocked = !result.ok
      this.unknownWrites = result.ok ? Object.fromEntries(result.records.map((row) => [`${row.action}|${row.objectId}`, row])) : {}
      const follow = result.ok && this.detailId ? result.records.find((row) => row.action === 'FOLLOWUP' && row.objectId === this.detailId && row.state === 'ACK' && row.ackId && row.parentId === this.detailId) : null
      this.followAck = follow ? { warningId: follow.parentId, interventionId: follow.ackId } : null
      return result
    },
    beginWrite(context, action, objectId) { const result = beginPersistentWrite(context, action, objectId); this.syncUnknownWrites(); if (!result.ok) toast(result.storageError ? '无法安全保存待核对记录，本次未提交' : '该操作正在等待正式记录核对'); return result.ok },
    ackWrite(context, action, objectId, ack) { const ok = persistWriteAck(context, action, objectId, ack); this.syncUnknownWrites(); return ok },
    clearWrite(context, action, objectId) { const ok = clearPersistentWrite(context, action, objectId); this.syncUnknownWrites(); return ok },
    clearPrivateState() {
      this._loadEpoch = (this._loadEpoch || 0) + 1; this._detailEpoch = (this._detailEpoch || 0) + 1
      this.state = 'error'; this.detailState = 'error'
      this.list = []; this.detail = null; this.detailId = ''; this.targetWarningId = ''; this.followAck = null
      this.followSubmitting = false; this.actingId = ''; this.followWayIndex = 0
      this.followForm = { content: '', result: '', nextPlan: '' }
      this.writeAccessDenied = true
    },
    reconcileWarningWrites(rows, detail = null) {
      const pending = listPersistentWrites(this.contextKey())
      if (!pending.ok) { this.syncUnknownWrites(); return }
      pending.records.forEach((record) => {
        if (record.state !== 'ACK') return
        const row = rows.find((item) => this.warningId(item) === record.objectId)
        const status = String((detail && detail.warning && this.warningId(detail.warning) === record.objectId ? detail.warning.status : row && row.status) || '').toUpperCase()
        if (record.action === 'CLOSE' && status === 'CLOSED') this.clearWrite(record.context, record.action, record.objectId)
        if (record.action === 'ESCALATE' && ['ESCALATED', 'HIGH_RISK'].includes(status)) this.clearWrite(record.context, record.action, record.objectId)
      })
    },
    wayLabel(way) { const found = WAYS.find((item) => item.key === way); return found ? found.label : way || '跟进' },
    onWayChange(event) { this.followWayIndex = Number(event.detail.value) },
    isTarget(item) { return !!this.targetWarningId && this.warningId(item) === this.targetWarningId },
    levelTone(lv) { return lv === 'HIGH' ? 'danger' : lv === 'MEDIUM' ? 'warning' : 'default' },
    focusTarget(rows) {
      if (!this.targetWarningId) return rows
      const index = rows.findIndex((item) => this.isTarget(item))
      if (index < 0) {
        toast('该学业预警不存在、已处理或不在当前数据范围内')
        this.targetWarningId = ''
        return rows
      }
      const target = rows[index]
      this.detailId = this.warningId(target)
      this.levelFilter = 'all'
      if (index === 0) return rows
      return [target, ...rows.slice(0, index), ...rows.slice(index + 1)]
    },
    async load(done) {
      const epoch = (this._loadEpoch || 0) + 1
      this._loadEpoch = epoch
      const context = this.contextKey()
      if (this._actionContext !== context) {
        this._actionContext = context
        this._writeEpoch = (this._writeEpoch || 0) + 1
        this.actingId = ''
        this.list = []
        this.detailId = ''
        this.queuePage = 0
        this.queueTotal = 0
        this.queueHasMore = false
        this.levelFilter = 'all'
        this.syncUnknownWrites(context)
        this.writeAccessDenied = false
        this.detail = null
        this.detailState = 'idle'
        this.followSubmitting = false
        this.followAck = null
        this.followWayIndex = 0
        this.followForm = { content: '', result: '', nextPlan: '' }
      }
      this.state = 'loading'
      try {
        const d = await teacherApi.getAcademicWarnings({ page: this.queuePage + 1, pageSize: 20, level: this.levelFilter === 'all' ? undefined : this.levelFilter })
        if (!this._pageActive || this._loadEpoch !== epoch || this.contextKey() !== context) return
        const rows = (d && (d.list || d.items)) || []
        this.queueTotal = Number(d && d.total != null ? d.total : rows.length)
        this.queueHasMore = !!(d && d.hasMore)
        this.list = rows
        if (this.targetWarningId && !rows.some((row) => this.warningId(row) === this.targetWarningId)) {
          const detail = await teacherApi.getAcademicWarningDetail(this.targetWarningId)
          if (!this._pageActive || this._loadEpoch !== epoch || this.contextKey() !== context) return
          if (this.warningId(detail && detail.warning) !== this.targetWarningId) throw new Error('WARNING_PARENT_MISMATCH')
          this.list = [detail.warning]
          this.detailId = this.targetWarningId
          this.detail = detail
          this.detailState = 'ready'
        } else this.list = this.focusTarget(rows)
        this.writeAccessDenied = false
        this.reconcileWarningWrites(this.list)
        if (this.detailId && !this.list.some((row) => this.warningId(row) === this.detailId)) this.detailId = ''
        this.state = 'ready'
      } catch (error) {
        if (this._pageActive && this._loadEpoch === epoch && this.contextKey() === context) {
          if (isForbiddenResponse(error)) this.clearPrivateState()
          this.state = 'error'
        }
      } finally { if (done) done() }
    },
    async loadDetail(warningId = this.detailId) {
      const id = String(warningId || '')
      if (!id) return null
      const context = this.contextKey()
      const epoch = (this._detailEpoch || 0) + 1
      this._detailEpoch = epoch
      this.detailState = 'loading'
      try {
        const detail = await teacherApi.getAcademicWarningDetail(id)
        if (!this._pageActive || this._detailEpoch !== epoch || this.contextKey() !== context || this.detailId !== id) return null
        if (this.warningId(detail && detail.warning) !== id) {
          this.detail = null
          this.detailState = 'error'
          toast('预警详情对象校验失败，请返回后重新打开')
          return null
        }
        this.detail = detail || { interventions: [] }
        this.writeAccessDenied = false
        this.reconcileWarningWrites(this.list || [], detail)
        this.syncUnknownWrites(context)
        this.detailState = 'ready'
        return this.detail
      } catch (error) {
        if (this._pageActive && this._detailEpoch === epoch && this.contextKey() === context && this.detailId === id) {
          if (isForbiddenResponse(error)) this.clearPrivateState()
          this.detailState = 'error'
        }
        return null
      }
    },
    async verifyFollowup() {
      const ack = this.followAck
      if (!ack || this.detailState === 'loading') return false
      if (String(ack.warningId || '') !== String(this.detailId || '')) return false
      const detail = await this.loadDetail(ack.warningId)
      if (!detail || !this.followAck || this.followAck.warningId !== ack.warningId || this.followAck.interventionId !== ack.interventionId) return false
      if (this.warningId(detail.warning) !== ack.warningId) return false
      const found = ((detail && detail.interventions) || []).some((item) => String(item.id || item.interventionId || '') === ack.interventionId)
      if (!found) { toast('正式详情暂未返回该跟进编号，请稍后只读核对'); return false }
      if (!this.clearWrite(this.contextKey(), 'FOLLOWUP', ack.warningId)) { toast('正式记录已核对，但本地待办清理失败'); return false }
      this.followAck = null
      this.followWayIndex = 0
      this.followForm = { content: '', result: '', nextPlan: '' }
      toast('跟进记录已保存并核对')
      this.load()
      return true
    },
    async submitFollowup(w) {
      const id = this.warningId(w)
      const content = this.followForm.content.trim()
      if (!id || this.followSubmitting || this.followAck || this.hasAnyUnknownWrite(w) || content.length < 5) return
      const context = this.contextKey()
      const detailEpoch = this._detailEpoch
      const snapshot = JSON.stringify([id, this.followWayIndex, this.followForm])
      const body = { way: WAYS[this.followWayIndex].key, content, result: this.followForm.result.trim(), nextPlan: this.followForm.nextPlan.trim() }
      if (!this.beginWrite(context, 'FOLLOWUP', id)) return
      this.followSubmitting = true
      const writeEpoch = (this._writeEpoch || 0) + 1
      this._writeEpoch = writeEpoch
      try {
        const ack = await teacherApi.addAcademicWarningIntervention(id, body)
        const ackId = String(ack && ack.interventionId || '')
        const ackParentId = String(ack && ack.warningId || '')
        if (ackId && ackParentId === id) this.ackWrite(context, 'FOLLOWUP', id, { ackId, parentId: ackParentId })
        if (!this._pageActive || this._writeEpoch !== writeEpoch || this.contextKey() !== context || this.detailId !== id || this._detailEpoch !== detailEpoch) return
        if (!ackId || ackParentId !== id) {
          toast('跟进结果未确认，已停止重复提交；请只读核对正式记录')
          await this.loadDetail(id)
          return
        }
        this.followAck = { warningId: id, interventionId: ackId }
        if (JSON.stringify([id, this.followWayIndex, this.followForm]) !== snapshot) { toast('原跟进已收到编号，当前新填写内容已保留'); return }
        return await this.verifyFollowup()
      } catch (error) {
        if (isForbiddenResponse(error)) {
          if (this._pageActive && this._writeEpoch === writeEpoch && this.contextKey() === context && this.detailId === id) this.clearPrivateState()
        } else if (isExplicitWriteRejection(error)) this.clearWrite(context, 'FOLLOWUP', id)
        if (!this._pageActive || this._writeEpoch !== writeEpoch || this.contextKey() !== context || this.detailId !== id) return
        if (isExplicitWriteRejection(error)) toast((error && error.message) || '跟进未受理，请修改后重试')
        else { toast('跟进结果未确认，已停止重复提交；请只读核对正式记录'); await this.loadDetail(id) }
      } finally {
        if (this._writeEpoch === writeEpoch && this.contextKey() === context) this.followSubmitting = false
      }
    },
    async verifyHandle(id, action) {
      const detail = await this.loadDetail(id)
      if (!detail || this.warningId(detail.warning) !== id) return false
      const status = String(detail.warning.status || '').toUpperCase()
      const matched = action === 'CLOSE' ? status === 'CLOSED' : ['ESCALATED', 'HIGH_RISK'].includes(status)
      if (!matched) { toast('正式详情暂未返回处理结果，请稍后只读核对'); return false }
      return this.clearWrite(this.contextKey(), action, id)
    },
    handle(w, action) {
      const id = this.warningId(w)
      if (!id || this.actingId || this.followSubmitting || this.hasAnyUnknownWrite(w)) return
      const context = this.contextKey()
      const epoch = this._loadEpoch
      const snapshot = JSON.stringify(w)
      const close = action === 'CLOSE'
      uni.showModal({
        title: close ? '关闭预警' : '升级为风险',
        editable: true,
        placeholderText: close ? '请填写处理结论（≥5 字）' : '请填写升级说明（≥5 字）',
        content: '',
        success: (r) => {
          if (!r.confirm || !this._pageActive || this.actingId || this._loadEpoch !== epoch || this.contextKey() !== context || !this.list.includes(w) || JSON.stringify(w) !== snapshot || this.warningId(w) !== id) return
          const note = (r.content || '').trim()
          if (note.length < 5) { toast('说明至少 5 个字'); return }
          if (!this.beginWrite(context, action, id)) return
          const writeEpoch = (this._writeEpoch || 0) + 1
          this._writeEpoch = writeEpoch
          this.actingId = id
          teacherApi.handleWarning(id, action, note)
            .then(async (ack) => {
              const ackParent = String(ack && ack.warningId || '')
              if (ackParent === id) this.ackWrite(context, action, id, { ackId: ack && (ack.interventionId || ack.id), parentId: id })
              if (!this._pageActive || this._writeEpoch !== writeEpoch || this.contextKey() !== context) return
              if (ackParent !== id) { toast('处理回执缺少原预警编号，结果待核实，请勿重复提交'); return }
              const verified = await this.verifyHandle(id, action)
              if (!verified) return
              toast(close ? '预警已关闭' : '已升级为风险'); this.targetWarningId = ''; this.load()
            })
            .catch((e) => {
              if (isForbiddenResponse(e)) {
                if (this._pageActive && this._writeEpoch === writeEpoch && this.contextKey() === context && this.detailId === id) this.clearPrivateState()
              } else if (isExplicitWriteRejection(e)) this.clearWrite(context, action, id)
              if (!this._pageActive || this._writeEpoch !== writeEpoch || this.contextKey() !== context) return
              const code = e && String(e.code)
              if (code && code.startsWith('409')) { toast('该预警已被处理，正在刷新'); this.targetWarningId = ''; this.load() }
              else if (code && code.startsWith('403')) toast((e && e.message) || '不在你的数据范围内')
              else if (isExplicitWriteRejection(e)) toast((e && e.message) || '处理未受理，请修改后重试')
              else { toast('处理结果未确认，已停止重复提交；请刷新后核对预警状态'); this.load() }
            })
            .finally(() => { if (this._writeEpoch === writeEpoch && this.contextKey() === context) this.actingId = '' })
        }
      })
    }
  }
}
</script>

<style scoped>
.aw__pages { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin: 16px 0; }
.btn.btn-primary { background: var(--teacher-600); border-color: var(--teacher-600); color: #fff; }
.btn.btn-ghost { color: var(--teacher-700); border-color: var(--teacher-200); }
.btn[disabled] { opacity: .5; }
.aw__back { margin-bottom: 16px; }
.aw__evidence { display: flex; flex-direction: column; gap: 8px; padding: 12px; border-radius: 12px; background: var(--teacher-50); color: var(--teacher-700); font-size: 13px; }
.aw__uncertain { margin-top: 10px; padding: 10px 12px; border-radius: 10px; background: var(--warning-50); color: var(--warning-700); font-size: 13px; line-height: 1.5; }
.aw__followup { display: flex; flex-direction: column; gap: 12px; padding-top: 20px; border-top: 1px solid var(--border-light); }
.aw__unavailable { font-size: 13px; color: var(--text-secondary); line-height: 1.6; }
.aw__note { width: 100%; min-height: 120px; padding: 12px; box-sizing: border-box; border: 1px solid var(--border-light); border-radius: 12px; font-size: 14px; }
.aw__input { display: flex; align-items: center; justify-content: space-between; width: 100%; min-height: 44px; box-sizing: border-box; padding: 0 12px; border: 1px solid var(--border-light); border-radius: 12px; font-size: 14px; }
.aw__history { display: flex; flex-direction: column; gap: 10px; }
.aw__history-item { display: flex; flex-direction: column; gap: 5px; padding: 10px 12px; border-radius: 10px; background: var(--gray-50); }
.aw__receipt, .aw__detail-error { display: flex; flex-direction: column; gap: 8px; padding: 10px 12px; border-radius: 10px; background: var(--teacher-50); color: var(--teacher-700); font-size: 13px; }
.aw__filter { display: flex; gap: var(--space-2); padding: var(--space-3) var(--page-padding-mobile) 0; background: var(--bg-card); }
.aw__chip { font-size: var(--font-size-sm); padding: 6px 13px; border-radius: var(--radius-full); background: var(--gray-50); color: var(--text-secondary); font-weight: var(--font-weight-medium); }
.aw__chip.is-on { background: var(--teacher-600); color: #fff; }
.aw { display: flex; flex-direction: column; gap: var(--space-2); }
.aw.is-target { border: 1px solid var(--teacher-500); box-shadow: 0 0 0 2px var(--teacher-50); }
.aw__target { color: var(--teacher-700); font-size: var(--font-size-xs); font-weight: 600; }
.aw__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.aw__time { font-size: var(--font-size-xs); color: var(--text-tertiary); flex-shrink: 0; }
.aw__reason { background: var(--gray-50); border-radius: var(--radius-md); padding: var(--space-2) var(--space-3); }
.aw__meta { display: flex; flex-wrap: wrap; gap: var(--space-3); }
.aw__meta-item { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.aw__meta-status { color: var(--teacher-700); font-weight: var(--font-weight-medium); }
.aw__actions { display: flex; gap: var(--space-2); margin-top: var(--space-1); }
.aw__escalate { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); border: 1px solid var(--danger-500); background: var(--bg-card); color: var(--danger-600); }
.aw__escalate::after { border: none; }
.aw__close { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); border: none; background: var(--teacher-600); color: #fff; }
.aw__close::after { border: none; }
</style>
