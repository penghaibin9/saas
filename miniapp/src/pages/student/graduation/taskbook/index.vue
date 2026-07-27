<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="毕设任务书" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="t">
        <MobileGlobalState v-if="!t.hasData" state="empty" title="导师尚未下达任务书" description="任务书下达后会显示在这里。" />
        <template v-else>
          <view class="card">
            <view class="row-between">
              <text class="card-title">v{{ t.taskbookVersion }}</text>
              <MobileStatusTag :label="t.statusLabel" :type="t.statusTone" />
            </view>
            <text class="tb__meta">下达人 {{ t.issuedBy }} · {{ (t.issuedAt || '').slice(0, 10) }}</text>
          </view>

          <view class="card">
            <text class="tb__label">研究目标</text>
            <text class="tb__text">{{ t.objective || '—' }}</text>
          </view>
          <view class="card">
            <text class="tb__label">研究内容</text>
            <text class="tb__text">{{ t.content || '—' }}</text>
          </view>
          <view class="card">
            <text class="tb__label">进度安排</text>
            <text class="tb__text">{{ t.progressPlan || '—' }}</text>
          </view>
          <view class="card">
            <text class="tb__label">成果要求</text>
            <text class="tb__text">{{ t.outcomeRequirement || '—' }}</text>
          </view>

          <MobileInlineAlert v-if="t.changeReason" type="warning" title="任务书已变更" :description="t.changeReason" />
        </template>
      </view>
    </MobileGlobalState>

    <MobileSafeAreaBar v-if="t && t.hasData && t.status !== 'CONFIRMED'">
      <button class="btn btn-primary flex-1" :disabled="submitting" @click="confirm">
        {{ submitting ? '提交中…' : '确认任务书' }}
      </button>
    </MobileSafeAreaBar>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

export default {
  data() { return { t: null, state: 'loading', submitting: false } },
  onLoad() { this.load() },
  methods: {
    load() {
      this.state = 'loading'
      studentApi.getGraduationTaskbook().then((d) => {
        this.t = d
        this.state = 'ready'
      }).catch(() => { this.state = 'error' })
    },
    confirm() {
      if (this.submitting) return
      this.submitting = true
      studentApi.confirmGraduationTaskbook().then(() => {
        uni.showToast({ title: '已确认', icon: 'success' })
        this.load()
      }).catch((e) => toast(e && e.biz ? normalizeError(e).text : '确认失败，请稍后重试'))
        .finally(() => { this.submitting = false })
    }
  }
}
</script>

<style scoped>
.tb__meta { display: block; margin-top: 4px; font-size: var(--font-size-sm); color: var(--text-secondary); }
.tb__label { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-bottom: var(--space-2); }
.tb__text { display: block; font-size: var(--font-size-base); color: var(--text-primary); line-height: 1.6; }
</style>
