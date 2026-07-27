<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="答辩安排" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="d">
        <MobileGlobalState v-if="!d.hasData || !d.assigned" state="empty" title="答辩分组尚未安排" description="学院编排答辩分组后会显示在这里。" />
        <template v-else>
          <view class="card df__hero">
            <view class="row-between">
              <text class="card-title">{{ d.groupName }}</text>
              <MobileStatusTag :label="d.published ? '已发布' : '编制中'" :type="d.published ? 'success' : 'warning'" />
            </view>
            <text v-if="!d.published" class="df__hint">{{ d.message }}</text>
          </view>

          <template v-if="d.published">
            <view class="card df__info">
              <view class="df__row"><text class="df__k">答辩时间</text><text class="df__v">{{ d.date }}</text></view>
              <view class="df__row"><text class="df__k">答辩地点</text><text class="df__v">{{ d.location }}</text></view>
              <view class="df__row"><text class="df__k">答辩组长</text><text class="df__v">{{ d.chair || '待定' }}</text></view>
              <view class="df__row"><text class="df__k">答辩秘书</text><text class="df__v">{{ d.secretary || '待定' }}</text></view>
            </view>

            <view class="section-head"><text class="section-head__title">评委组成</text></view>
            <view class="card">
              <text v-if="(d.members || []).length" class="df__v">{{ (d.members || []).join('、') }}</text>
              <text v-else class="df__hint">评委名单待安排</text>
            </view>
          </template>
        </template>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
export default {
  data() { return { d: null, state: 'loading' } },
  onLoad() { this.load() },
  methods: {
    load() {
      this.state = 'loading'
      studentApi.getGraduationDefense().then((data) => {
        this.d = data
        this.state = 'ready'
      }).catch(() => { this.state = 'error' })
    }
  }
}
</script>

<style scoped>
.df__hint { display: block; margin-top: var(--space-2); font-size: var(--font-size-sm); color: var(--text-tertiary); }
.df__row { display: flex; align-items: center; padding: var(--space-2) 0; border-bottom: 1px solid var(--border-light); }
.df__row:last-child { border-bottom: none; }
.df__k { width: 80px; flex-shrink: 0; font-size: var(--font-size-sm); color: var(--text-tertiary); }
.df__v { font-size: var(--font-size-base); color: var(--text-primary); line-height: 1.6; }
</style>
