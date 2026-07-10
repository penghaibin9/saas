<template>
  <GraduationFormPageShell
    :ctx="ctx"
    :title="detail ? detail.title : '课题详情'"
    subtitle="已入池课题 · 容量 / 已选学生"
    back-to="/admin/graduation/topics"
  >
    <LoadingState v-if="loading" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <template v-else-if="detail">
      <div class="gb-kv"><span>指导教师</span><span>{{ detail.advisorName || '—' }}</span></div>
      <div class="gb-kv"><span>容量</span><span>{{ detail.selected }}/{{ detail.capacity }}</span></div>
      <div class="gb-sec">
        <p class="ie-hint">已选学生</p>
        <EmptyState v-if="!assigned.length" title="暂无" />
        <ul v-else class="gb-trail">
          <li v-for="s in assigned" :key="s.id" class="gb-trail__item">
            <span>{{ s.name }}（{{ s.studentNo }}）</span>
          </li>
        </ul>
      </div>
    </template>
    <template v-if="detail && canEdit" #footer>
      <button type="button" class="mp-btn mp-btn--primary" @click="goEdit">编辑课题</button>
      <button type="button" class="mp-btn" @click="$router.push('/admin/graduation/students?panel=topic')">分配学生</button>
    </template>
  </GraduationFormPageShell>
</template>

<script>
import GraduationFormPageShell from './_shared/GraduationFormPageShell.vue'
import { LoadingState, ErrorState, EmptyState } from '@/components/business'
import { gdTopicApi } from '@/modules/graduation/api/graduation-topic.api'

export default {
  name: 'TopicManageDetailView',
  components: { GraduationFormPageShell, LoadingState, ErrorState, EmptyState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return { loading: true, error: '', detail: null, assigned: [] }
  },
  computed: {
    canEdit() {
      if (!this.detail) return false
      const row = this.detail
      return row.status !== 'ARCHIVED' && row.reviewStatus !== 'PENDING_REVIEW' && !(row.selected > 0 && row.reviewStatus === 'APPROVED')
    }
  },
  created() { this.load() },
  methods: {
    async load() {
      this.loading = true
      this.error = ''
      const id = this.$route.params.id
      const d = await gdTopicApi.getTopicDetail(id)
      if (d.code !== 0) { this.error = d.message; this.loading = false; return }
      this.detail = d.data
      const a = await gdTopicApi.getAssignedStudents(id)
      this.assigned = a.code === 0 ? (a.data || []) : []
      this.loading = false
    },
    goEdit() {
      this.$router.push(`/admin/graduation/topics/${this.detail.id}/edit`)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.gb-kv { display: flex; justify-content: space-between; padding: var(--space-2) 0; border-bottom: 1px solid var(--color-border-subtle); }
.gb-sec { margin-top: var(--space-4); }
.gb-trail { list-style: none; padding: 0; margin: 0; }
.gb-trail__item { padding: var(--space-2) 0; border-bottom: 1px solid var(--color-border-subtle); }
.mp-btn { padding: 7px 16px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; background: #fff; cursor: pointer; font-size: 13px; margin-left: var(--space-2); }
.mp-btn--primary { background: var(--pri, #2563eb); color: #fff; border-color: var(--pri, #2563eb); }
</style>
