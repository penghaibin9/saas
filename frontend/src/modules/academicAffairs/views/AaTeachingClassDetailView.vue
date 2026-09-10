<template>
  <ModulePageShell
    title="教学班详情"
    :subtitle="teachingClass ? `${teachingClass.classCode} · ${teachingClass.courseName || teachingClass.className}` : '查看教师关系、当前成员与名单版本历史'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="backToClasses">返回教学班</AppButton>
      <AppButton :disabled="loading || sourceLoading || !sourceTask" @click="openSourceTask">来源教学任务（形成时快照）</AppButton>
    </template>

    <AaOperationReceipt :receipt="receipt" />
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
          <div><span>形成时来源批次</span><b>{{ sourceTask ? `#${sourceTask.batchId} · 跳转前重新核对` : '未提供完整快照，不能定位来源' }}</b></div>
          <div><span>行政班来源</span><b>{{ teachingClass.administrativeClassName || teachingClass.administrativeClassId || '非行政班来源' }}</b></div>
          <div><span>容量</span><b>{{ teachingClass.capacity ?? '未设置' }}</b></div>
          <div><span>预计人数</span><b>{{ teachingClass.expectedStudents ?? '未设置' }}</b></div>
        </div>
      </AppSectionCard>

      <AppSectionCard title="教师关系">
        <div class="aa-section-toolbar">
          <div class="mp-cell-sub">主讲与共同授课教师均按有效周次参与课表、考勤、成绩与工作量办理。</div>
          <AppButton v-if="canManageTeacherRelations" variant="primary" @click="openCreateTeacher">新增共同授课</AppButton>
        </div>
        <AppInlineAlert
          v-if="!canManageTeachingClass"
          type="info"
          title="教师关系只读"
          description="当前账号没有教学班管理权限；可查看正式教师关系与历史授课周次，但不能新增、调整或停用。"
        />
        <AppInlineAlert
          v-else-if="teachingClass.status !== 'ACTIVE'"
          type="info"
          title="教学班已归档，教师关系只读"
          description="历史教师身份和授课周次继续保留用于审计，不允许覆盖。"
        />
        <EmptyState v-if="!teachingClass.teachers.length" title="尚未绑定教师" description="请回到教学任务分配稳定教师工号" />
        <DataTable v-else :columns="teacherColumns" :rows="teachingClass.teachers" row-key="teacherRelationId">
          <template #cell-teacher="{ row }"><div class="mp-cell-main">{{ row.teacherName || '—' }}</div><div class="mp-cell-sub">{{ row.teacherKey }}</div></template>
          <template #cell-roleType="{ row }">{{ teacherRoleLabel(row.roleType) }}</template>
          <template #cell-weeks="{ row }">第{{ row.startWeek || '?' }}—{{ row.endWeek || '?' }}周</template>
          <template #cell-status="{ row }"><AppStatusTag :type="row.status === 'ACTIVE' ? 'success' : 'info'" :label="relationStatusLabel(row.status)" /></template>
          <template #cell-actions="{ row }">
            <div v-if="row.status === 'ACTIVE' && canManageTeacherRelations" class="aa-row-actions">
              <button class="mp-link" @click="openEditTeacher(row)">调整</button>
              <button v-if="row.roleType === 'CO_TEACHER'" class="mp-link is-danger" @click="openDeactivateTeacher(row)">停用</button>
            </div>
            <span v-else class="mp-cell-sub">—</span>
          </template>
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
        <template v-else-if="canManageTeacherRelations">
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
        <AppInlineAlert v-else type="info" title="当前名单只读" description="需要教学班管理权限且教学班使用中，才能预览和创建名单版本。" />
      </AppSectionCard>

      <AppSectionCard title="名单版本历史">
        <EmptyState v-if="!teachingClass.rosterVersions.length" title="暂无名单版本" description="系统不会把临时推导名单伪装成已锁定版本" />
        <DataTable v-else :columns="versionColumns" :rows="teachingClass.rosterVersions" row-key="rosterVersionId">
          <template #cell-version="{ row }"><div class="mp-cell-main">第 {{ row.versionNo }} 版</div><div class="mp-cell-sub">{{ row.rosterVersionId }}</div></template>
          <template #cell-source="{ row }"><AppStatusTag :type="row.sourceType === 'SELECTION_LOCK' ? 'success' : 'info'" :label="sourceLabel(row.sourceType)" /><div class="mp-cell-sub">{{ row.sourceId || '—' }}</div></template>
          <template #cell-status="{ row }"><AppStatusTag :type="row.status === 'LOCKED' ? 'success' : 'info'" :label="versionStatusLabel(row.status)" /></template>
          <template #cell-locked="{ row }"><div>{{ row.lockedAt || '—' }}</div><div class="mp-cell-sub">{{ row.lockedBy || '未提供办理人' }}</div></template>
        </DataTable>
      </AppSectionCard>
    </div>

    <AppConfirmDialog
      v-model:visible="teacherEditor.visible"
      :title="teacherEditor.mode === 'create' ? '新增共同授课教师' : '调整正式教师关系'"
      type="primary"
      :confirm-text="teacherEditor.mode === 'create' ? '确认新增' : '确认调整'"
      :submitting="teacherEditor.submitting"
      @confirm="submitTeacherRelation"
    >
      <div class="aa-teacher-form">
        <label>授课教师
          <AppTeacherPicker v-model="teacherEditor.teacherKey" :query="teacherKeyQuery" placeholder="选择正式教师账号" />
        </label>
        <label>关系角色
          <input class="aa-input" :value="teacherRoleLabel(teacherEditor.roleType)" disabled />
        </label>
        <label>开始周
          <input v-model.number="teacherEditor.startWeek" type="number" min="1" max="60" class="aa-input" placeholder="默认教学任务开始周" />
        </label>
        <label>结束周
          <input v-model.number="teacherEditor.endWeek" type="number" min="1" max="60" class="aa-input" placeholder="默认教学任务结束周" />
        </label>
        <label class="is-wide">变更原因
          <textarea v-model.trim="teacherEditor.reason" class="aa-textarea" maxlength="500" placeholder="不少于5字；冲突与周次覆盖由服务端最终校验" />
        </label>
      </div>
    </AppConfirmDialog>

    <AppConfirmDialog
      v-model:visible="teacherDeactivate.visible"
      title="停用共同授课教师"
      type="danger"
      confirm-text="确认停用"
      :submitting="teacherDeactivate.submitting"
      @confirm="deactivateTeacherRelation"
    >
      <div class="aa-teacher-form">
        <AppInlineAlert
          type="warning"
          title="停用会立即影响后续授课权限"
          :description="`${teacherDeactivate.teacherName || '该教师'} 的历史授课关系会保留，但后续课表、考勤、成绩与工作量将按剩余正式关系重新裁决。`"
        />
        <label class="is-wide">停用原因
          <textarea v-model.trim="teacherDeactivate.reason" class="aa-textarea" maxlength="500" placeholder="不少于5字" />
        </label>
      </div>
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppInlineAlert, AppSectionCard, AppStatusTag, AppStudentPicker, AppTeacherPicker, AppConfirmDialog } from '@/components/common'
import { teachingClassApi } from '@/modules/academicAffairs/api/teaching-class.api'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { teachingTaskWorkbenchApi } from '@/modules/academicAffairs/api/teaching-task-workbench.api'
import { readTaskPages } from '../components/parallel-a/taskFacts'
import { getPermissionPatterns } from '@/security/permissionGate'
import { matchPermission } from '@/config/navPlan'
import { toast } from '@/utils/toast'
import AaOperationReceipt from '../components/parallel-a/AaOperationReceipt.vue'
import { isDeniedResult, isConflictResult } from '../components/parallel-a/resultState'

