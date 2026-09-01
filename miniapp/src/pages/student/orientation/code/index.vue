<template>
  <view class="page-wrap">
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="o">
        <view class="card oq__ticket" :class="{ 'is-invalid': !credential.token }">
          <text class="oq__ticket-label">到校报到二维码</text>
          <text class="oq__guide">到校后打开本页，请辅导员或现场核验人员扫码</text>
          <view class="oq__code-box">
            <image v-if="credential.qrDataUrl" class="oq__qr" :src="credential.qrDataUrl" mode="aspectFit" />
            <text v-else class="oq__code">{{ issuing ? '签发中…' : '尚未签发' }}</text>
          </view>
          <text class="oq__note">{{ credential.token ? '二维码仅用于本人本次报到，扫码确认后自动失效' : o.reportCode.note }}</text>
          <text v-if="credential.expiresAt" class="oq__expires">有效至 {{ credential.expiresAt.replace('T', ' ').slice(0, 19) }}</text>
          <button class="btn-primary oq__issue" :disabled="issuing || !o.reportCode.canIssue" @click="issue(false)">
            {{ credential.token ? '二维码过期了？重新生成' : '生成报到二维码' }}
          </button>
        </view>

        <view class="card oq__identity">
          <text class="card-title">身份信息</text>
          <view class="oq__row"><text class="oq__k">姓名</text><text class="oq__v">{{ o.identity.name }}</text></view>
          <view class="oq__row"><text class="oq__k">录取编号</text><text class="oq__v">{{ o.identity.admissionNo || '—' }}</text></view>
          <view class="oq__row"><text class="oq__k">学院</text><text class="oq__v">{{ o.identity.collegeName || '—' }}</text></view>
          <view class="oq__row"><text class="oq__k">专业</text><text class="oq__v">{{ o.identity.majorName || '—' }}</text></view>
          <view class="oq__row"><text class="oq__k">班级</text><text class="oq__v">{{ o.identity.className || '待分班' }}</text></view>
        </view>

        <MobileInlineAlert type="info" description="二维码十分钟内有效。无需截图保存，过期后在本页重新生成即可。" />
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { toast } from '@/utils/nav'
export default {
  data() { return { o: null, state: 'loading', issuing: false, credential: { token: '', qrDataUrl: '', expiresAt: '' } } },
  onLoad() { this.load() },
  methods: {
    async load() {
      this.state = 'loading'
      try {
        this.o = await studentApi.getOrientation()
        this.state = 'ready'
        if (this.o?.reportCode?.canIssue && !this.credential.token) await this.issue(true)
      } catch (_) { this.state = 'error' }
    },
    async issue(silent = false) {
      if (this.issuing || !this.o?.reportCode?.canIssue) return
      this.issuing = true
      try {
        this.credential = await studentApi.issueOrientationCheckinToken()
        if (!silent) toast('报到二维码已更新')
      } catch (e) {
        toast(e?.message || '报到凭证签发失败')
      } finally { this.issuing = false }
    }
  }
}
</script>

<style scoped>
.oq__ticket {
  position: relative; text-align: center; padding: var(--space-6) var(--space-5);
  background: linear-gradient(180deg, #fff, var(--primary-50));
  border: 1px dashed var(--brand-primary);
}
.oq__ticket.is-invalid { border-color: var(--border-dark); background: var(--gray-50); }
.oq__ticket-label { font-size: var(--font-size-sm); color: var(--text-tertiary); }
.oq__guide { display: block; margin-top: 6px; color: var(--text-primary); font-size: var(--font-size-base); font-weight: 600; }
.oq__code-box { margin: var(--space-4) 0; padding: var(--space-4); background: #fff; border-radius: var(--radius-md); box-shadow: var(--shadow-card); }
.oq__qr { display: block; width: 440rpx; height: 440rpx; max-width: 100%; margin: 0 auto; }
.oq__code { font-size: 28px; font-weight: var(--font-weight-semibold); color: var(--text-primary); letter-spacing: 4px; font-family: monospace; }
.oq__ticket.is-invalid .oq__code { color: var(--text-disabled); }
.oq__note { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); }
.oq__expires { display: block; margin-top: var(--space-2); font-size: var(--font-size-xs); color: var(--success-600); }
.oq__issue { margin-top: var(--space-4); }
.oq__done-badge { position: absolute; top: var(--space-3); right: var(--space-3); font-size: var(--font-size-xs); color: #fff; background: var(--success-500); padding: 3px 10px; border-radius: var(--radius-full); }
.oq__identity { margin: var(--card-gap-mobile) 0; }
.oq__row { display: flex; align-items: center; padding: 8px 0; border-bottom: 1px solid var(--border-light); }
.oq__row:last-child { border-bottom: none; }
.oq__k { width: 76px; flex-shrink: 0; font-size: var(--font-size-sm); color: var(--text-tertiary); }
.oq__v { font-size: var(--font-size-base); color: var(--text-primary); }
</style>
