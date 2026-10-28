<template>
  <view class="task-icon" :class="['task-icon--' + tone, { 'task-icon--plain': plain }]" aria-hidden="true">
    <image class="task-icon__image" :src="source" mode="aspectFit" alt="" />
  </view>
</template>

<script>
const NAMES = ['file-text', 'folder', 'calendar', 'map-pin', 'user', 'message-dots', 'layout-grid', 'clipboard-check', 'shield-exclamation', 'check', 'alert-circle', 'chevron-right']
const TONES = ['blue', 'teal', 'amber', 'gray', 'white']
export default {
  props: { name: { type: String, default: 'file-text' }, tone: { type: String, default: 'blue' }, plain: Boolean },
  computed: {
    source() { return '/static/internship-icons/' + (NAMES.includes(this.name) ? this.name : 'file-text') + '-' + (TONES.includes(this.tone) ? this.tone : 'blue') + '.svg' }
  }
}
</script>

<style scoped>
.task-icon{display:inline-flex;align-items:center;justify-content:center;width:44px;height:44px;border-radius:var(--radius-lg);flex-shrink:0;background:var(--primary-50)}
.task-icon--teal{background:var(--teacher-50)}.task-icon--amber{background:var(--warning-50)}.task-icon--gray{background:var(--gray-100)}.task-icon--white,.task-icon--plain{background:transparent}
.task-icon__image{display:block;width:24px;height:24px}.task-icon--plain{width:24px;height:24px}
</style>
