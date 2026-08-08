<template>
  <PlatformControlOverview />
</template>

<script>
/**
 * A5 / P0-07：旧 /admin/platform 首页兼容壳。
 * 正式看板统一复用 real-only PlatformControlOverview，旧 mock dashboard 不再可达。
 */
import PlatformControlOverview from '@/modules/platform/views/control/PlatformControlOverview.vue'

export default {
  name: 'PlatformDashboardView',
  components: { PlatformControlOverview },
  props: { ctx: { type: Object, required: false, default: null } }
}
</script>
