<template>
  <view class="page-wrap">
    <MobileNavBar variant="default" title="消息详情" show-back />
    <view class="page-pad stack" v-if="m">
      <view class="card">
        <view class="row-between">
          <text class="md__module">{{ m.module || '消息' }}</text>
          <text v-if="m.emergency || m.level === 'high'" class="md__urgent">{{ m.emergency ? '紧急' : '重要' }}</text>
        </view>
        <text v-if="summary" class="md__time">列表摘要 · 办理状态以业务页面为准</text>
        <text class="md__title">{{ m.title }}</text>
        <text class="md__time">{{ formatTime(m.time) }}</text>
        <view v-if="m.status" style="margin-top: var(--space-2);"><MobileStatusTag :status="m.status" /></view>
        <text v-if="m.content" class="md__content">{{ m.content }}</text>
        <text v-if="m.deadline" class="md__deadline">截止时间：{{ formatTime(m.deadline) }}</text>
        <button v-if="readError" class="btn btn-ghost" :disabled="reading" @click="readMessage">已读状态保存失败，点击重试</button>
        <text v-if="m.acked" class="md__acked">你已确认回执</text>
        <text v-if="m.withdrawn" class="md__withdrawn">该消息已撤回</text>
      </view>
    </view>
    <MobileGlobalState v-else-if="loading" state="loading" title="加载中" />
    <MobileGlobalState v-else :state="errorState" :title="errorText" description="请返回消息列表或重试。" @retry="loadDetail" />

    <MobileSafeAreaBar v-if="m && (canHandle || showAck)">
      <button v-if="canHandle" class="btn btn-primary flex-1" @click="handle">{{ handleLabel }}</button>
      <button v-if="showAck" class="btn btn-primary flex-1" :disabled="acking" @click="ack">{{ acking ? '提交中…' : '确认已阅' }}</button>
    </MobileSafeAreaBar>
  </view>
</template>

<script>
import { popDetail } from '@/utils/msgStash'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'
import { useSessionStore } from '@/stores/session'
import { canNavigate, disabledReasonOf, runAction } from '@/services/actionRouter'
import { ackMessageReceipt, getMessageDetail, markMessageRead } from '@/services/realApi'
import { ackTeacherMessageReceipt, getTeacherMessageDetail, markTeacherMessageRead } from '@/services/teacherMessagesV3Api'

