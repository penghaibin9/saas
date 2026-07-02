<template>
  <AppMetricCard v-bind="$attrs" @drill="$emit('drill', $event)" />
</template>

<script>
import { AppMetricCard } from '@/components/common'

export default {
  name: 'MetricCard',
  components: { AppMetricCard },
  inheritAttrs: false,
  emits: ['drill']
}
</script>