function emptyTeacherEditor() {
  return { visible: false, submitting: false, mode: 'create', relationId: '', roleType: 'CO_TEACHER', teacherKey: '', startWeek: null, endWeek: null, reason: '' }
}

export default {
  name: 'AaTeachingClassDetailView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppInlineAlert, AppSectionCard, AppStatusTag, AppStudentPicker, AppTeacherPicker, AppConfirmDialog, AaOperationReceipt },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', teachingClass: null, sourceLoading: false,
      previewing: false, saving: false, rosterImpact: null,
      revision: 0, previewRevision: 0, previewKey: '', receipt: null,
      rosterForm: { studentIds: [], reason: '' },
      teacherEditor: emptyTeacherEditor(), teacherKeyQuery: { valueField: 'loginName' },
      teacherDeactivate: { visible: false, submitting: false, relationId: '', teacherName: '', reason: '' },
      teacherColumns: [{ key: 'teacher', title: '教师' }, { key: 'roleType', title: '角色' }, { key: 'weeks', title: '授课周次' }, { key: 'status', title: '状态' }, { key: 'actions', title: '操作', width: '120px' }],
      memberColumns: [{ key: 'student', title: '学生' }, { key: 'classId', title: '行政班ID' }, { key: 'source', title: '成员来源' }, { key: 'status', title: '状态' }],
      versionColumns: [{ key: 'version', title: '版本' }, { key: 'source', title: '来源' }, { key: 'memberCount', title: '人数' }, { key: 'reason', title: '形成原因' }, { key: 'locked', title: '锁定信息' }, { key: 'status', title: '状态' }]
    }
  },
  computed: {
    sourceTask() {
      const source = this.teachingClass?.sourceSnapshot
      if (!source || !/^[1-9]\d*$/.test(String(source.batchId || '')) || !/^[1-9]\d*$/.test(String(source.teachingTaskId || '')) || String(source.teachingTaskId) !== String(this.teachingClass.teachingTaskId)) return null
      return { batchId: String(source.batchId), taskId: String(source.teachingTaskId) }
    },
    teachingClassId() { return String(this.$route.query.teachingClassId || this.$route.params.teachingClassId || '') },
    activeTeacher() { return (this.teachingClass?.teachers || []).find(row => row.roleType === 'PRIMARY' && row.status === 'ACTIVE') },
    canManageTeachingClass() {
      const patterns = getPermissionPatterns()
      return Array.isArray(patterns) && matchPermission(patterns, 'academicAffairs.teachingTask.manage')
    },
    canManageTeacherRelations() { return this.canManageTeachingClass && this.teachingClass?.status === 'ACTIVE' },
    rosterKey() {
      return JSON.stringify([this.teachingClassId, this.teachingClass?.currentRosterVersionId, this.teachingClass?.rosterVersionNo, [...new Set(this.rosterForm.studentIds.map(String))].sort()])
    },
    canCreateRosterVersion() {
      return Boolean(
        this.canManageTeacherRelations && !this.teachingClass?.rosterManagement?.managedBySelection
        && this.rosterImpact?.canCreate && this.previewKey === this.rosterKey
        && this.rosterForm.reason.trim().length >= 5
        && !this.saving && !this.previewing && !this.loading
      )
    },
    impactDescription() {
      if (!this.rosterImpact?.changed) return '拟提交名单与当前正式名单一致，无需创建新版本。'
      if (this.rosterImpact?.impact?.blocked) return this.rosterImpact.impact.blockerMessage || '下游已消费当前名单，暂不能直接变更。'
      return `新版本将由 ${this.rosterImpact.currentMemberCount} 人调整为 ${this.rosterImpact.proposedMemberCount} 人，历史版本继续保留。`
    }
  },
  created() { this.load() },
  watch: {
    teachingClassId() {
      this.teacherEditor = emptyTeacherEditor(); this.teacherDeactivate = { visible: false, submitting: false, reason: '' }
      this.rosterForm = { studentIds: [], reason: '' }; this.receipt = null; this.load()
    },
    rosterKey() { this.previewRevision++; this.previewing = false; this.previewKey = ''; this.rosterImpact = null }
  },
  beforeUnmount() { this.revision++; this.previewRevision++; this.disposed = true },
  methods: {
    backToClasses() {
      const target = this.$route.query.returnTo
      if (typeof target === 'string' && /^\/admin\/academic-affairs\/teaching-tasks\?/.test(target)) {
        const query = new URLSearchParams(target.split('?')[1])
        if (query.get('view') === 'classes' && !query.has('teachingClassId')) { this.$router.push(target); return }
      }
      this.$router.push({ path: '/admin/academic-affairs/teaching-tasks', query: { view: 'classes', termId: this.$route.query.termId || this.teachingClass?.termId || undefined } })
    },
    async openSourceTask() {
      if (!this.sourceTask || this.sourceLoading || this.loading) return
      const source = { ...this.sourceTask }, context = this.ctx, revision = this.revision, classId = this.teachingClassId
      const current = () => !this.disposed && revision === this.revision && context === this.ctx && classId === this.teachingClassId
      this.sourceLoading = true
      try {
        const batch = await teachingTaskWorkbenchApi.getBatch(source.batchId)
        if (!current()) return
        if (batch.code !== 0) { this.handleFailure(batch, '来源批次当前不可读。'); return }
        if (String(batch.data?.batchId) !== source.batchId) { this.handleFailure({ code: 409001, message: '来源批次返回了不同对象，不能跳转。' }); return }
        const tasks = await readTaskPages(page => academicAffairsApi.getBatchTasks(source.batchId, page), current)
        if (!current()) return
        if (tasks?.code !== 0) { this.handleFailure(tasks, '来源任务读取失败。'); return }
        if (!tasks.data.list.some(row => String(row.taskId) === source.taskId)) { this.handleFailure({ code: 409001, message: '形成时来源任务已不在该批次，请由教务核对历史来源。' }); return }
        this.$router.push({ path: `/admin/academic-affairs/teaching-tasks/${source.batchId}`, query: { teachingTaskId: source.taskId, returnTo: this.$route.fullPath } })
      } catch (error) { if (current()) this.handleFailure(error, '来源读取失败，请重试；未跳转。') }
      finally { this.sourceLoading = false }
    },
    classTypeLabel(value) { return ({ ADMIN: '行政班开课', SELECTION: '选课教学班', MERGED: '合班教学班', RETAKE: '重修教学班', LAYERED: '分层教学班' })[value] || (value ? '待确认' : '—') },
    classStatusLabel(value) { return ({ ACTIVE: '使用中', ARCHIVED: '已归档' })[value] || (value ? '待确认' : '—') },
    taskStatusLabel(value) { return ({ PENDING_ASSIGN: '待分配', ASSIGNED: '已分配', TEACHER_CONFIRMED: '教师已确认', READY: '已就绪', MERGED: '已并入合班', REJECTED_BY_TEACHER: '教师已退回' })[value] || (value ? '待确认' : '—') },
    teacherRoleLabel(value) { return ({ PRIMARY: '主讲', CO_TEACHER: '协同授课' })[value] || (value ? '待确认' : '—') },
    relationStatusLabel(value) { return ({ ACTIVE: '生效', INACTIVE: '历史关系' })[value] || (value ? '待确认' : '—') },
    memberStatusLabel(value) { return ({ ACTIVE: '当前成员', REMOVED: '已移出' })[value] || (value ? '待确认' : '—') },
    versionStatusLabel(value) { return ({ LOCKED: '当前生效', SUPERSEDED: '历史版本' })[value] || (value ? '待确认' : '—') },
    sourceLabel(value) { return ({ ADMIN_CLASS: '行政班初始化', SELECTION_LOCK: '选课锁定', MANUAL: '人工版本', RETAKE: '重修名单' })[value] || (value ? '待确认' : '—') },
    async load(options = {}) {
      const revision = ++this.revision, id = this.teachingClassId
      this.previewRevision++; this.previewing = false; this.rosterImpact = null; this.previewKey = ''
      this.teachingClass = null
      if (!this.teachingClassId) { this.error = '缺少教学班ID'; this.loading = false; return }
      this.loading = true; this.error = ''
      try {
        const res = await teachingClassApi.detail(id)
        if (revision !== this.revision || id !== this.teachingClassId) return false
        if (res.code !== 0) { this.handleFailure(res, '加载教学班失败'); return false }
        this.teachingClass = res.data
        if (!options.preserveDraft) this.rosterForm.studentIds = (res.data.currentMembers || []).map(row => row.studentId)
        return true
      } catch (error) { if (revision === this.revision) this.handleFailure(error, '网络连接失败，请重试。'); return false }
      finally { if (revision === this.revision) this.loading = false }
    },
    handleFailure(result, fallback) {
      const message = result?.message || fallback
      this.previewRevision++; this.previewing = false; this.previewKey = ''; this.rosterImpact = null
      if (isDeniedResult(result)) {
        this.revision++; this.loading = false; this.teachingClass = null; this.receipt = null
        this.rosterForm = { studentIds: [], reason: '' }; this.teacherEditor = emptyTeacherEditor()
        this.teacherDeactivate = { visible: false, submitting: false, reason: '' }
        this.error = `${message}；已清除先前教学班内容。`
      } else {
        this.error = message
        if (isConflictResult(result)) this.receipt = { object: `教学班 #${this.teachingClassId}`, status: '事实已变化，保留输入', pending: true, next: '重新读取正式名单并预览影响后再提交。' }
      }
    },
    openCreateTeacher() {
      if (!this.canManageTeacherRelations) return
      this.teacherEditor = emptyTeacherEditor()
      this.teacherEditor.visible = true
    },
    openEditTeacher(row) {
      if (!this.canManageTeacherRelations || row.status !== 'ACTIVE') return
      this.teacherEditor = {
        visible: true,
        submitting: false,
        mode: 'edit',
        relationId: row.teacherRelationId,
        roleType: row.roleType,
        teacherKey: row.teacherKey || '',
        startWeek: row.startWeek ?? null,
        endWeek: row.endWeek ?? null,
        reason: ''
      }
    },
    async submitTeacherRelation() {
      const form = this.teacherEditor
      if (!this.canManageTeacherRelations || form.submitting) return
      if (!form.teacherKey) { toast.error('请选择授课教师'); return }
      if (form.reason.trim().length < 5) { toast.error('变更原因不少于5字'); return }
      if (form.startWeek && form.endWeek && Number(form.startWeek) > Number(form.endWeek)) { toast.error('开始周不能晚于结束周'); return }
      const body = {
        teacherKey: form.teacherKey,
        startWeek: form.startWeek || undefined,
        endWeek: form.endWeek || undefined,
        reason: form.reason.trim()
      }
      const id = this.teachingClassId
      await this.runTeacherChange(form, () => form.mode === 'create' ? teachingClassApi.createTeacher(id, body) : teachingClassApi.updateTeacher(id, form.relationId, body), relation => relation.status === 'ACTIVE' && relation.teacherKey === body.teacherKey && (body.startWeek === undefined || relation.startWeek === body.startWeek) && (body.endWeek === undefined || relation.endWeek === body.endWeek), '正式教师关系已更新')
    },
    openDeactivateTeacher(row) {
      if (!this.canManageTeacherRelations || row.status !== 'ACTIVE' || row.roleType !== 'CO_TEACHER') return
      this.teacherDeactivate = { visible: true, submitting: false, relationId: row.teacherRelationId, teacherName: row.teacherName || row.teacherKey || '', reason: '' }
    },
    async deactivateTeacherRelation() {
      const form = this.teacherDeactivate
      if (!this.canManageTeacherRelations || form.submitting) return
      if (form.reason.trim().length < 5) { toast.error('停用原因不少于5字'); return }
      const id = this.teachingClassId
      await this.runTeacherChange(form, () => teachingClassApi.deactivateTeacher(id, form.relationId, form.reason.trim()), relation => relation.status === 'INACTIVE', '共同授课关系已停用')
    },
    async runTeacherChange(form, command, matches, status) {
      const id = this.teachingClassId
      const current = () => !this.disposed && id === this.teachingClassId
      form.submitting = true
      this.receipt = { object: `教学班 #${id}`, status: '结果待确认', pending: true, next: '读取正式教师关系后确认本次办理结果。' }
      try {
        const result = await command()
        if (!current()) return
        if (result.code !== 0) { this.handleFailure(result, '教师关系办理失败'); return }
        const relationId = result.data?.teacherRelationId
        const loaded = await this.load({ preserveDraft: true })
        if (!current() || !loaded) return
        const relation = relationId && this.teachingClass.teachers.find(row => String(row.teacherRelationId) === String(relationId))
        const confirmed = relation && matches(relation)
        form.visible = false
        this.receipt = { object: `教学班 #${id} · 教师关系 #${relationId || '未返回'}`, status: confirmed ? status : '结果待确认', pending: !confirmed, next: confirmed ? '后续授课权限由服务端按正式关系和有效周次裁决；历史关系保留。' : '请重新查询正式教师关系，不要重复提交。' }
      } catch (error) { if (current()) this.handleFailure(error, '连接中断，请重新查询正式教师关系。') }
      finally { form.submitting = false }
    },
    async previewRoster() {
      if (!this.canManageTeacherRelations || this.teachingClass?.rosterManagement?.managedBySelection || !this.rosterForm.studentIds.length || this.previewing || this.saving) return false
      const id = this.teachingClassId, key = this.rosterKey, revision = ++this.previewRevision
      this.rosterImpact = null; this.previewKey = ''
      this.previewing = true
      try {
        const res = await teachingClassApi.previewRosterChange(id, [...this.rosterForm.studentIds])
        if (revision !== this.previewRevision || key !== this.rosterKey) return false
        if (res.code !== 0) { this.handleFailure(res, '影响预览失败'); return false }
        this.rosterImpact = res.data; this.previewKey = key
        return Boolean(res.data?.canCreate)
      } catch (error) { if (revision === this.previewRevision) this.handleFailure(error, '影响预览失败，尚未提交。'); return false }
      finally { if (revision === this.previewRevision) this.previewing = false }
    },
    async createRosterVersion() {
      if (!this.canCreateRosterVersion) return
      const id = this.teachingClassId, key = this.rosterKey
      const studentIds = [...this.rosterForm.studentIds], reason = this.rosterForm.reason.trim()
      this.saving = true
      const current = () => !this.disposed && id === this.teachingClassId
      try {
        const check = await teachingClassApi.previewRosterChange(id, studentIds)
        if (!current() || key !== this.rosterKey) return
        if (check.code !== 0) { this.handleFailure(check, '提交前预览失败，尚未提交。'); return }
        if (!check.data?.canCreate) { this.handleFailure({ code: 409001, message: '名单影响已变化，当前不能创建版本。' }); return }
        const result = await teachingClassApi.createRosterVersion(id, studentIds, reason)
        if (!current()) return
        if (result.code !== 0) { this.handleFailure(result, '名单创建失败'); return }
        const loaded = await this.load({ preserveDraft: true })
        if (!current() || !loaded) return
        const returnedVersion = result.data?.rosterVersionId
        const currentVersion = this.teachingClass.currentRosterVersionId
        const members = this.teachingClass.currentMembers.map(row => String(row.studentId)).sort()
        const confirmed = returnedVersion && String(returnedVersion) === String(currentVersion) && JSON.stringify(members) === JSON.stringify([...new Set(studentIds.map(String))].sort()) && this.teachingClass.rosterStatus === 'LOCKED'
        const version = confirmed ? this.teachingClass.rosterVersions?.find(row => String(row.rosterVersionId) === String(currentVersion)) : null
        this.receipt = { object: `教学班 #${id}`, status: confirmed ? `第${this.teachingClass.rosterVersionNo}版名单已生效` : '结果待确认', pending: !confirmed, time: version?.lockedAt, next: confirmed ? '历史版本保留；下游读取正式生效名单。' : '尚未读到一致的正式名单版本，请刷新核对，不要重复创建。' }
        if (confirmed) this.rosterForm.reason = ''
      } catch (error) { if (current()) this.handleFailure(error, '连接中断，请核对正式名单，勿重复创建。') }
      finally { this.saving = false }
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
.aa-section-toolbar { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 12px; }
.aa-row-actions { display: flex; gap: 10px; align-items: center; }
.mp-link.is-danger { color: var(--danger-600, #d54941); }
.aa-roster-editor { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) auto; gap: 14px; align-items: end; margin-top: 14px; }
.aa-roster-editor label, .aa-teacher-form label { display: flex; flex-direction: column; gap: 6px; color: var(--text-700, #4e5969); font-size: 13px; }
.aa-teacher-form { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.aa-teacher-form .is-wide { grid-column: 1 / -1; }
.aa-input { height: 34px; padding: 0 12px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 14px; box-sizing: border-box; }
.aa-textarea { min-height: 72px; resize: vertical; padding: 9px 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; font: inherit; }
.aa-roster-actions { display: flex; gap: 8px; padding-bottom: 1px; }
.aa-impact-grid { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 10px; }
.aa-impact-grid strong { font-size: 20px; }
@media (max-width: 1000px) { .aa-impact-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } .aa-roster-editor { grid-template-columns: 1fr; } }
@media (max-width: 900px) { .aa-summary-grid, .aa-facts, .aa-teacher-form { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 640px) { .aa-section-toolbar { align-items: stretch; flex-direction: column; } .aa-teacher-form { grid-template-columns: 1fr; } .aa-teacher-form .is-wide { grid-column: auto; } }
</style>
