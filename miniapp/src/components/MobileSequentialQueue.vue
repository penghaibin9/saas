<template>
  <TeacherMobileSequentialQueue
    :title="title"
    :items="items"
    :current-index="currentIndex"
    :loading="loading"
    :action-label="actionLabel"
    :allow-manual-next="allowManualNext"
    :conflict="conflict"
    @open="forwardOpen"
    @action="forwardAction"
    @next="forwardNext"
  >
    <template #default="{ item, index, blocked }">
      <slot :item="item" :index="index" :blocked="blocked" />
    </template>
  </TeacherMobileSequentialQueue>
</template>

<script>
import TeacherMobileSequentialQueue from './teacher/MobileSequentialQueue.vue'

export default {
  name: 'MobileSequentialQueueCompat',
  components: { TeacherMobileSequentialQueue },
  props: {
    title: { type: String, default: '连续处理' },
    items: { type: Array, default: () => [] },
    currentIndex: { type: Number, default: 0 },
    loading: { type: Boolean, default: false },
    actionLabel: { type: String, default: '' },
    allowManualNext: { type: Boolean, default: false },
    conflict: { type: Boolean, default: false }
  },
  emits: ['open', 'action', 'next'],
  methods: {
    forwardOpen(item) {
      this.$emit('open', item)
    },
    forwardAction(item, meta) {
      this.$emit('action', item, meta)
    },
    forwardNext() {
      this.$emit('next')
    }
  }
}
</script>
