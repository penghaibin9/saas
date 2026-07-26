<template>
  <AppPageShell
    title="学生画像详情"
    subtitle="学生主档摘要、请假记录摘要、宿舍信息摘要、风险标签、处分摘要和成长时间线。"
    data-scope-name="后端按当前身份校验"
    watermark-purpose="学生画像详情查看"
  >
    <template #actions>
      <AppPermissionButton :allowed="canBtn('studentAffairs.student.view')" code="studentAffairs.student.view" variant="secondary" @click="$router.push('/admin/student/list')">
        返回列表
      </AppPermissionButton>
      <AppPermissionButton :allowed="canBtn('student.audit.view')" code="student.audit.view" variant="secondary" @click="showAudit = !showAudit">
        数据变更日志
      </AppPermissionButton>
    </template>

    <AppGlobalState
      :state="pageState"
      :description="errorMessage"
      loading-text="正在加载学生画像详情…"
      @retry="load"
      @back="$router.push('/admin/student/list')"
    >
      <section class="sa-summary-strip profile-summary">
        <div class="sa-summary-strip__content">
          <span class="sa-summary-strip__eyebrow">学生当前画像</span>
          <h2 class="sa-summary-strip__title">{{ profile.baseInfo?.realName || student.realName || '未命名学生' }} · {{ profile.baseInfo?.studentNo || student.studentNo || studentId }}</h2>
          <p class="sa-summary-strip__text">
            {{ classDisplay }} · 学籍状态 {{ profile.baseInfo?.studentStatus || student.studentStatus || '—' }} · 当前阶段 {{ profile.baseInfo?.currentStage || student.currentStage || '—' }}；
            未关闭风险 {{ profile.riskSummary?.openCount || 0 }} 条，生效处分 {{ profile.disciplineSummary?.activeCount || 0 }} 条。
          </p>
        </div>
        <div class="profile-summary__risk">
          <span>最高风险</span>
          <AppRiskTag :level="profile.riskSummary?.topLevel || 'LOW'" />
        </div>
      </section>

      <div class="profile-priority-grid">
        <div class="profile-priority-card" :class="{ 'has-risk': profile.riskSummary?.openCount }">
          <span>风险状态</span>
          <strong>未关闭 {{ profile.riskSummary?.openCount || 0 }} 条</strong>
          <AppPermissionButton :allowed="canBtn('studentAffairs.risk.view')" code="studentAffairs.risk.view" variant="secondary" size="sm" @click="goRisk">查看风险</AppPermissionButton>
        </div>
        <div class="profile-priority-card">
          <span>当前宿舍</span>
          <strong>{{ dormText }}</strong>
          <AppPermissionButton v-if="canBtn('studentAffairs.dorm.view')" :allowed="true" code="studentAffairs.dorm.view" variant="secondary" size="sm" @click="goDorm">宿舍管理</AppPermissionButton>
        </div>
        <div class="profile-priority-card">
          <span>困难认定</span>
          <strong>{{ aidText }}</strong>
          <AppPermissionButton :allowed="canBtn('studentAffairs.aid.view')" code="studentAffairs.aid.view" variant="secondary" size="sm" @click="goAid">查看认定</AppPermissionButton>
        </div>
        <div class="profile-priority-card" :class="{ 'has-warning': profile.disciplineSummary?.activeCount }">
          <span>处分摘要</span>
          <strong>{{ profile.disciplineSummary?.restricted ? '受限可见' : `${profile.disciplineSummary?.activeCount || 0} 条生效` }}</strong>
          <AppPermissionButton :allowed="canBtn('studentAffairs.discipline.view')" code="studentAffairs.discipline.view" variant="secondary" size="sm" @click="goDiscipline">查看处分</AppPermissionButton>
        </div>
      </div>

      <AppSectionCard title="学生主档摘要">
        <AppDescriptionList :items="baseItems" :columns="3" bordered />
      </AppSectionCard>

      <div class="sa-detail-grid">
        <AppSectionCard title="请假记录摘要">
          <div class="sa-inline profile-domain-summary">
            <div><span>累计请假</span><strong>{{ profile.leaveSummary?.total || 0 }} 次</strong></div>
            <AppPermissionButton :allowed="canBtn('studentAffairs.leave.view')" code="studentAffairs.leave.view" variant="secondary" size="sm" @click="goLeave">查看请假</AppPermissionButton>
          </div>
        </AppSectionCard>

        <AppSectionCard title="家庭与联系人摘要">
          <div class="sa-inline profile-domain-summary">
            <strong>{{ familyText }}</strong>
            <AppPermissionButton v-if="canBtn('studentAffairs.homeSchool.view')" :allowed="true" code="studentAffairs.homeSchool.view" variant="secondary" size="sm" @click="goFamily">家校联系</AppPermissionButton>
          </div>
        </AppSectionCard>

        <AppSectionCard title="奖助摘要">
          <div class="sa-inline profile-domain-summary">
            <div><span>已获资助</span><strong>{{ profile.fundingSummary?.grantedCount || 0 }} 项</strong></div>
            <AppPermissionButton :allowed="canBtn('studentAffairs.funding.view')" code="studentAffairs.funding.view" variant="secondary" size="sm" @click="goFunding">查看奖助</AppPermissionButton>
          </div>
        </AppSectionCard>

        <AppSectionCard title="谈心谈话摘要">
          <div class="sa-inline profile-domain-summary">
            <div><span>谈话记录</span><strong>{{ profile.talkSummary?.total || 0 }} 次</strong></div>
            <AppPermissionButton :allowed="canBtn('studentAffairs.talk.view')" code="studentAffairs.talk.view" variant="secondary" size="sm" @click="goTalk">查看谈话</AppPermissionButton>
          </div>
        </AppSectionCard>
      </div>

      <AppSectionCard title="成长时间线">
        <p class="profile-section-hint">按时间汇总学工业务事件，用于查看学生成长轨迹；具体业务明细仍按各域权限控制。</p>
        <AppAuditTrail :records="timelineRecords" compact empty-text="暂无成长时间线事件" />
      </AppSectionCard>

      <AppSectionCard v-if="showAudit" title="数据变更日志入口">
        <p class="profile-section-hint">仅具备审计权限的角色可查看，记录数据变更操作和结果。</p>
        <AppAuditTrail :records="auditLogs" compact empty-text="暂无审计记录" />
      </AppSectionCard>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import {
  AppAuditTrail,
  AppDescriptionList,
  AppGlobalState,
  AppPageShell,
  AppPermissionButton,
  AppRiskTag,
  AppSectionCard
} from '@/components/common'
import studentAffairsApi from '@/modules/studentAffairs/api/studentAffairsB.api'
import { canCode } from '@/modules/studentAffairs/composables/permission'

