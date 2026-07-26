<template>
  <view class="page-wrap">
    <MobileNavBar title="知情确认" subtitle="本人知情书与监护人确认进度" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="state === 'ready'">
        <MobileInlineAlert type="info" description="学生知情书须本人打开正文后确认；监护人任务仅展示进度，不会向学生端暴露确认链接或手机号。" />
        <MobileGlobalState v-if="!items.length" state="empty" title="暂无知情确认任务"
          description="学校下发知情书后会显示在这里。" />
        <view v-for="item in items" :key="item.id" class="card cs" @click="open(item)">
          <view class="row-between">
            <view class="flex-1">
              <text class="t-md t-bold">{{ item.consentType === 'GUARDIAN' ? '监护人知情确认' : '学生知情确认' }}</text>
              <text class="cs__sub">正文版本 {{ item.contentVersion || '—' }}</text>
            </view>
            <MobileStatusTag :label="statusLabel(item.status)" :type="statusTone(item.status)" />
          </view>
          <text class="cs__hint">{{ hint(item) }}</text>
          <view v-if="item.consentType === 'STUDENT' && item.status === 'PENDING'" class="cs__action">打开正文并办理 ›</view>
          <view v-else-if="item.consentType === 'GUARDIAN'" class="cs__guardian">
            <text>{{ item.participantRelation || '监护人' }}</text>
            <text>{{ item.contactMasked || '联系方式已脱敏' }}</text>
          </view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { go } from '@/utils/nav'

export default {
  data() { return { state: 'loading', items: [] } },
  onLoad() { this.load() },
  onShow() { if (this.state === 'ready') this.load() },
  onPullDownRefresh() { this.load(() => uni.stopPullDownRefresh()) },
  methods: {
    async load(done) {
      this.state = 'loading'
      try {
        const data = await studentApi.getInternshipConsents()
        this.items = Array.isArray(data) ? data : (data?.items || [])
        this.state = 'ready'
      } catch (e) {
        this.state = 'error'
      } finally { done && done() }
    },
    open(item) {
      if (item.consentType !== 'STUDENT') return
      go(`/pages/student/internship/consent/detail?id=${encodeURIComponent(item.id)}`)
    },
    statusLabel(status) {
      return ({ PENDING: '待确认', VALID: '已确认', REJECTED: '已拒绝', REVOKED: '已作废',
        SUPERSEDED: '已更新', NOT_APPLICABLE: '不适用' })[status] || status || '未知'
    },
    statusTone(status) {
      if (status === 'VALID' || status === 'NOT_APPLICABLE') return 'success'
      if (status === 'REJECTED' || status === 'REVOKED') return 'danger'
      return 'warning'
    },
    hint(item) {
      if (item.status === 'PENDING') return item.consentType === 'GUARDIAN' ? '等待已绑定监护人完成确认' : '请打开并完整阅读服务端保存的正文'
      if (item.status === 'VALID') return item.confirmedAt ? `确认时间：${item.confirmedAt}` : '已完成确认'
      if (item.status === 'SUPERSEDED') return '正文已更新，请办理最新版本'
      if (item.status === 'REJECTED') return '已拒绝，请联系指导教师处理'
      return '该任务当前无需办理'
    }
  }
}
</script>

<style scoped>
.cs { display: flex; flex-direction: column; gap: var(--space-2); }
.cs__sub { display: block; margin-top: 3px; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.cs__hint { font-size: var(--font-size-sm); color: var(--text-secondary); line-height: 1.6; }
.cs__action { align-self: flex-end; color: var(--brand-primary); font-size: var(--font-size-sm); }
.cs__guardian { display: flex; justify-content: space-between; font-size: var(--font-size-xs); color: var(--text-tertiary); }
</style>
