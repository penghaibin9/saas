<template>
  <ModulePageShell title="资源维修" subtitle="教室 / 实训室 / 设备共用维修工单：登记故障 → 维修中 → 完成，联动资源状态">
    <template #actions>
      <AppButton v-if="canManage" variant="primary" :disabled="saving || noteDialog.submitting || Boolean(pendingResult)" @click="openReport">登记报修</AppButton>
    </template>
    <div class="mp-stack">
      <AaOperationReceipt :receipt="receipt" />
      <AppButton v-if="pendingResult" :disabled="saving || noteDialog.submitting" @click="queryResult">查询办理结果</AppButton>
      <div class="aarr-bar">
        <AppSelect v-model="filterKind" :options="kindOptions" placeholder="全部资源类型" @change="pagination.page = 1; load()" />
        <AppSelect v-model="filterStatus" :options="statusOptions" placeholder="全部状态" @change="pagination.page = 1; load()" />
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="暂无维修工单" description="点击右上角登记故障报修" />
      <template v-else>
        <div class="aarr-flow" aria-label="维修流程">
          <div><span>当前对象</span><strong>{{ pagination.total }} 张维修工单</strong></div>
          <div><span>当前责任</span><strong>{{ canManage ? '资源维修岗' : '只读核对' }}</strong></div>
          <div><span>关闭条件</span><strong>工单状态与资源状态双重回读</strong></div>
        </div>
        <div class="aarr-board">
          <section v-for="group in repairGroups" :key="group.key" class="aarr-column">
            <header class="aarr-column-head">
              <div>
                <strong>{{ group.title }}</strong>
                <span>{{ group.hint }}</span>
              </div>
              <b>{{ group.rows.length }}</b>
            </header>
            <div v-if="!group.rows.length" class="aarr-column-empty">本页暂无工单</div>
            <article v-for="row in group.rows" :key="row.repairId" class="aarr-card">
              <div class="aarr-card-head">
                <div>
                  <strong>{{ row.resourceLabel || `资源 #${row.resourceId}` }}</strong>
                  <span>{{ kindLabel(row.resourceKind) }} · 工单 #{{ row.repairId }}</span>
                </div>
                <StatusTag :type="sType(row.status)" :label="row.statusLabel || statusLabel(row.status)" dot />
              </div>
              <p>{{ row.faultDesc || '故障描述待核对' }}</p>
              <dl>
                <div><dt>报修人</dt><dd>{{ row.reporterName || '待确认' }}</dd></div>
                <div><dt>报修时间</dt><dd>{{ row.createdAt || '待确认' }}</dd></div>
                <div v-if="row.repairNote"><dt>处理记录</dt><dd>{{ row.repairNote }}</dd></div>
                <div v-if="row.resolvedAt"><dt>恢复时间</dt><dd>{{ row.resolvedAt }}</dd></div>
              </dl>
              <div v-if="timelineIssue(row)" class="aarr-data-warning">{{ timelineIssue(row) }}</div>
              <div v-if="canManage && ['REPORTED', 'IN_REPAIR'].includes(row.status)" class="aarr-card-actions">
                <button v-if="row.status === 'REPORTED'" class="mp-link" :disabled="saving || noteDialog.submitting || Boolean(pendingResult)" @click="start(row.repairId)">领取维修</button>
                <button class="mp-link" :disabled="saving || noteDialog.submitting || Boolean(pendingResult)" @click="complete(row.repairId)">完成并回读</button>
                <button class="mp-link is-danger" :disabled="saving || noteDialog.submitting || Boolean(pendingResult)" @click="cancel(row.repairId)">取消</button>
              </div>
            </article>
          </section>
        </div>
        <AppPagination
          v-if="pagination.total > pagination.pageSize || pagination.page > 1"
          :total="pagination.total" :page="pagination.page" :page-size="pagination.pageSize"
          :show-size-changer="false" @change="changePage($event.page)"
        />
      </template>

      <p class="mp-note">
        报修登记后会自动把对应教室/实训室/设备状态置为"维修中"；完成维修且该资源无其它未结工单时，会自动恢复为可用/在用状态。
      </p>
    </div>

    <AppDrawer :visible="reportVisible" title="登记故障报修" mode="modal" size="medium" @close="reportVisible = false">
      <div class="aarr-form">
        <AppFormItem label="资源类型" required>
          <AppSelect v-model="form.resourceKind" :options="kindOptions.slice(1)" :disabled="saving" @change="onKindChange" />
        </AppFormItem>
        <AppFormItem label="资源" required>
          <AppClassroomPicker v-if="form.resourceKind === 'CLASSROOM'" v-model="form.resourceId" placeholder="选择教室" :disabled="saving" />
          <AppLabPicker v-else-if="form.resourceKind === 'LAB'" v-model="form.resourceId" placeholder="选择实训室" :disabled="saving" />
          <AppEquipmentPicker v-else v-model="form.resourceId" placeholder="选择设备" :disabled="saving" />
        </AppFormItem>
        <AppFormItem label="故障描述" required>
          <AppTextarea v-model="form.faultDesc" placeholder="如：空调不制冷/投影仪无法开机" :disabled="saving" />
        </AppFormItem>
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="reportVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" :disabled="!canManage || Boolean(pendingResult)" @click="submitReport">提交</AppButton>
      </template>
    </AppDrawer>

    <!-- 维修说明/取消原因均为选填：不设 require-reason，也不挂快捷用语（配置方案未给该场景词条） -->
    <AppConfirmDialog
      v-model:visible="noteDialog.visible" :title="noteDialog.title"
      :type="noteDialog.type" :confirm-text="noteDialog.confirmText"
      :submitting="noteDialog.submitting" @confirm="onNoteConfirm"
    >
      <p>{{ noteDialog.row?.resourceLabel }} · 工单 #{{ noteDialog.row?.repairId }} · {{ noteDialog.row?.statusLabel }}</p>
      <AppInlineAlert v-if="noteDialog.error" type="danger" :description="noteDialog.error" />
      <label v-if="noteDialog.action !== 'START'" class="aarr-note-label">{{ noteDialog.label }}
        <AppTextarea v-model="noteDialog.note" :placeholder="noteDialog.placeholder" :disabled="noteDialog.submitting" />
      </label>
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
/** 教学资源续卡 · 资源维修（/admin/academic-affairs/resources/repairs）：教室/实训室/设备共用工单台账。 */
import { ModulePageShell, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppSelect, AppTextarea, AppFormItem, AppInlineAlert, AppConfirmDialog, AppClassroomPicker, AppLabPicker, AppEquipmentPicker, AppPagination } from '@/components/common'
import { academicAffairsResourceApi, academicAffairsApi, academicAffairsLabApi, academicAffairsEquipmentApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { matchPermission } from '@/config/navPlan'
import AaOperationReceipt from '../components/parallel-a/AaOperationReceipt.vue'
import { isDeniedResult, isConflictResult } from '../components/parallel-a/resultState'

const _KIND_LABEL = { CLASSROOM: '教室', LAB: '实训室', EQUIPMENT: '设备' }
const _STATUS_LABEL = { REPORTED: '已报修', IN_REPAIR: '维修中', DONE: '已完成', CANCELLED: '已取消' }

export default {
  name: 'AaResourceRepairView',
  props: { ctx: { type: Object, required: true } },
  components: { AaOperationReceipt, ModulePageShell, StatusTag, LoadingState, ErrorState, EmptyState, AppButton, AppDrawer, AppSelect, AppTextarea, AppFormItem, AppInlineAlert, AppConfirmDialog, AppClassroomPicker, AppLabPicker, AppEquipmentPicker, AppPagination },
  data() {
    return {
      noteDialog: { visible: false, title: '', label: '', placeholder: '', type: 'primary', confirmText: '确认', note: '', submitting: false, action: null },
      loading: true, revision: 0, disposed: false, receipt: null, pendingResult: null, pagination: { page: 1, pageSize: 20, total: 0 },
      error: '',
      rows: [],
      filterKind: '',
      filterStatus: '',
      kindOptions: [
        { label: '全部资源类型', value: '' },
        { label: '教室', value: 'CLASSROOM' },
        { label: '实训室', value: 'LAB' },
        { label: '设备', value: 'EQUIPMENT' }
      ],
      statusOptions: [
        { label: '全部状态', value: '' },
        { label: '已报修', value: 'REPORTED' },
        { label: '维修中', value: 'IN_REPAIR' },
        { label: '已完成', value: 'DONE' },
        { label: '已取消', value: 'CANCELLED' }
      ],
      reportVisible: false,
      form: { resourceKind: 'CLASSROOM', resourceId: '', faultDesc: '' },
      formError: '',
      saving: false
    }
  },
  computed: {
    canManage() { return this.can('academicAffairs.resourceRepair.manage') },
    repairGroups() {
      return [
        { key: 'reported', title: '待领取', hint: '等待维修岗确认责任', rows: this.rows.filter(row => row.status === 'REPORTED') },
        { key: 'repairing', title: '处理中', hint: '维修完成后回读资源状态', rows: this.rows.filter(row => row.status === 'IN_REPAIR') },
        { key: 'closed', title: '已关闭', hint: '已完成或已取消', rows: this.rows.filter(row => ['DONE', 'CANCELLED'].includes(row.status)) }
      ]
    }
  },
  created() { this.load() },
  watch: { ctx() { this.clearPrivate(); this.load() } },
  beforeUnmount() { this.disposed = true; this.revision++ },
  methods: {
    can(key) { return matchPermission(this.ctx.permissionPatterns || [], key) },
    kindLabel(kind) { return _KIND_LABEL[kind] || '资源类型待确认' },
    statusLabel(status) { return _STATUS_LABEL[status] || '状态待确认' },
    timelineIssue(row) {
      if (!row?.createdAt || !row?.resolvedAt) return ''
      const created = Date.parse(row.createdAt), resolved = Date.parse(row.resolvedAt)
      return Number.isFinite(created) && Number.isFinite(resolved) && resolved < created
        ? '恢复时间早于报修时间，请核对沙箱工单数据。'
        : ''
    },
    sType(status) { return status === 'DONE' ? 'success' : status === 'CANCELLED' ? 'default' : status === 'IN_REPAIR' ? 'warning' : 'danger' },
    changePage(page) { this.pagination.page = page; this.load() },
    clearPrivate() { this.revision++; this.rows = []; this.pagination.total = 0; this.form = { resourceKind: 'CLASSROOM', resourceId: '', faultDesc: '' }; this.reportVisible = false; this.noteDialog = { visible: false, note: '', submitting: false, row: null }; this.receipt = null; this.pendingResult = null; this.saving = false },
    failure(e, field = 'error') {
      if (isDeniedResult(e)) { this.clearPrivate(); this.loading = false; this.error = (e.message || '无权访问') + '；已清除先前维修记录。'; return }
      const message = (isConflictResult(e) ? '事实已变化，保留输入，请重新核对。' : '') + (e?.message || '连接失败，请重试。')
      if (field === 'note') this.noteDialog.error = message; else this[field] = message
      if (isConflictResult(e)) this.receipt = { title: '维修办理回执', status: '事实已变化', pending: true, next: message }
    },
    async load() {
      const revision = ++this.revision, context = this.ctx, current = () => !this.disposed && revision === this.revision && context === this.ctx
      this.loading = true; this.error = ''; this.rows = []; this.pagination.total = 0
      try {
        const res = await academicAffairsResourceApi.repairs({ resourceKind: this.filterKind || undefined, status: this.filterStatus || undefined, page: this.pagination.page, pageSize: 20 })
        if (!current()) return
        if (res.code !== 0) throw res
        if (!Array.isArray(res.data?.list)) throw new Error('维修列表未完整返回。')
        this.rows = res.data.list; this.pagination.total = res.data.total
      } catch (e) { if (current()) this.failure(e) } finally { if (current()) this.loading = false }
    },
    onKindChange() { this.form.resourceId = '' },
    openReport() { if (!this.canManage || this.saving || this.noteDialog.submitting || this.pendingResult) return; this.form = { resourceKind: 'CLASSROOM', resourceId: '', faultDesc: '' }; this.formError = ''; this.reportVisible = true },
    async findRepair(id, kind, current) {
      let page = 1, seen = 0
      const ids = new Set()
      while (current()) {
        const res = await academicAffairsResourceApi.repairs({ resourceKind: kind, page, pageSize: 100 })
        if (!current()) return null
        if (res.code !== 0) throw res
        const list = res.data?.list
        if (!Array.isArray(list) || !Number.isInteger(res.data.total)) throw new Error('维修记录未完整返回。')
        for (const row of list) { if (!row.repairId || ids.has(String(row.repairId))) throw new Error('维修分页已变化，请重新查询。'); ids.add(String(row.repairId)) }
        const row = list.find(item => String(item.repairId) === String(id)); if (row) return row
        seen += list.length; if (seen >= res.data.total) return null
        if (!list.length) throw new Error('维修分页已变化，请重新查询。')
        page++
      }
      return null
    },
    async submitReport() {
      if (!this.canManage || this.saving || this.noteDialog.submitting || this.pendingResult) return
      const body = { ...this.form, faultDesc: this.form.faultDesc?.trim() }
      if (!body.resourceId || !body.faultDesc || !_KIND_LABEL[body.resourceKind]) { this.formError = '资源与故障描述均必填'; return }
      const context = this.ctx, current = () => !this.disposed && context === this.ctx
      this.saving = true; this.formError = ''; this.pendingResult = { id: '', row: body, expected: 'REPORTED' }
      this.receipt = { title: '维修办理回执', object: `${this.kindLabel(body.resourceKind)} #${body.resourceId}`, status: '结果待确认', pending: true, next: '正在读取正式工单和资源状态，不会重复报修。' }
      try {
        const res = await academicAffairsResourceApi.reportRepair(body); if (!current()) return
        if (res.code !== 0) { if (isDeniedResult(res) || isConflictResult(res) || String(res.code || '').startsWith('400')) this.pendingResult = null; throw res }
        this.pendingResult.id = res.data?.repairId || ''; this.reportVisible = false; await this.readResult(current)
      } catch (e) { if (current()) await this.recover(e, 'formError', current) } finally { if (current()) this.saving = false }
    },
    start(id) { this.openAction(id, 'START') },
    complete(id) { this.openAction(id, 'COMPLETE') },
    cancel(id) { this.openAction(id, 'CANCEL') },
    openAction(id, action) {
      if (!this.canManage || this.saving || this.noteDialog.submitting || this.pendingResult) return
      const row = this.rows.find(item => String(item.repairId) === String(id))
      if (!row || !(action === 'START' ? row.status === 'REPORTED' : ['REPORTED', 'IN_REPAIR'].includes(row.status))) return
      const title = { START: '开始维修', COMPLETE: '完成维修', CANCEL: '取消维修工单' }[action]
      this.noteDialog = { visible: true, title, label: action === 'CANCEL' ? '取消原因（选填）' : '维修处理说明（选填）', placeholder: '请核对资源和当前工单状态', type: action === 'CANCEL' ? 'danger' : 'primary', confirmText: title, note: '', submitting: false, error: '', row, action }
    },
    async onNoteConfirm() {
      const dialog = this.noteDialog
      if (!this.canManage || dialog.submitting || this.saving || this.pendingResult || !dialog.row) return
      const context = this.ctx, current = () => !this.disposed && context === this.ctx && this.noteDialog === dialog
      dialog.submitting = true; dialog.error = ''
      try {
        const fresh = await this.findRepair(dialog.row.repairId, dialog.row.resourceKind, current); if (!current()) return
        const valid = fresh && String(fresh.resourceId) === String(dialog.row.resourceId) && fresh.resourceKind === dialog.row.resourceKind && (dialog.action === 'START' ? fresh.status === 'REPORTED' : ['REPORTED', 'IN_REPAIR'].includes(fresh.status))
        if (!valid) throw { code: 409001, message: '工单状态或关联资源已变化。' }
        this.pendingResult = { id: fresh.repairId, row: fresh, expected: { START: 'IN_REPAIR', COMPLETE: 'DONE', CANCEL: 'CANCELLED' }[dialog.action] }
        this.receipt = { title: '维修办理回执', object: `工单 #${fresh.repairId} · ${fresh.resourceLabel}`, status: '结果待确认', pending: true, next: '办理后读取正式工单与资源状态。' }
        const note = dialog.note.trim()
        const res = dialog.action === 'START' ? await academicAffairsResourceApi.startRepair(fresh.repairId) : dialog.action === 'COMPLETE' ? await academicAffairsResourceApi.completeRepair(fresh.repairId, note) : await academicAffairsResourceApi.cancelRepair(fresh.repairId, note)
        if (!current()) return
        if (res.code !== 0) { if (isDeniedResult(res) || isConflictResult(res)) this.pendingResult = null; throw res }
        dialog.visible = false; await this.readResult(current)
      } catch (e) { if (current()) await this.recover(e, 'note', current) } finally { if (current()) dialog.submitting = false }
    },
    async recover(e, field, current) {
      this.failure(e, field)
      if (this.pendingResult && !isDeniedResult(e) && !isConflictResult(e)) { try { await this.readResult(current) } catch (readError) { if (current()) this.failure(readError, field) } }
    },
    async readResult(current) {
      const pending = this.pendingResult
      if (!pending?.id) { this.receipt = { ...this.receipt, next: '未取得正式工单编号，请在维修台账核对本次结果，不会自动重复报修。' }; await this.load(); return }
      const row = await this.findRepair(pending.id, pending.row.resourceKind, current); if (!current()) return
      if (row && (String(row.resourceId) !== String(pending.row.resourceId) || row.resourceKind !== pending.row.resourceKind)) throw new Error('正式工单关联资源与原办理对象不一致。')
      let resourceNote = '资源当前状态未读取，请到对应资源目录核对。'
      const resourcePermission = { CLASSROOM: 'classroom', LAB: 'lab', EQUIPMENT: 'equipment' }[pending.row.resourceKind]
      if (row && this.can(`academicAffairs.${resourcePermission}.view`)) {
        const res = row.resourceKind === 'CLASSROOM' ? await academicAffairsApi.getClassroom(row.resourceId) : row.resourceKind === 'LAB' ? await academicAffairsLabApi.get(row.resourceId) : await academicAffairsEquipmentApi.get(row.resourceId)
        if (!current()) return
        if (isDeniedResult(res)) throw res
        if (res.code === 0) resourceNote = `资源当前状态：${res.data.statusLabel || res.data.status}。有其它未结工单时，完成本单不等于恢复可用。`
      }
      const confirmed = row?.status === pending.expected
      this.receipt = { title: '维修办理回执', object: `工单 #${pending.id} · ${row?.resourceLabel || pending.row.resourceId}`, status: confirmed ? _STATUS_LABEL[row.status] : '结果待确认', pending: !confirmed, time: row?.resolvedAt || (row?.status === 'REPORTED' ? row.createdAt : undefined), next: resourceNote + (confirmed ? '请在正式维修台账继续核对。' : '尚未读到对应办理状态，请继续查询。') }
      if (confirmed) this.pendingResult = null
      await this.load()
    },
    async queryResult() {
      if (!this.pendingResult || this.saving || this.noteDialog.submitting) return
      const context = this.ctx, current = () => !this.disposed && context === this.ctx
      this.saving = true; try { await this.readResult(current) } catch (e) { if (current()) this.failure(e) } finally { if (current()) this.saving = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aarr-bar { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; margin-bottom: 12px; }
.aarr-flow { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.aarr-flow > div { padding: 12px 14px; border: 1px solid var(--border-base); border-radius: 10px; background: var(--surface-card); }
.aarr-flow span, .aarr-flow strong { display: block; }
.aarr-flow span { color: var(--text-tertiary); font-size: 12px; }
.aarr-flow strong { margin-top: 4px; color: var(--text-primary); font-size: 14px; }
.aarr-board { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; align-items: start; }
.aarr-column { min-width: 0; padding: 12px; border: 1px solid var(--border-base); border-radius: 12px; background: var(--fill-light, #f8fafc); }
.aarr-column-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; margin-bottom: 12px; }
.aarr-column-head strong, .aarr-column-head span { display: block; }
.aarr-column-head span { margin-top: 3px; color: var(--text-tertiary); font-size: 12px; }
.aarr-column-head b { min-width: 28px; padding: 3px 8px; border-radius: 999px; background: var(--surface-card); color: var(--primary-600, #2563eb); text-align: center; }
.aarr-column-empty { padding: 28px 10px; color: var(--text-tertiary); font-size: 13px; text-align: center; }
.aarr-card { padding: 14px; border: 1px solid var(--border-base); border-radius: 10px; background: var(--surface-card); box-shadow: 0 4px 16px rgba(15, 40, 90, .05); }
.aarr-card + .aarr-card { margin-top: 10px; }
.aarr-card-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; }
.aarr-card-head strong, .aarr-card-head span { display: block; }
.aarr-card-head span { margin-top: 3px; color: var(--text-tertiary); font-size: 12px; }
.aarr-card p { margin: 12px 0; color: var(--text-primary); line-height: 1.6; }
.aarr-card dl { margin: 0; font-size: 12px; }
.aarr-card dl > div { display: grid; grid-template-columns: 62px 1fr; gap: 8px; padding: 3px 0; }
.aarr-card dt { color: var(--text-tertiary); }
.aarr-card dd { margin: 0; color: var(--text-secondary); overflow-wrap: anywhere; }
.aarr-card-actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 12px; padding-top: 10px; border-top: 1px solid var(--border-base); }
.aarr-data-warning { margin-top: 10px; padding: 8px 10px; border-radius: 8px; background: var(--warning-50, #fff7ed); color: var(--warning-700, #b45309); font-size: 12px; }
.aarr-form { display: flex; flex-direction: column; gap: 12px; }
.aarr-note-label { display: block; font-size: 13px; color: var(--text-secondary, #64748b); }
.aarr-note-label > * { margin-top: 6px; }
.mp-link.is-danger { color: var(--danger-500); }
@media (max-width: 1100px) { .aarr-board { grid-template-columns: 1fr; } }
@media (max-width: 760px) { .aarr-flow { grid-template-columns: 1fr; } }
</style>
