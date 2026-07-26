<template>
  <ModulePageShell
    title="教学班详情"
    :subtitle="teachingClass ? `${teachingClass.classCode} · ${teachingClass.courseName || teachingClass.className}` : '查看教师关系、当前成员与名单版本历史'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="$router.push('/admin/academic-affairs/teaching-classes')">返回教学班</AppButton>
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
        :description="teachingClass.rosterStatus === 'LOCKED' ? '考勤、考务和成绩应读取本版本；名单变化必须生成新版本，不直接覆盖历史成员。' : '返回教学班列表运行存量对账，或完成选课名单锁定。'"
      />

      <AppSectionCard title="教学班事实">
        <div class="aa-facts">
          <div><span>教学班编号</span><b>{{ teachingClass.classCode }}</b></div>
          <div><span>状态</span><b><AppStatusTag :status="teachingClass.status" /></b></div>
          <div><span>来源任务</span><b>#{{ teachingClass.teachingTaskId }} · {{ teachingClass.taskStatus }}</b></div>
          <div><span>行政班来源</span><b>{{ teachingClass.administrativeClassName || teachingClass.administrativeClassId || '非行政班来源' }}</b></div>
          <div><span>容量</span><b>{{ teachingClass.capacity ?? '未设置' }}</b></div>
          <div><span>预计人数兼容字段</span><b>{{ teachingClass.expectedStudents ?? '未设置' }}</b></div>
        </div>
      </AppSectionCard>

      <AppSectionCard title="教师关系">
        <EmptyState v-if="!teachingClass.teachers.length" title="尚未绑定教师" description="请回到教学任务分配稳定教师工号" />
        <DataTable v-else :columns="teacherColumns" :rows="teachingClass.teachers" row-key="teacherRelationId">
          <template #cell-teacher="{ row }"><div class="mp-cell-main">{{ row.teacherName || '—' }}</div><div class="mp-cell-sub">{{ row.teacherKey }}</div></template>
          <template #cell-weeks="{ row }">第{{ row.startWeek || '?' }}—{{ row.endWeek || '?' }}周</template>
          <template #cell-status="{ row }"><AppStatusTag :status="row.status" /></template>
        </DataTable>
      </AppSectionCard>

      <AppSectionCard :title="`当前正式成员（${teachingClass.currentMembers.length}人）`">
        <EmptyState v-if="!teachingClass.currentMembers.length" title="当前版本没有有效成员" description="名单为空或存在学生主档欠账，不能继续下游业务" />
        <DataTable v-else :columns="memberColumns" :rows="teachingClass.currentMembers" row-key="memberId">
          <template #cell-student="{ row }"><div class="mp-cell-main">{{ row.realName }}</div><div class="mp-cell-sub">{{ row.studentNo || row.studentId }}</div></template>
          <template #cell-source="{ row }"><AppStatusTag :type="row.sourceType === 'SELECTION_LOCK' ? 'success' : 'info'" :label="sourceLabel(row.sourceType)" /><div class="mp-cell-sub">{{ row.sourceId ? `来源 ${row.sourceId}` : '—' }}</div></template>
          <template #cell-status="{ row }"><AppStatusTag :status="row.status" /></template>
        </DataTable>
      </AppSectionCard>

      <AppSectionCard title="名单版本历史">
        <EmptyState v-if="!teachingClass.rosterVersions.length" title="暂无名单版本" description="系统不会把临时推导名单伪装成已锁定版本" />
        <DataTable v-else :columns="versionColumns" :rows="teachingClass.rosterVersions" row-key="rosterVersionId">
          <template #cell-version="{ row }"><div class="mp-cell-main">第 {{ row.versionNo }} 版</div><div class="mp-cell-sub">{{ row.rosterVersionId }}</div></template>
          <template #cell-source="{ row }"><AppStatusTag :type="row.sourceType === 'SELECTION_LOCK' ? 'success' : 'info'" :label="sourceLabel(row.sourceType)" /><div class="mp-cell-sub">{{ row.sourceId || '—' }}</div></template>
          <template #cell-status="{ row }"><AppStatusTag :status="row.status" /></template>
          <template #cell-locked="{ row }"><div>{{ row.lockedAt || '—' }}</div><div class="mp-cell-sub">{{ row.lockedBy || '系统' }}</div></template>
        </DataTable>
      </AppSectionCard>
    </div>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppInlineAlert, AppSectionCard, AppStatusTag } from '@/components/common'
import { teachingClassApi } from '@/modules/academicAffairs/api/teaching-class.api'

export default {
  name: 'AaTeachingClassDetailView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppInlineAlert, AppSectionCard, AppStatusTag },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', teachingClass: null,
      teacherColumns: [{ key: 'teacher', title: '教师' }, { key: 'roleType', title: '角色' }, { key: 'weeks', title: '授课周次' }, { key: 'status', title: '状态' }],
      memberColumns: [{ key: 'student', title: '学生' }, { key: 'classId', title: '行政班ID' }, { key: 'source', title: '成员来源' }, { key: 'status', title: '状态' }],
      versionColumns: [{ key: 'version', title: '版本' }, { key: 'source', title: '来源' }, { key: 'memberCount', title: '人数' }, { key: 'reason', title: '形成原因' }, { key: 'locked', title: '锁定信息' }, { key: 'status', title: '状态' }]
    }
  },
  computed: {
    teachingClassId() { return String(this.$route.params.teachingClassId || '') },
    activeTeacher() { return (this.teachingClass?.teachers || []).find(row => row.roleType === 'PRIMARY' && row.status === 'ACTIVE') }
  },
  created() { this.load() },
  methods: {
    classTypeLabel(value) { return ({ ADMIN: '行政班开课', SELECTION: '选课教学班', MERGED: '合班教学班', RETAKE: '重修教学班', LAYERED: '分层教学班' })[value] || value || '—' },
    sourceLabel(value) { return ({ ADMIN_CLASS: '行政班初始化', SELECTION_LOCK: '选课锁定', MANUAL: '人工版本', RETAKE: '重修名单' })[value] || value || '—' },
    async load() {
      this.loading = true; this.error = ''
      const res = await teachingClassApi.detail(this.teachingClassId)
      if (res.code === 0) this.teachingClass = res.data
      else { this.teachingClass = null; this.error = res.message || '加载教学班失败' }
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-summary-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.aa-summary-grid > div { padding: 14px 16px; border: 1px solid var(--border-200, #e5e7eb); border-radius: 8px; background: var(--bg-white, #fff); }
.aa-summary-grid strong, .aa-summary-grid span { display: block; }
.aa-summary-grid strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 18px; }
.aa-summary-grid span { margin-top: 4px; color: var(--text-500, #64748b); font-size: 12px; }
.aa-summary-grid .is-danger { border-color: var(--danger-200, #fecaca); }
.aa-facts { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.aa-facts > div { padding: 12px; border: 1px solid var(--border-200, #e5e7eb); border-radius: 6px; }
.aa-facts span, .aa-facts b { display: block; }.aa-facts span { color: var(--text-500, #64748b); font-size: 12px; }.aa-facts b { margin-top: 4px; }
@media (max-width: 900px) { .aa-summary-grid, .aa-facts { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>
