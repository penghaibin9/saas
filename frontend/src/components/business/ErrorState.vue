<template>
  <AppGlobalState
    state="error"
    :title="title"
    :description="description"
    :error-code="errorCode"
    @retry="$emit('retry')"
    @back="$emit('back')"
  />
</template>

<script>
/** ErrorState — 加载异常状态（AppGlobalState 的语义化别名）。 */
import { AppGlobalState } from '@/components/common'

export default {
  name: 'ErrorState',
  components: { AppGlobalState },
  props: {
    title: { type: String, default: '' },
    description: { type: String, default: '' },
    errorCode: { type: String, default: '' }
  },
  emits: ['retry', 'back']
}
</script>
