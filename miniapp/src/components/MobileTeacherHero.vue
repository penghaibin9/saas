<template>
  <view class="teacher-hero" :style="{ paddingTop: top + 'px' }">
    <image class="teacher-hero__art" src="/static/teacher-shell/campus-header.jpg" mode="aspectFill" />
    <view class="teacher-hero__content">
      <view class="teacher-hero__heading">
        <text class="teacher-hero__title">{{ title }}</text>
        <button v-if="showIdentity" class="teacher-hero__identity" @click="switchIdentity">
          <text>{{ roleLabel || '选择身份' }}</text><MobileShellIcon name="chevron-right" tone="gray" :size="14" class="teacher-hero__chevron" />
        </button>
      </view>
      <text v-if="subtitle" class="teacher-hero__subtitle">{{ subtitle }}</text>
      <view v-if="primaryText" class="teacher-hero__summary">
        <text class="teacher-hero__primary">{{ primaryText }}</text>
        <text v-if="secondaryText" class="teacher-hero__secondary">{{ secondaryText }}</text>
      </view>
    </view>
  </view>
</template>
<script>
import { getStatusBarHeight } from '@/utils/deviceInfo'
import { go } from '@/utils/nav'
export default {
  props: {
    title: String, subtitle: String, roleLabel: String,
    primaryText: { type: String, default: '' }, secondaryText: { type: String, default: '' },
    showIdentity: { type: Boolean, default: true }
  },
  data: () => ({ top: 68 }),
  mounted() {
    // App content sits below the native capsule; never draw a second WeChat capsule.
    let capsuleBottom = 0
    try { capsuleBottom = uni.getMenuButtonBoundingClientRect?.().bottom || 0 } catch (_) { /* H5 has no capsule. */ }
    this.top = Math.max(getStatusBarHeight() + 44, capsuleBottom + 12)
    // #ifdef H5
    this.top = 28
    // #endif
  },
  methods: { switchIdentity() { go('/pages/role-switch/index') } }
}
</script>
<style scoped>
.teacher-hero { position: relative; padding: 68px 20px 20px; overflow: hidden; background: linear-gradient(0deg, #fff 0%, rgba(255,255,255,0) 75%), linear-gradient(110deg, #ffe9e7 0%, #eee8ff 48%, #dff5fc 100%); }
.teacher-hero__art { position: absolute; top: 0; left: 0; z-index: 0; display: block; width: 100%; height: 100%; pointer-events: none; }
.teacher-hero__content { position: relative; z-index: 1; }
.teacher-hero__heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.teacher-hero__title { font-size: 28px; font-weight: 700; line-height: 1.35; color: #142440; flex-shrink: 0; }
.teacher-hero__identity { display: flex; align-items: center; justify-content: center; gap: 5px; max-width: 52%; min-height: 36px; margin: 0; padding: 5px 12px; background: rgba(255,255,255,.84); border-radius: 24px; font-size: 13px; line-height: 1.5; color: #294266; text-align: left; }
.teacher-hero__chevron { transform: rotate(90deg); }
.teacher-hero__subtitle { display: block; margin-top: 5px; font-size: 13px; line-height: 1.6; color: #64748b; }
.teacher-hero__summary { padding-top: 24px; }
.teacher-hero__primary { display: block; font-size: 21px; font-weight: 600; line-height: 1.5; color: #142440; }
.teacher-hero__secondary { display: block; margin-top: 5px; font-size: 13px; line-height: 1.65; color: #62738e; }
</style>