export default {
  name: 'StudentAffairsProfileDetailView',
  props: { ctx: { type: Object, default: null } },
  components: {
    AppAuditTrail,
    AppDescriptionList,
    AppGlobalState,
    AppPageShell,
    AppPermissionButton,
    AppRiskTag,
    AppSectionCard
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
    classDisplay() {
      const b = this.profile.baseInfo || {}
      return this.student.className || b.className || '未分班'
    },
    dormText() {
      const d = this.profile.dormSummary
      if (d?.hasDorm && d.text) return d.text
      return '暂无宿舍入住信息'
    },
    familyText() {
      if (!this.canBtn('studentAffairs.homeSchool.view')) {
        return '暂无授权可见的家庭联系人信息'
      }
      const f = this.profile.familySummary
      if (f?.hasContact) {
        return `已登记联系人 ${f.contactCount || 0} 条，家校联系记录 ${f.logCount || 0} 条`
      }
      return '暂无授权可见的家庭联系人信息'
    },
    aidText() {
      const a = this.profile.aidSummary || {}
      if (a.inLibrary) return `困难库在库 · 等级 ${a.difficultLevel || '已认定'}`
      return '当前暂无相关记录'
    },
    baseItems() {
      const b = this.profile.baseInfo || {}
      return [
        { label: '姓名', value: b.realName || this.student.realName },
        { label: '学号', value: b.studentNo || this.student.studentNo },
        { label: '班级', value: this.classDisplay },
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
    canBtn(code) { return canCode(this.ctx, code) },
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
      this.$router.push({ path: '/admin/student-affairs/risk', query: { studentId: this.studentId, status: 'OPEN' } })
    },
    goLeave() {
      this.$router.push({ path: '/admin/campus-service/leave-ledger', query: { studentId: this.studentId } })
    },
    goDorm() {
      this.$router.push({
        path: '/admin/student-affairs/dorm/transfer',
        query: { studentId: this.studentId, status: 'PENDING' }
      })
    },
    goFamily() {
      this.$router.push({ path: '/admin/student-affairs/family', query: { studentId: this.studentId } })
    },
    goAid() {
      this.$router.push({ path: '/admin/student-affairs/aid', query: { studentId: this.studentId } })
    },
    goFunding() {
      this.$router.push({ path: '/admin/student-affairs/funding', query: { studentId: this.studentId } })
    },
    goDiscipline() {
      this.$router.push({ path: '/admin/student-affairs/discipline', query: { studentId: this.studentId } })
    },
    goTalk() {
      this.$router.push({ path: '/admin/student-affairs/talk', query: { studentId: this.studentId } })
    }
  }
}
</script>

<style scoped>
.profile-summary__risk { display: grid; justify-items: end; gap: 5px; white-space: nowrap; }
.profile-summary__risk span { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.profile-priority-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--space-3); margin-bottom: var(--space-4); }
.profile-priority-card { display: flex; flex-direction: column; align-items: flex-start; gap: var(--space-2); min-width: 0; padding: var(--space-3); border: 1px solid var(--border-light); border-radius: var(--radius-lg); background: var(--bg-card); }
.profile-priority-card.has-risk, .profile-priority-card.has-warning { border-color: var(--warning-200, #fde68a); background: var(--warning-50, #fffbeb); }
.profile-priority-card > span { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.profile-priority-card > strong { min-height: 42px; color: var(--text-primary); font-size: var(--font-size-sm); line-height: 1.55; overflow-wrap: anywhere; }
.sa-detail-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-4); }
.sa-inline { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); flex-wrap: wrap; color: var(--text-secondary); }
.profile-domain-summary > div { display: grid; gap: 3px; }
.profile-domain-summary span { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.profile-domain-summary strong { color: var(--text-primary); font-size: var(--font-size-base); line-height: 1.55; }
.profile-section-hint { margin: 0 0 var(--space-3); color: var(--text-secondary); font-size: var(--font-size-sm); line-height: 1.65; }
@media (max-width: 1100px) { .profile-priority-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 760px) { .profile-priority-grid, .sa-detail-grid { grid-template-columns: 1fr; } .profile-summary__risk { justify-items: start; } }
</style>
