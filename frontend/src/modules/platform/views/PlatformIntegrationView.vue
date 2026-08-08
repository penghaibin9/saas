<template>
  <PlatformCapabilityView :ctx="ctx" capability-key="plt-integrations" />
</template>

<script>
/** A5：真实集成服务未形成统一合同前只展示受控能力边界，禁止旧 mock CRUD/测试连接/导出假成功。 */
import PlatformCapabilityView from '@/modules/platform/views/PlatformCapabilityView.vue'

export default {
  name: 'PlatformIntegrationView',
  components: { PlatformCapabilityView },
  props: { ctx: { type: Object, required: true } }
}
</script>
