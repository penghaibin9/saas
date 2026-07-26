<template>
  <ModulePageShell
    title="教学班详情"
    :subtitle="teachingClass ? `${teachingClass.classCode} · ${teachingClass.courseName || teachingClass.className}` : '查看教师关系、当前成员与名单版本历史'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="backToClasses">返回教学班</AppButton>
      <AppButton @click="$router.push('/admin/academic-affairs/teaching-tasks')">来源教学任务</AppButton>
    </template>

    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <div v-else-if="teachingClass" class="mp-stack">
      <div class="aa-summary-grid">
        <div><strong>{{ teachingClass.className }}</strong><span>{{ classTypeLabel(teachingClass.classType) }}</span></div>
        <div><strong>{{ teachingClass.courseName || '—' }}</strong><span>{{ teachingClass.courseCode || teachingClass.courseId }}</span></div>
        <div><strong>{{ activeTeacher?.teacherName || '待分配' }}</strong><span>{{ activeTeacher?.teacherKey || '主讲教师未绑定' }}</span></div>
        <div :class="{ 'is-danger': teachingClass.rosterStatus !== 'LOCKED' }"><strong>{{ teachingClass.currentMembers.length }}</strong><span>{{ teachingClass.rosterStatus === 'LOCKED' ? `当前第${teachingClass.rosterVersionNo}版` : '尚无正式名单' }}</span></div>
      </div>

      <AppInlineAlert
        :type="teachingClass.rosterStatus === 'LOCKED' ? 'success' : 'warning'"
        :title="teachingClass.rosterStatus === 'LOCKED' ? '当前名单已锁定' : '当前教学班尚无正式名单版本'"
        :description="teachingClass.rosterStatus === 'LOCKED' ? '考勤、考务和成绩读取当前版本；名单变化必须创建新版本，不能覆盖历史成员。' : '返回教学班列表运行存量对账，或完成选课名单锁定。'"
      />

      <AppSectionCard title="教学班事实">
        <div class="aa-facts">
          <div><span>教学班编号</span><b>{{ teachingClass.classCode }}</b></div>
          <div><span>状态</span><b><AppStatusTag :type="teachingClass.status === 'ACTIVE' ? 'success' : 'info'" :label="classStatusLabel(teachingClass.status)" /></b></div>
          <div><span>来源任务</span><b>#{{ teachingClass.teachingTaskId }} · {{ taskStatusLabel(teachingClass.taskStatus) }}</b></div>
          <div><span>行政班来源</span><b>{{ teachingClass.administrativeClassName || teachingClass.administrativeClassId || '非行政班来源' }}</b></div>
          <div><span>容量</span><b>{{ teachingClass.capacity ?? '未设置' }}</b></div>
          <div><span>预计人数兼容字段</span><b>{{ teachingClass.expectedStudents ?? '未设置' }}</b></div>
        </div>
      </AppSectionCard>

      <AppSectionCard title="教师关系">
        <EmptyState v-if="!teachingClass.teachers.length" title="尚未绑定教师" description="请回到教学任务分配稳定教师工号" />
        <DataTable v-else :columns="teacherColumns" :rows="teachingClass.teachers" row-key="teacherRelationId">
          <template #cell-teacher="{ row }"><div class="mp-cell-main">{{ row.teacherName || '—' }}</div><div class="mp-cell-sub">{{ row.teacherKey }}</div></template>
          <template #cell-roleType="{ row }">{{ teacherRoleLabel(row.roleType) }}</template>
          <template #cell-weeks="{ row }">第{{ row.startWeek || '?' }}—{{ row.endWeek || '?' }}周</template>
          <template #cell-status="{ row }"><AppStatusTag :type="row.status === 'ACTIVE' ? 'success' : 'info'" :label="relationStatusLabel(row.status)" /></template>
        </DataTable>
      </AppSectionCard>

      <AppSectionCard :title="`当前正式成员（${teachingClass.currentMembers.length}人）`">
        <EmptyState v-if="!teachingClass.currentMembers.length" title="当前版本没有有效成员" description="名单为空或存在学生主档欠账，不能继续下游业务" />
        <DataTable v-else :columns="memberColumns" :rows="teachingClass.currentMembers" row-key="memberId">
          <template #cell-student="{ row }"><div class="mp-cell-main">{{ row.realName }}</div><div class="mp-cell-sub">{{ row.studentNo || row.studentId }}</div></template>
          <template #cell-source="{ row }"><AppStatusTag :type="row.sourceType === 'SELECTION_LOCK' ? 'success' : 'info'" :label="sourceLabel(row.sourceType)" /><div class="mp-cell-sub">{{ row.sourceId ? `来源 ${row.sourceId}` : '—' }}</div></template>
          <template #cell-status="{ row }"><AppStatusTag type="success" :label="memberStatusLabel(row.status)" /></template>
        </DataTable>
      </AppSectionCard>

      <AppSectionCard title="名单变更">
        <AppInlineAlert
          v-if="teachingClass.rosterManagement?.managedBySelection"
          type="warning"
          title="该教学班由选课名单管理"
          :description="teachingClass.rosterManagement.reason || '请在选课管理中补退选并重新锁定名单，禁止在此覆盖。'"
        />
        <template v-else>
          <AppInlineAlert
            type="info"
            title="先预览影响，再创建新版本"
            description="课表只提示影响；已有考勤、考务或成绩任务时会阻断直接变更，防止下游继续使用旧名单。"
          />
          <div class="aa-roster-editor">
            <label class="is-grow">拟生效学生
              <AppStudentPicker
                v-model="rosterForm.studentIds"
                multiple
                placeholder="选择新版本全部学生"
                data-scope-hint="仅可选择当前学院或班级数据范围内的学生"
              />
            </label>
            <label class="is-grow">变更原因
              <textarea v-model.trim="rosterForm.reason" class="aa-textarea" maxlength="500" placeholder="说明增减学生原因，不少于5字" />
            </label>
            <div class="aa-roster-actions">
              <AppButton :loading="previewing" :disabled="!rosterForm.studentIds.length" @click="previewRoster">预览影响</AppButton>
              <AppButton variant="primary" :loading="saving" :disabled="!canCreateRosterVersion" @click="createRosterVersion">生成新版本</AppButton>
            </div>
          </div>

          <div v-if="rosterImpact" class="mp-stack">
            <div class="aa-impact-grid">
              <div><strong>+{{ rosterImpact.addedStudentIds.length }}</strong><span>新增学生</span></div>
              <div><strong>-{{ rosterImpact.removedStudentIds.length }}</strong><span>移除学生</span></div>
              <div><strong>{{ rosterImpact.impact.scheduleCount }}</strong><span>课表项</span></div>
              <div :class="{ 'is-danger': rosterImpact.impact.attendanceCount }"><strong>{{ rosterImpact.impact.attendanceCount }}</strong><span>考勤场次</span></div>
              <div :class="{ 'is-danger': rosterImpact.impact.examCourseCount }"><strong>{{ rosterImpact.impact.examCourseCount }}</strong><span>考试课程</span></div>
              <div :class="{ 'is-danger': rosterImpact.impact.gradeTaskCount }"><strong>{{ rosterImpact.impact.gradeTaskCount }}</strong><span>成绩任务</span></div>
            </div>
            <AppInlineAlert
              :type="rosterImpact.canCreate ? 'success' : 'warning'"
              :title="rosterImpact.canCreate ? '可以创建新名单版本' : '当前不能创建新版本'"
              :description="impactDescription"
            />
          </div>
        </template>
      </AppSectionCard>

      <AppSectionCard title="名单版本历史">
        <EmptyState v-if="!teachingClass.rosterVersions.length" title="暂无名单版本" description="系统不会把临时推导名单伪装成已锁定版本" />
        <DataTable v-else :columns="versionColumns" :rows="teachingClass.rosterVersions" row-key="rosterVersionId">
          <template #cell-version="{ row }"><div class="mp-cell-main">第 {{ row.versionNo }} 版</div><div class="mp-cell-sub">{{ row.rosterVersionId }}</div></template>
          <template #cell-source="{ row }"><AppStatusTag :type="row.sourceType === 'SELECTION_LOCK' ? 'success' : 'info'" :label="sourceLabel(row.sourceType)" /><div class="mp-cell-sub">{{ row.sourceId || '—' }}</div></template>
          <template #cell-status="{ row }"><AppStatusTag :type="row.status === 'LOCKED' ? 'success' : 'info'" :label="versionStatusLabel(row.status)" /></template>
          <template #cell-locked="{ row }"><div>{{ row.lockedAt || '—' }}</div><div class="mp-cell-sub">{{ row.lockedBy || '系统' }}</div></template>
        </DataTable>
      </AppSectionCard>
    </div>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppInlineAlert, AppSectionCard, AppStatusTag, AppStudentPicker } from '@/components/common'
