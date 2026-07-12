<template>
  <ModulePageShell title="平台系统参数" subtitle="平台名称 / 试用咨询电话 / 试用默认时长 / 到期提醒" role-name="平台超级管理员" data-scope-name="全平台（跨租户）">
    <LoadingState v-if="loading" text="正在加载系统参数…" />
    <AppCard v-else class="pcst__panel">
      <AppSectionHeader title="全局参数" />
      <div class="pcst__grid">
        <label class="pcst__field"><span>平台名称</span><input v-model.trim="settings.platformName" class="pcst__input" /></label>
        <label class="pcst__field"><span>试用咨询电话</span><input v-model.trim="settings.trialContactPhone" class="pcst__input" /></label>
        <label class="pcst__field"><span>试用默认时长（天）</span><input v-model.number="settings.trialDefaultDays" type="number" class="pcst__input" /></label>
        <label class="pcst__field"><span>到期提前提醒（天）</span><input v-model.number="settings.expireRemindDays" type="number" class="pcst__input" /></label>
        <label class="pcst__field"><span>演示租户编码</span><input v-model.trim="settings.demoTenantCode" class="pcst__input" /></label>
        <label class="pcst__field pcst__field--row"><span>开放自助注册</span><input v-model="settings.allowSelfRegister" type="checkbox" class="pcst__check" /></label>
      </div>
      <div class="pcst__ops">
        <AppButton variant="primary" :loading="saving" @click="save">保存系统参数</AppButton>
      </div>
    </AppCard>
  </ModulePageShell>
</template>

<script>
import { AppButton, AppCard, AppSectionHeader } from '@/components/ui'
import { LoadingState, ModulePageShell } from '@/components/business'
import { platformControlApi } from '@/modules/platform/api/platformControl.api'
import { toast } from '@/utils/toast'

export default {
  name: 'PlatformControlSettings',
  components: { AppButton, AppCard, AppSectionHeader, LoadingState, ModulePageShell },
  data() {
    return { loading: true, saving: false, settings: {} }
  },
  created() {
    this.load()
  },
  methods: {
    async load() {
      this.loading = true
      const res = await platformControlApi.getSettings()
      this.loading = false
      if (res.code === 0) this.settings = res.data.settings
      else toast.error(res.message)
    },
    async save() {
      this.saving = true
      const res = await platformControlApi.putSettings({ ...this.settings })
      this.saving = false
      if (res.code === 0) {
        this.settings = res.data.settings
        toast.success('系统参数已保存')
      } else {
        toast.error(res.message)
      }
    }
  }
}
</script>

<style scoped>
.pcst__panel {
  padding: var(--space-4);
}
.pcst__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: var(--space-3);
  margin-top: var(--space-3);
}
.pcst__field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.pcst__field--row {
  flex-direction: row;
  align-items: center;
  gap: var(--space-2);
}
.pcst__input {
  height: 34px;
  padding: 0 10px;
  border: 1px solid var(--card-b);
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.85);
  color: var(--t1);
  font-size: 13px;
  font-family: inherit;
}
.pcst__input:focus {
  outline: none;
  border-color: var(--glow);
}
.pcst__check {
  width: 16px;
  height: 16px;
}
.pcst__ops {
  margin-top: var(--space-4);
}
</style>
