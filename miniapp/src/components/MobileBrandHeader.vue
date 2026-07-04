<template>
  <view class="mbh" :class="{ 'is-center': center }">
    <view class="mbh__logo" :class="`is-${side}`">
      <image v-if="brand.logo" :src="brand.logo" class="mbh__logo-img" mode="aspectFit" />
      <text v-else>{{ logoText }}</text>
    </view>
    <view class="mbh__text">
      <text class="mbh__platform">{{ brand.platformName }}</text>
      <text class="mbh__school">{{ brand.schoolName }}</text>
    </view>
  </view>
</template>

<script>
/** MobileBrandHeader 品牌头（校名/Logo 全部来自 tenantBrandConfig，不硬编码） */
import { tenantBrandConfig } from '@/config'
export default {
  name: 'MobileBrandHeader',
  props: {
    center: { type: Boolean, default: false },
    side: { type: String, default: 'student' }
  },
  data() {
    return { brand: tenantBrandConfig }
  },
  computed: {
    logoText() {
      return (this.brand.schoolShortName || this.brand.schoolName || '校').slice(0, 1)
    }
  }
}
</script>

<style scoped>
.mbh { display: flex; align-items: center; gap: var(--space-3); }
.mbh.is-center { flex-direction: column; text-align: center; gap: var(--space-2); }
.mbh__logo {
  width: 48px; height: 48px; border-radius: var(--radius-md);
  display: flex; align-items: center; justify-content: center;
  font-size: var(--font-size-2xl); font-weight: var(--font-weight-semibold); color: #fff;
}
.mbh__logo.is-student { background: var(--brand-gradient); }
.mbh__logo.is-teacher { background: var(--brand-gradient-teacher); }
.mbh__logo-img { width: 48px; height: 48px; }
.mbh__text { display: flex; flex-direction: column; }
.mbh__platform { font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.mbh__school { font-size: var(--font-size-sm); color: var(--text-secondary); }
</style>
