<template>
  <view class="internship-surface mobile-page mobile-student page-wrap">
    <MobileNavBar title="知情书正文" show-back :fallback-url="'/pages/student-internship/consent/index' + (batchId ? '?batchId=' + encodeURIComponent(batchId) : '')" />
    <view v-if="state === 'error' && !id" class="page-pad stack"><MobileInlineAlert type="warning" title="链接不完整" description="请从知情确认列表进入。" /><navigator :url="'/pages/student-internship/consent/index' + (batchId ? '?batchId=' + encodeURIComponent(batchId) : '')" open-type="redirect" class="mobile-control btn btn-primary">返回知情确认</navigator></view>
    <MobileGlobalState v-else :state="state" @retry="load">
      <view class="page-pad stack" v-if="state === 'ready' && detail">
        <view class="card cd__meta">
          <view class="row-between">
            <text class="t-md t-bold">学生知情确认</text>
            <MobileStatusTag :label="statusLabel(detail.status)" :type="statusTone(detail.status)" />
          </view>
          <text class="cd__version">正文版本：{{ detail.contentVersion }}</text>
          <text v-if="detail.confirmedAt" class="cd__version">确认时间：{{ confirmedTime }}</text>
          <text v-if="detail.status === 'PENDING'" class="cd__version">请完整阅读本版本正文，再由本人决定是否确认；打开正文只记录阅读，不代替确认。</text>
          <text v-else class="cd__version">本页为已办记录，请核对上方处理结果和正文版本。</text>
          <view class="cd__reading-tools" role="group" aria-label="正文字号"><button v-for="choice in [{size:15,label:'标准字'},{size:17,label:'大字'},{size:19,label:'更大字'}]" :key="choice.size" class="mobile-control btn btn-ghost" :aria-pressed="readFontSize===choice.size" @click="readFontSize=choice.size">{{ choice.label }}</button></view>
          <text class="cd__version">阅读位置：{{ readingEnd ? '本页末段' : readingScrolled ? '正文阅读中' : '页首' }}</text>
          <text class="cd__content" :style="{fontSize:readFontSize+'px'}" selectable>{{ detail.contentSnapshot || '正文为空，请联系学校管理员。' }}</text>
        </view>

        <MobileInlineAlert v-if="detail.status === 'REJECTED' && detail.rejectionReason" type="warning" :description="'已提交原因：' + detail.rejectionReason" />
        <MobileInlineAlert v-if="actionError" type="warning" :description="actionError" />
        <button class="mobile-control" v-if="actionError" :disabled="submitting" @click="load">重新打开正文并核对</button>

        <view v-if="detail.status === 'PENDING'" class="card cd__reject">
          <text class="cd__label">拒绝原因（拒绝时必填，至少5字）</text>
          <textarea v-model="rejectReason" :disabled="submitting" class="mobile-textarea cd__textarea" maxlength="300" placeholder="说明无法确认的具体原因" />
        </view>
      </view>
    </MobileGlobalState>

    <MobileSafeAreaBar v-if="state === 'ready' && detail && detail.status === 'PENDING'">
      <button class="mobile-control btn btn-ghost flex-1" :disabled="submitting || !viewed" @click="reject">拒绝并提交原因</button>
      <button class="mobile-control btn btn-primary flex-1" :disabled="submitting || !viewed" @click="confirm">{{ submitting ? '处理中…' : '本人已阅读并确认' }}</button>
    </MobileSafeAreaBar>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'
import { getDeviceDigest } from '@/utils/deviceInfo'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { formatDateTime } from '@/utils/format'

