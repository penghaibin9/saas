<template>
  <GraduationFormPageShell
    layout="inline"
    :ctx="ctx"
    :title="detail ? detail.title : '题目详情'"
    subtitle="题目库详情 · 来源 / 审核 / 容量 / 已选学生"
    :back-to="backTo"
  >
    <LoadingState v-if="loading" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <template v-else-if="detail">
      <div class="mp-kv"><span class="mp-kv__k">来源</span><span class="mp-kv__v">{{ detail.sourceLabel }}</span></div>
      <div class="mp-kv"><span class="mp-kv__k">分类</span><span class="mp-kv__v">{{ detail.category || '未分类' }}</span></div>
      <div class="mp-kv"><span class="mp-kv__k">指导教师</span><span class="mp-kv__v">{{ detail.advisorName || '—' }}</span></div>
      <div class="mp-kv"><span class="mp-kv__k">审核</span><span class="mp-kv__v">{{ detail.reviewLabel }} / {{ detail.statusLabel }}</span></div>
      <div class="mp-kv"><span class="mp-kv__k">容量</span><span class="mp-kv__v">{{ detail.selected }}/{{ detail.capacity }}（余 {{ detail.remaining }}）</span></div>
      <div v-if="detail.requirements" class="detail-block"><p class="ie-hint">题目要求</p><p class="detail-text">{{ detail.requirements }}</p></div>
      <div v-if="detail.outcome" class="detail-block"><p class="ie-hint">预期成果</p><p class="detail-text">{{ detail.outcome }}</p></div>
      <div v-if="detail.attachments && detail.attachments.length" class="detail-block">
        <p class="ie-hint">附件（{{ detail.attachments.length }}）</p>
        <ul class="detail-list">
          <li v-for="(a, i) in detail.attachments" :key="i" class="detail-list__item">
            <span>{{ a.name || '未命名' }}</span>
            <span class="detail-list__meta">{{ a.url || '—' }}</span>
          </li>
        </ul>
      </div>
      <div class="detail-block">
        <p class="ie-hint">已选学生（{{ assigned.length }}）</p>
        <EmptyState v-if="!assigned.length" title="暂无学生" />
        <ul v-else class="detail-list">
          <li v-for="s in assigned" :key="s.id" class="detail-list__item">
            <span>{{ s.name }}（{{ s.studentNo }}）</span>
            <span class="detail-list__meta">{{ s.className || '—' }}</span>
          </li>
        </ul>
      </div>
    </template>
    <template v-if="detail && canEdit" #footer>
      <button type="button" class="mp-btn mp-btn--primary" @click="goEdit">编辑题目</button>
    </template>
  </GraduationFormPageShell>
</template>

<script>
import GraduationFormPageShell from './_shared/GraduationFormPageShell.vue'
import { LoadingState, ErrorState, EmptyState } from '@/components/business'
import { gdTopicApi } from '@/modules/graduation/api/graduation-topic.api'

export default {
  name: 'TopicLibDetailView',
  components: { GraduationFormPageShell, LoadingState, ErrorState, EmptyState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return { loading: true, error: '', detail: null, assigned: [] }
  },
  computed: {
    backTo() {
      const panel = this.$route.query.returnPanel || 'list'
      return `/admin/graduation/topic-lib?panel=${panel}`
    },
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
      const panel = this.$route.query.returnPanel || 'list'
      this.$router.push({ path: `/admin/graduation/topic-lib/${this.detail.id}/edit`, query: { returnPanel: panel } })
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.detail-block { margin-top: var(--space-4); }
.detail-text { margin: var(--space-1) 0 0; font-size: 13px; color: var(--text-secondary, #475569); line-height: 1.6; white-space: pre-wrap; }
.detail-list { list-style: none; padding: 0; margin: var(--space-1) 0 0; }
.detail-list__item { display: flex; justify-content: space-between; gap: var(--space-3); padding: var(--space-2) 0; border-bottom: 1px solid var(--dv, #eef1f6); }
.detail-list__meta { color: var(--text-secondary, #6b7280); font-size: 12px; }
</style>
