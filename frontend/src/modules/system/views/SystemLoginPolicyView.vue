<template>
  <ModulePageShell
    title="登录与安全策略"
    subtitle="SEC_* 配置真实生效于登录锁定与密码校验"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <section v-else class="mp-card">
        <header class="mp-card__head">
          <span class="mp-card__title">安全策略（SEC_*）</span>
          <span class="mp-note">变更需填写原因并写入审计</span>
        </header>
        <div class="mp-card__body" style="padding-top: 0">
          <table class="mp-audit">
            <thead>
              <tr><th style="width: 220px">配置项</th><th>当前值</th><th style="width: 170px">最近变更</th><th style="width: 90px">操作</th></tr>
            </thead>
            <tbody>
              <tr v-for="c in secConfigs" :key="c.key">
                <td class="is-who">{{ c.name }}<span class="lp-key">{{ c.key }}</span></td>
                <td>{{ c.valueText }}</td>
                <td>{{ c.updatedAt || '—' }} · {{ c.updatedBy || '—' }}</td>
                <td><button class="mp-link" @click="openEdit(c)">编辑</button></td>
              </tr>
            </tbody>
          </table>
          <EmptyState v-if="!secConfigs.length" title="未找到 SEC_* 配置" description="请先在系统参数中初始化安全策略项" />
        </div>
      </section>
    </div>

    <AppDrawer v-model:visible="edit.open" :title="'编辑 · ' + edit.name" mode="modal" size="medium">
      <label class="lp-label">配置值</label>
      <AppTextarea v-model="edit.valueText" :rows="2" />
      <label class="lp-label" style="margin-top: var(--space-3)">变更原因<span style="color: var(--danger-600)">*</span></label>
      <AppTextarea v-model="edit.reason" :rows="2" placeholder="至少 5 个字" />
      <div v-if="edit.error" class="mp-form-err">{{ edit.error }}</div>
      <template #footer>
        <AppButton variant="ghost" @click="edit.open = false">取消</AppButton>
        <AppButton variant="primary" :loading="edit.submitting" @click="submitEdit">保存并留痕</AppButton>
      </template>
    </AppDrawer>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import { AppTextarea } from '@/components/common'
import { systemApi } from '@/modules/system/api/system.api'
import { toast } from '@/utils/toast'

const SEC_KEYS = ['SEC_LOCK_MAX_FAIL', 'SEC_LOCK_MINUTES', 'SEC_PASSWORD_MIN_LEN']

export default {
  name: 'SystemLoginPolicyView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppButton, AppDrawer, AppTextarea },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      configs: [],
      edit: { open: false, key: '', name: '', valueText: '', reason: '', error: '', submitting: false }
    }
  },
  computed: {
    secConfigs() {
      return this.configs.filter((c) => SEC_KEYS.includes(c.key) || String(c.key || '').startsWith('SEC_'))
    }
  },
  created() { this.load() },
  methods: {
    openEdit(c) {
      this.edit = { open: true, key: c.key, name: c.name, valueText: c.valueText, reason: '', error: '', submitting: false }
    },
    async submitEdit() {
      if (!this.edit.reason || this.edit.reason.trim().length < 5) {
        this.edit.error = '变更原因不少于 5 个字'
        return
      }
      this.edit.submitting = true
      const res = await systemApi.saveConfig(this.edit.key, this.edit.valueText, { reason: this.edit.reason })
      this.edit.submitting = false
      if (res.code === 0) {
        toast.success('安全策略已保存并生效')
        this.edit.open = false
        this.load()
      } else {
        this.edit.error = res.message
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await systemApi.getConfigs()
      if (res.code === 0) this.configs = res.data || []
      else this.error = res.message
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.lp-key {
  display: block;
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  font-weight: normal;
}
.lp-label {
  display: block;
  font-size: var(--font-size-sm);
  margin-bottom: var(--space-1);
}
</style>
