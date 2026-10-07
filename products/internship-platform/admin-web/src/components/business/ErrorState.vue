<template>
  <AppGlobalState
    :state="safeError.pageState"
    :title="safeError.pageState === 'error' ? title : ''"
    :description="safeError.userMessage"
    :error-code="errorCode || safeError.supportCode"
    @retry="$emit('retry')"
    @back="goBack"
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
    description: { type: [String, Object], default: '' },
    error: { type: [String, Object], default: null },
    errorCode: { type: String, default: '' }
  },
  computed: {
    safeError() {
      return normalizeUiError(this.error || this.description, { fallback: '页面暂时无法加载，请稍后重试' })
    }
  },
  methods: {
    goBack() {
      if (this.$?.vnode?.props?.onBack) this.$emit('back')
      else if (this.$router?.options?.history?.state?.back) this.$router.back()
      else this.$router?.push('/workbench')
    }
  },
  emits: ['retry', 'back']
}
</script>
