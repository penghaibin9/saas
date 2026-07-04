<template>
  <ModulePageShell
    title="套餐 / 模块授权管理"
    subtitle="单模块 / 组合 / 旗舰套餐定义 · 底座模块（主档 / 权限流程 / 集成 / PC 端）随套餐必含"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <div class="mp-stack">
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="暂无套餐" description="请由平台管理员创建套餐定义" />
      <div v-else class="mp-grid-cards">
        <section v-for="p in rows" :key="p.id" class="mp-card pk-card">
          <header class="mp-card__head">
            <span class="mp-card__title">{{ p.name }}</span>
            <StatusTag :type="p.status === 'ENABLED' ? 'success' : 'default'" :label="p.statusLabel" dot />
          </header>
          <div class="mp-card__body">
            <p class="pk-pos">{{ p.positioning }}</p>
            <div class="pk-mods">
              <span v-for="code in p.modules" :key="code" class="pk-mod" :title="moduleName(code)">{{ moduleName(code) }}</span>
            </div>
            <div class="mp-kv"><span class="mp-kv__k">学生 / 教师上限</span><span class="mp-kv__v">{{ p.limits.students.toLocaleString() }} / {{ p.limits.teachers.toLocaleString() }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">存储 / API 日配额</span><span class="mp-kv__v">{{ p.limits.storageGB }} GB / {{ p.limits.apiQpd.toLocaleString() }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">定价口径</span><span class="mp-kv__v">{{ p.priceNote }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">在用租户</span><span class="mp-kv__v">{{ p.tenantCount }} 个 · 更新于 {{ p.updatedAt }}</span></div>
            <div class="pk-ops">
              <button class="mp-link" @click="openDetail(p)">查看</button>
              <button class="mp-link" :class="{ 'is-disabled': !can('editPackage') }" :title="reason('editPackage')" @click="openEdit(p)">编辑</button>
              <button class="mp-link" :class="{ 'is-disabled': !can('exportPackageConfig') }" :title="reason('exportPackageConfig')" @click="doExport(p)">导出配置</button>
              <button
                v-if="p.status === 'ENABLED'"
                class="mp-link pk-danger"
                :class="{ 'is-disabled': !can('disablePackage') }"
                :title="reason('disablePackage')"
                @click="askDisable(p)"
              >停售</button>
            </div>
          </div>
        </section>
      </div>
      <p class="mp-note">套餐停售为逻辑操作：仅停止新售，存量租户授权不受影响；套餐定义变更全部写入审计日志。</p>
    </div>

    <!-- 新增 / 编辑套餐 -->
    <AppDrawer v-model:visible="form.open" :title="form.id ? '编辑套餐' : '新增套餐'">
      <FormFields v-model="form.value" :fields="formFields" :errors="form.errors" />
      <p class="mp-note" style="margin-top: var(--space-3)">底座模块（学生主档 / PC 管理端 / 权限与流程 / 集成开放）随任意套餐自动包含，无需勾选。</p>
      <template #footer>
        <AppButton variant="ghost" @click="form.open = false">取消</AppButton>
        <AppButton variant="primary" :loading="form.submitting" @click="submitForm">保存套餐</AppButton>
      </template>
    </AppDrawer>

    <!-- 套餐详情 -->
    <AppDrawer v-model:visible="detail.open" :title="'套餐详情 · ' + (detail.data ? detail.data.name : '')">
      <LoadingState v-if="detail.loading" />
      <template v-else-if="detail.data">
        <div class="mp-kv"><span class="mp-kv__k">定位</span><span class="mp-kv__v">{{ detail.data.positioning }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">包含模块</span><span class="mp-kv__v">{{ detail.data.modules.map(moduleName).join('、') }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">限制</span><span class="mp-kv__v">学生 {{ detail.data.limits.students.toLocaleString() }} · 教师 {{ detail.data.limits.teachers.toLocaleString() }} · 存储 {{ detail.data.limits.storageGB }}GB · API {{ detail.data.limits.apiQpd.toLocaleString() }}/日</span></div>
        <h4 class="pk-sec">操作留痕</h4>
        <EmptyState v-if="!detail.data.auditTrail.length" title="暂无变更记录" description="套餐创建后的每次调整都会记录在此" />
        <table v-else class="mp-audit">
          <thead><tr><th>操作人</th><th>动作</th><th>影响</th><th>时间</th></tr></thead>
          <tbody>
            <tr v-for="(a, i) in detail.data.auditTrail" :key="i">
              <td class="is-who">{{ a.who }}</td><td>{{ a.action }}</td><td>{{ a.affected }}</td><td>{{ a.time }}</td>
            </tr>
          </tbody>
        </table>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="confirmDisable"
      type="danger"
      :title="'停售套餐「' + (disableRow ? disableRow.name : '') + '」？'"
      message="停售后不可再售卖给新租户；存量租户授权与续费不受影响（逻辑操作，可恢复）。"
      confirm-text="确认停售并留痕"
      require-reason
      reason-label="停售原因"
      :submitting="disableSubmitting"
      @confirm="doDisable"
    />
  </ModulePageShell>
</template>

<script>
/**
 * 套餐 / 模块授权管理（/admin/platform/packages）：
 * 套餐卡片 / 新增编辑（平台管理员权限，运营侧置灰演示）/ 停售留痕 / 模块与限制配置 / 导出配置。
 */
import { ModulePageShell, ModuleToolbar, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import FormFields from '@/modules/platform/components/FormFields.vue'
import { platformApi } from '@/modules/platform/api/platform.api'
import { toast } from '@/utils/toast'

export default {
  name: 'PlatformPackageView',
  components: { ModulePageShell, ModuleToolbar, StatusTag, LoadingState, ErrorState, EmptyState, AppButton, AppDrawer, AppConfirmDialog, FormFields },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      form: { open: false, id: '', value: {}, errors: {}, submitting: false },
      detail: { open: false, loading: false, data: null },
      confirmDisable: false,
      disableRow: null,
      disableSubmitting: false
    }
  },
  computed: {
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [{ key: 'createPackage', label: '＋ 新增套餐', variant: 'primary' }]
        .filter((a) => pa[a.key] && pa[a.key].visible)
        .map((a) => ({ ...a, disabled: !pa[a.key].allowed, disabledReason: pa[a.key].reason }))
    },
    optionalModules() {
      return this.ctx.moduleLicenseList.filter((m) => !m.required).map((m) => ({ value: m.code, label: m.name }))
    },
    formFields() {
      return [
        { key: 'name', label: '套餐名称', required: true },
        { key: 'positioning', label: '销售定位', placeholder: '如：实习就业处首购切入' },
        { key: 'modules', label: '可选业务模块', type: 'checkbox-group', full: true, options: this.optionalModules, required: true },
        { key: 'priceNote', label: '定价口径', full: true, placeholder: '如：按年订阅 · 3~5 万/年' }
      ]
    }
  },
  created() {
    this.load()
  },
  methods: {
    can(key) {
      const pa = this.ctx.permissionActions[key]
      return !!(pa && pa.visible && pa.allowed)
    },
    reason(key) {
      const pa = this.ctx.permissionActions[key]
      return pa && !pa.allowed ? pa.reason : ''
    },
    moduleName(code) {
      const hit = this.ctx.moduleLicenseList.find((m) => m.code === code)
      return hit ? hit.name : code
    },
    onToolbar(key) {
      if (key === 'createPackage') this.openEdit(null)
    },
    openEdit(row) {
      const key = row ? 'editPackage' : 'createPackage'
      if (!this.can(key)) return
      const required = this.ctx.moduleLicenseList.filter((m) => m.required).map((m) => m.code)
      this.form = {
        open: true,
        id: row ? row.id : '',
        value: row
          ? { name: row.name, positioning: row.positioning, modules: row.modules.filter((c) => !required.includes(c)), priceNote: row.priceNote }
          : { name: '', positioning: '', modules: [], priceNote: '' },
        errors: {},
        submitting: false
      }
    },
    async submitForm() {
      const errors = FormFields.validateRequired(this.formFields, this.form.value)
      this.form.errors = errors
      if (Object.keys(errors).length) return
      this.form.submitting = true
      const required = this.ctx.moduleLicenseList.filter((m) => m.required).map((m) => m.code)
      const res = await platformApi.savePackage({
        id: this.form.id || undefined,
        ...this.form.value,
        modules: [...new Set([...required, ...(this.form.value.modules || [])])]
      })
      this.form.submitting = false
      if (res.code === 0) {
        toast.success('套餐已保存并留痕')
        this.form.open = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async openDetail(row) {
      this.detail = { open: true, loading: true, data: null }
      const res = await platformApi.getPackageDetail(row.id)
      this.detail.loading = false
      if (res.code === 0) this.detail.data = res.data
    },
    async doExport(row) {
      if (!this.can('exportPackageConfig')) return
      const res = await platformApi.exportPackageConfig(row.id)
      if (res.code === 0) toast.success('导出任务已创建：' + res.data.fileName + '（含水印），已留痕')
    },
    askDisable(row) {
      if (!this.can('disablePackage')) return
      this.disableRow = row
      this.confirmDisable = true
    },
    async doDisable({ reason }) {
      this.disableSubmitting = true
      const res = await platformApi.disablePackage(this.disableRow.id, { reason })
      this.disableSubmitting = false
      if (res.code === 0) {
        toast.success('套餐已停售（逻辑操作），原因已留痕')
        this.confirmDisable = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await platformApi.getPackages()
      if (res.code === 0) this.rows = res.data.list
      else this.error = res.message
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.pk-card {
  display: flex;
  flex-direction: column;
}
.pk-pos {
  margin: 0 0 var(--space-2);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.pk-mods {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
  margin-bottom: var(--space-2);
}
.pk-mod {
  font-size: 10px;
  color: var(--primary-700);
  background: var(--primary-50);
  border: 1px solid var(--primary-100);
  border-radius: var(--radius-full);
  padding: 0 var(--space-2);
  white-space: nowrap;
}
.pk-ops {
  margin-top: var(--space-3);
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.pk-danger {
  color: var(--danger-600);
}
.pk-sec {
  margin: var(--space-4) 0 var(--space-2);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
}
</style>
