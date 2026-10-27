<template>
  <ModulePageShell
    title="临时授权与工作移交"
    subtitle="创建临时授权 · 到期自动回收 · 可提前回收并留痕"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="[{ key: 'create', label: '＋ 创建临时授权', variant: 'primary' }]" @action="openCreate" />
    </template>

    <div class="mp-stack">
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="暂无临时授权" description="可创建受控临时授权，到期后自动回收" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="id">
        <template #cell-status="{ row }">
          <StatusTag :type="row.status === 'ACTIVE' ? 'success' : row.status === 'REVOKED' ? 'warning' : 'default'" :label="row.statusLabel || row.status" dot />
        </template>
        <template #cell-actions="{ row }">
          <button
            v-if="row.status === 'ACTIVE'"
            class="mp-link mp-link--danger"
            @click="askRevoke(row)"
          >回收</button>
          <span v-else class="mp-note">—</span>
        </template>
      </DataTable>
    </div>

    <AppDrawer v-model:visible="form.open" title="创建临时授权" mode="modal" size="medium">
      <fieldset :disabled="form.submitting || uncertain" class="delegation-fields">
        <AccountCandidatePicker v-model="person" :ctx="ctx" :disabled="form.submitting || uncertain" />
        <FormFields v-model="form.value" :fields="formFields" :errors="form.errors" />
        <label>到期时间<input v-model="form.value.expiresAt" type="datetime-local" class="mp-input" /></label>
      </fieldset>
      <section v-if="uncertain">
        <p role="alert">原提交结果待确认，输入已保留，不会自动重发。</p>
        <button type="button" class="mp-link" :disabled="checking" @click="checkSubmission">{{ checking ? '正在核对…' : '读取原授权结果' }}</button>
        <p v-if="checkError" role="alert">{{ checkError }}</p>
        <template v-if="checkedRows">
          <p>本次读到 {{ checkedRows.length }} 条该人员、角色的记录。未查到不代表请求一定失败；如仍无法判断，请稍后再核对。</p>
          <p v-for="row in checkedRows" :key="row.id">授权编号 {{ row.id }} · {{ row.statusLabel || '状态待核对' }} · {{ row.reason }} · 到期 {{ row.expiresAt }}</p>
          <label><input v-model="acknowledged" type="checkbox" :disabled="checking" />我已核对原结果，结束本次提交，不重发原请求</label>
          <button type="button" class="mp-link" :disabled="checking || !acknowledged" @click="finishCheck">结束本次提交，开始新授权</button>
        </template>
      </section>
      <p class="mp-note">仅增加所选角色的临时操作权限；具体业务对象仍由原业务范围与关系校验。授课、学工责任、毕设及实习指导关系需在相应业务中心办理。</p>
      <template #footer>
        <AppButton variant="ghost" @click="form.open = false">取消</AppButton>
        <AppButton variant="primary" :loading="form.submitting" :disabled="uncertain" @click="submitCreate">创建并留痕</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="revoke.open"
      type="danger"
      title="回收该临时授权？"
      :message="'将立即回收 ' + (revoke.row ? revoke.row.granteeUserNo : '') + ' 的临时角色授权。'"
      confirm-text="确认回收"
      require-reason
      reason-label="回收原因"
      :submitting="revoke.submitting"
      @confirm="doRevoke"
    />
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, ModuleToolbar, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import FormFields from '@/modules/system/components/FormFields.vue'
import { systemApi } from '@/modules/system/api/system.api'
import { toast } from '@/utils/toast'
import AccountCandidatePicker from '../components/AccountCandidatePicker.vue'
import { contextFingerprint } from '../utils/workspaceContract'

