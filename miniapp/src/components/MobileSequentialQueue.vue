<template>
  <component :is="queueComponent" v-bind="$attrs">
    <template #default="slotProps">
      <slot v-bind="slotProps" />
    </template>
  </component>
</template>

<script>
import TeacherMobileSequentialQueue from './teacher/MobileSequentialQueue.vue'

export default {
  name: 'MobileSequentialQueueCompat',
  inheritAttrs: false,
  computed: {
    queueComponent() {
      return TeacherMobileSequentialQueue
    }
  }
}
</script>
