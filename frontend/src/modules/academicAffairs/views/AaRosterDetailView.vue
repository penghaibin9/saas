<template>
  <ModulePageShell
    title="学籍档案"
    :subtitle="detail ? `${detail.realName} · 学号 ${detail.studentNo}` : '学籍档案详情'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="systemReturnTo ? $router.push(systemReturnTo) : $router.back()">{{ systemReturnTo ? '返回系统管理' : '返回' }}</AppButton>
    </template>

    <div class="mp-stack">
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <template v-else-if="detail">
        <AppSectionCard title="基础信息">
          <AppDescriptionList :items="baseItems" :columns="3" />
        </AppSectionCard>

        <AppSectionCard title="证件与联系">
          <div class="aa-sensitive-row">
            <span class="aa-sensitive-label">身份证号</span>
            <span class="aa-mask">{{ revealed ? revealedIdCard : detail.idCardMasked || '—' }}</span>
            <button v-if="!revealed" class="mp-link" @click="revealVisible = true">查看完整</button>
            <button v-else class="mp-link" @click="hideRevealed">隐藏</button>
          </div>
          <p class="mp-note">查看完整证件号需填写理由，系统将记录本次查看审计。</p>
        </AppSectionCard>

        <AppSectionCard title="学籍状态历史">
          <EmptyState v-if="!detail.statusHistory.length" title="暂无学籍状态变更记录" />
          <AppTimeline v-else :items="historyItems" />
        </AppSectionCard>

        <AppSectionCard title="快捷入口">
          <div class="aa-quick-actions">
            <AppButton :disabled="!detail.enrolled" @click="goChange">发起学籍异动</AppButton>
            <AppButton @click="goCorrection">发起学籍信息更正</AppButton>
            <AppButton @click="goTranscript">查看成绩单</AppButton>
            <AppButton @click="goChanges">查看该生全部异动记录</AppButton>
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
import { AppSectionCard, AppTimeline, AppConfirmDialog } from '@/components/common'
import AppDescriptionList from '@/components/common/display/AppDescriptionList.vue'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'
import { systemRelationshipReturnTo } from '@/utils/systemRelationshipNavigation'
import { formatDateTime } from '@/utils/dateUtils'
import { ACADEMIC_STUDENT_STATUS_LABELS as STATUS_LABEL, ACADEMIC_STATUS_CHANGE_LABELS as CHANGE_TYPE_LABEL } from '../config/academicStudentLabels'

const STAGE_LABEL = {
  ADMITTED: '新生阶段·已录取', PRE_STUDENT_VERIFIED: '新生阶段·预报到已核验',
  REGISTERED_PENDING_ENROLLMENT: '新生阶段·已报到待注册', ENROLLED: '在读阶段',
  GRADUATING: '毕业阶段', INTERN: '岗位实习阶段', GRADUATED: '已毕业', ALUMNI: '校友'
}

export default {
  name: 'AaRosterDetailView',
  components: {
    ModulePageShell, AppButton, AppSectionCard, LoadingState, ErrorState, EmptyState,
    AppTimeline, AppDescriptionList, AppConfirmDialog
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', detail: null,
      revealVisible: false, revealing: false, revealed: false, revealedIdCard: ''
    }
  },
  computed: {
    systemReturnTo() { return systemRelationshipReturnTo(this.$route.query.returnTo) },
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
        { label: '当前阶段', value: STAGE_LABEL[d.currentStage] || (d.currentStage ? '阶段待确认' : '—') },
        { label: '入学日期', value: d.enrollDate || '—' },
        { label: '备注', value: d.remark || '—' }
      ]
    },
    historyItems() {
      return (this.detail?.statusHistory || []).map((h) => ({
        id: h.changeId,
        title: `${CHANGE_TYPE_LABEL[h.changeType] || '学籍变更'}：${STATUS_LABEL[h.fromStatus] || '状态待确认'} → ${STATUS_LABEL[h.toStatus] || '状态待确认'}`,
        time: formatDateTime(h.effectiveDate, '生效时间未提供'),
        status: h.status,
        description: ({ ENROLL注册: '入学注册', ANNUAL注册: '学年注册', SEMESTER注册: '学期注册' })[h.reason] || h.reason || '',
        type: h.status === 'EFFECTIVE' ? 'success' : h.status === 'REJECTED' ? 'danger' : 'default'
      }))
    }
  },
  created() {
    this.load()
  },
  methods: {
    async load() {
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getRosterDetail(this.studentId)
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
      this.revealing = true
      const res = await academicAffairsApi.revealRosterSensitive(this.studentId, reason)
      this.revealing = false
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
      this.$router.push({ path: '/admin/academic-affairs/status-changes/new', query: { studentId: this.studentId, name: this.detail?.realName } })
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
.aa-sensitive-row { display: flex; align-items: center; gap: var(--space-3); }
.aa-sensitive-label { color: var(--text-tertiary); font-size: var(--font-size-sm); }
.aa-mask { font-family: var(--font-mono, monospace); color: var(--text-900, #1f2329); }
.aa-quick-actions { display: flex; gap: var(--space-3); flex-wrap: wrap; }
</style>
