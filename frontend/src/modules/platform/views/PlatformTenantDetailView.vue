<template>
  <ModulePageShell
    :title="detail ? detail.name : '租户详情'"
    :subtitle="detail ? detail.code + ' · ' + detail.packageName + ' · 到期 ' + detail.expireAt : ''"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <button class="mp-link" @click="$router.push('/admin/platform/tenants')">← 返回租户列表</button>
    </template>

    <div class="mp-stack">
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <template v-else-if="detail">
        <div v-if="detail.status === 'EXPIRING'" class="td-notice td-notice--warn">
          ⚠ 该租户将于 {{ detail.expireAt }} 到期（剩余 {{ detail.remainDays }} 天）；到期后自动锁写（历史可读、可导出）。
          <button class="mp-link" @click="$router.push('/admin/platform/orders')">去处理续费订单 →</button>
        </div>

        <div class="mp-tabs">
          <button v-for="t in tabs" :key="t.key" class="mp-tab" :class="{ 'is-active': tab === t.key }" @click="tab = t.key">{{ t.label }}</button>
        </div>

        <!-- 概览 -->
        <div v-if="tab === 'overview'" class="mp-grid-2">
          <section class="mp-card">
            <header class="mp-card__head"><span class="mp-card__title">基础信息</span>
              <StatusTag :type="statusTone(detail.status)" :label="detail.statusLabel" dot />
            </header>
            <div class="mp-card__body">
              <div class="mp-kv"><span class="mp-kv__k">租户编码</span><span class="mp-kv__v">{{ detail.code }}</span></div>
              <div class="mp-kv"><span class="mp-kv__k">区域</span><span class="mp-kv__v">{{ detail.regionLabel }}</span></div>
              <div class="mp-kv"><span class="mp-kv__k">套餐</span><span class="mp-kv__v">{{ detail.packageName }}</span></div>
              <div class="mp-kv"><span class="mp-kv__k">有效期至</span><span class="mp-kv__v">{{ detail.expireAt }}</span></div>
              <div class="mp-kv"><span class="mp-kv__k">客户成功</span><span class="mp-kv__v">{{ detail.csOwnerName }}</span></div>
              <div class="mp-kv"><span class="mp-kv__k">实施负责人</span><span class="mp-kv__v">{{ detail.implOwnerName }}</span></div>
              <div class="mp-kv"><span class="mp-kv__k">联系人</span><span class="mp-kv__v">{{ detail.contactName }} {{ maskPhone(detail.contactPhone) }}</span></div>
            </div>
          </section>
          <section class="mp-card">
            <header class="mp-card__head"><span class="mp-card__title">用量与限制</span><span class="mp-note">超限 90% 将提醒扩容</span></header>
            <div class="mp-card__body">
              <div class="mp-kv"><span class="mp-kv__k">学生数</span><span class="mp-kv__v">{{ detail.usage.students }}</span></div>
              <div class="mp-kv"><span class="mp-kv__k">教师数</span><span class="mp-kv__v">{{ detail.usage.teachers }}</span></div>
              <div class="mp-kv"><span class="mp-kv__k">存储</span><span class="mp-kv__v">{{ detail.usage.storage }}</span></div>
              <div class="mp-kv"><span class="mp-kv__k">API 今日调用</span><span class="mp-kv__v">{{ detail.usage.apiToday }}</span></div>
            </div>
          </section>
        </div>

        <!-- 品牌配置 -->
        <section v-else-if="tab === 'brand'" class="mp-card">
          <header class="mp-card__head">
            <span class="mp-card__title">租户品牌配置（tenantBrandConfig）</span>
            <span class="mp-note">学校名称由合同核定；简称 / 主色 / 口号 / 水印可代维护</span>
          </header>
          <div class="mp-card__body">
            <FormFields v-model="brandForm" :fields="brandFields" />
            <div class="td-brand-preview" :style="{ '--pv': brandForm.brandColor || '#2563eb' }">
              <span class="td-brand-preview__chip">主色预览</span>
              <span class="td-brand-preview__wm">{{ brandForm.watermarkText }} · 操作人 · 时间</span>
            </div>
            <AppButton
              variant="primary"
              style="margin-top: var(--space-3)"
              :disabled="!can('configTenantBrand')"
              :title="reason('configTenantBrand')"
              :loading="brandSubmitting"
              @click="confirmBrand = can('configTenantBrand')"
            >保存品牌配置</AppButton>
          </div>
        </section>

        <!-- 套餐与模块授权 -->
        <section v-else-if="tab === 'license'" class="mp-card">
          <header class="mp-card__head">
            <span class="mp-card__title">模块授权（{{ detail.packageName }}）</span>
            <span class="mp-note">底座模块随套餐必含，不可单独关闭；开关变更即时生效并留痕</span>
          </header>
          <div class="mp-card__body" style="padding-top: 0">
            <table class="mp-audit">
              <thead><tr><th>模块</th><th>授权状态</th><th>有效期</th><th style="width: 120px">操作</th></tr></thead>
              <tbody>
                <tr v-for="m in detail.moduleLicenses" :key="m.code">
                  <td class="is-who">{{ m.name }}<span v-if="m.locked" class="td-lock">底座</span></td>
                  <td><StatusTag :type="m.enabled ? 'success' : 'default'" :label="m.enabled ? '已开通' : '未开通'" dot /></td>
                  <td>{{ m.enabled ? m.expireAt : '—' }}</td>
                  <td>
                    <span v-if="m.locked" class="mp-note" title="底座模块随套餐必含，不可单独关闭">不可关闭</span>
                    <button
                      v-else-if="m.enabled"
                      class="mp-link td-danger"
                      :class="{ 'is-disabled': !can('configTenantLicense') }"
                      :title="reason('configTenantLicense')"
                      @click="askToggleModule(m, false)"
                    >关闭</button>
                    <button
                      v-else
                      class="mp-link"
                      :class="{ 'is-disabled': !can('configTenantLicense') }"
                      :title="reason('configTenantLicense')"
                      @click="askToggleModule(m, true)"
                    >开通</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <!-- 订单记录 -->
        <section v-else-if="tab === 'orders'" class="mp-card">
          <header class="mp-card__head">
            <span class="mp-card__title">订单记录</span>
            <button class="mp-link" @click="$router.push('/admin/platform/orders')">订单授权中心 →</button>
          </header>
          <div class="mp-card__body" style="padding-top: 0">
            <EmptyState v-if="!detail.orders.length" title="暂无订单" description="可在订单授权中心为该租户创建订单" />
            <table v-else class="mp-audit">
              <thead><tr><th>订单号</th><th>类型</th><th>套餐</th><th>服务期</th><th>状态</th></tr></thead>
              <tbody>
                <tr v-for="o in detail.orders" :key="o.orderNo">
                  <td class="is-who">{{ o.orderNo }}</td><td>{{ o.typeLabel }}</td><td>{{ o.packageName }}</td><td>{{ o.period }}</td><td>{{ o.statusLabel }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <!-- 操作留痕 -->
        <section v-else class="mp-card">
          <header class="mp-card__head"><span class="mp-card__title">操作留痕</span><span class="mp-note">审计记录只增不删</span></header>
          <div class="mp-card__body" style="padding-top: 0">
            <table class="mp-audit">
              <thead><tr><th>操作人</th><th>动作</th><th>影响</th><th style="width: 140px">时间</th></tr></thead>
              <tbody>
                <tr v-for="(a, i) in detail.auditTrail" :key="i">
                  <td class="is-who">{{ a.who }}</td><td>{{ a.action }}</td><td>{{ a.affected }}</td><td>{{ a.time }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </template>
    </div>

    <AppConfirmDialog
      v-model:visible="confirmBrand"
      type="warning"
      title="保存该租户品牌配置？"
      message="品牌项影响该校全端展示，保存后即时生效并写入审计日志。"
      confirm-text="确认保存并生效"
      require-reason
      reason-label="变更原因"
      :submitting="brandSubmitting"
      @confirm="doSaveBrand"
    />
    <AppConfirmDialog
      v-model:visible="confirmModule"
      :type="moduleAction.enabled ? 'primary' : 'danger'"
      :title="(moduleAction.enabled ? '开通' : '关闭') + '模块「' + moduleAction.name + '」？'"
      :message="moduleAction.enabled ? '开通后该校菜单即时可见，按套餐有效期计费。' : '关闭后该校对应菜单灰显、新增拦截、历史数据可读；不删除任何数据。'"
      :confirm-text="moduleAction.enabled ? '确认开通' : '确认关闭并留痕'"
      :require-reason="!moduleAction.enabled"
      reason-label="关闭原因"
      :submitting="moduleSubmitting"
      @confirm="doToggleModule"
    />
  </ModulePageShell>
</template>

<script>
/**
 * 租户详情（/admin/platform/tenants/:id）：
 * 概览 / 品牌配置代维护 / 模块授权开关（底座锁定）/ 订单记录 / 操作留痕。
 */
import { ModulePageShell, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import FormFields from '@/modules/platform/components/FormFields.vue'
import { platformApi } from '@/modules/platform/api/platform.api'
import { toast } from '@/utils/toast'

export default {
  name: 'PlatformTenantDetailView',
  components: { ModulePageShell, StatusTag, LoadingState, ErrorState, EmptyState, AppButton, AppConfirmDialog, FormFields },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      detail: null,
      tab: 'overview',
      tabs: [
        { key: 'overview', label: '概览' },
        { key: 'brand', label: '品牌配置' },
        { key: 'license', label: '套餐与模块授权' },
        { key: 'orders', label: '订单记录' },
        { key: 'audit', label: '操作留痕' }
      ],
      brandForm: {},
      brandSubmitting: false,
      confirmBrand: false,
      confirmModule: false,
      moduleAction: { code: '', name: '', enabled: false },
      moduleSubmitting: false
    }
  },
  computed: {
    brandFields() {
      return [
        { key: 'schoolName', label: '学校名称', disabled: true, lockNote: '（合同核定，变更走平台管理员流程）' },
        { key: 'schoolShortName', label: '学校简称' },
        { key: 'brandColor', label: '租户主色', type: 'color' },
        { key: 'loginSlogan', label: '登录页口号', full: true },
        { key: 'watermarkText', label: '水印文案', full: true, hint: '实际水印 = 文案 · 操作人 · 时间' },
        { key: 'footerText', label: '页脚说明', full: true }
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
    maskPhone(v) {
      return v ? v.slice(0, 3) + '****' + v.slice(-4) : ''
    },
    statusTone(s) {
      return { ACTIVE: 'success', TRIAL: 'processing', EXPIRING: 'warning', EXPIRED: 'danger', SUSPENDED: 'default' }[s] || 'default'
    },
    async doSaveBrand({ reason }) {
      this.brandSubmitting = true
      const res = await platformApi.saveTenantBrand(this.detail.id, { ...this.brandForm }, { reason })
      this.brandSubmitting = false
      if (res.code === 0) {
        toast.success('品牌配置已保存并生效，已写入审计日志')
        this.confirmBrand = false
      } else {
        toast.error(res.message)
      }
    },
    askToggleModule(m, enabled) {
      if (!this.can('configTenantLicense')) return
      this.moduleAction = { code: m.code, name: m.name, enabled }
      this.confirmModule = true
    },
    async doToggleModule({ reason }) {
      this.moduleSubmitting = true
      const res = await platformApi.toggleTenantModule(this.detail.id, { ...this.moduleAction, reason })
      this.moduleSubmitting = false
      if (res.code === 0) {
        toast.success((this.moduleAction.enabled ? '模块已开通' : '模块已关闭（历史可读）') + '，已留痕')
        this.confirmModule = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await platformApi.getTenantDetail(this.$route.params.id)
      if (res.code === 0) {
        this.detail = res.data
        this.brandForm = { ...res.data.brand }
      } else {
        this.error = res.message
      }
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.td-notice {
  font-size: var(--font-size-sm);
  border-radius: var(--radius-base);
  padding: var(--space-2) var(--space-3);
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}
.td-notice--warn {
  color: var(--warning-700);
  background: var(--warning-50);
  border: 1px solid var(--warning-100);
}
.td-lock {
  display: inline-block;
  margin-left: var(--space-1);
  font-size: 10px;
  color: var(--primary-700);
  background: var(--primary-50);
  border-radius: var(--radius-full);
  padding: 0 var(--space-1);
}
.td-danger {
  color: var(--danger-600);
}
.td-brand-preview {
  margin-top: var(--space-3);
  display: flex;
  align-items: center;
  gap: var(--space-3);
  border: 1px dashed var(--border-base);
  border-radius: var(--radius-base);
  padding: var(--space-2) var(--space-3);
}
.td-brand-preview__chip {
  background: var(--pv);
  color: #fff;
  border-radius: var(--radius-full);
  font-size: var(--font-size-xs);
  padding: 2px var(--space-3);
}
.td-brand-preview__wm {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  opacity: 0.7;
  transform: rotate(-2deg);
}
</style>
