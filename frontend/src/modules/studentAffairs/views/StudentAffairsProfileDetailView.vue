<template>
  <AppPageShell
    title="学生画像详情"
    subtitle="学生主档摘要、请假记录摘要、宿舍信息摘要、风险标签、处分摘要和成长时间线。"
    data-scope-name="后端按当前身份校验"
    watermark-purpose="学生画像详情查看"
  >
    <template #actions>
      <AppPermissionButton code="studentAffairs.profile.back" variant="secondary" @click="$router.push('/admin/student-affairs/profile')">
        返回列表
      </AppPermissionButton>
      <AppPermissionButton code="student.audit.view" variant="secondary" @click="showAudit = !showAudit">
        数据变更日志
      </AppPermissionButton>
    </template>

    <AppGlobalState
      :state="pageState"
      :description="errorMessage"
      loading-text="正在加载学生画像详情…"
      @retry="load"
      @back="$router.push('/admin/student-affairs/profile')"
    >
      <div class="sa-detail-grid">
        <AppSectionCard title="学生主档摘要">
          <AppDescriptionList :items="baseItems" bordered />
        </AppSectionCard>

        <AppSectionCard title="风险标签">
          <div class="sa-inline">
            <AppRiskTag :level="profile.riskSummary?.topLevel || 'LOW'" />
            <span>未关闭风险 {{ profile.riskSummary?.openCount || 0 }} 条</span>
            <AppPermissionButton code="studentAffairs.risk.view" variant="secondary" size="sm" @click="goRisk">
              查看风险
            </AppPermissionButton>
          </div>
        </AppSectionCard>

        <AppSectionCard title="请假记录摘要">
          <AppMetricCard title="累计请假" :value="profile.leaveSummary?.total || 0" unit="次" accent="warning" />
        </AppSectionCard>

        <AppSectionCard title="宿舍信息摘要">
          <div class="sa-inline">
            <AppStatusTag type="info" label="B2 串联" />
            <span>宿舍入住、调宿和夜不归宿将在 B2 与宿舍管理联动。</span>
          </div>
        </AppSectionCard>

        <AppSectionCard title="家庭与联系人摘要">
          <div class="sa-inline">
            <AppSensitiveText value="联系人信息按敏感字段权限脱敏展示" />
            <AppStatusTag type="info" label="C 包补强" />
          </div>
        </AppSectionCard>

        <AppSectionCard title="处分摘要">
          <div class="sa-inline">
            <AppStatusTag
              :type="profile.disciplineSummary?.restricted ? 'warning' : 'info'"
              :label="profile.disciplineSummary?.restricted ? '受限可见' : `${profile.disciplineSummary?.activeCount || 0} 条生效`"
            />
            <span>处分明细按角色权限控制，未授权角色只看摘要。</span>
          </div>
        </AppSectionCard>

        <AppSectionCard title="成长时间线">
          <AppAuditTrail :records="timelineRecords" compact empty-text="暂无成长时间线事件" />
        </AppSectionCard>

        <AppSectionCard v-if="showAudit" title="数据变更日志入口">
          <AppAuditTrail :records="auditLogs" compact empty-text="暂无审计记录" />
        </AppSectionCard>
      </div>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import {
  AppAuditTrail,
  AppDescriptionList,
  AppGlobalState,
  AppMetricCard,
  AppPageShell,
  AppPermissionButton,
  AppRiskTag,
  AppSectionCard,
  AppSensitiveText,
  AppStatusTag
} from '@/components/common'
import studentAffairsApi from '@/modules/studentAffairs/api/studentAffairsB.api'

export default {
  name: 'StudentAffairsProfileDetailView',
  components: {
    AppAuditTrail,
    AppDescriptionList,
    AppGlobalState,
    AppMetricCard,
    AppPageShell,
    AppPermissionButton,
    AppRiskTag,
    AppSectionCard,
    AppSensitiveText,
    AppStatusTag
  },
  data() {
    return {
      loading: true,
      errorMessage: '',
      student: {},
      profile: {},
      timeline: [],
      auditLogs: [],
      showAudit: false
    }
  },
  computed: {
    studentId() {
      return this.$route.params.studentId
    },
    pageState() {
      if (this.loading) return 'loading'
      if (this.errorMessage) return 'error'
      return this.profile.baseInfo ? 'ready' : 'empty'
    },
    baseItems() {
      const b = this.profile.baseInfo || {}
      return [
        { label: '姓名', value: b.realName || this.student.realName },
        { label: '学号', value: b.studentNo || this.student.studentNo },
        { label: '班级', value: this.student.className || b.className },
        { label: '学籍状态', value: b.studentStatus || this.student.studentStatus },
        { label: '当前阶段', value: b.currentStage || this.student.currentStage },
        { label: '心理关注摘要', value: this.profile.psyFlag || '无' }
      ]
    },
    timelineRecords() {
      return this.timeline.map((item) => ({
        id: item.eventId,
        action: item.title,
        actor: item.module,
        target: item.eventType,
        reason: item.detail,
        at: (item.occurredAt || '').replace('T', ' ').slice(0, 19),
        result: '成功'
      }))
    }
  },
  created() {
    this.load()
  },
  methods: {
    async load() {
      this.loading = true
      this.errorMessage = ''
      try {
        const [studentRes, profileRes, timelineRes, auditRes] = await Promise.all([
          studentAffairsApi.getStudentBasic(this.studentId).catch(() => ({ data: {} })),
          studentAffairsApi.getProfile(this.studentId),
          studentAffairsApi.getTimeline(this.studentId),
          studentAffairsApi.getAuditLogs().catch(() => ({ data: [] }))
        ])
        this.student = studentRes.data || {}
        this.profile = profileRes.data || {}
        this.timeline = timelineRes.data?.items || []
        this.auditLogs = auditRes.data || []
      } catch (e) {
        this.errorMessage = e?.message || '学生画像详情加载失败'
      } finally {
        this.loading = false
      }
    },
    goRisk() {
      this.$router.push('/admin/student-affairs/risk')
    }
  }
}
</script>

<style scoped>
.sa-detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: var(--space-4);
}
.sa-inline {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
  color: var(--text-secondary);
}
</style>