import { teachingClassApi } from '@/modules/academicAffairs/api/teaching-class.api'
import { toast } from '@/utils/toast'

export default {
  name: 'AaTeachingClassDetailView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppInlineAlert, AppSectionCard, AppStatusTag, AppStudentPicker },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', teachingClass: null,
      previewing: false, saving: false, rosterImpact: null,
      rosterForm: { studentIds: [], reason: '' },
      teacherColumns: [{ key: 'teacher', title: '教师' }, { key: 'roleType', title: '角色' }, { key: 'weeks', title: '授课周次' }, { key: 'status', title: '状态' }],
      memberColumns: [{ key: 'student', title: '学生' }, { key: 'classId', title: '行政班ID' }, { key: 'source', title: '成员来源' }, { key: 'status', title: '状态' }],
      versionColumns: [{ key: 'version', title: '版本' }, { key: 'source', title: '来源' }, { key: 'memberCount', title: '人数' }, { key: 'reason', title: '形成原因' }, { key: 'locked', title: '锁定信息' }, { key: 'status', title: '状态' }]
    }
  },
  computed: {
    teachingClassId() { return String(this.$route.query.teachingClassId || this.$route.params.teachingClassId || '') },
    activeTeacher() { return (this.teachingClass?.teachers || []).find(row => row.roleType === 'PRIMARY' && row.status === 'ACTIVE') },
    canCreateRosterVersion() {
      return Boolean(
        this.rosterImpact?.canCreate
        && this.rosterForm.reason.trim().length >= 5
        && !this.saving
      )
    },
    impactDescription() {
      if (!this.rosterImpact?.changed) return '拟提交名单与当前正式名单一致，无需创建新版本。'
      if (this.rosterImpact?.impact?.blocked) return this.rosterImpact.impact.blockerMessage || '下游已消费当前名单，暂不能直接变更。'
      return `新版本将由 ${this.rosterImpact.currentMemberCount} 人调整为 ${this.rosterImpact.proposedMemberCount} 人，历史版本继续保留。`
    }
  },
  created() { this.load() },
  methods: {
    backToClasses() { this.$router.push({ path: '/admin/academic-affairs/teaching-tasks', query: { view: 'classes' } }) },
    classTypeLabel(value) { return ({ ADMIN: '行政班开课', SELECTION: '选课教学班', MERGED: '合班教学班', RETAKE: '重修教学班', LAYERED: '分层教学班' })[value] || value || '—' },
    classStatusLabel(value) { return ({ ACTIVE: '使用中', ARCHIVED: '已归档' })[value] || value || '—' },
    taskStatusLabel(value) { return ({ PENDING_ASSIGN: '待分配', ASSIGNED: '已分配', TEACHER_CONFIRMED: '教师已确认', READY: '已就绪', MERGED: '已并入合班', REJECTED_BY_TEACHER: '教师已退回' })[value] || value || '—' },
    teacherRoleLabel(value) { return ({ PRIMARY: '主讲', CO_TEACHER: '协同授课' })[value] || value || '—' },
    relationStatusLabel(value) { return ({ ACTIVE: '生效', INACTIVE: '历史关系' })[value] || value || '—' },
    memberStatusLabel(value) { return ({ ACTIVE: '当前成员', REMOVED: '已移出' })[value] || value || '—' },
    versionStatusLabel(value) { return ({ LOCKED: '当前生效', SUPERSEDED: '历史版本' })[value] || value || '—' },
    sourceLabel(value) { return ({ ADMIN_CLASS: '行政班初始化', SELECTION_LOCK: '选课锁定', MANUAL: '人工版本', RETAKE: '重修名单' })[value] || value || '—' },
    async load() {
      if (!this.teachingClassId) { this.error = '缺少教学班ID'; this.loading = false; return }
      this.loading = true; this.error = ''
      const res = await teachingClassApi.detail(this.teachingClassId)
      if (res.code === 0) {
        this.teachingClass = res.data
        this.rosterForm.studentIds = (res.data.currentMembers || []).map(row => row.studentId)
        this.rosterImpact = null
      } else { this.teachingClass = null; this.error = res.message || '加载教学班失败' }
      this.loading = false
    },
    async previewRoster() {
      if (!this.rosterForm.studentIds.length || this.previewing) return
      this.previewing = true
      const res = await teachingClassApi.previewRosterChange(this.teachingClassId, this.rosterForm.studentIds)
      this.previewing = false
      if (res.code === 0) this.rosterImpact = res.data
      else { this.rosterImpact = res.data || null; toast.error(res.message || '影响预览失败') }
    },
    async createRosterVersion() {
      if (!this.canCreateRosterVersion) return
      this.saving = true
      const res = await teachingClassApi.createRosterVersion(
        this.teachingClassId,
        this.rosterForm.studentIds,
        this.rosterForm.reason.trim()
      )
      this.saving = false
      if (res.code === 0) {
        toast.success(`第${res.data.versionNo}版名单已生效`)
        this.rosterForm.reason = ''
        await this.load()
      } else { this.rosterImpact = res.data || this.rosterImpact; toast.error(res.message || '创建名单版本失败') }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-summary-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.aa-summary-grid > div, .aa-impact-grid > div { padding: 14px 16px; border: 1px solid var(--border-200, #e5e7eb); border-radius: 8px; background: var(--bg-white, #fff); }
.aa-summary-grid strong, .aa-summary-grid span, .aa-impact-grid strong, .aa-impact-grid span { display: block; }
.aa-summary-grid strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 18px; }
.aa-summary-grid span, .aa-impact-grid span { margin-top: 4px; color: var(--text-500, #64748b); font-size: 12px; }
.aa-summary-grid .is-danger, .aa-impact-grid .is-danger { border-color: var(--danger-200, #fecaca); }
.aa-facts { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.aa-facts > div { padding: 12px; border: 1px solid var(--border-200, #e5e7eb); border-radius: 6px; }
.aa-facts span, .aa-facts b { display: block; }.aa-facts span { color: var(--text-500, #64748b); font-size: 12px; }.aa-facts b { margin-top: 4px; }
.aa-roster-editor { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) auto; gap: 14px; align-items: end; margin-top: 14px; }
.aa-roster-editor label { display: flex; flex-direction: column; gap: 6px; color: var(--text-700, #4e5969); font-size: 13px; }
.aa-textarea { min-height: 72px; resize: vertical; padding: 9px 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; font: inherit; }
.aa-roster-actions { display: flex; gap: 8px; padding-bottom: 1px; }
.aa-impact-grid { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 10px; }
.aa-impact-grid strong { font-size: 20px; }
@media (max-width: 1000px) { .aa-impact-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } .aa-roster-editor { grid-template-columns: 1fr; } }
@media (max-width: 900px) { .aa-summary-grid, .aa-facts { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>
