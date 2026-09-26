<template>
  <section class="academic-flow-overview" aria-label="学期责任接力">
    <header class="flow-heading">
      <div><h2>{{ heading }}</h2><p>{{ flow?.term?.termLabel || '学期责任进度' }}<template v-if="flow"> · {{ scopeLabel(flow.viewer) }}</template></p></div>
      <AppTermEntityPicker :model-value="termId" placeholder="当前学期" @update:model-value="$emit('term-change', $event)" />
      <AppButton :loading="loading" @click="load">更新责任进度</AppButton>
    </header>
    <LoadingState v-if="loading" text="正在核对各责任方的真实进度…" />
    <ErrorState v-else-if="error" :title="errorTitle" :description="error" @retry="load" />
    <template v-else-if="flow">
      <div v-if="currentStage && !majorView" class="flow-current">
        <header><h3>当前阶段 · {{ stageLabel(currentStage) }}</h3><StatusTag :label="status(currentStage.status).label" :type="status(currentStage.status).type" /></header>
        <AcademicResponsibilityBar :responsibility="currentStage.responsibility" />
        <ul v-if="currentStage.blockers?.length" class="flow-blockers"><li v-for="(blocker, index) in currentStage.blockers" :key="index">{{ blockerMessage(blocker) }}</li></ul>
        <div v-if="currentStage.primaryAction?.route" class="flow-action"><AppButton v-if="canOpen(currentStage.primaryAction.route)" variant="primary" @click="$emit('navigate', currentStage.primaryAction.route)">{{ text(currentStage.primaryAction.label, '进入责任工作区') }}</AppButton><p v-else>请由上述责任方按其授权范围继续办理。</p></div>
        <AcademicHandoffCard v-if="currentStage.nextStep" :next-step="currentStage.nextStep" :can-open="canOpen" @navigate="$emit('navigate', $event)" />
      </div>
      <EmptyState v-else-if="!majorView" title="当前责任阶段待明确" description="请核对学期设置与有效责任任职。" />
      <section v-if="majorView" class="flow-major" aria-label="专业教学只读对账">
        <p class="flow-note">依据当前授权专业的正式培养方案与应开教学任务核对；教师分配和学院确认由开课责任学院办理。</p>
        <div class="flow-responsibilities"><article v-for="stage in majorStages" :key="stage.stageCode">
          <header><strong>{{ stageLabel(stage) }}</strong><StatusTag :label="status(stage.status).label" :type="status(stage.status).type" /></header>
          <p>{{ text(stage.evidence?.summary, '当前专业事实摘要待核对') }}</p>
          <dl class="flow-major-counts">
            <template v-if="stage.stageCode === 'F30_PROGRAM_COURSE'"><dt>培养方案数</dt><dd>{{ count(stage.evidence?.programCount) }}</dd></template>
            <template v-else>
              <dt>应开课程项</dt><dd>{{ count(stage.evidence?.expectedCourseCount) }}</dd>
              <dt>实际教学任务</dt><dd>{{ count(stage.evidence?.actualTaskCount) }}</dd>
              <dt>待教师确认</dt><dd>{{ count(stage.evidence?.pendingTeacherCount) }}</dd>
              <dt>阻断项</dt><dd>{{ count(stage.evidence?.blockerCount) }}</dd>
            </template>
          </dl>
          <ul v-if="stage.blockers?.length"><li v-for="(blocker, index) in stage.blockers" :key="index">{{ blockerMessage(blocker) }}</li></ul>
        </article></div>
      </section>
      <AcademicUnitProgressMatrix v-if="!teacherView && !majorView" :units="flow.unitProgress" :title="schoolView ? '各学院并行进度' : '本学院教学进度'" />
      <section v-if="!majorView && flow.currentResponsibilities.length" class="flow-mine" aria-label="我的责任事项">
        <h3>{{ schoolView ? '我的校级责任' : '当前岗位责任' }}</h3>
        <div class="flow-responsibilities"><article v-for="(stage, index) in flow.currentResponsibilities" :key="`${stage.stageCode}:${stage.responsibility?.orgId || index}`">
          <header><strong>{{ stageLabel(stage) }}</strong><StatusTag :label="status(stage.status).label" :type="status(stage.status).type" size="sm" /></header>
          <p>{{ responsibility(stage.responsibility).orgName }} · {{ responsibility(stage.responsibility).assigneeLabel }}</p>
          <ul v-if="stage.blockers?.length"><li v-for="(blocker, index) in stage.blockers" :key="index">{{ blockerMessage(blocker) }}</li></ul>
          <AppButton v-if="stage.primaryAction?.route && canOpen(stage.primaryAction.route)" variant="ghost" @click="$emit('navigate', stage.primaryAction.route)">{{ text(stage.primaryAction.label, '查看责任事项') }}</AppButton>
          <p v-else class="flow-note">按责任分工等待前置事项或下一责任方办理。</p>
        </article></div>
      </section>
      <section v-if="!majorView && flow.schoolGates.length" class="flow-gates" aria-label="学校统一办理条件"><h3>学校统一办理条件</h3><div><AcademicSchoolGateCard v-for="gate in flow.schoolGates" :key="gate.stageCode" :gate="gate" /></div></section>
    </template>
  </section>
</template>

<script>
import { LoadingState, ErrorState, EmptyState, StatusTag } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppTermEntityPicker } from '@/components/common'
import { currentUserFromToken } from '@/services/http/client'
import { normalizeUiError } from '@/utils/presentationSafety'
import { academicIdentity, createAcademicRequestGate } from '../academicFlowContext.js'
import { academicFlowApi } from '../api/academic-flow.api.js'
import { academicFlowText, academicFlowCount, academicFlowStatus, academicFlowStageLabel, academicFlowScopeLabel, academicFlowResponsibility, academicFlowBlockerMessage } from '../config/academicFlowRegistry.js'
import AcademicResponsibilityBar from './AcademicResponsibilityBar.vue'
import AcademicUnitProgressMatrix from './AcademicUnitProgressMatrix.vue'
import AcademicSchoolGateCard from './AcademicSchoolGateCard.vue'
import AcademicHandoffCard from './AcademicHandoffCard.vue'

