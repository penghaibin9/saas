<template>
  <view class="page-wrap">
    <MobileNavBar variant="default" title="消息详情" show-back />
    <view class="page-pad stack" v-if="m">
      <view class="card">
        <view class="row-between">
          <text class="md__module">{{ m.module || '消息' }}</text>
          <text v-if="m.emergency || m.level === 'high'" class="md__urgent">{{ m.emergency ? '紧急' : '重要' }}</text>
        </view>
        <text class="md__title">{{ m.title }}</text>
        <text class="md__time">{{ formatTime(m.time) }}</text>
        <view v-if="m.status" style="margin-top: var(--space-2);"><MobileStatusTag :status="m.status" /></view>
        <text v-if="m.content" class="md__content">{{ m.content }}</text>
        <text v-if="m.deadline" class="md__deadline">截止时间：{{ formatTime(m.deadline) }}</text>
        <text v-if="m.acked" class="md__acked">你已确认回执</text>
        <text v-if="m.withdrawn" class="md__withdrawn">该消息已撤回</text>
      </view>
    </view>
    <MobileGlobalState v-else-if="loading" state="loading" title="加载中" />
    <MobileGlobalState v-else state="empty" title="消息不存在或已过期" description="请返回消息列表重新查看。" />

    <MobileSafeAreaBar v-if="m && (canHandle || showAck)">
      <button v-if="canHandle" class="btn btn-primary flex-1" @click="handle">{{ handleLabel }}</button>
      <button v-if="showAck" class="btn btn-primary flex-1" :disabled="acking" @click="ack">{{ acking ? '提交中…' : '确认已阅' }}</button>
    </MobileSafeAreaBar>
  </view>
</template>

<script>
import { popDetail } from '@/utils/msgStash'
import { toast } from '@/utils/nav'
import { useSessionStore } from '@/stores/session'
import { canNavigate, disabledReasonOf, runAction } from '@/services/actionRouter'
import { ackMessageReceipt, getMessageDetail, markMessageRead } from '@/services/realApi'
import { ackTeacherMessageReceipt, getTeacherMessageDetail, markTeacherMessageRead } from '@/services/teacherMessagesV3Api'

export default {
  data() { return { m: null, acking: false, loading: false, side: 'student' } },
  computed: {
    showAck() {
      if (!this.m || this.m.withdrawn || this.m.acked) return false
      return !!(this.m.receipt || this.m.requireAck)
    },
    action() { return (this.m && this.m.action) || null },
    canHandle() { return canNavigate(this.action, this.side) && !this.isDetailAction(this.action) },
    handleLabel() { return (this.action && this.action.label) || '去处理' }
  },
  onLoad(query) {
    this.side = useSessionStore().side === 'teacher' ? 'teacher' : 'student'
    const stashed = popDetail()
    const mid = (query && (query.id || query.messageId)) || (stashed && (stashed.messageId || stashed.id))
    const raw = String(mid || '').replace('msg-', '')
    if (raw && /^\d+$/.test(raw)) {
      this.loading = true
      const loadDetail = this.side === 'teacher' ? getTeacherMessageDetail : getMessageDetail
      const markRead = this.side === 'teacher' ? markTeacherMessageRead : markMessageRead
      loadDetail(raw).then((d) => {
        this.m = d || stashed || { id: raw, messageId: raw }
        if (this.m && !this.m.read) {
          markRead(raw).catch(() => {})
          this.m.read = true
        }
      }).catch(() => { this.m = stashed || null }).finally(() => { this.loading = false })
    } else {
      this.m = stashed || null
    }
  },
  methods: {
    formatTime(t) { return t ? String(t).slice(0, 16).replace('T', ' ') : '' },
    isDetailAction(action) { return !!(action && action.target && action.target.path === '/pages/common/message-detail/index') },
    async ack() {
      if (!this.m || this.acking) return
      const raw = String(this.m.messageId || this.m.id || '').replace('msg-', '')
      if (!/^\d+$/.test(raw)) { toast('无法确认该消息'); return }
      this.acking = true
      try {
        const ackReceipt = this.side === 'teacher' ? ackTeacherMessageReceipt : ackMessageReceipt
        await ackReceipt(raw)
        this.m.acked = true; this.m.receipt = false; this.m.read = true; toast('已确认')
      } catch (e) { toast((e && e.message) || '确认失败') }
      finally { this.acking = false }
    },
    handle() {
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