export default {
  data() { return { m: null, acking: false, loading: false, side: 'student', messageId: '', summary: null, summaryGeneration: -1, epoch: 0, generation: 0, active: true, reading: false, readError: false, errorState: 'empty', errorText: '消息不存在或已过期' } },
  computed: {
    showAck() {
      if (this.summary || !this.m || this.m.withdrawn || this.m.acked) return false
      return !!(this.m.receipt || this.m.requireAck)
    },
    action() { return (this.m && this.m.action) || null },
    canHandle() { return !!this.m && !this.m.withdrawn && canNavigate(this.action, this.side) && !this.isDetailAction(this.action) },
    handleLabel() { return (this.action && this.action.label) || '去处理' }
  },
  onLoad(query) {
    this.side = useSessionStore().side === 'teacher' ? 'teacher' : 'student'
    const requested = query && (query.id || query.messageId)
    const stashed = popDetail(requested)
    this.messageId = String(requested || '').replace(/^msg-/, '')
    if (stashed && !/^\d+$/.test(this.messageId) && !stashed.messageId && stashed.kind !== 'UNIFIED_MESSAGE') {
      this.summary = stashed
      this.summaryGeneration = currentSessionGeneration()
    }
    this.loadDetail()
  },
  onHide() { this.active = false; this.epoch++; this.m = null },
  onUnload() { this.active = false; this.epoch++; this.m = null },
  onShow() { if (!this.active) { this.active = true; this.loadDetail() } },
  methods: {
    isCurrent(epoch) { return this.active && epoch === this.epoch && this.generation === currentSessionGeneration() },
    async loadDetail() {
      const epoch = ++this.epoch
      this.generation = currentSessionGeneration()
      this.m = null
      this.readError = false
      this.reading = false
      this.acking = false
      if (!/^\d+$/.test(this.messageId)) {
        this.loading = false
        this.m = this.summaryGeneration === this.generation ? this.summary : null
        return
      }
      this.loading = true
      try {
        const load = this.side === 'teacher' ? getTeacherMessageDetail : getMessageDetail
        const message = await load(this.messageId)
        if (!this.isCurrent(epoch)) return
        if (!message || String(message.messageId || message.id || '').replace(/^msg-/, '') !== this.messageId) {
          this.errorState = 'empty'; this.errorText = '消息不存在或已过期'; return
        }
        this.m = message
        this.readMessage()
      } catch (error) {
        if (!this.isCurrent(epoch)) return
        this.m = null
        const normalized = error?.httpStatus === 404
          ? { kind: 'notfound', text: '消息不存在或已过期' }
          : (error?.httpStatus === 403 ? { pageState: 'forbidden', text: '无权查看该消息' } : normalizeError(error))
        this.errorState = normalized.kind === 'notfound' ? 'empty' : (normalized.pageState || 'error')
        this.errorText = normalized.text
      } finally { if (this.isCurrent(epoch)) this.loading = false }
    },
    async readMessage() {
      if (this.summary || !this.m || this.m.read || this.reading || !this.isCurrent(this.epoch)) return
      const epoch = this.epoch
      this.reading = true
      try {
        const mark = this.side === 'teacher' ? markTeacherMessageRead : markMessageRead
        await mark(this.messageId)
        if (this.isCurrent(epoch)) { this.m.read = true; this.readError = false }
      } catch (error) {
        if (this.isCurrent(epoch)) this.readError = !this.m.read
      } finally { if (this.isCurrent(epoch)) this.reading = false }
    },
    formatTime(t) { return t ? String(t).slice(0, 16).replace('T', ' ') : '' },
    isDetailAction(action) { return !!(action && action.target && action.target.path === '/pages/common/message-detail/index') },
    async ack() {
      if (this.summary || !this.m || this.acking || !this.isCurrent(this.epoch)) return
      const epoch = this.epoch
      const raw = String(this.m.messageId || this.m.id || '').replace('msg-', '')
      if (!/^\d+$/.test(raw)) { toast('无法确认该消息'); return }
      this.acking = true
      try {
        const ackReceipt = this.side === 'teacher' ? ackTeacherMessageReceipt : ackMessageReceipt
        await ackReceipt(raw)
        if (!this.isCurrent(epoch)) return
        this.m.acked = true; this.m.receipt = false; this.m.read = true; this.readError = false; toast('已确认')
      } catch (e) { if (this.isCurrent(epoch)) toast((e && e.message) || '确认失败') }
      finally { if (this.isCurrent(epoch)) this.acking = false }
    },
    handle() {
      if (!this.isCurrent(this.epoch)) return
      if (!this.canHandle) { toast(disabledReasonOf(this.action)); return }
      runAction(this.action, { side: this.side })
    }
  }
}
</script>

<style scoped>
.md__module { font-size: var(--font-size-sm); color: var(--brand-primary); }
.md__urgent { font-size: 11px; color: #fff; background: var(--danger-500); padding: 2px 8px; border-radius: var(--radius-sm); }
.md__title { display: block; font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: var(--text-primary); margin-top: var(--space-2); line-height: 1.5; }
.md__time { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 4px; }
.md__content { display: block; font-size: var(--font-size-base); color: var(--text-secondary); line-height: 1.7; margin-top: var(--space-4); white-space: pre-wrap; }
.md__deadline { display: block; font-size: var(--font-size-sm); color: var(--warning-700); margin-top: var(--space-3); }
.md__acked { display: block; margin-top: var(--space-3); font-size: var(--font-size-sm); color: var(--success-600, #16a34a); }
.md__withdrawn { display: block; margin-top: var(--space-3); font-size: var(--font-size-sm); color: var(--danger-600); }
</style>
