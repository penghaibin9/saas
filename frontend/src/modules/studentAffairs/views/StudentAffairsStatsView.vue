<template>
  <StudentAffairsCockpitView />
</template>

<script>
/**
 * 兼容旧“学工统计”路由。统计事实统一来自 /stats/cockpit，
 * 禁止在浏览器按单页数据二次聚合或把接口失败解释为 0。
 */
import StudentAffairsCockpitView from './StudentAffairsCockpitView.vue'

export default {
  name: 'StudentAffairsStatsView',
  components: { StudentAffairsCockpitView }
}
</script>
