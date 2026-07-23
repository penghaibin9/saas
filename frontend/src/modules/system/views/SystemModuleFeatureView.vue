<template>
  <ModulePageShell
    title="模块授权与业务开关"
    subtitle="套餐开通状态只读 · 学校可在授权范围内调整业务开关"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="[{ key: 'save', label: '保存开关', variant: 'primary' }]" @action="askSave" />
    </template>

    <div class="mp-stack">
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <section v-else class="mp-card">
        <header class="mp-card__head"><span class="mp-card__title">业务中心开关</span></header>
        <div class="mp-card__body">
          <label v-for="(item, key) in features" :key="key" class="mf-row">
            <input v-model="item.enabled" type="checkbox" />
            <span class="mf-row__label">{{ item.label || key }}</span>
            <span class="mp-note">{{ item.expiresAt ? ('授权至 ' + item.expiresAt) : '当前套餐已开通' }}</span>
          </label>
        </div>
      </section>
    </div>

    <AppConfirmDialog
      v-model:visible="confirmOpen"
      type="warning"
      title="保存业务开关？"
      message="调整将即时影响本校菜单与模块入口，须填写原因并写入审计。"
      confirm-text="确认保存"
      require-reason
      reason-label="调整原因"
      :submitting="submitting"
      @confirm="doSave"
    />
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, ModuleToolbar, LoadingState, ErrorState } from '@/components/business'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { systemApi } from '@/modules/system/api/system.api'
import { toast } from '@/utils/toast'

export default {
  name: 'SystemModuleFeatureView',
  components: { ModulePageShell, ModuleToolbar, LoadingState, ErrorState, AppConfirmDialog },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      features: {},
      confirmOpen: false,
      submitting: false
    }
  },
  created() { this.load() },
  methods: {
    askSave() { this.confirmOpen = true },
    async doSave({ reason }) {
      this.submitting = true
      const payload = {}
      Object.keys(this.features).forEach((key) => {
        payload[key] = { enabled: !!this.features[key].enabled }
      })
      const res = await systemApi.saveModuleFeatures(payload, { reason })
      this.submitting = false
      if (res.code === 0) {
        toast.success('业务开关已更新')
        this.confirmOpen = false
        this.features = res.data || this.features
      } else {
        toast.error(res.message)
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await systemApi.getModuleFeatures()
      if (res.code === 0) this.features = res.data || {}
      else this.error = res.message
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.mf-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) 0;
  border-bottom: 1px solid var(--border-light);
}
.mf-row__label {
  min-width: 140px;
  font-weight: var(--font-weight-medium);
}
</style>
