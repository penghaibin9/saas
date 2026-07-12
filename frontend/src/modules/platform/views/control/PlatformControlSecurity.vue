<template>
  <ModulePageShell title="安全策略" subtitle="登录锁定 / 令牌时长 / 限流 / 跨域，越界值将被后端拒绝（不允许不设防）" role-name="平台超级管理员" data-scope-name="全平台（跨租户）">
    <LoadingState v-if="loading" text="正在加载安全参数…" />
    <AppCard v-else class="pcs__panel">
      <AppSectionHeader title="全局安全参数" />
      <div class="pcs__grid">
        <label v-for="f in fields" :key="f.key" class="pcs__field">
          <span>{{ f.label }}<em v-if="bounds[f.key]" class="pcs__bound">（{{ bounds[f.key][0] }} ~ {{ bounds[f.key][1] }}）</em></span>
          <input v-if="f.type === 'number'" v-model.number="security[f.key]" type="number" class="pcs__input" />
          <input v-else-if="f.type === 'bool'" v-model="security[f.key]" type="checkbox" class="pcs__check" />
          <input v-else v-model="security[f.key]" class="pcs__input" />
        </label>
      </div>
      <div class="pcs__ops">
        <AppButton variant="primary" :loading="saving" @click="save">保存安全参数</AppButton>
        <span class="pcs__tip">保存即生效；参数越界会被拒绝并提示合法范围</span>
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
  name: 'PlatformControlSecurity',
  components: { AppButton, AppCard, AppSectionHeader, LoadingState, ModulePageShell },
  data() {
    return {
      loading: true,
      saving: false,
      security: {},
      bounds: {},
      fields: [
        { key: 'loginFailMaxTimes', label: '登录失败锁定次数', type: 'number' },
        { key: 'loginFailLockMinutes', label: '锁定时长（分钟）', type: 'number' },
        { key: 'accessTokenExpireMinutes', label: 'AccessToken 有效期（分钟）', type: 'number' },
        { key: 'refreshTokenExpireDays', label: 'RefreshToken 有效期（天）', type: 'number' },
        { key: 'uploadMaxSizeMb', label: '上传大小上限（MB）', type: 'number' },
        { key: 'exportRateLimitPerMinute', label: '导出限流（次/分钟）', type: 'number' },
        { key: 'uploadRateLimitPerMinute', label: '上传限流（次/分钟）', type: 'number' },
        { key: 'normalApiRateLimitPerMinute', label: '普通接口限流（次/分钟）', type: 'number' },
        { key: 'corsAllowedOrigins', label: '允许跨域来源（逗号分隔）', type: 'text' },
        { key: 'docsEnabledInProduction', label: '生产环境开放 /docs', type: 'bool' }
      ]
    }
  },
  created() {
    this.load()
  },
  methods: {
    async load() {
      this.loading = true
      const res = await platformControlApi.getSecurity()
      this.loading = false
      if (res.code === 0) {
        this.security = res.data.security
        this.bounds = res.data.bounds || {}
      } else {
        toast.error(res.message)
      }
    },
    async save() {
      this.saving = true
      const res = await platformControlApi.putSecurity({ ...this.security })
      this.saving = false
      if (res.code === 0) {
        this.security = res.data.security
        toast.success('安全参数已保存')
      } else {
        toast.error(res.message)
      }
    }
  }
}
</script>

<style scoped>
.pcs__panel {
  padding: var(--space-4);
}
.pcs__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: var(--space-3);
  margin-top: var(--space-3);
}
.pcs__field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.pcs__bound {
  font-style: normal;
  color: var(--text-tertiary);
  font-size: 12px;
}
.pcs__input {
  height: 34px;
  padding: 0 10px;
  border: 1px solid var(--card-b);
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.85);
  color: var(--t1);
  font-size: 13px;
  font-family: inherit;
}
.pcs__input:focus {
  outline: none;
  border-color: var(--glow);
}
.pcs__check {
  width: 16px;
  height: 16px;
}
.pcs__ops {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-top: var(--space-4);
}
.pcs__tip {
  font-size: 12px;
  color: var(--text-tertiary);
}
</style>
