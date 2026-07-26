<template>
  <view class="page-wrap">
    <MobileNavBar title="知情书正文" subtitle="阅读后方可确认" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="state === 'ready' && detail">
        <view class="card cd__meta">
          <view class="row-between">
            <text class="t-md t-bold">学生知情确认</text>
            <MobileStatusTag :label="statusLabel(detail.status)" :type="statusTone(detail.status)" />
          </view>
          <text class="cd__version">正文版本：{{ detail.contentVersion }} · 校验摘要：{{ shortHash }}</text>
        </view>

        <view class="card cd__body">
          <text class="cd__body-title">知情书正文</text>
          <text class="cd__content" selectable>{{ detail.contentSnapshot || '正文为空，请联系学校管理员。' }}</text>
        </view>

        <MobileInlineAlert type="info" description="系统将记录本人账号、正文版本、正文摘要和确认时间；不会保存设备原始标识或IP明文。" />

        <view v-if="detail.status === 'PENDING'" class="card cd__reject">
          <text class="cd__label">拒绝原因（拒绝时必填，至少5字）</text>
          <textarea v-model="rejectReason" class="cd__textarea" maxlength="300" placeholder="说明无法确认的具体原因" />
        </view>
      </view>
    </MobileGlobalState>

    <MobileSafeAreaBar v-if="state === 'ready' && detail && detail.status === 'PENDING'">
      <button class="btn btn-ghost flex-1" :disabled="submitting" @click="reject">拒绝并提交原因</button>
      <button class="btn btn-primary flex-1" :disabled="submitting || !viewed" @click="confirm">{{ submitting ? '提交中…' : '本人已阅读并确认' }}</button>
    </MobileSafeAreaBar>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

export default {
  data() {
    return { id: '', detail: null, state: 'loading', viewed: false, submitting: false, rejectReason: '' }
  },
  computed: {
    shortHash() {
      const h = this.detail?.contentHash || ''
      return h ? `${h.slice(0, 10)}…${h.slice(-6)}` : '—'
    }
  },
  onLoad(options) { this.id = options?.id || ''; this.load() },
  methods: {
    async load() {
      if (!this.id) { this.state = 'error'; return }
      this.state = 'loading'
      try {
        let detail = await studentApi.getInternshipConsentDetail(this.id)
        if (detail.status === 'PENDING') {
          detail = await studentApi.viewInternshipConsent(this.id)
          this.viewed = true
        } else {
          this.viewed = !!detail.viewedAt
        }
        this.detail = detail
        this.state = 'ready'
      } catch (e) {
        this.state = 'error'
      }
    },
    deviceDigest() {
      try {
        const s = uni.getSystemInfoSync()
        return [s.platform, s.model, s.system, s.appVersion].filter(Boolean).join('|')
      } catch (e) { return 'miniapp-device' }
    },
    confirm() {
      if (this.submitting || !this.viewed) return
      uni.showModal({
        title: '确认知情书',
        content: `确认已阅读正文版本 ${this.detail.contentVersion} 并同意按学校实习要求执行？`,
        success: async (r) => {
          if (!r.confirm) return
          this.submitting = true
          try {
            await studentApi.confirmInternshipConsent(this.id, {
              expectedVersion: this.detail.version,
              contentVersion: this.detail.contentVersion,
              contentHash: this.detail.contentHash,
              deviceDigest: this.deviceDigest()
            })
            toast('知情确认已完成')
            await this.load()
          } catch (e) {
            toast(normalizeError(e).text || '确认失败，请刷新后重试')
            if (String(e?.code || '').includes('CONFLICT')) await this.load()
          } finally { this.submitting = false }
        }
      })
    },
    async reject() {
      if (this.submitting) return
      const reason = this.rejectReason.trim()
      if (reason.length < 5) { toast('拒绝原因至少5个字'); return }
      this.submitting = true
      try {
        await studentApi.rejectInternshipConsent(this.id, {
          expectedVersion: this.detail.version,
          reason
        })
        toast('拒绝原因已提交')
        await this.load()
      } catch (e) {
        toast(normalizeError(e).text || '提交失败，请重试')
        if (String(e?.code || '').includes('CONFLICT')) await this.load()
      } finally { this.submitting = false }
    },
    statusLabel(status) {
      return ({ PENDING: '待确认', VALID: '已确认', REJECTED: '已拒绝', REVOKED: '已作废', SUPERSEDED: '已更新' })[status] || status
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
.cd__version { font-size: var(--font-size-xs); color: var(--text-tertiary); word-break: break-all; }
.cd__body-title, .cd__label { font-size: var(--font-size-sm); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.cd__content { white-space: pre-wrap; font-size: var(--font-size-base); color: var(--text-secondary); line-height: 1.8; }
.cd__textarea { min-height: 100px; padding: var(--space-3); border: 1px solid var(--border-light); border-radius: var(--radius-md); box-sizing: border-box; width: 100%; }
</style>
