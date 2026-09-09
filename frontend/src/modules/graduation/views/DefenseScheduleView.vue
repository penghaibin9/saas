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

    <section class="ds-command" aria-label="答辩编排结论">
      <div>
        <span>当前编排结论</span>
        <strong>{{ conclusion }}</strong>
        <small>发布前检查时间、地点、评委、秘书、回避冲突与学生数；正式结果只认服务端回执。</small>
      </div>
      <div class="ds-command__facts">
        <div><b>{{ rows.length }}</b><span>答辩组</span></div>
        <div><b>{{ totalStudents }}</b><span>已入组学生</span></div>
        <div><b>{{ publishReadyCount }}</b><span>前端预检通过</span></div>
        <div><b>{{ conflictCount }}</b><span>回避冲突</span></div>
      </div>
    </section>

    <aside v-if="actionReceipt" class="ds-receipt" role="status">
      <div><strong>{{ actionReceipt.title }}</strong><span>{{ actionReceipt.result }}</span><small>{{ actionReceipt.next }}</small></div>
      <button type="button" :disabled="contextLocked" @click="actionReceipt = null">关闭</button>
    </aside>

    <EmptyState
      v-if="!hasBatch"
      title="请先选择或创建毕设批次"
      description="顶部批次条选择当前工作批次后，再安排答辩组、时间地点和评委。"
    />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <EmptyState
      v-else-if="!rows.length"
      title="还没有答辩组"
      description="先把学生分进组、排好时间地点和评委秘书，再发布并发送通知。"
    >
      <template #actions>
        <button v-if="canCreateGroup" class="mp-btn mp-btn--primary" :disabled="contextLocked" @click="openCreate">＋ 新增答辩组</button>
        <button class="mp-btn" :disabled="contextLocked" @click="goExperts">先维护答辩专家库</button>
      </template>
    </EmptyState>

    <div v-else class="mp-stack" :class="{ 'is-command-locked': contextLocked }" :aria-busy="contextLocked">
      <div class="ds-summary" aria-label="答辩编排筛选">
        <button
          v-for="chip in summaryChips"
          :key="chip.key"
          type="button"
          class="ds-chip"
          :class="['ds-chip--' + chip.tone, { 'is-active': filterKey === chip.key }]"
          :disabled="contextLocked"
          @click="setFilter(chip.key)"
        >
          {{ chip.label }} <b>{{ chip.count }}</b>
        </button>
        <button v-if="selectedGroupId" type="button" class="mp-link ds-clear-focus" :disabled="contextLocked" @click="selectGroup(null)">清除当前组定位</button>
      </div>

      <section v-if="selectedGroup" class="ds-focus" aria-label="当前答辩组">
        <div>
          <span>当前答辩组</span>
          <strong>{{ selectedGroup.groupName }}</strong>
          <small>{{ selectedGroup.studentCount }} 名学生 · {{ selectedGroup.date }} · {{ selectedGroup.location }}</small>
        </div>
        <StatusTag :type="selectedGroup.published ? 'success' : publishPreflight(selectedGroup).ready ? 'warning' : 'danger'" :label="selectedGroup.published ? '已发布' : publishPreflight(selectedGroup).ready ? '可发布' : '仍有缺口'" dot />
        <button type="button" class="mp-link" :disabled="contextLocked" @click="openEdit(selectedGroup)">查看与编辑 →</button>
      </section>

      <DataTable :columns="columns" :rows="filteredRows" row-key="id">
        <template #cell-group="{ row }">
          <button type="button" class="ds-group-link" :disabled="contextLocked" @click="selectGroup(row)">{{ row.groupName }}</button>
          <div class="mp-cell-sub">{{ row.studentCount }} 名学生</div>
        </template>
        <template #cell-schedule="{ row }">
          <div class="ds-schedule"><AppDateDisplay :value="row.date === '待定' ? '' : row.date" mode="datetime" empty-text="待定" /></div>
          <div class="mp-cell-sub">{{ row.location }}</div>
        </template>
        <template #cell-panel="{ row }">
          <div class="ds-panel-main">组长：{{ row.chair }}</div>
          <div class="mp-cell-sub">{{ row.members.length ? '评委：' + memberNames(row).join('、') : '评委待安排' }} · 秘书：{{ row.secretary }}</div>
          <div v-if="row.conflict" class="mp-cell-sub ds-danger">⚠ {{ row.conflict }}</div>
          <div v-else-if="!publishPreflight(row).ready" class="mp-cell-sub ds-preflight-warning">发布前：{{ publishPreflight(row).summary }}</div>
        </template>
        <template #cell-published="{ row }">
          <StatusTag :type="row.published ? 'success' : row.conflict ? 'danger' : 'warning'" :label="row.publishedLabel" dot />
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" :disabled="contextLocked || !canManage" :title="manageReason" @click="openEdit(row)">编辑</button>
          <button
            v-if="!row.published"
            class="mp-link"
            :disabled="contextLocked || !canPublish || !publishPreflight(row).ready"
            :title="!publishPreflight(row).ready ? publishPreflight(row).summary : publishReason"
            @click="askPublish(row)"
          >发布</button>
          <button v-if="row.published" class="mp-link" :disabled="contextLocked" @click="notify(row)">{{ actionBusy === `notify:${row.id}` ? '通知中…' : '通知' }}</button>
        </template>
      </DataTable>
      <p class="mp-note">页面预检覆盖六类明显缺口，但不能替代服务端权限、数据范围、回避规则和发布状态机；发布与通知均锁定当前组，等待服务器回执后才释放。</p>
    </div>

    <AppConfirmDialog
      v-model:visible="confirm.visible"
      :title="confirm.title"
      :message="confirm.message"
      type="warning"
      confirm-text="确认发布"
      :submitting="Boolean(actionBusy)"
      @cancel="onConfirmCancel"
      @confirm="doPublish"
    />
    <AppPageGuide guide-key="graduation.gd-defense" />
  </ModulePageShell>
