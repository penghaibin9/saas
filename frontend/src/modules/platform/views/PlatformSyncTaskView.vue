<template>
  <PlatformCapabilityView :ctx="ctx" capability-key="plt-operations" />
</template>

<script>
/** A5：同步任务/运行日志未形成统一真实任务合同前仅展示治理边界，禁止 mock 重试、暂停、导出和假审计。 */
import PlatformCapabilityView from '@/modules/platform/views/PlatformCapabilityView.vue'

export default {
  name: 'PlatformSyncTaskView',
  components: { PlatformCapabilityView },
  props: { ctx: { type: Object, required: true } }
}
</script>
