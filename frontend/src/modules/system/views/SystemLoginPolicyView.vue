<template>
  <ModulePageShell
    title="登录与安全策略"
    subtitle="SEC_* 配置真实生效于登录锁定与密码校验；每个值都能看到来自哪一层、平台底线是多少"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <template v-else>
        <section class="mp-card">
          <header class="mp-card__head">
            <span class="mp-card__title">安全策略（SEC_*）</span>
            <span class="mp-note">变更需填写原因并写入审计；越过平台底线会被拒绝</span>
          </header>
          <div class="mp-card__body" style="padding-top: 0">
            <table class="mp-audit">
              <thead>
                <tr>
                  <th style="width: 230px">配置项</th>
                  <th style="width: 90px">当前值</th>
                  <th style="width: 130px">生效来源</th>
                  <th style="width: 120px">平台允许范围</th>
                  <th>真实读取方</th>
                  <th style="width: 100px">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="c in configs" :key="c.configKey">
                  <td class="is-who">
                    {{ c.configName || c.configKey }}
                    <span class="lp-key">{{ c.configKey }}</span>
                  </td>
                  <td><b>{{ c.value }}</b></td>
                  <td><StatusTag :type="sourceTagType(c.sourceLayer)" :label="sourceLabel(c.sourceLayer)" /></td>
                  <td class="mp-cell-sub">{{ floorText(c.platformFloor) }}</td>
                  <td class="mp-cell-sub">
                    <template v-if="c.consumers && c.consumers.length">
                      {{ c.consumers.join('、') }}
                    </template>
                    <span v-else class="lp-warn">暂无消费者，改了不会有行为变化</span>
                  </td>
                  <td>
                    <button class="mp-link" :disabled="!c.schoolEditable" @click="openEdit(c)">编辑</button>
                    <button class="mp-link" @click="openHistory(c)">历史</button>
                  </td>
                </tr>
              </tbody>
            </table>
            <EmptyState v-if="!configs.length" title="未找到安全配置定义" description="请刷新页面重新初始化配置目录" />
          </div>
        </section>

        <section v-if="detail" class="mp-card">
          <header class="mp-card__head">
            <span class="mp-card__title">{{ detail.configName || detail.configKey }} · 来源链</span>
            <button class="mp-link" @click="detail = null">收起</button>
          </header>
          <div class="mp-card__body">
            <p v-for="(layer, i) in detail.chain" :key="i" class="lp-chain">
              <span class="lp-chain__layer">{{ sourceLabel(layer.layer) }}</span>
              <template v-if="layer.constraint">
                允许范围 {{ floorText(layer.constraint) }}
              </template>
              <template v-else>
                值 = {{ layer.value }}
                <template v-if="layer.scopeId">（作用对象 {{ layer.scopeId }}）</template>
                <template v-if="layer.effectiveAt">，{{ fmt(layer.effectiveAt) }} 起</template>
                <template v-if="layer.expiresAt">，至 {{ fmt(layer.expiresAt) }}</template>
              </template>
              <span v-if="i === detail.chain.length - 1" class="lp-final">← 最终生效</span>
            </p>
          </div>
        </section>
      </template>
    </div>

    <AppDrawer v-model:visible="edit.open" :title="'编辑 · ' + edit.name">
      <p class="lp-tip">
        平台允许范围 {{ floorText(edit.floor) }}；超出会被后端拒绝，不会被悄悄改成边界值。
      </p>
      <label class="lp-label">配置值<span class="lp-required">*</span></label>
      <input v-model="edit.value" class="mp-input" />

      <label class="lp-label">生效时间（留空=立即）</label>
      <input v-model="edit.effectiveAt" type="datetime-local" class="mp-input" />

      <label class="lp-label">变更原因<span class="lp-required">*</span></label>
      <textarea v-model="edit.reason" class="mp-textarea" rows="2" placeholder="至少 5 个字" />

      <div v-if="edit.error" class="mp-form-err">{{ edit.error }}</div>
      <template #footer>
        <AppButton variant="ghost" @click="edit.open = false">取消</AppButton>
        <AppButton variant="primary" :loading="edit.submitting" @click="submitEdit">保存并留痕</AppButton>
      </template>
    </AppDrawer>

    <AppDrawer v-model:visible="history.open" :title="'变更历史 · ' + history.name">
      <LoadingState v-if="history.loading" />
      <template v-else>
        <table v-if="history.items.length" class="mp-audit">
          <thead><tr><th style="width: 150px">时间</th><th style="width: 110px">变化</th><th>原因</th></tr></thead>
          <tbody>
            <tr v-for="(h, i) in history.items" :key="i">
              <td>{{ fmt(h.occurredAt) }}</td>
              <td>{{ (h.before && h.before.value) ?? '—' }} → {{ (h.after && h.after.value) ?? '—' }}</td>
              <td>{{ h.reason || '—' }}</td>
            </tr>
          </tbody>
        </table>
        <EmptyState v-else title="暂无变更记录" description="" />
      </template>
    </AppDrawer>
  </ModulePageShell>
