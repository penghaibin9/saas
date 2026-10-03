<template>
  <AppGlobalState state="empty" :title="title" :description="description" @back="$emit('back')">
    <template v-if="$slots.actions" #actions><slot name="actions" /></template>
  </AppGlobalState>
</template>

<script>
/** EmptyState — 空数据状态（AppGlobalState 的语义化别名，供各业务模块统一引用）。 */
import { AppGlobalState } from '@/components/common'

export default {
  name: 'EmptyState',
  components: { AppGlobalState },
  props: {
    title: { type: String, default: '' },
    description: { type: String, default: '' }
  },
  emits: ['back']
}
</script>
