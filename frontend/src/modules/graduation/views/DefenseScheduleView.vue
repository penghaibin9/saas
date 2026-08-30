<template>
  <ModulePageShell
    title="答辩安排"
    :subtitle="pageSubtitle"
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
    <EmptyState
      v-else-if="!rows.length"
      :title="hasBatch ? '还没有答辩组' : '请先选择或创建毕设批次'"
      :description="hasBatch ? '答辩要先建组：把学生分进组、排好时间地点，再发通知。评委可以从「答辩专家库」里选，不用每次重新录。' : '顶部批次条选择当前工作批次后，再安排答辩。'"
    >
      <template v-if="hasBatch" #actions>
        <button v-if="canCreateGroup" class="mp-btn mp-btn--primary" @click="$router.push('/admin/graduation/defense/groups/create')">＋ 新增答辩组</button>
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
            {{ row.members.length ? '评委：' + memberNames(row).join('、') : '评委待安排' }} · 秘书：{{ row.secretary }}
          </div>
          <div v-if="row.conflict" class="mp-cell-sub" style="color: var(--danger-600)">⚠ {{ row.conflict }}</div>
          <div v-else-if="!publishPreflight(row).ready" class="mp-cell-sub ds-preflight-warning">发布前：{{ publishPreflight(row).summary }}</div>
        </template>
        <template #cell-published="{ row }">
          <StatusTag :type="row.published ? 'success' : row.conflict ? 'danger' : 'warning'" :label="row.publishedLabel" dot />
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" :class="{ 'is-disabled': !canManage }" :title="manageReason" @click="openEdit(row)">编辑</button>
          <button
            v-if="!row.published"
            class="mp-link"
            :class="{ 'is-disabled': !canPublish || !publishPreflight(row).ready }"
            :title="!publishPreflight(row).ready ? publishPreflight(row).summary : publishReason"
            style="margin-left: var(--space-2)"
            @click="askPublish(row)"
          >发布</button>
          <button v-if="row.published" class="mp-link" style="margin-left: var(--space-2)" @click="notify(row)">通知</button>
        </template>
      </DataTable>
      <p class="mp-note">评委回避：评委/组长不得是本组学生的指导教师，系统自动检测并拦截发布；单组学生 ≤ 30 人。导出答辩表含水印与导出留痕。</p>
      <aside v-if="actionReceipt" class="ds-receipt" role="status">
        <div><strong>{{ actionReceipt.title }}</strong><span>{{ actionReceipt.result }}</span><small>{{ actionReceipt.next }}</small></div>
        <button type="button" @click="actionReceipt = null">关闭</button>
      </aside>
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
import { exportFilenameHint } from '@/modules/graduation/utils/queryParams'
import { useGraduationBatchStore } from '@/stores/graduationBatch'
import { toast } from '@/utils/toast'

