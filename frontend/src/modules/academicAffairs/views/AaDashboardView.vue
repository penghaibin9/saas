<template>
  <AaTeacherTodayView v-if="isAcademicTeacher" :ctx="ctx" />
  <AaLeadershipWallView v-else-if="$route.query.wall === '1'" :ctx="ctx" />
  <AaOverviewWorkspace v-else-if="activePanel === 'todos'" key="todos" :ctx="ctx" mode="todos" />
  <AaAcademicProgressWorkspace v-else-if="activePanel === 'academicProgress'" :ctx="ctx" />
  <AaTodayTeachingWorkspace v-else-if="activePanel === 'todayTeaching'" :ctx="ctx" />
  <AaDashboardPanelWorkspace v-else-if="activePanel" :key="activePanel" :panel="activePanel" :ctx="ctx" />
  <AaOverviewWorkspace v-else :ctx="ctx" />
</template>

<script>
import { defineAsyncComponent } from 'vue'
import { dashboardPanel } from '../config/dashboardPanels'
export default {
  name: 'AaDashboardView',
  components: {
    AaTeacherTodayView: defineAsyncComponent(() => import('./AaTeacherTodayView.vue')),
    AaLeadershipWallView: defineAsyncComponent(() => import('./AaLeadershipWallView.vue')),
    AaDashboardPanelWorkspace: defineAsyncComponent(() => import('../components/AaDashboardPanelWorkspace.vue')),
    AaOverviewWorkspace: defineAsyncComponent(() => import('../components/AaOverviewWorkspace.vue')),
    AaAcademicProgressWorkspace: defineAsyncComponent(() => import('../components/AaAcademicProgressWorkspace.vue')),
    AaTodayTeachingWorkspace: defineAsyncComponent(() => import('../components/AaTodayTeachingWorkspace.vue'))
  },
  props: { ctx: { type: Object, required: true } },
  computed: {
    isAcademicTeacher() {
      return String(this.ctx?.currentRole?.roleCode || this.ctx?.currentRole?.roleType || '').toUpperCase() === 'ACADEMIC_TEACHER'
    },
    activePanel() { return dashboardPanel(this.$route.query.panel) }
  }
}
</script>
