<template>
  <view>
    <view v-if="error && !active" class="notice-warning">
      <MobileInlineAlert type="warning" title="通知读取未完成" :description="error" />
      <button class="btn btn-ghost" :disabled="loading" @click="refresh()">重新读取通知</button>
    </view>
    <view v-if="active" class="notice-mask">
      <view class="notice-dialog" role="dialog" aria-label="教师重要通知">
        <text class="notice-kicker">重要通知</text>
        <text class="notice-title">{{ active.title }}</text>
        <text class="notice-meta">{{ active.senderName || '学校' }} · {{ formatDateTime(active.publishedAt) }}</text>
        <text class="notice-meta">{{ typeLabel(active.noticeType) }} · {{ active.urgency==='URGENT' ? '紧急' : '重要' }}</text>
        <text v-if="active.validFrom || active.validUntil" class="notice-meta">有效期：{{ noticeDate(active.validFrom) }} 至 {{ noticeDate(active.validUntil) }}</text>
        <scroll-view scroll-y class="notice-body">
          <text class="notice-content">{{ active.content }}</text>
          <view v-if="active.attachments?.length" class="notice-files">
            <text v-for="file in active.attachments" :key="file.fileId" class="notice-file" @click="openFile(file)">{{ file.fileName || '通知附件' }} · 查看</text>
          </view>
        </scroll-view>
        <MobileInlineAlert type="warning" description="请本人明确确认。退出、刷新或确认失败都不会自动登记已读。" />
        <MobileInlineAlert v-if="error" type="warning" title="通知操作未完成" :description="error" />
        <button v-if="error" class="btn btn-ghost" :disabled="loading" @click="refresh()">重新读取通知</button>
        <button class="btn btn-primary" :disabled="acking || loading" @click="acknowledge">{{ acking ? '正在记录…' : '我已知悉' }}</button>
      </view>
    </view>
  </view>
</template>

<script>
import teacherApi from '@/services/teacherApi'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { formatDateTime } from '@/utils/format'
import { openBusinessFile } from '@/services/fileApi'

export default {
  props: { batchId: { type:String, default:'' } },
  data: () => ({ rows:[], active:null, error:'', loading:false, acking:false, sequence:0, hidden:false, generation:currentSessionGeneration() }),
  watch: { batchId() { this.pause(); this.rows=[]; this.active=null; this.error=''; this.hidden=false } },
  beforeUnmount() { this.pause() },
  methods: {
    formatDateTime,
    typeLabel(value) { return ({AGREEMENT:'实习协议',TRAINING:'岗前培训',SAFETY:'安全条例',NOTICE:'通知公告',OTHER:'其他'})[value] || '通知公告' },
    noticeDate(value) { return value ? formatDateTime(value).slice(0,10) : '不限' },
    reset() { this.pause(); this.rows=[]; this.active=null; this.error=''; this.generation=currentSessionGeneration() },
    pause() { this.hidden=true; this.sequence++; this.acking=false; this.loading=false },
    current(sequence,generation,batchId) { return !this.hidden && sequence===this.sequence && generation===currentSessionGeneration() && batchId===this.batchId },
    async refresh() {
      if(this.generation!==currentSessionGeneration()) { this.rows=[]; this.active=null; this.error=''; this.generation=currentSessionGeneration() }
      this.hidden=false; this.acking=false
      const sequence=++this.sequence,generation=currentSessionGeneration(),batchId=this.batchId
      if(!batchId) { this.rows=[]; this.active=null; this.loading=false; return }
      this.loading=true
      try {
        const rows=await teacherApi.getPendingInternshipEmergencyNotices(batchId)
        if(!this.current(sequence,generation,batchId)) return
        this.rows=Array.isArray(rows)?rows:[]; this.active=this.rows[0]||null; this.error=''
      } catch(e) {
        if(this.current(sequence,generation,batchId)) this.error='暂不能确认是否有新的重要通知，请重新读取；已有通知会保留。'
      } finally { if(this.current(sequence,generation,batchId)) this.loading=false }
    },
    async acknowledge() {
      if(!this.active || this.acking || this.loading || this.hidden) return
      const row=this.active,sequence=this.sequence,generation=currentSessionGeneration(),batchId=this.batchId
      const current=()=>this.current(sequence,generation,batchId) && this.active===row
      this.acking=true
      try {
        await teacherApi.acknowledgeInternshipEmergencyNotice(row.id,batchId)
        if(!current()) return
        this.acking=false; this.error=''; this.rows=this.rows.filter(x=>String(x.id)!==String(row.id)); this.active=this.rows[0]||null
      } catch(e) { if(current()) this.error=e?.message || '知悉确认未完成，通知仍会保留。' }
      finally { if(current()) this.acking=false }
    },
    async openFile(file) { try { await openBusinessFile(file.fileId,file.fileName||'通知附件') } catch(e) { this.error=e?.message||'附件暂时无法打开' } }
  }
}
</script>

<style scoped>
.notice-warning{padding:16px}.notice-mask{position:fixed;z-index:9999;inset:0;background:rgba(15,23,42,.68);display:flex;align-items:center;justify-content:center;padding:24px;box-sizing:border-box}
.notice-dialog{width:100%;max-width:560px;max-height:82vh;background:var(--bg-card);border-radius:var(--radius-lg);padding:20px;box-sizing:border-box;display:flex;flex-direction:column;gap:14px;box-shadow:0 24px 64px rgba(15,23,42,.28)}
.notice-kicker{font-size:12px;font-weight:600;color:var(--danger-600,#dc2626)}.notice-title{font-size:20px;font-weight:700;line-height:1.45;color:var(--text-primary)}.notice-meta{font-size:11px;color:var(--text-tertiary)}
.notice-body{max-height:38vh;padding:12px;background:var(--gray-50,#f8fafc);border:1px solid var(--border-light);border-radius:var(--radius-sm);box-sizing:border-box}.notice-content{white-space:pre-wrap;word-break:break-word;font-size:14px;line-height:1.8;color:var(--text-secondary)}
.notice-files{display:flex;flex-direction:column;gap:8px;margin-top:12px}.notice-file{font-size:13px;color:var(--brand-primary);word-break:break-word}
</style>