</template>

<script>
/** 答辩安排（/admin/graduation/defense）：可恢复工作上下文、latest-wins、发布/通知命令快照。 */
import { ModulePageShell, ModuleToolbar, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppDateDisplay } from '@/components/common/date'
import { AppExportButton, AppPageGuide } from '@/components/common'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { graduationApi } from '@/modules/graduation/api/graduation.api'
import { graduationMoreApi } from '@/modules/graduation/api/graduation-more.api'
import { exportFilenameHint } from '@/modules/graduation/utils/queryParams'
import { useGraduationBatchStore } from '@/stores/graduationBatch'
import { toast } from '@/utils/toast'

const VALID_FILTERS = ['all', 'published', 'unpublished', 'conflict', 'pending']
const EMPTY_CONFIRM = () => ({ visible: false, title: '', message: '', row: null })
const freezeSnapshot = (value) => Object.freeze({ ...value })

export default {
  name: 'DefenseScheduleView',
  components: { AppPageGuide, ModulePageShell, ModuleToolbar, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppDateDisplay, AppExportButton, AppConfirmDialog },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      batchStore: useGraduationBatchStore(),
      loading: true,
      error: '',
      rows: [],
      filterKey: 'all',
      selectedGroupId: '',
      routeReady: false,
      loadToken: 0,
      actionBusy: '',
      commandSnapshot: null,
      actionReceipt: null,
      confirm: EMPTY_CONFIRM(),
      columns: [
        { key: 'group', title: '答辩分组' },
        { key: 'schedule', title: '时间 / 地点' },
        { key: 'panel', title: '评委 / 秘书' },
        { key: 'published', title: '学生端发布状态' },
        { key: 'actions', title: '操作', width: '150px' }
      ]
    }
  },
  computed: {
    hasBatch() { return Boolean(this.batchStore.selectedBatchId) },
    contextLocked() { return Boolean(this.actionBusy || (this.confirm.visible && this.commandSnapshot)) },
    pageSubtitle() {
      if (!this.hasBatch) return '请先在顶部选择或创建毕设批次'
      const batch = this.batchStore.selectedBatchName ? `${this.batchStore.selectedBatchName} · ` : ''
      return `${batch}分组 / 时间 / 地点 / 评委 / 秘书 · 发布与通知以服务器回执为准`
    },
    summaryChips() {
      const rows = this.rows
      return [
        { key: 'all', label: '答辩组', count: rows.length, tone: 'default' },
        { key: 'published', label: '已发布', count: rows.filter((row) => row.published).length, tone: 'success' },
        { key: 'unpublished', label: '待发布', count: rows.filter((row) => !row.published).length, tone: 'warning' },
        { key: 'conflict', label: '回避冲突', count: rows.filter((row) => Boolean(row.conflict)).length, tone: 'danger' },
        { key: 'pending', label: '编排缺口', count: rows.filter((row) => !this.publishPreflight(row).ready).length, tone: 'warning' }
      ]
    },
    totalStudents() { return this.rows.reduce((sum, row) => sum + Math.max(0, Number(row.studentCount) || 0), 0) },
    publishReadyCount() { return this.rows.filter((row) => !row.published && this.publishPreflight(row).ready).length },
    conflictCount() { return this.rows.filter((row) => Boolean(row.conflict)).length },
    conclusion() {
      if (!this.hasBatch) return '先选择批次，再读取答辩编排。'
      if (this.loading) return '正在读取服务端答辩组。'
      if (this.error) return '答辩编排暂不可用，请按错误信息重试。'
      if (!this.rows.length) return '当前批次还没有答辩组，先建立分组。'
      const pending = this.rows.filter((row) => !row.published).length
      const blocked = this.rows.filter((row) => !row.published && !this.publishPreflight(row).ready).length
      return pending ? `待发布 ${pending} 组，其中 ${blocked} 组仍有编排缺口；先修复缺口再发布。` : '当前批次答辩组均已发布，可按服务器回执发送通知。'
    },
    filteredRows() {
      if (this.filterKey === 'published') return this.rows.filter((row) => row.published)
      if (this.filterKey === 'unpublished') return this.rows.filter((row) => !row.published)
      if (this.filterKey === 'conflict') return this.rows.filter((row) => Boolean(row.conflict))
      if (this.filterKey === 'pending') return this.rows.filter((row) => !this.publishPreflight(row).ready)
      return this.rows
    },
    selectedGroup() { return this.rows.find((row) => String(row.id) === this.selectedGroupId) || null },
    canManage() {
      const permission = this.ctx.permissionActions.manageDefense
      return Boolean(permission?.visible && permission?.allowed) && this.ctx.writeEnabled !== false
    },
    canCreateGroup() {
      const scopeName = String(this.ctx.dataScope?.scopeName || '')
      return this.canManage && scopeName.startsWith('本校毕设数据')
    },
    manageReason() {
      if (this.ctx.writeEnabled === false) return '写操作已禁用'
      return this.ctx.permissionActions.manageDefense?.reason || ''
    },
    canPublish() {
      const permission = this.ctx.permissionActions.publishDefense
      return Boolean(permission?.visible && permission?.allowed) && this.ctx.writeEnabled !== false
    },
    publishReason() {
      if (this.ctx.writeEnabled === false) return '写操作已禁用'
      return this.ctx.permissionActions.publishDefense?.reason || ''
    },
    exportPerm() {
      const permission = this.ctx.permissionActions.exportDefense || {}
      return { visible: Boolean(permission.visible && this.hasBatch), allowed: Boolean(permission.allowed && !this.contextLocked) }
    },
    toolbarActions() {
      const permission = this.ctx.permissionActions.manageDefense
      if (!permission?.visible) return []
      return [{
        key: 'manageDefense',
        label: '＋ 新增答辩组',
        variant: 'primary',
        disabled: this.contextLocked || !permission.allowed || !this.canCreateGroup || this.ctx.writeEnabled === false || !this.hasBatch,
        disabledReason: this.contextLocked
          ? '答辩命令执行中'
          : this.ctx.writeEnabled === false
            ? '写操作已禁用'
            : !this.hasBatch
              ? '请先选择批次'
              : !this.canCreateGroup
                ? '仅全校毕设管理员可新建或重新分配答辩组'
                : permission.reason
      }]
    },
    safeReturnTo() {
      const value = this.routeText(this.$route.query.returnTo)
      return value.startsWith('/admin/graduation/') ? value : '/admin/graduation/defense'
    }
  },
  created() {
    this.applyRouteState(this.$route.query)
    this.routeReady = true
    this.syncUrl()
    this.load()
  },
  beforeUnmount() {
    ++this.loadToken
  },
  beforeRouteLeave(to, from, next) {
    if (this.contextLocked) {
      toast.info('答辩发布或通知正在等待服务器回执，请完成后再离开')
      next(false)
      return
    }
    next()
  },
  watch: {
    '$route.query': {
      deep: true,
      handler(query) {
        if (!this.routeReady) return
        if (this.contextLocked) {
          this.restoreCommandContext()
          return
        }
        this.applyRouteState(query)
      }
    },
    'batchStore.selectedBatchId'(batchId) {
      const snapshot = this.commandSnapshot
      if (snapshot) {
        if (String(batchId || '') !== String(snapshot.batchId || '')) this.batchStore.selectBatch(snapshot.batchId)
        this.restoreCommandContext()
        return
      }
      ++this.loadToken
      this.selectedGroupId = ''
      this.actionReceipt = null
      void this.syncUrl({ batchId: batchId ? String(batchId) : undefined, groupId: undefined })
      this.load()
    }
  },
  methods: {
    routeText(value) { return Array.isArray(value) ? String(value[0] || '') : String(value || '') },
    applyRouteState(query = {}) {
      const filter = this.routeText(query.filter)
      this.filterKey = VALID_FILTERS.includes(filter) ? filter : 'all'
      this.selectedGroupId = this.routeText(query.groupId)
    },
    buildRouteQuery(overrides = {}) {
      const query = {
        ...this.$route.query,
        batchId: this.batchStore.selectedBatchId ? String(this.batchStore.selectedBatchId) : undefined,
        groupId: this.selectedGroupId || undefined,
        filter: this.filterKey !== 'all' ? this.filterKey : undefined,
        returnTo: this.safeReturnTo !== '/admin/graduation/defense' ? this.safeReturnTo : undefined,
        ...overrides
      }
      Object.keys(query).forEach((key) => {
        if (query[key] == null || query[key] === '') delete query[key]
      })
      return query
    },
    syncUrl(overrides = {}) {
      return this.$router.replace({ query: this.buildRouteQuery(overrides) }).catch(() => {})
    },
    currentReturnTo() {
      return this.$router.resolve({ path: '/admin/graduation/defense', query: this.buildRouteQuery() }).fullPath
    },
    restoreCommandContext() {
      if (!this.commandSnapshot?.routeQuery) return
      this.$router.replace({ path: '/admin/graduation/defense', query: this.commandSnapshot.routeQuery }).catch(() => {})
    },
    setFilter(key) {
      if (this.contextLocked || !VALID_FILTERS.includes(key)) return
      this.filterKey = key === this.filterKey && key !== 'all' ? 'all' : key
      void this.syncUrl({ filter: this.filterKey !== 'all' ? this.filterKey : undefined })
    },
    selectGroup(row) {
      if (this.contextLocked) return
      this.selectedGroupId = row?.id ? String(row.id) : ''
      void this.syncUrl({ groupId: this.selectedGroupId || undefined })
    },
    onToolbar(key) {
      if (key === 'manageDefense') this.openCreate()
    },
    openCreate() {
      if (!this.canCreateGroup || this.contextLocked) return
      this.$router.push({
        name: 'graduation-defense-group-create',
        query: {
          batchId: String(this.batchStore.selectedBatchId),
          returnTo: this.currentReturnTo()
        }
      })
    },
    goExperts() {
      if (this.contextLocked) return
      this.$router.push({ path: '/admin/graduation/more', query: { panel: 'experts', batchId: String(this.batchStore.selectedBatchId), returnTo: this.currentReturnTo() } })
    },
    openEdit(row) {
      if (!this.canManage || this.contextLocked || !row) return
      this.selectGroup(row)
      this.$router.push({
        name: 'graduation-defense-group-edit',
        params: { id: String(row.id) },
        query: { batchId: String(this.batchStore.selectedBatchId), returnTo: this.currentReturnTo() }
      })
    },
    exportDefenseFn() {
      const hint = exportFilenameHint(this.batchStore.selectedBatchName, '答辩安排')
      const params = { batchId: this.batchStore.selectedBatchId }
      return graduationApi.exportDefenseGroups(params).then((res) => {
        if (res.code === 0 && res.data) res.data = { ...res.data, filename: res.data.filename || `${hint}.xlsx` }
        return res
      })
    },
    askPublish(row) {
      const preflight = this.publishPreflight(row)
      if (this.contextLocked || !this.canPublish || !preflight.ready) {
        if (!preflight.ready) toast.error(`暂不能发布：${preflight.summary}`)
        return
      }
      this.selectedGroupId = String(row.id)
      const snapshot = freezeSnapshot({
        action: 'PUBLISH',
        batchId: String(this.batchStore.selectedBatchId),
        groupId: String(row.id),
        groupName: row.groupName,
        studentCount: Number(row.studentCount) || 0,
        routeQuery: this.buildRouteQuery({ groupId: String(row.id) })
      })
      this.commandSnapshot = snapshot
      this.confirm = {
        visible: true,
        title: '发布答辩安排',
        message: `页面预检：${preflight.summary}。确认发布「${row.groupName}」？正式权限、数据范围与状态机仍由服务端裁决。`,
        row: { ...row }
      }
      void this.syncUrl({ groupId: snapshot.groupId })
    },
    onConfirmCancel() {
      if (!this.actionBusy) this.commandSnapshot = null
      this.confirm = EMPTY_CONFIRM()
    },
    async doPublish() {
      const snapshot = this.commandSnapshot
      if (!snapshot || snapshot.action !== 'PUBLISH' || this.actionBusy) return
      this.actionBusy = `publish:${snapshot.groupId}`
      try {
        const res = await graduationApi.publishDefenseSchedule(snapshot.groupId)
        if (res.code === 0) {
          this.confirm = EMPTY_CONFIRM()
          await this.load()
          const latest = this.rows.find((item) => String(item.id) === snapshot.groupId)
          this.actionReceipt = {
            title: `${snapshot.groupName} 已发布`,
            result: `服务器最新状态：${latest?.published ? '已发布' : '状态仍需核对'}；编排对象 ${snapshot.studentCount} 名学生。`,
            next: latest?.published ? '下一步发送答辩通知；发送结果仍只认服务器回执。' : '不要重复发布，先刷新或核对服务端状态。'
          }
          toast.success(`${snapshot.groupName} 已发布，服务器最新状态已回读`)
        } else {
          this.confirm = EMPTY_CONFIRM()
          toast.error(res.message || '答辩发布失败')
        }
      } catch (error) {
        this.confirm = EMPTY_CONFIRM()
        toast.error(error?.message || '答辩发布失败，结果不确定时请先刷新核对')
      } finally {
        this.actionBusy = ''
        this.commandSnapshot = null
      }
    },
    async notify(row) {
      if (this.contextLocked || !row?.published) return
      const snapshot = freezeSnapshot({
        action: 'NOTIFY',
        batchId: String(this.batchStore.selectedBatchId),
        groupId: String(row.id),
        groupName: row.groupName,
        routeQuery: this.buildRouteQuery({ groupId: String(row.id) })
      })
      this.commandSnapshot = snapshot
      this.actionBusy = `notify:${snapshot.groupId}`
      this.selectedGroupId = snapshot.groupId
      void this.syncUrl({ groupId: snapshot.groupId })
      try {
        const res = await graduationMoreApi.notifyDefense(snapshot.groupId)
        if (res.code === 0) {
          const notified = Number(res.data?.notified) || 0
          const queued = Number(res.data?.queued) || 0
          const pending = Number(res.data?.pending) || 0
          const failed = Number(res.data?.failed) || 0
          this.actionReceipt = {
            title: `${snapshot.groupName} · 通知结果`,
            result: `服务器回执：已送达 ${notified} 人；排队 ${queued} 人；待重试 ${pending + failed} 人。`,
            next: pending || failed ? '发送队列会继续重试，当前按钮已防重复提交。' : '当前无需继续操作。'
          }
          if (notified > 0) toast.success(res.data?.message || res.message || `已向 ${notified} 名学生发送答辩通知`)
          else toast.info(res.data?.message || res.message || '暂无可投递学生')
        } else {
          toast.error(res.message || '通知失败')
        }
      } catch (error) {
        toast.error(error?.message || '通知请求失败，请先核对发送台账后再决定是否重试')
      } finally {
        this.actionBusy = ''
        this.commandSnapshot = null
      }
    },
    async load() {
      const batchId = String(this.batchStore.selectedBatchId || '')
      const token = ++this.loadToken
      if (!batchId) {
        this.loading = false
        this.error = ''
        this.rows = []
        return false
      }
      this.loading = true
      this.error = ''
      try {
        const res = await graduationApi.getDefenseSchedules({ page: 1, pageSize: 50, batchId })
        if (token !== this.loadToken || batchId !== String(this.batchStore.selectedBatchId || '')) return false
        if (res.code === 0) {
          this.rows = Array.isArray(res.data?.list) ? res.data.list : []
          if (this.selectedGroupId && !this.rows.some((row) => String(row.id) === this.selectedGroupId)) {
            this.selectedGroupId = ''
            void this.syncUrl({ groupId: undefined })
          }
          return true
        }
        this.rows = []
        this.error = res.message || '答辩安排加载失败'
      } catch (error) {
        if (token === this.loadToken) {
          this.rows = []
          this.error = error?.message || '答辩安排加载失败'
        }
      } finally {
        if (token === this.loadToken) this.loading = false
      }
      return false
    },
    publishPreflight(row) {
      const members = Array.isArray(row?.members) ? row.members : []
      const missingJudges = (row?.chairMentorId ? 0 : 1) + members.filter((member) => !(member?.mentorId || member?.expertId)).length
      const students = Math.max(0, Number(row?.studentCount) || 0)
      const gaps = {
        missingJudges,
        conflicts: row?.conflict ? 1 : 0,
        missingLocation: !row?.location || row.location === '待定' ? 1 : 0,
        missingTime: !row?.date || row.date === '待定' ? 1 : 0,
        missingSecretary: row?.secretaryMentorId ? 0 : 1,
        students,
        studentsOverLimit: students > 30 ? 1 : 0
      }
      const ready = !gaps.missingJudges && !gaps.conflicts && !gaps.missingLocation && !gaps.missingTime && !gaps.missingSecretary && gaps.students > 0 && !gaps.studentsOverLimit
      return { ...gaps, ready, summary: `缺稳定评委 ${gaps.missingJudges} · 回避冲突 ${gaps.conflicts} · 无地点 ${gaps.missingLocation} · 无时间 ${gaps.missingTime} · 缺秘书 ${gaps.missingSecretary} · 超 30 人 ${gaps.studentsOverLimit}` }
    },
    memberNames(row) {
      return (Array.isArray(row?.members) ? row.members : []).map((member) => typeof member === 'string' ? member : (member?.name || member?.teacherName || '未命名评委'))
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.ds-command { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: var(--space-4); align-items: center; margin-bottom: var(--space-3); padding: 12px 14px; border: 1px solid var(--primary-100, #dbeafe); border-radius: var(--radius-lg, 12px); background: linear-gradient(120deg, var(--primary-50, #eff6ff), var(--bg-card, #fff) 76%); }
.ds-command > div:first-child { display: grid; min-width: 0; gap: 2px; }
.ds-command > div:first-child > span { color: var(--primary-600, #2563eb); font-size: 10px; font-weight: 700; letter-spacing: .08em; }
.ds-command strong { color: var(--text-primary, #0f172a); font-size: 14px; }
.ds-command small { color: var(--text-tertiary, #64748b); font-size: 10px; line-height: 1.5; }
.ds-command__facts { display: flex; align-items: stretch; }
.ds-command__facts div { display: grid; min-width: 84px; gap: 1px; padding: 2px 12px; border-left: 1px solid var(--primary-100, #dbeafe); }
.ds-command__facts b { color: var(--text-primary, #0f172a); font-size: 18px; }
.ds-command__facts span { color: var(--text-tertiary, #64748b); font-size: 9px; }
.ds-summary { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
.ds-chip { display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; border: 1px solid var(--border-light, #e2e8f0); border-radius: var(--radius-full, 999px); background: var(--bg-card, #fff); color: var(--text-secondary, #475569); cursor: pointer; font: inherit; font-size: var(--font-size-sm, 13px); transition: border-color .15s ease, background .15s ease, box-shadow .15s ease; }
.ds-chip:hover:not(:disabled) { border-color: var(--primary-200, #bfdbfe); background: var(--bg-subtle, #f8fafc); }
.ds-chip:focus-visible { outline: 2px solid var(--primary-400, #60a5fa); outline-offset: 2px; }
.ds-chip:disabled { cursor: not-allowed; opacity: .55; }
.ds-chip b { color: var(--text-primary, #0f172a); font-weight: 600; }
.ds-chip.is-active { border-color: var(--brand-primary, #2563eb); background: var(--primary-50, #eff6ff); color: var(--brand-primary, #2563eb); }
.ds-chip--danger b { color: var(--danger, #dc2626); }
.ds-chip--warning b { color: var(--warning-600, #d97706); }
.ds-chip--success b { color: var(--success-600, #16a34a); }
.ds-clear-focus { margin-left: auto; }
.ds-focus { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; gap: var(--space-3); align-items: center; padding: 9px 11px; border: 1px solid var(--primary-100, #dbeafe); border-radius: var(--radius-md, 9px); background: var(--primary-50, #eff6ff); }
.ds-focus > div { display: grid; min-width: 0; gap: 2px; }
.ds-focus span { color: var(--primary-600, #2563eb); font-size: 9px; font-weight: 700; }
.ds-focus strong { color: var(--text-primary, #0f172a); font-size: 12px; }
.ds-focus small { overflow: hidden; color: var(--text-tertiary, #64748b); font-size: 9px; text-overflow: ellipsis; white-space: nowrap; }
.ds-group-link { padding: 0; border: 0; background: transparent; color: var(--text-primary, #0f172a); cursor: pointer; font-size: var(--font-size-sm, 13px); font-weight: 600; text-align: left; }
.ds-group-link:hover { color: var(--primary-600, #2563eb); }
.ds-schedule, .ds-panel-main { font-size: var(--font-size-sm, 13px); }
.ds-danger { color: var(--danger-600, #dc2626); }
.ds-preflight-warning { color: var(--warning-700, #a16207); }
.ds-receipt { display: flex; align-items: center; gap: 14px; margin-bottom: var(--space-3); padding: 11px 12px; border: 1px solid var(--success-200, #b7ebc6); border-radius: 9px; background: var(--success-50, #f0fff4); }
.ds-receipt div { display: grid; flex: 1; gap: 3px; }
.ds-receipt strong { color: var(--success-700, #137a43); }
.ds-receipt span { font-size: 12px; }
.ds-receipt small { color: var(--text-tertiary, #64748b); font-size: 10px; }
.ds-receipt button { border: 0; background: transparent; color: var(--primary-600, #2563eb); cursor: pointer; }
.gd-actions { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
.mp-link { display: inline-flex; margin-right: var(--space-2); padding: 0; border: 0; background: transparent; color: var(--primary-600, #2563eb); cursor: pointer; font-size: 11px; }
.mp-link:disabled { cursor: not-allowed; opacity: .5; }
.is-command-locked { pointer-events: none; opacity: .75; }
@media (max-width: 900px) { .ds-command { grid-template-columns: 1fr; } .ds-command__facts div:first-child { border-left: 0; padding-left: 0; } }
@media (max-width: 700px) { .ds-focus { grid-template-columns: 1fr; } .ds-command__facts { overflow-x: auto; } }
</style>
