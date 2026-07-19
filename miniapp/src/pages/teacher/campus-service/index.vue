<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="在校服务待处理" subtitle="学生请假等在校服务待审申请" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="list">
        <MobileGlobalState v-if="!list.length" state="empty" title="暂无待处理在校服务"
          description="学生提交的请假等在校服务申请会出现在这里。" />
        <template v-else>
          <view class="cs__hint">共 {{ list.length }} 条待处理，正式审批与销假请在「审批中心」完成。</view>
          <view class="stack">
            <view v-for="x in list" :key="x.id" class="card cs">
              <view class="row-between">
                <view class="flex-1">
                  <view class="row" style="gap:6px;">
                    <text class="t-md t-bold">{{ x.name || '—' }}</text>
                    <text class="cs__type">{{ x.typeLabel || x.type }}</text>
                  </view>
                  <text class="cs__sub">{{ x.className || '' }}<text v-if="x.code"> · {{ x.code }}</text></text>
                </view>
                <MobileStatusTag :label="x.statusLabel || x.status" type="warning" />
              </view>
              <view class="cs__period" v-if="x.startTime">
                <text class="cs__period-k">起止</text>
                <text class="flex-1 t-sm">{{ (x.startTime || '').slice(5, 16) }} ~ {{ (x.endTime || '').slice(5, 16) }}<text v-if="x.duration" class="cs__dur">（{{ x.duration }}）</text></text>
              </view>
              <view class="cs__reason" v-if="x.reason"><text class="cs__reason-k">事由</text><text class="flex-1 t-sm">{{ x.reason }}</text></view>
              <text class="cs__apply" v-if="x.applyTime">提交于 {{ (x.applyTime || '').slice(0, 16).replace('T', ' ') }}</text>
            </view>
          </view>
          <view class="cs__foot">
            <button class="btn btn-primary" @click="goApproval">前往审批中心处理</button>
          </view>
        </template>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { go } from '@/utils/nav'

export default {
  data() { return { list: null, state: 'loading' } },
  onLoad() { this.load() },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  methods: {
    load(done) {
      this.state = 'loading'
      teacherApi.getCampusServicePending()
        .then((d) => { this.list = (d && d.list) || []; this.state = 'ready' })
        .catch(() => { this.state = 'error' })
        .finally(() => { if (done) done() })
    },
    goApproval() { go('/pages/teacher/approval/index') }
  }
}
</script>

<style scoped>
.cs__hint { font-size: var(--font-size-xs); color: var(--text-tertiary); padding: 0 var(--space-1) var(--space-2); }
.cs { display: flex; flex-direction: column; gap: var(--space-2); }
.cs__type { font-size: 10px; color: var(--teacher-700); background: var(--teacher-50); padding: 1px 6px; border-radius: var(--radius-sm); }
.cs__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.cs__period, .cs__reason { display: flex; gap: var(--space-3); }
.cs__period-k, .cs__reason-k { font-size: var(--font-size-sm); color: var(--text-tertiary); width: 40px; flex-shrink: 0; }
.cs__dur { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.cs__apply { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.cs__foot { margin-top: var(--space-4); }
</style>
