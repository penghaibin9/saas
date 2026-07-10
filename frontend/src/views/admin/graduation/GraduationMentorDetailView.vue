<template>
  <GraduationFormPageShell
    :ctx="ctx"
    :title="detail ? detail.teacherName : '导师详情'"
    subtitle="资格状态 / 工作量 / 在指导学生 / 操作记录"
    back-to="/admin/graduation/mentors"
  >
    <LoadingState v-if="loading" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <template v-else-if="detail">
      <div class="gm-detail-kv"><span>资格状态</span><StatusTag :type="detail.qualificationTone" :label="detail.qualificationLabel" dot /></div>
      <div class="gm-detail-kv"><span>工作量</span><span>{{ detail.capacityText }}</span></div>
      <div class="gm-detail-kv"><span>指导方向</span><span>{{ detail.researchDirection || '—' }}</span></div>
      <div class="gm-detail-kv"><span>联系电话</span><span>{{ detail.phone || '—' }}</span></div>
      <div v-if="detail.reviewComment" class="gm-detail-kv"><span>审核意见</span><span>{{ detail.reviewComment }}</span></div>
      <div v-if="detail.latestEval" class="gm-detail-kv"><span>最新评价</span><span>{{ detail.latestEval.level }} · {{ detail.latestEval.score }}分（{{ detail.latestEval.evaluatedBy }}）</span></div>
      <div class="gm-section-title" style="margin-top: var(--space-3)">在指导学生</div>
      <EmptyState v-if="!detail.students.length" title="暂无在指导学生" />
      <ul v-else class="gm-stu-list">
        <li v-for="s in detail.students" :key="s.id">{{ s.name }}（{{ s.studentNo }}）· {{ s.topicTitle || '未确认选题' }}</li>
      </ul>
      <div class="gm-section-title" style="margin-top: var(--space-3)">操作记录</div>
      <AppAuditTrail :records="mentorAuditRecords" compact :show-ip="false" />
    </template>
    <template v-if="detail && detail.qualificationStatus !== 'ARCHIVED'" #footer>
      <button type="button" class="mp-btn mp-btn--primary" @click="goEdit">编辑导师</button>
      <button v-if="detail.qualificationStatus === 'QUALIFIED'" type="button" class="mp-btn" @click="goEval">导师评价</button>
    </template>
  </GraduationFormPageShell>
</template>

<script>
import GraduationFormPageShell from './_shared/GraduationFormPageShell.vue'
import { LoadingState, ErrorState, EmptyState, StatusTag } from '@/components/business'
import { AppAuditTrail } from '@/components/common'
import { graduationMentorApi } from '@/modules/graduation/api/graduation-mentor.api'

export default {
  name: 'GraduationMentorDetailView',
  components: { GraduationFormPageShell, LoadingState, ErrorState, EmptyState, StatusTag, AppAuditTrail },
  props: { ctx: { type: Object, required: true } },
  data() {
    return { loading: true, error: '', detail: null }
  },
  computed: {
    mentorAuditRecords() {
      return (this.detail?.auditTrail || []).map((a, i) => ({
        id: i, action: a.action, actor: a.operator, at: a.occurredAt
      }))
    }
  },
  created() { this.load() },
  methods: {
    async load() {
      this.loading = true
      this.error = ''
      const res = await graduationMentorApi.getMentorDetail(this.$route.params.id)
      if (res.code !== 0) { this.error = res.message; this.loading = false; return }
      this.detail = res.data
      this.loading = false
    },
    goEdit() {
      this.$router.push(`/admin/graduation/mentors/${this.detail.id}/edit`)
    },
    goEval() {
      this.$router.push(`/admin/graduation/mentors/${this.detail.id}/eval`)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.gm-detail-kv { display: flex; justify-content: space-between; gap: var(--space-3); padding: 6px 0; border-bottom: 1px dashed var(--line, #eef1f6); font-size: 13px; }
.gm-section-title { font-size: 13px; font-weight: 600; color: var(--t1, #1e293b); margin-bottom: var(--space-2); }
.gm-stu-list { margin: 0; padding-left: 18px; font-size: 13px; }
.gm-stu-list li { padding: 4px 0; }
.mp-btn { padding: 7px 16px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; background: #fff; cursor: pointer; font-size: 13px; margin-left: var(--space-2); }
.mp-btn--primary { background: var(--pri, #2563eb); color: #fff; border-color: var(--pri, #2563eb); }
</style>
