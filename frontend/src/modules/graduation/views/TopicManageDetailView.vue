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
      <div class="mp-stack">
        <section class="mp-card">
          <header class="mp-card__head"><span class="mp-card__title">课题信息</span></header>
          <div class="mp-card__body">
            <div class="mp-kv"><span class="mp-kv__k">指导教师</span><span class="mp-kv__v">{{ detail.advisorName || '—' }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">容量</span><span class="mp-kv__v">{{ detail.selected }}/{{ detail.capacity }}</span></div>
          </div>
        </section>
        <section class="mp-card">
          <header class="mp-card__head"><span class="mp-card__title">已选学生</span></header>
          <div class="mp-card__body">
            <EmptyState v-if="!assigned.length" title="暂无" />
            <ul v-else class="assigned-list">
              <li v-for="s in assigned" :key="s.id" class="assigned-list__item">
                <span>{{ s.name }}（{{ s.studentNo }}）</span>
              </li>
            </ul>
          </div>
        </section>
      </div>
    </template>
    <template v-if="detail && (canTopicCreate || canTopicAssign)" #footer>
      <button v-if="canTopicCreate" type="button" class="mp-btn mp-btn--primary" @click="goEdit">编辑课题</button>
      <button v-if="canTopicAssign" type="button" class="mp-btn" @click="goAssign">分配学生</button>
    </template>
  </GraduationFormPageShell>
</template>

<script>
import GraduationFormPageShell from './_shared/GraduationFormPageShell.vue'
import { LoadingState, ErrorState, EmptyState } from '@/components/business'
import { gdTopicApi } from '@/modules/graduation/api/graduation-topic.api'
import { matchPermission } from '@/config/navPlan'

export default {
  name: 'TopicManageDetailView',
  components: { GraduationFormPageShell, LoadingState, ErrorState, EmptyState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return { loading: true, error: '', detail: null, assigned: [] }
  },
  computed: {
    permissionPatterns() { return Array.isArray(this.ctx?.permissionPatterns) ? this.ctx.permissionPatterns : [] },
    canTopicCreate() { return matchPermission(this.permissionPatterns, 'graduationDesign.topic.create') },
    canTopicAssign() { return matchPermission(this.permissionPatterns, 'graduationDesign.topic.assign') }
  },
  mounted() {
    this.load()
  },
  methods: {
    async load() {
      this.loading = true
      this.error = ''
      try {
        const res = await gdTopicApi.getTopicDetail(this.$route.params.id)
        if (res.code === 0) {
          this.detail = res.data
          this.assigned = res.data.assignedStudents || []
        } else {
          this.error = res.message
        }
      } catch (e) {
        this.error = e.message
      } finally {
        this.loading = false
      }
    },
    goEdit() {
      if (!this.canTopicCreate || !this.detail) return
      this.$router.push(`/admin/graduation/topics/${this.detail.id}/edit`)
    },
    goAssign() {
      if (!this.canTopicAssign) return
      this.$router.push('/admin/graduation/students?panel=topic')
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.assigned-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.assigned-list__item { padding: 8px 10px; background: var(--bg-subtle, #f8fafc); border-radius: 6px; font-size: 13px; }
</style>