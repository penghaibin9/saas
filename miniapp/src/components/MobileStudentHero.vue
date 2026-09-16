<template>
  <view class="student-hero" :style="{ paddingTop: top + 'px' }">
    <image class="student-hero__art" src="/static/student-shell/campus-header.png" mode="aspectFill" />
    <view class="student-hero__content">
      <text class="student-hero__title">{{ title }}</text>
      <text v-if="subtitle" class="student-hero__subtitle">{{ subtitle }}</text>
      <slot />
    </view>
  </view>
</template>
<script>
import { getStatusBarHeight } from '@/utils/deviceInfo'
export default {
  props: { title: String, subtitle: String },
  data: () => ({ top: 20 }),
  mounted() {
    // Native capsule owns the top-right navigation row. Content starts below it.
    this.top = getStatusBarHeight() + 48
    // #ifdef H5
    this.top = 28
    // #endif
  }
}
</script>
<style scoped>
.student-hero { position: relative; overflow: hidden; padding: 68px 20px 24px; background: #287cf0; color: #fff; }
.student-hero__art { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; }
.student-hero__content { position: relative; }
.student-hero__title { display: block; font-size: 28px; font-weight: 700; line-height: 1.3; letter-spacing: .5px; }
.student-hero__subtitle { display: block; font-size: 14px; line-height: 1.6; margin-top: 6px; color: #fff; }
</style>
