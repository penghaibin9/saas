<template>
  <AppHandleDrawer
    :visible="visible"
    :title="title"
    :payload="payload"
    @update:visible="$emit('update:visible', $event)"
    @contact="$emit('contact')"
    @remind="$emit('remind')"
    @follow="$emit('follow')"
    @resolve="$emit('resolve')"
  />
</template>

<script>
import AppHandleDrawer from './AppHandleDrawer.vue'

/** @deprecated 使用 RiskHandleDrawer */
export default {
  name: 'RiskHandleDrawer',
  components: { AppHandleDrawer },
  props: {
    visible: { type: Boolean, default: false },
    title: { type: String, default: '风险处理' },
    payload: { type: Object, default: null }
  },
  emits: ['update:visible', 'contact', 'remind', 'follow', 'resolve']
}
</script>