</template>

<script>
/**
 * 登录与安全策略（/admin/system/login-policy）。
 * SYS-11 起读取走后端唯一 Resolver：PLATFORM_FLOOR → PACKAGE_DEFAULT → t_sys_config
 * → 学校/组织/学期覆盖。页面只展示后端算出的链，不自行推断来源，也不做本地夹逼。
 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState, StatusTag } from '@/components/business'
import { AppButton } from '@/components/ui'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import { systemApi } from '@/modules/system/api/system.api'
import { toast } from '@/utils/toast'

const SOURCE_LABEL = {
  PLATFORM_FLOOR: '平台底线',
  PACKAGE_DEFAULT: '套餐默认',
  TENANT_LEGACY: '学校配置',
  TENANT: '学校覆盖',
  ORG_UNIT: '组织覆盖',
  TERM: '学期覆盖'
}

export default {
  name: 'SystemLoginPolicyView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, StatusTag, AppButton, AppDrawer },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      configs: [],
      detail: null,
      edit: {
        open: false, configKey: '', name: '', value: '', floor: null,
        effectiveAt: '', reason: '', error: '', submitting: false
      },
      history: { open: false, loading: false, name: '', items: [] }
    }
  },
  created() { this.load() },
  methods: {
    fmt(v) { return v ? String(v).replace('T', ' ').slice(0, 16) : '—' },
    sourceLabel(s) { return SOURCE_LABEL[s] || s || '—' },
    sourceTagType(s) {
      if (s === 'TENANT' || s === 'ORG_UNIT' || s === 'TERM') return 'processing'
      if (s === 'TENANT_LEGACY') return 'info'
      return 'default'
    },
    floorText(floor) {
      if (!floor) return '不限'
      if (floor.enum) return floor.enum.join(' / ')
      const min = floor.min ?? '不限'
      const max = floor.max ?? '不限'
      return `${min} ~ ${max}`
    },

    async load() {
      this.loading = true
      this.error = ''
      const res = await systemApi.getEffectiveConfig({ domain: 'SECURITY' })
      if (res.code === 0) this.configs = (res.data || {}).items || []
      else this.error = res.message
      this.loading = false
    },

    openEdit(c) {
      this.edit = {
        open: true, configKey: c.configKey, name: c.configName || c.configKey,
        value: String(c.value ?? ''), floor: c.platformFloor,
        effectiveAt: '', reason: '', error: '', submitting: false
      }
      this.detail = c
    },

    async submitEdit() {
      if (!String(this.edit.value).trim()) { this.edit.error = '请填写配置值'; return }
      if (this.edit.reason.trim().length < 5) { this.edit.error = '变更原因不少于 5 个字'; return }
      this.edit.submitting = true
      this.edit.error = ''
      const res = await systemApi.setConfigOverride({
        configKey: this.edit.configKey,
        value: this.edit.value,
        scopeType: 'TENANT',
        effectiveAt: this.edit.effectiveAt ? new Date(this.edit.effectiveAt).toISOString() : null,
        reason: this.edit.reason.trim()
      })
      this.edit.submitting = false
      if (res.code === 0) {
        toast.success('安全策略已保存并写入审计')
        this.edit.open = false
        await this.load()
        this.detail = this.configs.find((c) => c.configKey === this.edit.configKey) || null
      } else {
        // 越过平台底线时后端返回明确错误码与允许区间，直接展示给管理员
        this.edit.error = res.message
      }
    },

    async openHistory(c) {
      this.history = { open: true, loading: true, name: c.configName || c.configKey, items: [] }
      const res = await systemApi.getConfigHistory(c.configKey)
      this.history.loading = false
      if (res.code === 0) this.history.items = (res.data || {}).items || []
      else toast.error(res.message)
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
  margin-top: var(--space-3);
  margin-bottom: var(--space-1);
  font-size: var(--font-size-sm);
}
.lp-required { color: var(--danger-600); }
.lp-tip { margin: 0; font-size: var(--font-size-sm); color: var(--text-secondary); }
.lp-warn { color: var(--warning-600, var(--text-tertiary)); }
.lp-chain {
  margin: 0 0 var(--space-2);
  font-size: var(--font-size-sm);
}
.lp-chain__layer {
  display: inline-block;
  min-width: 90px;
  margin-right: var(--space-2);
  padding: 0 var(--space-1);
  border-radius: var(--radius-sm);
  background: var(--fill-secondary);
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
}
.lp-final {
  margin-left: var(--space-2);
  color: var(--success-600, var(--text-primary));
  font-weight: 600;
}
</style>