export default {
  name: 'SystemDelegationView',
  components: {
    ModulePageShell, ModuleToolbar, DataTable, StatusTag, LoadingState, ErrorState, EmptyState,
    AppButton, AppDrawer, AppConfirmDialog, FormFields, AccountCandidatePicker
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      person: null,
      roles: [],
      uncertain: false,
      checking: false, checkedRows: null, checkError: '', acknowledged: false,
      columns: [
        { key: 'granteeUserNo', title: '受权人工号' },
        { key: 'roleName', title: '临时角色' },
        { key: 'expiresAt', title: '到期时间' },
        { key: 'reason', title: '原因' },
        { key: 'status', title: '状态' },
        { key: 'createdAt', title: '创建时间' },
        { key: 'actions', title: '操作', width: '80px' }
      ],
      form: {
        open: false,
        value: { granteeUserNo: '', roleCode: '', expiresAt: '', reason: '' },
        errors: {},
        submitting: false
      },
      revoke: { open: false, row: null, submitting: false }
    }
  },
  computed: {
    formFields() {
      return [
        { key: 'roleCode', label: '临时角色', type: 'select', required: true, options: this.roles.map(role => ({ value: role.code, label: role.name })) },
        { key: 'reason', label: '授权原因', type: 'textarea', required: true, full: true, hint: '不少于 5 个字' }
      ]
    }
  },
  created() { this.load() },
  methods: {
    openCreate() {
      if (this.uncertain) { this.form.open = true; return }
      this.person = null
      this.form = {
        open: true,
        value: { granteeUserNo: '', roleCode: '', expiresAt: '', reason: '' },
        errors: {},
        submitting: false
      }
    },
    async submitCreate() {
      if (this.form.submitting || this.uncertain) return
      if (!this.person?.id) return toast.error('请查询并选择本校人员')
      if (!this.form.value.expiresAt || new Date(this.form.value.expiresAt).getTime() <= Date.now()) return toast.error('请选择晚于当前时间的到期时间')
      const errors = FormFields.validateRequired(this.formFields, this.form.value)
      this.form.errors = errors
      if (Object.keys(errors).length) return
      this.form.submitting = true
      this.checkedRows = null; this.checkError = ''; this.acknowledged = false
      const res = await systemApi.createDelegation({ ...this.form.value, granteeUserNo: this.person.loginName || this.person.userNo,
        expiresAt: this.form.value.expiresAt.replace('T', ' ') + ':00' })
      this.form.submitting = false
      if (res.code === 0) {
        toast.success('临时授权已创建')
        this.form.open = false
        this.load()
      } else {
        this.uncertain = !['VALIDATION_ERROR', 'NO_PERMISSION', 'DATA_CONFLICT'].includes(res.bizCode)
        if (this.uncertain) this.form.errors = { ...this.form.errors, reason: '结果尚未确认，输入已保留。请先刷新授权清单核对，不能重复提交。' }
        toast.error(res.message)
      }
    },
    askRevoke(row) {
      this.revoke = { open: true, row, submitting: false }
    },
    async checkSubmission() {
      if (!this.uncertain || this.checking) return
      this.checking = true; this.checkedRows = null; this.checkError = ''; this.acknowledged = false
      const context = contextFingerprint(this.ctx)
      try {
        const result = await systemApi.listDelegations()
        if (context !== contextFingerprint(this.ctx)) return
        if (result.code !== 0) { this.checkError = result.message || '核对失败，请重试'; return }
        this.rows = result.data.list || []
        this.checkedRows = this.rows.filter(row => row.granteeUserNo === (this.person.loginName || this.person.userNo) && row.roleCode === this.form.value.roleCode)
      } catch (error) { this.checkError = error.message || '核对失败，请重试' }
      finally { this.checking = false }
    },
    finishCheck() {
      if (this.checking || !this.checkedRows || !this.acknowledged) return
      this.uncertain = false; this.checkedRows = null; this.acknowledged = false
      this.openCreate()
    },
    async doRevoke({ reason }) {
      this.revoke.submitting = true
      const res = await systemApi.revokeDelegation(this.revoke.row.id, { reason })
      this.revoke.submitting = false
      if (res.code === 0) {
        toast.success('临时授权已回收')
        this.revoke.open = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await systemApi.listDelegations()
      if (res.code === 0) {
        this.roles = res.data.assignableRoles || []
        this.rows = (res.data.list || []).map(row => ({ ...row, roleName: row.roleName || this.roles.find(role => role.code === row.roleCode)?.name || '角色名称待核对' }))
      }
      else this.error = res.message
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.delegation-fields { border: 0; padding: 0; margin: 0; min-width: 0; }
</style>
