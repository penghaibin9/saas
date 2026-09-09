<template>
  <ModulePageShell
    class="aa-foundation-workspace"
    :title="detail ? `${detail.realName} · 学籍档案` : '学籍档案'"
    :subtitle="detail ? `${detail.realName} · 学号 ${detail.studentNo}` : '学籍档案详情'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="$router.push('/admin/academic-affairs/roster')">返回名册</AppButton>
    </template>

    <div class="mp-stack">
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <template v-else-if="detail">
        <AppSectionCard title="基础信息">
          <AppDescriptionList :items="baseItems" :columns="3">
            <template #currentStage><AppStatusTag :status="detail.currentStage" /></template>
          </AppDescriptionList>
        </AppSectionCard>

        <AppSectionCard title="证件与联系">
          <div class="aa-sensitive-row">
            <span class="aa-sensitive-label">身份证号</span>
            <span class="aa-mask">{{ revealed ? revealedIdCard : detail.idCardMasked || '—' }}</span>
            <button v-if="!revealed && hasPermission('academicAffairs.roster.viewSensitive')" class="mp-link" @click="revealVisible = true">查看完整</button>
            <button v-else-if="revealed" class="mp-link" @click="hideRevealed">隐藏</button>
          </div>
          <p class="mp-note">查看完整证件号需填写理由，系统将记录本次查看审计。</p>
        </AppSectionCard>

        <AppSectionCard title="学籍状态历史">
          <EmptyState v-if="!detail.statusHistory?.length" title="暂无学籍状态变更记录" description="该生尚无学籍状态变更历史。" />
          <AppTimeline v-else :items="historyItems" />
        </AppSectionCard>

        <AppSectionCard title="快捷入口">
          <div class="aa-quick-actions">
            <AppButton v-if="hasPermission('academicAffairs.statusChange.apply') && (detail.enrolled || canResume)" @click="goChange">{{ canResume ? '办理复学' : '发起学籍异动' }}</AppButton>
            <AppButton v-if="hasPermission('academicAffairs.roster.correction.view') && hasPermission('academicAffairs.roster.correction.apply')" @click="goCorrection">发起学籍信息更正</AppButton>
            <AppButton v-if="hasPermission('academicAffairs.grade.view')" @click="goTranscript">查看成绩单</AppButton>
            <AppButton v-if="hasPermission('academicAffairs.statusChange.view')" @click="goChanges">查看该生全部异动记录</AppButton>
          </div>
        </AppSectionCard>
      </template>
    </div>

    <AppConfirmDialog
      v-model:visible="revealVisible"
      title="查看完整证件号"
      message="查看学生完整身份证号将写入敏感数据查看审计，请填写查看理由。"
      type="warning"
      confirm-text="确认查看"
      require-reason
      reason-label="查看理由"
      reason-placeholder="如：核对身份证材料真实性（不少于 5 个字，将写入审计日志）"
      :submitting="revealing"
      @confirm="doReveal"
    />
  </ModulePageShell>
</template>

