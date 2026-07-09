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

    <AppDrawer v-model:visible="drawer.visible" :title="drawer.id ? '编辑答辩组' : '新增答辩组'">
      <form class="ie-form" @submit.prevent="save">
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">答辩组名称 <i>*</i></span>
          <input v-model.trim="form.groupName" class="ie-in" placeholder="如 软件工程专业第一答辩组" />
        </label>
        <AppDateTimePicker v-model="form.defenseDate" class="ie-fld" label="答辩时间" hint="建议提前一周排期" />
        <label class="ie-fld"><span class="ie-lbl">答辩地点</span><input v-model.trim="form.location" class="ie-in" placeholder="如 实训楼 A301" /></label>
        <label class="ie-fld"><span class="ie-lbl">答辩组长（副高+）</span><input v-model.trim="form.chair" class="ie-in" placeholder="组长姓名" /></label>
        <label class="ie-fld"><span class="ie-lbl">答辩秘书</span><input v-model.trim="form.secretary" class="ie-in" placeholder="秘书姓名" /></label>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">评委名单（顿号/逗号分隔，建议≥5人）</span>
          <input v-model.trim="form.membersText" class="ie-in" placeholder="张老师、李老师、王老师…" />
        </label>
        <p v-if="formError" class="ie-err">{{ formError }}</p>
        <div class="ie-actions">
          <button type="button" class="mp-btn" @click="drawer.visible = false">取消</button>
          <button type="submit" class="mp-btn mp-btn--primary" :disabled="submitting">{{ drawer.id ? '保存' : '创建' }}</button>
        </div>
      </form>

      <template v-if="drawer.id">
        <div class="dg-sec">
          <div class="dg-sec__head">已分配学生（{{ assigned.length }}/30）</div>
          <EmptyState v-if="!assigned.length" title="暂未分配学生" description="从下方候选学生中勾选分配" />
          <div v-for="s in assigned" :key="s.id" class="dg-row">
            <div>
              <div class="dg-row__main">{{ s.name }} · {{ s.className }}</div>
              <div class="dg-row__sub" :style="s.conflict ? 'color:var(--danger-600)' : ''">
                {{ s.topicTitle }} · 导师 {{ s.advisorName }}{{ s.conflict ? '（与评委冲突，须回避）' : '' }}
              </div>
            </div>
            <button class="mp-link mp-link--danger" @click="unassign(s)">移出</button>
          </div>
        </div>

        <div class="dg-sec">
          <div class="dg-sec__head">
            候选学生
            <input v-model.trim="eligKeyword" class="ie-in dg-search" placeholder="搜索姓名" @input="loadEligible" />
          </div>
          <EmptyState v-if="!eligibleFree.length" title="暂无可分配学生" description="已确认选题且未被其他组占用的学生会显示在此" />
          <div v-for="s in eligibleFree" :key="s.id" class="dg-row" @click="togglePick(s.id)">
            <div>
              <div class="dg-row__main">
                <input type="checkbox" :checked="picked.includes(s.id)" @click.stop="togglePick(s.id)" /> {{ s.name }} · {{ s.className }}
              </div>
              <div class="dg-row__sub">{{ s.topicTitle }} · 导师 {{ s.advisorName }}{{ s.assignedElsewhere ? '（已在「' + s.currentGroup + '」）' : '' }}</div>
            </div>
          </div>
          <div v-if="eligibleFree.length" class="ie-actions">
            <button type="button" class="mp-btn mp-btn--primary" :disabled="!picked.length || submitting" @click="assign">分配所选（{{ picked.length }}）</button>
          </div>
        </div>
      </template>
    </AppDrawer>
  </ModulePageShell>
</template>

<script>
/** 答辩安排（/admin/graduation/defense）：答辩组 CRUD + 学生分配 + 评委回避 + 发布 + 导出。 */
import { ModulePageShell, ModuleToolbar, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppDrawer } from '@/components/ui'
import { AppDateTimePicker, AppDateDisplay } from '@/components/common/date'
import { AppExportButton } from '@/components/common'
import { graduationApi } from '@/modules/graduation/api/graduation.api'
import { graduationMoreApi } from '@/modules/graduation/api/graduation-more.api'
import { toast } from '@/utils/toast'
import { toDateTimeInputValue, addDays } from '@/utils/dateUtils'

