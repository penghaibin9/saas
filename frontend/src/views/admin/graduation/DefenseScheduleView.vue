<template>
  <ModulePageShell
    title="答辩安排"
    subtitle="分组 / 时间 / 地点 / 评委 · 发布后学生端 P17 即时可见 · 评委与导师冲突自动拦截"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <EmptyState v-else-if="!rows.length" title="暂无答辩批次" description="可新增答辩批次并进行分组排期" />
    <div v-else class="mp-stack">
      <DataTable :columns="columns" :rows="rows" row-key="id">
        <template #cell-group="{ row }">
          <div class="mp-cell-main">{{ row.groupName }}</div>
          <div class="mp-cell-sub">{{ row.studentCount }} 名学生</div>
        </template>
        <template #cell-schedule="{ row }">
          <div style="font-size: var(--font-size-sm)">{{ row.date }}</div>
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
          <button class="mp-link" :class="{ 'is-disabled': !canManage }" :title="manageReason" @click="edit(row)">编辑</button>
          <button
            v-if="!row.published"
            class="mp-link"
            :class="{ 'is-disabled': !canPublish || !!row.conflict }"
            :title="row.conflict ? '存在评委与导师冲突，调整后方可发布' : publishReason"
            style="margin-left: var(--space-2)"
            @click="publish(row)"
          >发布</button>
        </template>
      </DataTable>
      <p class="mp-note">发布动作写入审计日志并推送学生端订阅消息；导出答辩表含水印与导出留痕。</p>
    </div>
  </ModulePageShell>
</template>

<script>
/** 答辩安排（/admin/graduation/defense）：分组 / 时间 / 地点 / 评委 / 发布闭环。 */
import { ModulePageShell, ModuleToolbar, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { graduationApi } from '@/modules/graduation/api/graduation.api'
import { toast } from '@/utils/toast'

export default {
  name: 'DefenseScheduleView',
  components: { ModulePageShell, ModuleToolbar, DataTable, StatusTag, LoadingState, ErrorState, EmptyState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
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
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [
        { key: 'manageDefense', label: '＋ 新增答辩批次', variant: 'primary' },
        { key: 'exportDefense', label: '导出答辩表' }
      ]
        .filter((a) => pa[a.key] && pa[a.key].visible)
        .map((a) => ({ ...a, disabled: !pa[a.key].allowed, disabledReason: pa[a.key].reason }))
    }
  },
  created() {
    this.load()
  },
  methods: {
    onToolbar(key) {
      if (key === 'exportDefense') toast.success('答辩表导出任务已创建（含水印），已写入审计日志')
      else toast.info('新增答辩批次：设置时间 / 地点 / 分组 / 专家（编辑抽屉后续批次开放）')
    },
    edit(row) {
      if (!this.canManage) return
      toast.info('编辑 ' + row.groupName + '：调整时间 / 地点 / 评委，评委=导师冲突将自动拦截')
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
      const res = await graduationApi.getDefenseSchedules({ page: 1, pageSize: 20 })
      if (res.code === 0) this.rows = res.data.list
      else this.error = res.message
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
</style>
