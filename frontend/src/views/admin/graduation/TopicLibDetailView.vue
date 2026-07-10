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
      <div class="gb-kv"><span>来源</span><span>{{ detail.sourceLabel }}</span></div>
      <div class="gb-kv"><span>分类</span><span>{{ detail.category || '未分类' }}</span></div>
      <div class="gb-kv"><span>指导教师</span><span>{{ detail.advisorName || '—' }}</span></div>
      <div class="gb-kv"><span>审核</span><span>{{ detail.reviewLabel }} / {{ detail.statusLabel }}</span></div>
      <div class="gb-kv"><span>容量</span><span>{{ detail.selected }}/{{ detail.capacity }}（余 {{ detail.remaining }}）</span></div>
      <div v-if="detail.requirements" class="gb-sec"><p class="ie-hint">题目要求</p><p>{{ detail.requirements }}</p></div>
      <div v-if="detail.outcome" class="gb-sec"><p class="ie-hint">预期成果</p><p>{{ detail.outcome }}</p></div>
      <div v-if="detail.attachments && detail.attachments.length" class="gb-sec">
        <p class="ie-hint">附件（{{ detail.attachments.length }}）</p>
        <ul class="gb-trail">
          <li v-for="(a, i) in detail.attachments" :key="i" class="gb-trail__item">
            <span>{{ a.name || '未命名' }}</span>
            <span class="gb-trail__meta">{{ a.url || '—' }}</span>
          </li>
        </ul>
      </div>
      <div class="gb-sec">
        <p class="ie-hint">已选学生（{{ assigned.length }}）</p>
        <EmptyState v-if="!assigned.length" title="暂无学生" />
        <ul v-else class="gb-trail">
          <li v-for="s in assigned" :key="s.id" class="gb-trail__item">
            <span>{{ s.name }}（{{ s.studentNo }}）</span>
            <span class="gb-trail__meta">{{ s.className || '—' }}</span>
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
.gb-kv { display: flex; justify-content: space-between; padding: var(--space-2) 0; border-bottom: 1px solid var(--color-border-subtle); }
.gb-sec { margin-top: var(--space-4); }
.gb-trail { list-style: none; padding: 0; margin: 0; }
.gb-trail__item { display: flex; justify-content: space-between; padding: var(--space-2) 0; border-bottom: 1px solid var(--color-border-subtle); }
.gb-trail__meta { color: var(--color-text-secondary); font-size: var(--font-size-sm); }
.mp-btn { padding: 7px 16px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; background: #fff; cursor: pointer; font-size: 13px; }
.mp-btn--primary { background: var(--pri, #2563eb); color: #fff; border-color: var(--pri, #2563eb); }
</style>
