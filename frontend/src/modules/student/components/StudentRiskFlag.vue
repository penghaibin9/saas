<template>
  <span class="stu-risk-flags">
    <AppBadge v-for="f in flags" :key="f" :type="badgeOf(f)">{{ labelOf(f) }}</AppBadge>
    <span v-if="!flags.length" class="stu-risk-flags__none">无风险</span>
  </span>
</template>

<script>
/** StudentRiskFlag — 学生风险标记（学业预警/资料缺失/证件过期/需复核/账号未绑定） */
import { AppBadge } from '@/components/ui'
import { formatRiskFlag } from '../helpers/student-format.helper'
import { riskFlagBadge } from '../rules/student.rules'

export default {
  name: 'StudentRiskFlag',
  components: { AppBadge },
  props: { flags: { type: Array, default: () => [] } },
  methods: {
    labelOf: formatRiskFlag,
    badgeOf: riskFlagBadge
  }
}
</script>

<style scoped>
.stu-risk-flags { display: inline-flex; gap: var(--space-1); flex-wrap: wrap; }
.stu-risk-flags__none { font-size: var(--font-size-xs); color: var(--text-tertiary); }
</style>
