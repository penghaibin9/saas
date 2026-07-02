<template>
  <AppBadge :type="badgeType">{{ label }}</AppBadge>
</template>

<script>
/** DataScopeTag —— 数据范围标签 */
import { AppBadge } from '@/components/ui'
import { DATA_SCOPE, DATA_SCOPE_LABELS } from '../constants/workflow.constants'

export default {
  name: 'DataScopeTag',
  components: { AppBadge },
  props: {
    scope: { type: String, required: true }
  },
  computed: {
    label() {
      return DATA_SCOPE_LABELS[this.scope] || this.scope
    },
    badgeType() {
      if (this.scope === DATA_SCOPE.ALL) return 'danger'
      if (this.scope === DATA_SCOPE.SCHOOL) return 'info'
      if (this.scope === DATA_SCOPE.SELF) return 'neutral'
      return 'success'
    }
  }
}
</script>