export default {
  name: 'DefenseScheduleView',
  components: { ModulePageShell, ModuleToolbar, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppDrawer, AppDateTimePicker, AppDateDisplay, AppExportButton },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', rows: [], submitting: false,
      drawer: { visible: false, id: null },
      form: { groupName: '', defenseDate: '', location: '', chair: '', secretary: '', membersText: '' },
      formError: '',
      assigned: [], eligible: [], picked: [], eligKeyword: '',
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
    eligibleFree() {
      // 候选区排除"已在本组"的（它们在上方"已分配"里）
      return this.eligible.filter((s) => !s.assignedHere)
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
    _members() {
      return (this.form.membersText || '').split(/[、,，]/).map((s) => s.trim()).filter(Boolean)
    },
    _formBody() {
      return {
        groupName: this.form.groupName, defenseDate: this.form.defenseDate, location: this.form.location,
        chair: this.form.chair, secretary: this.form.secretary, members: this._members()
      }
    },
    async onToolbar(key) {
      if (key === 'manageDefense' && this.canManage) {
        this.openCreate()
      }
    },
    exportDefenseFn() {
      return graduationApi.exportDefenseGroups()
    },
    openCreate() {
      this.drawer = { visible: true, id: null }
      this.form = {
        groupName: '',
        defenseDate: toDateTimeInputValue(addDays(new Date(), 7)),
        location: '', chair: '', secretary: '', membersText: ''
      }
      this.formError = ''
      this.assigned = []; this.eligible = []; this.picked = []; this.eligKeyword = ''
    },
    async openEdit(row) {
      if (!this.canManage) return
      this.drawer = { visible: true, id: row.id }
      this.form = {
        groupName: row.groupName === '待指定' ? '' : row.groupName,
        defenseDate: row.date === '待定' ? '' : toDateTimeInputValue(row.date),
        location: row.location === '待定' ? '' : row.location,
        chair: row.chair === '待指定' ? '' : row.chair,
        secretary: row.secretary === '待指定' ? '' : row.secretary,
        membersText: (row.members || []).join('、')
      }
      this.formError = ''
      this.picked = []; this.eligKeyword = ''
      await this.reloadDetail()
      await this.loadEligible()
    },
    async reloadDetail() {
      const res = await graduationApi.getDefenseGroupDetail(this.drawer.id)
      if (res.code === 0) this.assigned = res.data.students || []
    },
    async loadEligible() {
      if (!this.drawer.id) return
      const res = await graduationApi.getDefenseEligibleStudents(this.drawer.id, this.eligKeyword)
      if (res.code === 0) this.eligible = res.data.list
    },
    togglePick(id) {
      const i = this.picked.indexOf(id)
      if (i >= 0) this.picked.splice(i, 1)
      else this.picked.push(id)
    },
    async save() {
      this.formError = ''
      if (!this.form.groupName) { this.formError = '答辩组名称必填'; return }
      this.submitting = true
      const res = this.drawer.id
        ? await graduationApi.updateDefenseGroup(this.drawer.id, this._formBody())
        : await graduationApi.createDefenseGroup(this._formBody())
      this.submitting = false
      if (res.code === 0) {
        toast.success(this.drawer.id ? '已保存（编辑后需重新发布）' : '答辩组已创建，可继续分配学生')
        if (!this.drawer.id) { this.drawer.id = res.data.id; await this.reloadDetail(); await this.loadEligible() }
        else { this.assigned = res.data.students || [] }
        this.load()
      } else {
        this.formError = res.message || '保存失败'
      }
    },
    async assign() {
      if (!this.picked.length) return
      this.submitting = true
      const res = await graduationApi.assignDefenseStudents(this.drawer.id, this.picked)
      this.submitting = false
      if (res.code === 0) {
        toast.success('已分配')
        this.assigned = res.data.students || []
        this.picked = []
        await this.loadEligible()
        this.load()
      } else {
        toast.error(res.message || '分配失败')
      }
    },
    async unassign(s) {
      const res = await graduationApi.unassignDefenseStudents(this.drawer.id, [s.id])
      if (res.code === 0) {
        this.assigned = res.data.students || []
        await this.loadEligible()
        this.load()
      } else {
        toast.error(res.message || '移出失败')
      }
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
.dg-sec { margin-top: var(--space-4); }
.dg-sec__head { display: flex; align-items: center; justify-content: space-between; font-weight: var(--font-weight-medium); color: var(--text-primary); margin-bottom: var(--space-2); font-size: var(--font-size-sm); }
.dg-search { width: 140px; }
.dg-row { display: flex; align-items: center; justify-content: space-between; padding: var(--space-2) 0; border-bottom: 1px solid var(--border-light); }
.dg-row__main { font-size: var(--font-size-sm); color: var(--text-primary); }
.dg-row__sub { font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
</style>
