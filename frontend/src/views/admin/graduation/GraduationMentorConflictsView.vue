<template>
  <GraduationFormPageShell
    :ctx="ctx"
    title="分配冲突自动检测"
    subtitle="导师超容量 / 无导师学生 / 非认证导师"
    back-to="/admin/graduation/mentors"
  >
    <LoadingState v-if="loading" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <template v-else-if="conflicts">
      <div class="gm-assign-hint">共检出 <b>{{ conflicts.total }}</b> 项分配冲突，请及时处理。</div>
      <div class="gm-section-title" style="margin-top: var(--space-3)">导师超容量（{{ conflicts.overCapacity.length }}）</div>
      <EmptyState v-if="!conflicts.overCapacity.length" title="无超容量导师" />
      <ul v-else class="gm-stu-list"><li v-for="m in conflicts.overCapacity" :key="m.mentorId">{{ m.teacherName }}：{{ m.current }}/{{ m.capacity }}</li></ul>
      <div class="gm-section-title" style="margin-top: var(--space-3)">进入指导阶段却无导师（{{ conflicts.advancedNoMentor.length }}）</div>
      <EmptyState v-if="!conflicts.advancedNoMentor.length" title="无此类学生" />
      <ul v-else class="gm-stu-list"><li v-for="s in conflicts.advancedNoMentor" :key="s.gdStudentId">{{ s.name }}（{{ s.className }}）· {{ s.stage }}</li></ul>
      <div class="gm-section-title" style="margin-top: var(--space-3)">学生导师非「已认证」（{{ conflicts.unqualifiedMentor.length }}）</div>
      <EmptyState v-if="!conflicts.unqualifiedMentor.length" title="无此类学生" />
      <ul v-else class="gm-stu-list"><li v-for="s in conflicts.unqualifiedMentor" :key="s.gdStudentId">{{ s.name }} → {{ s.mentorName }}（{{ s.mentorStatus }}）</li></ul>
    </template>
    <template #footer>
      <button type="button" class="mp-btn" @click="$router.push('/admin/graduation/mentors')">返回导师列表</button>
    </template>
  </GraduationFormPageShell>
</template>

<script>
import GraduationFormPageShell from './_shared/GraduationFormPageShell.vue'
import { LoadingState, ErrorState, EmptyState } from '@/components/business'
import { graduationMentorApi } from '@/modules/graduation/api/graduation-mentor.api'

export default {
  name: 'GraduationMentorConflictsView',
  components: { GraduationFormPageShell, LoadingState, ErrorState, EmptyState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return { loading: true, error: '', conflicts: null }
  },
  created() { this.load() },
  methods: {
    async load() {
      this.loading = true
      this.error = ''
      const res = await graduationMentorApi.getConflicts()
      if (res.code !== 0) { this.error = res.message; this.loading = false; return }
      this.conflicts = res.data
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.gm-assign-hint { font-size: 12px; color: var(--t3, #64748b); }
.gm-section-title { font-size: 13px; font-weight: 600; margin-bottom: var(--space-2); }
.gm-stu-list { margin: 0; padding-left: 18px; font-size: 13px; }
.gm-stu-list li { padding: 4px 0; }
.mp-btn { padding: 7px 16px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; background: #fff; cursor: pointer; font-size: 13px; }
</style>
