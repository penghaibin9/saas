<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="志愿办理结果" show-back />
    <view class="page-pad result-wrap">
      <MobileGlobalState :state="state" title="暂时无法读取原志愿" :description="error" @retry="load">
        <template v-if="result">
          <MobileInlineAlert v-if="updatedSinceMessage" type="warning" title="志愿已有更新" description="这条消息发出后，志愿已有更新。以下展示本组志愿的当前状态。" />
          <view class="result-card">
            <text class="result-context">{{ result.batchName }} · {{ result.campaignName }}</text>
            <text class="result-title">{{ statusLabel }}</text>
            <text class="result-description">{{ guidance }}</text>
            <view v-if="result.status === 'NEEDS_REVISION'" class="result-revision"><text class="result-label">学校补正意见</text><text class="result-description">{{ result.revisionReason || '请联系指导教师核对补正要求。' }}</text></view>
            <button v-if="result.status === 'NEEDS_REVISION' && result.campaignStatus === 'OPEN'" class="result-refresh" @click="openSelection">进入原招聘季补正</button>
            <text v-else-if="result.status === 'NEEDS_REVISION'" class="result-description">原招聘季当前未开放补正，请联系指导教师核对安排。</text>
            <view class="result-facts"><view><text>本组投递次数</text><text>{{ result.submissionVersion }} 次</text></view>
              <view><text>最近投递</text><text>{{ fmt(result.submittedAt) }}</text></view>
              <view v-if="result.approvedAt"><text>学校确认</text><text>{{ fmt(result.approvedAt) }}</text></view>
              <view v-else-if="result.revisionRequestedAt"><text>学校退回</text><text>{{ fmt(result.revisionRequestedAt) }}</text></view>
              <view v-else-if="result.teacherConfirmDeadline"><text>学校确认截止</text><text>{{ fmt(result.teacherConfirmDeadline) }}</text></view></view>
          </view>
          <view class="result-card"><text class="result-label">本组志愿 · {{ result.items.length }} 个</text>
            <text v-if="!result.items.length" class="result-description">本组暂无岗位志愿。</text>
            <view v-for="item in result.items" :key="item.id" class="result-choice">
              <view class="result-choice-head"><text class="result-context">第 {{ item.volunteerNo }} 志愿</text><MobileStatusTag :status="item.status" /></view>
              <text class="result-position">{{ item.positionName || '岗位名称未记录' }}</text>
              <text class="result-context">{{ item.companyName || '企业名称未记录' }}</text>
              <text v-if="item.applicationStatement" class="result-description">{{ item.applicationStatement }}</text>
            </view>
          </view>
          <text class="result-footnote">此页始终对应原招聘季。查看消息不会修改志愿、解除锁定或办理上岗。</text>
          <button class="result-refresh" @click="load">刷新当前结果</button>
        </template>
      </MobileGlobalState>
    </view>
  </view>
</template>

<script>
import { internshipSelectionApi } from '@/services/internshipSelectionApi'

