<template>
  <ModulePageShell
    title="答辩安排"
    subtitle="分组 / 时间 / 地点 / 评委 · 评委回避导师自动检测 · 发布后学生端 P17 即时可见"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <div class="gd-actions">
        <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
        <AppExportButton
          v-if="exportPerm.visible"
          :export-fn="exportDefenseFn"
          :has-permission="exportPerm.allowed"
        >导出答辩表</AppExportButton>
      </div>
    </template>

    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <EmptyState v-else-if="!rows.length" title="暂无答辩组" description="点击「新增答辩组」创建分组并排期" />
    <div v-else class="mp-stack">
      <DataTable :columns="columns" :rows="rows" row-key="id">
        <template #cell-group="{ row }">
          <div class="mp-cell-main">{{ row.groupName }}</div>
          <div class="mp-cell-sub">{{ row.studentCount }} 名学生</div>
        </template>
        <template #cell-schedule="{ row }">
          <div style="font-size: var(--font-size-sm)"><AppDateDisplay :value="row.date === '待定' ? '' : row.date" mode="datetime" empty-text="待定" /></div>
          <div class="mp-cell-sub">{{ row.location }}</div>
        </template>
        <template #cell-panel="{ row }">
          <div style="font-size: var(--font-size-sm)">组长：{{ row.chair }}</div>
          <div class="mp-cell-sub">
            {{ row.members.length ? '评委：' + row.members.join('、') : '评委待安排' }} · 秘书：{{ row.secretary }}
          </div>
          <div v-if="row.conflict" class="mp-cell-sub" style="color: var(--danger-600)">⚠ {{ row.conflict }}</div>
        </template>
        <template #cell-published="{ row }">
          <StatusTag :type="row.published ? 'success' : row.conflict ? 'danger' : 'warning'" :label="row.publishedLabel" dot />
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" :class="{ 'is-disabled': !canManage }" :title="manageReason" @click="openEdit(row)">编辑</button>
          <button
            v-if="!row.published"
            class="mp-link"
            :class="{ 'is-disabled': !canPublish || !!row.conflict }"
            :title="row.conflict ? '存在评委与导师冲突，调整后方可发布' : publishReason"
            style="margin-left: var(--space-2)"
            @click="publish(row)"
          >发布</button>
          <button v-if="row.published" class="mp-link" style="margin-left: var(--space-2)" @click="notify(row)">通知</button>
        </template>
      </DataTable>
      <p class="mp-note">评委回避：评委/组长不得是本组学生的指导教师，系统自动检测并拦截发布；单组学生 ≤ 30 人。导出答辩表含水印与导出留痕。</p>
    </div>
  </ModulePageShell>
</template>

<script>
/** 答辩安排（/admin/graduation/defense）：答辩组 CRUD + 学生分配 + 评委回避 + 发布 + 导出。 */
import { ModulePageShell, ModuleToolbar, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppDateDisplay } from '@/components/common/date'
import { AppExportButton } from '@/components/common'
import { graduationApi } from '@/modules/graduation/api/graduation.api'
import { graduationMoreApi } from '@/modules/graduation/api/graduation-more.api'
import { toast } from '@/utils/toast'

export default {
  name: 'DefenseScheduleView',
  components: { ModulePageShell, ModuleToolbar, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppDateDisplay, AppExportButton },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', rows: [], submitting: false,
      columns: [
        { key: 'group', title: '答辩分组' },
        { key: 'schedule', title: '时间 / 地点' },
        { key: 'panel', title: '评委 / 秘书' },
        { key: 'published', title: '学生端发布状态' },
        { key: 'actions', title: '操作', width: '110px' }
      ]
    }
  },
  computed: {
    canManage() {
      const pa = this.ctx.permissionActions.manageDefense
      return !!(pa && pa.visible && pa.allowed)
    },
    manageReason() {
      const pa = this.ctx.permissionActions.manageDefense
      return pa && !pa.allowed ? pa.reason : ''
    },
    canPublish() {
      const pa = this.ctx.permissionActions.publishDefense
      return !!(pa && pa.visible && pa.allowed)
    },
    publishReason() {
      const pa = this.ctx.permissionActions.publishDefense
      return pa && !pa.allowed ? pa.reason : ''
    },
    exportPerm() {
      const pa = this.ctx.permissionActions.exportDefense || {}
      return { visible: !!pa.visible, allowed: !!pa.allowed }
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [{ key: 'manageDefense', label: '＋ 新增答辩组', variant: 'primary' }]
        .filter((a) => pa[a.key] && pa[a.key].visible)
        .map((a) => ({ ...a, disabled: !pa[a.key].allowed, disabledReason: pa[a.key].reason }))
    }
  },
  created() {
    this.load()
  },
  methods: {
    async onToolbar(key) {
      if (key === 'manageDefense' && this.canManage) {
        this.$router.push('/admin/graduation/defense/groups/create')
      }
    },
    exportDefenseFn() {
      return graduationApi.exportDefenseGroups()
    },
    openCreate() {
      this.$router.push('/admin/graduation/defense/groups/create')
    },
    openEdit(row) {
      if (!this.canManage) return
      this.$router.push(`/admin/graduation/defense/groups/${row.id}/edit`)
    },
    async notify(row) {
      const res = await graduationMoreApi.notifyDefense(row.id)
      if (res.code === 0) toast.success(res.data.notified ? `已向 ${res.data.notified} 名学生发送答辩通知` : (res.message || '暂无可通知学生'))
      else toast.error(res.message || '通知失败')
    },
    async publish(row) {
      if (!this.canPublish || row.conflict) return
      const res = await graduationApi.publishDefenseSchedule(row.id)
      if (res.code === 0) {
        toast.success(row.groupName + ' 已发布：学生端 P17 即时可见，发布动作已留痕')
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await graduationApi.getDefenseSchedules({ page: 1, pageSize: 50 })
      if (res.code === 0) this.rows = res.data.list
      else this.error = res.message
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.gd-actions { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
</style>
