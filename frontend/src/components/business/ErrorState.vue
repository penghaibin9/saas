<template>
  <AppGlobalState
    state="error"
    :title="title"
    :description="safeError.userMessage"
    :error-code="errorCode || safeError.supportCode"
    @retry="$emit('retry')"
    @back="$emit('back')"
  />
</template>

<script>
/** ErrorState — 加载异常状态（AppGlobalState 的语义化别名）。 */
import { AppGlobalState } from '@/components/common'
import { normalizeUiError } from '@/utils/presentationSafety'

export default {
  name: 'ErrorState',
  components: { AppGlobalState },
  props: {
    title: { type: String, default: '' },
    description: { type: String, default: '' },
    errorCode: { type: String, default: '' }
  },
  computed: {
    safeError() {
      return normalizeUiError(this.description, { fallback: '页面暂时无法加载，请稍后重试' })
    }
  },
  emits: ['retry', 'back']
}
</script>