export default {
  name: 'DefenseScheduleView',
  components: { AppPageGuide, ModulePageShell, ModuleToolbar, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppDateDisplay, AppExportButton, AppConfirmDialog },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      batchStore: useGraduationBatchStore(),
      loading: true, error: '', rows: [], submitting: false,
      filterKey: 'all',
      actionReceipt: null,
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
    hasBatch() {
      return !!this.batchStore.selectedBatchId
    },
    pageSubtitle() {
      if (!this.hasBatch) return '请先在顶部选择或创建毕设批次'
      const batch = this.batchStore.selectedBatchName ? `${this.batchStore.selectedBatchName} · ` : ''
      return `${batch}分组 / 时间 / 地点 / 评委 · 自动检测评委与导师回避 · 发布后学生端即时可见`
    },
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
      return !!(pa && pa.visible && pa.allowed) && this.ctx.writeEnabled !== false
    },
    canCreateGroup() {
      const scopeName = String(this.ctx.dataScope?.scopeName || '')
      return this.canManage && scopeName.startsWith('本校毕设数据')
    },
    manageReason() {
      if (this.ctx.writeEnabled === false) return '写操作已禁用'
      const pa = this.ctx.permissionActions.manageDefense
      return pa && !pa.allowed ? pa.reason : ''
    },
    canPublish() {
      const pa = this.ctx.permissionActions.publishDefense
      return !!(pa && pa.visible && pa.allowed) && this.ctx.writeEnabled !== false
    },
    publishReason() {
      if (this.ctx.writeEnabled === false) return '写操作已禁用'
      const pa = this.ctx.permissionActions.publishDefense
      return pa && !pa.allowed ? pa.reason : ''
    },
    exportPerm() {
      const pa = this.ctx.permissionActions.exportDefense || {}
      return { visible: !!pa.visible && this.hasBatch, allowed: !!pa.allowed }
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [{ key: 'manageDefense', label: '＋ 新增答辩组', variant: 'primary' }]
        .filter((a) => pa[a.key] && pa[a.key].visible)
        .map((a) => ({
          ...a,
          disabled: !pa[a.key].allowed || !this.canCreateGroup || this.ctx.writeEnabled === false || !this.hasBatch,
          disabledReason: this.ctx.writeEnabled === false
            ? '写操作已禁用'
            : (!this.hasBatch
                ? '请先选择批次'
                : (!this.canCreateGroup ? '仅全校毕设管理员可新建或重新分配答辩组' : pa[a.key].reason))
        }))
    }
  },
  created() {
    this.load()
  },
  watch: {
    'batchStore.selectedBatchId'() {
      this.load()
    }
  },
  methods: {
    async onToolbar(key) {
      if (key === 'manageDefense' && this.canCreateGroup) {
        this.$router.push('/admin/graduation/defense/groups/create')
      }
    },
    exportDefenseFn() {
      const hint = exportFilenameHint(this.batchStore.selectedBatchName, '答辩安排')
      const p = { batchId: this.batchStore.selectedBatchId }
      return graduationApi.exportDefenseGroups(p).then((res) => {
        if (res.code === 0 && res.data) {
          res.data = { ...res.data, filename: res.data.filename || `${hint}.xlsx` }
        }
        return res
      })
    },
    openCreate() {
      if (!this.canCreateGroup) return
      this.$router.push('/admin/graduation/defense/groups/create')
    },
    openEdit(row) {
      if (!this.canManage) return
      this.$router.push(`/admin/graduation/defense/groups/${row.id}/edit`)
    },
    async notify(row) {
      const res = await graduationMoreApi.notifyDefense(row.id)
      if (res.code === 0) {
        const n = res.data?.notified || 0
        const msg = res.data?.message || res.message
        this.actionReceipt = {
          title: `${row.groupName} · 通知结果`,
          result: `服务器回执：已送达 ${n} 人；排队 ${res.data?.queued || 0} 人；待重试 ${Number(res.data?.pending || 0) + Number(res.data?.failed || 0)} 人`,
          next: res.data?.pending || res.data?.failed ? '发送队列会继续重试，无需重复点击。' : '当前无需继续操作。'
        }
        if (n > 0) toast.success(msg || `已向 ${n} 名学生发送答辩通知`)
        else toast.info(msg || '暂无可投递学生')
      } else toast.error(res.message || '通知失败')
    },
    askPublish(row) {
      const preflight = this.publishPreflight(row)
      if (!this.canPublish || !preflight.ready) {
        if (!preflight.ready) toast.error(`暂不能发布：${preflight.summary}`)
        return
      }
      this.confirm = {
        visible: true,
        title: '发布答辩安排',
        message: `发布前检查全部通过：${preflight.summary}。确认发布「${row.groupName}」？发布后 ${row.studentCount} 名学生的学生端即时可见，后端将再次校验回避与完整性。`,
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
        this.confirm.visible = false
        await this.load()
        const latest = this.rows.find(item => String(item.id) === String(row.id))
        this.actionReceipt = {
          title: `${row.groupName} 已发布`,
          result: `服务器最新状态：${latest?.published ? '已发布' : '状态待确认'}；${row.studentCount} 名学生可见`,
          next: '下一步：发送答辩通知；未送达项将进入重试队列。'
        }
        toast.success(row.groupName + ' 已发布，服务器最新状态已回读')
      } else {
        toast.error(res.message)
      }
    },
    async load() {
      if (!this.batchStore.selectedBatchId) {
        this.loading = false
        this.error = ''
        this.rows = []
        return
      }
      this.loading = true
      this.error = ''
      const res = await graduationApi.getDefenseSchedules({
        page: 1,
        pageSize: 50,
        batchId: this.batchStore.selectedBatchId
      })
      if (res.code === 0) this.rows = res.data.list
      else this.error = res.message
      this.loading = false
    },
    publishPreflight(row) {
      const members = Array.isArray(row?.members) ? row.members : []
      const missingJudges = (row?.chairMentorId ? 0 : 1) + members.filter(member => !(member?.mentorId || member?.expertId)).length
      const gaps = {
        missingJudges,
        conflicts: row?.conflict ? 1 : 0,
        missingLocation: !row?.location || row.location === '待定' ? 1 : 0,
        missingTime: !row?.date || row.date === '待定' ? 1 : 0,
        missingSecretary: row?.secretaryMentorId ? 0 : 1,
        students: Number(row?.studentCount || 0)
      }
      const ready = !gaps.missingJudges && !gaps.conflicts && !gaps.missingLocation && !gaps.missingTime && !gaps.missingSecretary && gaps.students > 0
      return { ...gaps, ready, summary: `缺稳定评委 ${gaps.missingJudges} · 回避冲突 ${gaps.conflicts} · 无地点 ${gaps.missingLocation} · 无时间 ${gaps.missingTime} · 缺秘书 ${gaps.missingSecretary} · 学生 ${gaps.students}` }
    },
    memberNames(row) {
      return (Array.isArray(row?.members) ? row.members : [])
        .map(member => typeof member === 'string' ? member : (member?.name || member?.teacherName || '未命名评委'))
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
.ds-preflight-warning{color:var(--warning-700,#a16207)!important}.ds-receipt{display:flex;align-items:center;gap:14px;padding:11px 12px;border:1px solid #b7ebc6;border-radius:9px;background:#f0fff4}.ds-receipt div{display:grid;gap:3px;flex:1}.ds-receipt strong{color:#137a43}.ds-receipt span{font-size:13px}.ds-receipt small{color:var(--text-tertiary)}.ds-receipt button{border:0;background:transparent;color:var(--primary-600);cursor:pointer}
.gd-actions { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
@media (max-width: 700px) { .ds-summary .mp-note { width: 100%; margin-left: 0 !important; } }
</style>
