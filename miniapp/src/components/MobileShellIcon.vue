<template>
  <view class="shell-icon" :class="{ 'shell-icon--round': round }" :style="{ backgroundColor: round ? backgrounds[tone] || backgrounds.blue : 'transparent', width: (round ? size + 22 : size) + 'px', height: (round ? size + 22 : size) + 'px' }" aria-hidden="true">
    <image :src="shellIcon(name, tone)" :style="{ width: size + 'px', height: size + 'px' }" mode="aspectFit" alt="" />
  </view>
</template>
<script>
import { shellIcon } from './student-shell-icons.mjs'
export default {
  props: { name: { type: String, default: 'file-text' }, tone: { type: String, default: 'blue' }, size: { type: Number, default: 24 }, round: Boolean },
  data: () => ({ backgrounds: { blue: '#eaf3ff', teal: '#e4f8f3', green: '#e6f8f2', cyan: '#e5f8fb', amber: '#fff5dc', violet: '#f0eaff', red: '#ffeded', gray: '#f1f3f7' } }),
  methods: { shellIcon }
}
</script>
<style scoped>
.shell-icon { display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0; vertical-align: middle; }
.shell-icon--round { border-radius: 50%; }
</style>
