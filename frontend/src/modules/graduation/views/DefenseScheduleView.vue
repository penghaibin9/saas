<template>
  <ModulePageShell
    title="答辩安排"
    subtitle="分组 / 时间 / 地点 / 评委 · 自动检测评委与导师回避 · 发布后学生端即时可见"
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

    <GraduationBatchStrip />
    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <EmptyState
      v-else-if="!rows.length"
      title="还没有答辩组"
      description="答辩要先建组：把学生分进组、排好时间地点，再发通知。评委可以从「答辩专家库」里选，不用每次重新录。"
    >
      <template #actions>
        <button class="mp-btn mp-btn--primary" @click="$router.push('/admin/graduation/defense/groups/create')">＋ 新增答辩组</button>
        <button class="mp-btn" @click="$router.push('/admin/graduation/more?panel=experts')">先维护答辩专家库</button>
        <button class="mp-btn" @click="$router.push('/admin/help?topic=gd-card-defense-grade')">怎么安排答辩？</button>
      </template>
    </EmptyState>
    <div v-else class="mp-stack">
      <!-- 编排摘要：一眼看清当前编排缺口，点击即过滤对应队列 -->
      <div class="ds-summary">
        <button v-for="c in summaryChips" :key="c.key" type="button" class="ds-chip" :class="['ds-chip--' + c.tone, { 'is-active': filterKey === c.key }]" @click="filterKey = filterKey === c.key ? 'all' : c.key">
          {{ c.label }} <b>{{ c.count }}</b>
        </button>
        <span class="mp-note" style="margin-left: auto">共 {{ totalStudents }} 名学生已入组</span>
      </div>
      <DataTable :columns="columns" :rows="filteredRows" row-key="id">
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
            @click="askPublish(row)"
          >发布</button>
          <button v-if="row.published" class="mp-link" style="margin-left: var(--space-2)" @click="notify(row)">通知</button>
        </template>
      </DataTable>
      <p class="mp-note">评委回避：评委/组长不得是本组学生的指导教师，系统自动检测并拦截发布；单组学生 ≤ 30 人。导出答辩表含水印与导出留痕。</p>
    </div>

    <AppConfirmDialog
      v-model:visible="confirm.visible" :title="confirm.title" :message="confirm.message"
      type="warning" confirm-text="确认发布" :submitting="submitting" @confirm="doPublish"
    />
    <!-- 首次进入本模块时的 4 步说明；「已看过」存后端偏好，顶栏「?」可重看 -->
    <AppPageGuide guide-key="graduation.gd-defense" />
  </ModulePageShell>
</template>

<script>
/** 答辩安排（/admin/graduation/defense）：答辩组 CRUD + 学生分配 + 评委回避 + 发布 + 导出。 */
import { ModulePageShell, ModuleToolbar, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppDateDisplay } from '@/components/common/date'
import { AppExportButton, AppPageGuide } from '@/components/common'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { graduationApi } from '@/modules/graduation/api/graduation.api'
import { graduationMoreApi } from '@/modules/graduation/api/graduation-more.api'
import { toast } from '@/utils/toast'

import GraduationBatchStrip from './_shared/GraduationBatchStrip.vue'

export default {
  name: 'DefenseScheduleView',
  components: { AppPageGuide, GraduationBatchStrip, ModulePageShell, ModuleToolbar, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppDateDisplay, AppExportButton, AppConfirmDialog },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', rows: [], submitting: false,
      filterKey: 'all',
      confirm: { visible: false, title: '', message: '', row: null },
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
    summaryChips() {
      const r = this.rows
      return [
        { key: 'all', label: '答辩组', count: r.length, tone: 'default' },
        { key: 'published', label: '已发布', count: r.filter((x) => x.published).length, tone: 'success' },
        { key: 'unpublished', label: '待发布', count: r.filter((x) => !x.published).length, tone: 'warning' },
        { key: 'conflict', label: '回避冲突', count: r.filter((x) => !!x.conflict).length, tone: 'danger' },
        { key: 'pending', label: '时间地点待定', count: r.filter((x) => x.date === '待定' || !x.location || x.location === '待定').length, tone: 'warning' }
      ]
    },
    totalStudents() {
      return this.rows.reduce((s, x) => s + (x.studentCount || 0), 0)
    },
    filteredRows() {
      const k = this.filterKey
      if (k === 'published') return this.rows.filter((x) => x.published)
      if (k === 'unpublished') return this.rows.filter((x) => !x.published)
      if (k === 'conflict') return this.rows.filter((x) => !!x.conflict)
      if (k === 'pending') return this.rows.filter((x) => x.date === '待定' || !x.location || x.location === '待定')
      return this.rows
    },
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
    askPublish(row) {
      if (!this.canPublish || row.conflict) return
      this.confirm = {
        visible: true,
        title: '发布答辩安排',
        message: `确认发布「${row.groupName}」？发布后 ${row.studentCount} 名学生的学生端即时可见，发布动作写入留痕；后端将再次校验回避与完整性。`,
        row
      }
    },
    async doPublish() {
      const row = this.confirm.row
      if (!row) return
      this.submitting = true
      const res = await graduationApi.publishDefenseSchedule(row.id)
      this.submitting = false
      if (res.code === 0) {
        toast.success(row.groupName + ' 已发布：学生端即时可见，发布动作已留痕')
        this.confirm.visible = false
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
.ds-summary { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
.ds-chip { display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; border-radius: var(--radius-full, 999px); border: 1px solid var(--border-light, #e2e8f0); background: #fff; font: inherit; font-size: var(--font-size-sm, 13px); color: var(--text-secondary, #475569); cursor: pointer; transition: border-color .15s ease, background .15s ease, box-shadow .15s ease; }
.ds-chip:hover { border-color: var(--primary-200, #bfdbfe); background: var(--gray-50, #f8fafc); }
.ds-chip:focus-visible { outline: 2px solid var(--primary-400, #60a5fa); outline-offset: 2px; }
.ds-chip b { font-weight: 600; color: var(--text-primary, #0f172a); }
.ds-chip.is-active { border-color: var(--brand-primary, #2563eb); color: var(--brand-primary, #2563eb); background: var(--primary-50, #eff6ff); }
.ds-chip--danger b { color: var(--danger, #dc2626); }
.ds-chip--warning b { color: var(--warning-600, #d97706); }
.ds-chip--success b { color: var(--success-600, #16a34a); }
.gd-actions { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
@media (max-width: 700px) { .ds-summary .mp-note { width: 100%; margin-left: 0 !important; } }
</style>