export default {
  data() { return { groupId: '', messageVersion: '', state: 'loading', error: '', result: null, sequence: 0, alive: true } },
  computed: {
    updatedSinceMessage() { return this.result && /^\d+$/.test(this.messageVersion) && this.messageVersion !== String(this.result.version) },
    statusLabel() { return ({ DRAFT: '尚未投递', SUBMITTED: '等待企业与学校处理', LOCKED: '企业拟接收，待学校确认', NEEDS_REVISION: '学校退回，请补正后重提', APPROVED: '学校已确认岗位', CLOSED: '本组志愿已关闭' }[this.result?.status] || '请核对办理状态') },
    guidance() {
      if (this.result?.lockExpired) return '学校确认期限已过，当前仍保留锁定记录。请联系指导教师核对后续安排。'
      return ({ APPROVED: '岗位已经确定。还需完成协议、保险及上岗核验，通过学校要求后再上岗。', NEEDS_REVISION: '请先阅读学校意见，补充材料并重新投递。此前企业处理意见属于旧投递记录。', LOCKED: '企业拟接收不等于正式落岗，请等待学校最终确认。', SUBMITTED: '投递已送达，请留意企业处理与学校确认消息。', DRAFT: '本组内容尚未正式投递。', CLOSED: '本组志愿已结束，保留记录供你查看。' }[this.result?.status] || '请联系指导教师核对当前安排。')
    }
  },
  onLoad(query = {}) {
    this.applyQuery(query)
  },
  // H5 may reuse this page for a changed hash query without invoking uni onLoad.
  watch: {
    '$route.fullPath'() {
      if (this.$route?.path === '/pages/student-internship/volunteer-result/index') this.applyQuery(this.$route.query || {})
    }
  },
  onUnload() { this.alive = false; this.sequence++ },
  methods: {
    openSelection() {
      const row = this.result
      if (!row || row.status !== 'NEEDS_REVISION' || row.campaignStatus !== 'OPEN') return
      const query = ['batchId', 'campaignId', 'recordId'].map(key => `${key}=${encodeURIComponent(row[key])}`).join('&')
      uni.navigateTo({ url: `/pages/student-internship/enterprises/index?${query}` })
    },
    applyQuery(query = {}) {
      this.groupId = typeof query.groupId === 'string' && /^[1-9]\d*$/.test(query.groupId) ? query.groupId : ''
      this.messageVersion = typeof query.groupVersion === 'string' ? query.groupVersion : ''
      return this.load()
    },
    fmt(value) { if (!value) return '尚无记录'; const date = new Date(value); return Number.isNaN(date.getTime()) ? '时间待核对' : date.toLocaleString('zh-CN', { hour12: false }) },
    async load() {
      const current = ++this.sequence
      this.result = null; this.error = ''; this.state = 'loading'
      if (!this.groupId) { this.error = '消息缺少有效的原志愿编号，请从消息重新进入。'; this.state = 'error'; return }
      const id = this.groupId
      try {
        const data = await internshipSelectionApi.volunteerResult(id)
        if (!this.alive || current !== this.sequence) return
        if (String(data?.id) !== id) throw new Error('返回结果与原志愿不一致，请重试。')
        this.result = { ...data, items: Array.isArray(data.items) ? data.items : [] }; this.state = 'ready'
      } catch (e) { if (this.alive && current === this.sequence) { this.error = e?.message || '读取失败，请稍后重试。'; this.state = 'error' } }
    }
  }
}
</script>

<style scoped>
.result-wrap{padding-bottom:calc(24px + env(safe-area-inset-bottom))}.result-card{padding:20px;margin-bottom:16px;background:var(--bg-card,#fff);border:1px solid var(--border-light);border-radius:var(--radius-lg,16px)}.result-context,.result-title,.result-description,.result-label,.result-position,.result-footnote{display:block}.result-context{color:var(--text-tertiary);font-size:var(--font-size-xs);line-height:1.6}.result-title{font-size:22px;font-weight:600;color:var(--text-primary);line-height:1.5;margin:14px 0 8px}.result-description{font-size:var(--font-size-base);color:var(--text-secondary);line-height:1.8;white-space:pre-wrap;overflow-wrap:anywhere}.result-revision{padding:16px;background:var(--bg-page,#f6f8fb);border-radius:10px;margin-top:16px}.result-label,.result-position{font-size:16px;font-weight:600;color:var(--text-primary);line-height:1.6}.result-revision .result-description{margin-top:8px}.result-facts{padding-top:16px;margin-top:16px;border-top:1px solid var(--border-light);font-size:var(--font-size-xs);color:var(--text-secondary)}.result-facts>view{display:flex;justify-content:space-between;gap:12px;margin:8px 0}.result-facts>view>text:last-child{text-align:right}.result-choice{border-top:1px solid var(--border-light);padding-top:16px;margin-top:16px}.result-choice-head{display:flex;justify-content:space-between;gap:12px;margin-bottom:8px}.result-choice .result-description{margin-top:8px}.result-footnote{color:var(--text-tertiary);font-size:12px;line-height:1.8;margin-bottom:16px}.result-refresh{min-height:44px;font-size:14px;color:var(--text-primary);background:var(--bg-card,#fff)}
</style>
