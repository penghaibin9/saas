<template>
  <PlatformCapabilityView :ctx="ctx" capability-key="plt-api-access" />
</template>

<script>
/** A5：API/密钥/Webhook 未形成统一真实服务合同前 fail-closed，禁止旧浏览器凭证/日志/Webhook 假事实。 */
import PlatformCapabilityView from '@/modules/platform/views/PlatformCapabilityView.vue'

export default {
  name: 'PlatformApiAccessView',
  components: { PlatformCapabilityView },
  props: { ctx: { type: Object, required: true } }
}
</script>
