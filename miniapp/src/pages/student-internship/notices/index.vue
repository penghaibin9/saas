<template>
  <view class="internship-surface mobile-page mobile-student page-wrap">
    <MobileNavBar variant="brand" title="通知公告" show-back :fallback-url="'/pages/student-internship/index' + (requestedBatchId ? '?batchId=' + encodeURIComponent(requestedBatchId) : '')" />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack">
        <view v-if="notices.length" class="stack">
          <view v-for="item in notices" :key="item.id" class="card nt__item">
            <view class="row-between">
              <view class="nt__title-wrap">
                <text class="nt__title">{{ item.title }}</text>
                <text class="nt__meta">{{ typeLabel(item.noticeType) }}</text>
                <text v-if="item.schoolCategory" class="nt__meta">学校分类：{{ item.schoolCategory }}</text>
              </view>
              <MobileStatusTag :label="urgencyLabel(item.urgency)" :type="urgencyTone(item.urgency)" />
            </view>
            <text class="nt__content">{{ item.content }}</text>
            <view class="nt__meta-block">
              <text>发布人：{{ item.senderName || '学校' }}</text>
              <text>发布时间：{{ formatTime(item.publishedAt) }}</text>
              <text v-if="item.validFrom || item.validUntil">有效期：{{ formatDate(item.validFrom) }} 至 {{ formatDate(item.validUntil) }}</text>
            </view>
            <view v-if="item.attachments?.length" class="nt__attachments">
              <text class="nt__section-label">附件</text>
              <view v-for="file in item.attachments" :key="file.fileId" class="nt__file" @click="openAttachment(file)">
                <view class="flex-1">
                  <text class="nt__file-name">{{ file.fileName || '通知附件' }}</text>
                  <text class="nt__file-meta">{{ formatSize(file.sizeBytes) }}</text>
                </view>
                <text class="nt__file-open">查看</text>
              </view>
            </view>
          </view>
        </view>

        <MobileInlineAlert v-else type="info" description="当前批次暂无有效通知公告。" />
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { openBusinessFile } from '@/services/fileApi'
import { toast } from '@/utils/nav'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { formatDateTime } from '@/utils/format'

const TYPE_LABEL = {
  AGREEMENT: '实习协议',
  TRAINING: '岗前培训',
  SAFETY: '安全条例',
  NOTICE: '通知公告',
  OTHER: '其他'
}
const URGENCY_LABEL = {
  NORMAL: '普通',
  IMPORTANT: '重要',
  URGENT: '紧急'
}

export default {
  data() {
    return {
      state: 'loading',
      requestedBatchId: '',
      notices: [],
      hidden: false, loadSequence: 0, generation: currentSessionGeneration()
    }
  },
  onLoad(options = {}) {
    this.requestedBatchId = String(options.batchId || '')
    this.load()
  },
  onPullDownRefresh() {
    this.load(() => uni.stopPullDownRefresh())
  },
  onShow() {
    const reload = this.hidden || this.generation !== currentSessionGeneration()
    this.hidden = false
    if (reload) this.load()
  },
  onHide() { this.hidden = true; this.loadSequence++ },
  onUnload() { this.hidden = true; this.loadSequence++ },
  methods: {
    async load(done) {
      if (this.generation !== currentSessionGeneration()) { this.notices = []; this.requestedBatchId = ''; this.generation = currentSessionGeneration() }
      const sequence = ++this.loadSequence, generation = currentSessionGeneration(), batchId = this.requestedBatchId
      const current = () => !this.hidden && sequence === this.loadSequence && generation === currentSessionGeneration() && batchId === this.requestedBatchId
      this.state = 'loading'
      try {
        const dashboard = await studentApi.getInternship(this.requestedBatchId)
        if (!current()) return
        const rows = await studentApi.getInternshipNotices(dashboard?.batchId || this.requestedBatchId)
        if (!current()) return
        this.notices = Array.isArray(rows) ? rows : []
        this.state = 'ready'
      } catch (error) {
        if (!current()) return
        this.state = 'error'
        toast(error?.message || '通知公告加载失败')
      } finally {
        done?.()
      }
    },
    typeLabel(value) { return TYPE_LABEL[String(value || '').toUpperCase()] || '通知公告' },
    urgencyLabel(value) { return URGENCY_LABEL[String(value || '').toUpperCase()] || '普通' },
    urgencyTone(value) {
      const v = String(value || '').toUpperCase()
      if (v === 'URGENT') return 'danger'
      if (v === 'IMPORTANT') return 'warning'
      return 'info'
    },
    formatTime(value) { return formatDateTime(value) },
    formatDate(value) { return value ? formatDateTime(value).slice(0, 10) : '不限' },
    formatSize(value) {
      const size = Number(value || 0)
      if (!size) return ''
      if (size < 1024) return size + ' B'
      if (size < 1024 * 1024) return (size / 1024).toFixed(1) + ' KB'
      return (size / 1024 / 1024).toFixed(1) + ' MB'
    },
    async openAttachment(file) {
      try {
        await openBusinessFile(file.fileId, file.fileName || '通知附件')
      } catch (error) {
        toast(error?.message || '附件暂时无法打开')
      }
    }
  }
}
</script>

<style scoped>
.nt__hint{display:block;margin-top:8px;font-size:var(--font-size-base);line-height:1.6;color:var(--text-secondary)}
.nt__item{display:flex;flex-direction:column;gap:12px}.nt__title-wrap{min-width:0;display:flex;flex-direction:column;gap:4px}.nt__title{font-size:var(--font-size-md);font-weight:600;line-height:1.45;color:var(--text-primary)}.nt__meta{font-size:var(--font-size-base);color:var(--text-tertiary)}
.nt__content{font-size:var(--font-size-base);line-height:1.75;white-space:pre-wrap;word-break:break-word;color:var(--text-secondary)}
.nt__meta-block{display:flex;flex-direction:column;gap:4px;padding-top:10px;border-top:1px solid var(--border-light);font-size:var(--font-size-base);color:var(--text-tertiary)}
.nt__attachments{display:flex;flex-direction:column;gap:8px}.nt__section-label{font-size:var(--font-size-base);font-weight:600;color:var(--text-secondary)}
.nt__file{display:flex;align-items:center;gap:12px;padding:10px;border-radius:var(--radius-md);background:var(--gray-50)}.nt__file-name{display:block;font-size:var(--font-size-base);color:var(--text-primary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.nt__file-meta{display:block;margin-top:2px;font-size:var(--font-size-base);color:var(--text-tertiary)}.nt__file-open{font-size:var(--font-size-base);color:var(--brand-primary)}
.nt__item>.row-between{gap:12px;align-items:flex-start}.nt__title-wrap{flex:1}.nt__file{min-height:44px;box-sizing:border-box}</style>