export default {
  data() {
    return { readFontSize:15,readingScrolled:false,readingEnd:false,id: '', batchId: '', detail: null, state: 'loading', viewed: false, submitting: false,
      rejectReason: '', actionError: '', hidden: false, sequence: 0, generation: currentSessionGeneration() }
  },
  computed: { confirmedTime() { return formatDateTime(this.detail?.confirmedAt) } },
  onLoad(options) { this.id = String(options?.id || ''); this.batchId = String(options?.batchId || ''); this.load() },
  onShow() { const hidden = this.hidden; this.hidden = false; if (this.checkSession() && hidden) this.load() },
  onHide() { this.pause() },
  onPageScroll(event) { this.readingScrolled=Number(event.scrollTop)>0;if(!this.readingScrolled)this.readingEnd=false },
  onReachBottom() { this.readingEnd=true },
  onUnload() { this.pause(); this.id = ''; this.batchId = ''; this.rejectReason = '' },
  methods: {
    pause() { this.hidden = true; this.sequence++; this.submitting = false; this.viewed = false; this.detail = null },
    checkSession() {
      if (this.generation === currentSessionGeneration()) return true
      this.pause(); this.hidden = false; this.generation = currentSessionGeneration()
      this.id = ''; this.batchId = ''; this.rejectReason = ''; this.actionError = ''; this.state = 'forbidden'
      return false
    },
    capture() { return { sequence: this.sequence, id: this.id, batchId: this.batchId, generation: this.generation } },
    current(target) { return !this.hidden && target.sequence === this.sequence && target.id === this.id &&
      target.batchId === this.batchId && target.generation === currentSessionGeneration() },
    async load() {
      if (!this.checkSession() || this.hidden) return
      if (!this.id) { this.state = 'error'; return }
      this.sequence++; const target = this.capture()
      this.readingScrolled=false;this.readingEnd=false
      this.state = 'loading'; this.viewed = false; this.detail = null; this.actionError = ''; this.submitting = false
      try {
        let detail = await studentApi.getInternshipConsentDetail(target.id)
        if (!this.current(target)) return
        this.detail = detail; this.state = 'ready'
        await this.$nextTick()
        if (!this.current(target)) return
        if (detail.status === 'PENDING') {
          detail = await studentApi.viewInternshipConsent(target.id)
          if (!this.current(target)) return
          this.viewed = true
        } else {
          this.viewed = !!detail.viewedAt
        }
        this.detail = detail
        this.state = 'ready'
      } catch (e) {
        if (this.current(target)) { this.viewed = false; this.state = normalizeError(e).pageState || 'error' }
      }
    },
    deviceDigest() {
      return getDeviceDigest()
    },
    confirm() {
      const target = this.capture()
      if (!this.current(target) || this.submitting || !this.viewed || this.detail?.status !== 'PENDING') return
      const body = { expectedVersion: this.detail.version, contentVersion: this.detail.contentVersion,
        contentHash: this.detail.contentHash, deviceDigest: this.deviceDigest() }
      let settled = false
      this.submitting = true
      uni.showModal({
        title: '确认知情书',
        content: `确认已阅读正文版本 ${body.contentVersion} 并同意按学校实习要求执行？`,
        success: async (r) => {
          if (settled) return
          settled = true
          if (!this.current(target)) return
          if (!r.confirm) { this.submitting = false; return }
          try {
            await studentApi.confirmInternshipConsent(target.id, body)
            if (!this.current(target)) return
            toast('知情确认已完成')
            await this.load()
          } catch (e) {
            if (this.current(target)) this.failed(e)
          } finally { if (this.current(target)) this.submitting = false }
        },
        fail: () => { if (settled) return; settled = true; if (this.current(target)) this.submitting = false }
      })
    },
    async reject() {
      const target = this.capture()
      if (!this.current(target) || this.submitting || !this.viewed || this.detail?.status !== 'PENDING') return
      const reason = this.rejectReason.trim()
      if (reason.length < 5) { toast('拒绝原因至少5个字'); return }
      this.submitting = true
      try {
        await studentApi.rejectInternshipConsent(target.id, {
          expectedVersion: this.detail.version,
          reason
        })
        if (!this.current(target)) return
        toast('拒绝原因已提交')
        await this.load()
      } catch (e) {
        if (this.current(target)) this.failed(e)
      } finally { if (this.current(target)) this.submitting = false }
    },
    failed(e) {
      this.actionError = e?.bizCode === 'DATA_CONFLICT' ? '任务或正文已变化，本次未提交。请重新打开正文核对后再办理；拒绝原因已保留。' : normalizeError(e).text
      if (e?.bizCode === 'DATA_CONFLICT') this.viewed = false
      toast(this.actionError)
    },
    statusLabel(status) {
      return ({ PENDING: '待确认', VALID: '已确认', REJECTED: '已拒绝', REVOKED: '已作废', SUPERSEDED: '已更新', NOT_APPLICABLE: '不适用' })[status] || '状态待核对'
    },
    statusTone(status) {
      if (status === 'VALID') return 'success'
      if (status === 'REJECTED' || status === 'REVOKED') return 'danger'
      return 'warning'
    }
  }
}
</script>

<style scoped>
.cd__meta, .cd__body, .cd__reject { display: flex; flex-direction: column; gap: var(--space-3); }
.cd__version { font-size: var(--font-size-base); color: var(--text-tertiary); word-break: break-all; }
.cd__body-title, .cd__label { font-size: var(--font-size-base); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.cd__content { white-space: pre-wrap; font-size: var(--font-size-base); color: var(--text-secondary); line-height: 1.8; }
.cd__textarea { min-height: 100px; padding: var(--space-3); border: 1px solid var(--border-light); border-radius: var(--radius-md); box-sizing: border-box; width: 100%; }
.cd__meta>.row-between{gap:12px;align-items:flex-start}.cd__content{padding-top:12px;border-top:1px solid var(--border-light);color:var(--text-primary);font-size:15px;overflow-wrap:anywhere}.cd__textarea{font-size:14px;line-height:1.6}.cd__reject{padding:14px}.cd__content{font-size:var(--font-size-md);line-height:1.9;white-space:pre-wrap;overflow-wrap:anywhere}
.cd__reading-tools{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:12px}.cd__reading-tools>button{width:100%;margin:0;padding:0 4px;font-size:14px}.cd__reading-tools>button[aria-pressed=true]{background:var(--primary-50)}
</style>
