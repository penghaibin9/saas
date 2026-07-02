<template>
  <AppRiskAlertCard
    :title="risk.riskTitle || risk.title"
    :level="risk.riskLevel || risk.level"
    :rule="risk.reason || risk.rule"
    :count="risk.affectedCount"
    :owner="risk.ownerTeacher || risk.responsibleTeacher"
    :status="statusCode"
    :status-label="statusLabel"
    @handle="$emit('handle')"
  />
</template>

<script>
import AppRiskAlertCard from './AppRiskAlertCard.vue'
import { riskStatusCode, riskStatusLabel } from './presentation.js'

export default {
  name: 'RiskAlertCard',
  components: { AppRiskAlertCard },
  props: {
    risk: { type: Object, required: true }
  },
  emits: ['handle'],
  computed: {
    statusCode() {
      return riskStatusCode(this.risk.status)
    },
    statusLabel() {
      return riskStatusLabel(this.risk)
    }
  }
}
</script>
