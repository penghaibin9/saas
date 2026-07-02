<template>
  <div class="operation-log-list">
    <AppProcessRecordRow
      v-for="log in logs"
      :key="log.recordId"
      :time="log.time"
      :operator="log.operator"
      :action="log.action"
      :result="log.result"
      :closed="log.closed"
    />
  </div>
</template>

<script>
import AppProcessRecordRow from './AppProcessRecordRow.vue'

export default {
  name: 'OperationLogList',
  components: { AppProcessRecordRow },
  props: {
    logs: { type: Array, default: () => [] }
  }
}
</script>

<style scoped>
.operation-log-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
</style>