export default {
  name: 'AcademicFlowOverview',
  components: { LoadingState, ErrorState, EmptyState, StatusTag, AppButton, AppTermEntityPicker, AcademicResponsibilityBar, AcademicUnitProgressMatrix, AcademicSchoolGateCard, AcademicHandoffCard },
  props: { ctx: { type: Object, required: true }, termId: { type: String, default: '' }, collegeId: { type: String, default: '' }, canOpen: { type: Function, default: () => false } },
  emits: ['navigate', 'term-change'],
  data() { return { flow: null, loading: false, error: '', errorTitle: '责任进度读取失败', readGate: null, disposed: false } },
  computed: {
    contextKey() { return JSON.stringify([academicIdentity(currentUserFromToken(), this.ctx), this.ctx.currentRole, this.termId, this.collegeId]) },
    schoolView() { return ['TENANT_ALL', 'SCHOOL'].includes(this.flow?.viewer?.scopeType) },
    teacherView() { return this.flow?.viewer?.roleCode === 'ACADEMIC_TEACHER' },
    majorView() { return Array.isArray(this.flow?.viewer?.majorIds) && this.flow.viewer.majorIds.length > 0 },
    majorStages() { return this.majorView ? this.flow.stages.filter(stage => ['F30_PROGRAM_COURSE', 'F40_TEACHING_TASK'].includes(stage.stageCode)) : [] },
    heading() { return !this.flow ? '学期责任接力' : this.majorView ? '本专业教学对账' : this.teacherView ? '我的教学责任' : this.schoolView ? '学校教学运行总控' : this.flow.viewer.scopeType === 'COLLEGE' ? '本学院教学运行' : '当前授权范围教学进度' },
    currentStage() { const stage = this.schoolView ? this.flow?.schoolStage : this.flow?.myStage; return stage?.stageCode ? stage : null }
  },
  created() { this.readGate = createAcademicRequestGate(() => this.contextKey); this.load() },
  mounted() { window.addEventListener('focus', this.load) },
  beforeUnmount() { this.disposed = true; this.readGate.invalidate(); this.flow = null; window.removeEventListener('focus', this.load) },
  watch: { contextKey() { this.load() } },
  methods: {
    text: academicFlowText, count: academicFlowCount, status: academicFlowStatus, stageLabel: academicFlowStageLabel, scopeLabel: academicFlowScopeLabel,
    responsibility: academicFlowResponsibility, blockerMessage: academicFlowBlockerMessage,
    async load() {
      if (!this.readGate || this.disposed) return
      const current = this.readGate.begin()
      this.flow = null; this.error = ''; this.errorTitle = '责任进度读取失败'; this.loading = true
      try {
        const data = await academicFlowApi.get({ termId: this.termId || undefined, collegeId: this.collegeId || undefined })
        if (current() && !this.disposed) this.flow = data
      } catch (error) {
        if (!current() || this.disposed) return
        const display = normalizeUiError(error, { fallback: '责任进度暂时无法读取，请重试' })
        this.errorTitle = display.pageState === 'forbidden' ? '当前身份无法读取此项责任进度' : '责任进度读取失败'
        this.error = display.pageState === 'forbidden'
          ? '请由负责该范围的学院、教师或校教务人员继续办理。当前账号仍可在下方查看本人正式待办。'
          : academicFlowText(display.userMessage, '责任进度暂时无法读取，请重试')
      } finally { if (current() && !this.disposed) this.loading = false }
    }
  }
}
</script>

<style scoped>
.flow-major { display:grid; gap:12px; }.flow-major-counts { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:6px 16px; margin:12px 0; }.flow-major-counts dt { color:var(--text-secondary); }.flow-major-counts dd { margin:0; font-weight:600; }
.academic-flow-overview { display:grid; gap:16px; min-width:0; }.flow-heading { display:flex; align-items:center; gap:12px; flex-wrap:wrap; padding-bottom:14px; border-bottom:1px solid var(--border-base); }.flow-heading > div { flex:1; min-width:180px; }.flow-heading h2 { font-size:18px; margin:0; }.flow-heading p,.flow-note { color:var(--text-secondary); font-size:12px; line-height:1.7; margin:6px 0 0; }.flow-current { display:grid; gap:12px; }.flow-current > header,.flow-responsibilities header { display:flex; align-items:center; gap:12px; justify-content:space-between; flex-wrap:wrap; }.academic-flow-overview h3 { font-size:15px; margin:0; }.flow-blockers { margin:0; padding:12px 14px 12px 32px; border-radius:8px; background:var(--warning-bg,#fff6e5); color:var(--warning-text,#97600c); font-size:13px; line-height:1.8; }.flow-action p { color:var(--text-secondary); font-size:13px; margin:0; }.flow-mine,.flow-gates { display:grid; gap:12px; }.flow-responsibilities,.flow-gates > div { display:grid; grid-template-columns:repeat(auto-fit,minmax(min(100%,280px),1fr)); gap:12px; }.flow-responsibilities article { padding:14px; border:1px solid var(--border-base); border-radius:9px; background:var(--bg-card); font-size:12px; line-height:1.7; overflow-wrap:anywhere; }.flow-responsibilities p { margin:8px 0; }.flow-responsibilities ul { padding-left:18px; }
</style>
