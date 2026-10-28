<template>
  <view class="mobile-page mobile-student page-wrap">
    <MobileNavBar title="知情确认" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="state === 'ready'">
        <MobileGlobalState v-if="!items.length" class="cs-empty" state="empty" title="本批次暂无知情确认任务" />
        <view v-for="item in items" :key="item.id" class="card cs" @click="open(item)">
          <view class="row-between">
            <view class="flex-1">
              <text class="t-md t-bold">{{ item.consentType === 'GUARDIAN' ? '监护人知情确认' : '学生知情确认' }}</text>
              <text class="cs__sub">正文版本 {{ item.contentVersion || '—' }}</text>
            </view>
            <MobileStatusTag :label="statusLabel(item.status)" :type="statusTone(item.status)" />
          </view>
          <text class="cs__hint">{{ hint(item) }}</text>
          <view v-if="item.consentType === 'STUDENT'" class="cs__action">{{ item.status === 'PENDING' ? '打开正文并办理' : '查看正文与结果' }} ›</view>
          <view v-else-if="item.consentType === 'GUARDIAN'" class="cs__guardian">
            <text>{{ item.participantRelation || '监护人' }}</text>
            <text>{{ item.contactMasked || '联系方式未提供' }}</text>
          </view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentInternshipConsents } from '@/services/internshipApi'
import { go } from '@/utils/nav'
import { normalizeError } from '@/services/request'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { formatDateTime } from '@/utils/format'

export default {
  data() { return { state: 'loading', items: [], batchId: '', hidden: false, sequence: 0, generation: currentSessionGeneration() } },
  onLoad(options) { this.batchId = String(options?.batchId || ''); this.load() },
  onShow() { const hidden = this.hidden; this.hidden = false; if (hidden || this.generation !== currentSessionGeneration()) this.load() },
  onHide() { this.hidden = true; this.sequence++; this.items = [] },
  onUnload() { this.hidden = true; this.sequence++; this.items = []; this.batchId = '' },
  onPullDownRefresh() { this.load(() => uni.stopPullDownRefresh()) },
  methods: {
    async load(done) {
      if (this.generation !== currentSessionGeneration()) {
        this.sequence++; this.items = []; this.batchId = ''; this.state = 'forbidden'
        done && done(); return
      }
      if (this.hidden) { done && done(); return }
      const sequence = ++this.sequence, batchId = this.batchId, generation = this.generation
      const current = () => !this.hidden && sequence === this.sequence && batchId === this.batchId && generation === currentSessionGeneration()
      this.state = 'loading'; this.items = []
      try {
        const data = await studentInternshipConsents(batchId)
        if (!current()) return
        this.items = Array.isArray(data) ? data : (data?.items || [])
        this.state = 'ready'
      } catch (e) { if (current()) this.state = normalizeError(e).pageState || 'error' }
      finally { done && done() }
    },
    open(item) {
      if (this.hidden || this.state !== 'ready' || this.generation !== currentSessionGeneration() || item.consentType !== 'STUDENT' || !this.items.some(x => String(x.id) === String(item.id) && x.consentType === 'STUDENT')) return
      const query = [`id=${encodeURIComponent(item.id)}`]
      if (this.batchId) query.push(`batchId=${encodeURIComponent(this.batchId)}`)
      go(`/pages/student-internship/consent/detail?${query.join('&')}`)
    },
    statusLabel(status) {
      return ({ PENDING: '待确认', VALID: '已确认', REJECTED: '已拒绝', REVOKED: '已作废',
        SUPERSEDED: '已更新', NOT_APPLICABLE: '不适用' })[status] || '状态待核对'
    },
    statusTone(status) {
      if (status === 'VALID' || status === 'NOT_APPLICABLE') return 'success'
      if (status === 'REJECTED' || status === 'REVOKED') return 'danger'
      return 'warning'
    },
    hint(item) {
      if (item.status === 'PENDING') return item.consentType === 'GUARDIAN' ? '等待已绑定监护人完成确认' : '请完整阅读正文后确认'
      if (item.status === 'VALID') return item.confirmedAt ? `确认时间：${formatDateTime(item.confirmedAt)}` : '已完成确认'
      if (item.status === 'SUPERSEDED') return '正文已更新，请办理最新版本'
      if (item.status === 'REJECTED') return '已拒绝，请联系指导教师处理'
      return '该任务当前无需办理'
    }
  }
}
</script>

<style scoped>
.cs-empty :deep(.mgs-desc){display:none}
.cs { display: flex; flex-direction: column; gap: var(--space-2); }
.cs__sub { display: block; margin-top: 3px; font-size: var(--font-size-base); color: var(--text-tertiary); }
.cs__hint { font-size: var(--font-size-base); color: var(--text-secondary); line-height: 1.6; }
.cs__action { align-self: flex-end; display:flex;align-items:center;min-height:var(--touch-target-min);color: var(--brand-primary); font-size: var(--font-size-md); }
.cs__guardian { display: flex; flex-wrap:wrap;gap:8px;justify-content: space-between; font-size: var(--font-size-base); color: var(--text-tertiary); }
</style>
