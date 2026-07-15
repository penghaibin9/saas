<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" :title="d ? d.viewLabel + '看板' : '数据看板'" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="d">
        <text class="t-xs t-tertiary">更新于 {{ (d.updatedAt || '').slice(0, 16).replace('T', ' ') }}</text>

        <view class="db__grid">
          <view class="card db__stat" v-for="c in d.summaryCards" :key="c.key">
            <text class="db__stat-val">{{ c.value }}<text class="db__stat-unit">{{ c.unit }}</text></text>
            <text class="db__stat-label">{{ c.label }}</text>
          </view>
        </view>

        <template v-if="d.moduleCards && d.moduleCards.length">
          <view class="section-head"><text class="section-head__title">业务模块状态</text></view>
          <view class="list-group">
            <view v-for="m in d.moduleCards" :key="m.key" class="list-row">
              <text class="flex-1 t-md">{{ m.label }}</text>
              <MobileStatusTag :label="m.empty ? (m.emptyHint || '待上线') : '运行中'" :type="m.empty ? 'default' : 'success'" />
            </view>
          </view>
        </template>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'

export default {
  data() { return { d: null, state: 'loading' } },
  onLoad() { this.load() },
  methods: {
    load() {
      this.state = 'loading'
      teacherApi.getDashboard().then((d) => { this.d = d; this.state = 'ready' })
        .catch(() => { this.state = 'error' })
    }
  }
}
</script>

<style scoped>
.db__grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-2); }
.db__stat { display: flex; flex-direction: column; align-items: center; gap: 4px; padding: var(--space-3) var(--space-2); }
.db__stat-val { font-size: var(--font-size-metric-sm); font-weight: var(--font-weight-semibold); color: var(--teacher-700); }
.db__stat-unit { font-size: var(--font-size-xs); color: var(--text-tertiary); margin-left: 2px; }
.db__stat-label { font-size: var(--font-size-xs); color: var(--text-tertiary); text-align: center; }
</style>