<script>
/** 学籍档案详情（/admin/academic-affairs/roster/:studentId）：GET /academic-affairs/roster/{id}（数据范围收敛，越权 403）。
 * 证件号查看走 POST /roster/{id}/reveal（理由必填≥5字，服务层二次鉴权+SUCCESS/DENY 双向审计）。 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSectionCard, AppTimeline, AppConfirmDialog, AppStatusTag } from '@/components/common'
import AppDescriptionList from '@/components/common/display/AppDescriptionList.vue'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'
import { matchPermission } from '@/config/navPlan'
import { formatDate } from '@/utils/dateUtils'
import { ACADEMIC_STUDENT_STATUS_LABELS as STATUS_LABEL, ACADEMIC_STATUS_CHANGE_LABELS as CHANGE_TYPE_LABEL } from '@/modules/academicAffairs/config/academicStudentLabels'

export default {
  name: 'AaRosterDetailView',
  components: {
    ModulePageShell, AppButton, AppSectionCard, LoadingState, ErrorState, EmptyState,
    AppTimeline, AppDescriptionList, AppConfirmDialog, AppStatusTag
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', detail: null,
      requestVersion: 0,
      revealVisible: false, revealing: false, revealed: false, revealedIdCard: ''
    }
  },
  computed: {
    canResume() { return ['SUSPENDED', 'PRESERVED'].includes(this.detail?.studentStatus) },
    studentId() {
      return this.$route.params.studentId
    },
    baseItems() {
      const d = this.detail
      if (!d) return []
      return [
        { label: '学号', value: d.studentNo },
        { label: '姓名', value: d.realName },
        { label: '性别', value: d.gender || '—' },
        { label: '学院', value: d.collegeName || '—' },
        { label: '专业', value: d.majorName || '—' },
        { label: '班级', value: d.className || '—' },
        { label: '年级', value: d.grade || '—' },
        { label: '学籍状态', value: STATUS_LABEL[d.studentStatus] || '状态待确认' },
        { label: '是否在籍', value: d.enrolled ? '在籍' : '非在籍' },
        { key: 'currentStage', label: '当前阶段', value: d.currentStage },
        { label: '入学日期', value: formatDate(d.enrollDate, '—') },
        { label: '备注', value: d.remark || '—' }
      ]
    },
    historyItems() {
      return (this.detail?.statusHistory || []).map((h) => ({
        id: h.changeId,
        title: `${CHANGE_TYPE_LABEL[h.changeType] || '学籍变更'}：${STATUS_LABEL[h.fromStatus] || '—'} → ${STATUS_LABEL[h.toStatus] || '—'}`,
        time: h.effectiveDate || '',
        status: h.status,
        description: h.reason || '',
        type: h.status === 'EFFECTIVE' ? 'success' : h.status === 'REJECTED' ? 'danger' : 'default'
      }))
    }
  },
  created() {
    this.load()
  },
  watch: { studentId() { this.load() } },
  beforeUnmount() { this.requestVersion++; this.hideRevealed() },
  methods: {
    hasPermission(key) { return matchPermission(this.ctx.permissionPatterns || [], key) },
    async load() {
      const version = ++this.requestVersion
      this.hideRevealed()
      this.revealVisible = false
      this.detail = null
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getRosterDetail(this.studentId)
      if (version !== this.requestVersion) return
      if (res.code === 0) {
        this.detail = res.data
      } else {
        this.error = res.message
      }
      this.loading = false
    },
    hideRevealed() {
      this.revealed = false
      this.revealedIdCard = ''
    },
    async doReveal({ reason }) {
      if (!this.hasPermission('academicAffairs.roster.viewSensitive') || this.loading || this.revealing) return
      if ((reason || '').trim().length < 5) { toast.warning('请填写至少 5 个字的查看理由'); return }
      this.revealing = true
      const version = this.requestVersion
      const res = await academicAffairsApi.revealRosterSensitive(this.studentId, reason)
      this.revealing = false
      if (version !== this.requestVersion) return
      if (res.code === 0) {
        this.revealed = true
        this.revealedIdCard = res.data.idCard || ''
        this.revealVisible = false
        toast.success('已记录本次查看审计')
      } else {
        toast.error(res.message || '查看失败')
      }
    },
    goChange() {
      if (!this.hasPermission('academicAffairs.statusChange.apply') || !(this.detail?.enrolled || this.canResume)) return
      this.$router.push({ path: '/admin/academic-affairs/status-changes/new', query: { studentId: this.studentId, name: this.detail?.realName, ...(this.canResume ? { type: 'RESUME' } : {}) } })
    },
    goCorrection() {
      this.$router.push({ path: '/admin/academic-affairs/roster/corrections', query: { studentId: this.studentId, name: this.detail?.realName } })
    },
    goTranscript() {
      this.$router.push(`/admin/academic-affairs/transcript?studentId=${this.studentId}`)
    },
    goChanges() {
      this.$router.push({ path: '/admin/academic-affairs/roster/changes', query: { studentId: this.studentId } })
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
@import '../styles/foundation-workspace.css';
.aa-sensitive-row { display: flex; align-items: center; gap: var(--space-3); }
.aa-sensitive-label { color: var(--text-tertiary); font-size: var(--font-size-sm); }
.aa-mask { font-family: var(--font-mono, monospace); color: var(--text-900, #1f2329); }
.aa-quick-actions { display: flex; gap: var(--space-3); flex-wrap: wrap; }
</style>
