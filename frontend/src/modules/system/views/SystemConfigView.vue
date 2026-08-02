<template>
  <ModulePageShell
    title="系统与品牌配置"
    subtitle="租户品牌项 / 安全策略 / 数据导出策略 · 敏感配置变更需二次确认并留痕"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <div class="mp-stack">
      <div class="mp-tabs">
        <button class="mp-tab" :class="{ 'is-active': tab === 'brand' }" @click="tab = 'brand'">品牌配置</button>
        <button class="mp-tab" :class="{ 'is-active': tab === 'system' }" @click="tab = 'system'">系统参数</button>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />

      <!-- ===== 品牌配置 ===== -->
      <template v-else-if="tab === 'brand'">
        <div class="mp-grid-2">
          <section class="mp-card">
            <header class="mp-card__head">
              <span class="mp-card__title">租户品牌项（tenantBrandConfig）</span>
              <span class="mp-note">{{ brand.editableNote }}</span>
            </header>
            <div class="mp-card__body">
              <FormFields v-model="brandForm" :fields="brandFields" :errors="brandErrors" />
              <div class="cf-ops">
                <AppButton variant="primary" :disabled="!can('editBrandConfig')" :title="reason('editBrandConfig')" :loading="brandSubmitting" @click="askSaveBrand">保存品牌配置</AppButton>
                <AppButton variant="warning" :disabled="!can('resetBrandConfig')" :title="reason('resetBrandConfig')" @click="confirmResetBrand = can('resetBrandConfig')">恢复默认</AppButton>
              </div>
            </div>
          </section>

          <section class="mp-card">
            <header class="mp-card__head"><span class="mp-card__title">效果预览</span><span class="mp-note">保存前实时预览</span></header>
            <div class="mp-card__body">
              <div class="cf-preview" :style="{ '--pv': brandForm.brandColor || '#2563eb' }">
                <div class="cf-preview__top">
                  <span class="cf-preview__logo">{{ (brandForm.schoolShortName || brand.schoolName || '').slice(0, 2) }}</span>
                  <span class="cf-preview__name">{{ brand.schoolName }}<i>{{ brand.platformDisplayName }}</i></span>
                  <span class="cf-preview__role">{{ ctx.currentRole.roleName }}</span>
                </div>
                <div class="cf-preview__hero">
                  <b>{{ brand.schoolName }} · 管理端</b>
                  <span>{{ brandForm.loginSlogan }}</span>
                </div>
                <div class="cf-preview__wm">水印预览：{{ brandForm.watermarkText }} · {{ ctx.currentRole.userName }} · {{ previewTime }}</div>
                <button class="cf-preview__btn">主色按钮</button>
              </div>
            </div>
          </section>
        </div>
      </template>

      <!-- ===== 系统参数 ===== -->
      <template v-else>
        <section v-for="group in configGroups" :key="group.name" class="mp-card">
          <header class="mp-card__head">
            <span class="mp-card__title">{{ group.name }}</span>
            <span v-if="group.name === '数据与导出'" class="mp-note">涉敏策略：变更需说明原因并写入审计</span>
          </header>
          <div class="mp-card__body" style="padding-top: 0">
            <table class="mp-audit">
              <thead>
                <tr><th style="width: 180px">配置项</th><th>当前值</th><th style="width: 170px">最近变更</th><th style="width: 90px">操作</th></tr>
              </thead>
              <tbody>
                <tr v-for="c in group.items" :key="c.key">
                  <td class="is-who">{{ c.name }}<span v-if="c.sensitive" class="cf-sens">涉敏</span></td>
                  <td>{{ c.valueText }}</td>
                  <td>{{ c.updatedAt }} · {{ c.updatedBy }}</td>
                  <td>
                    <button class="mp-link" :class="{ 'is-disabled': !can('editSystemConfig') }" :title="reason('editSystemConfig')" @click="openConfigEdit(c)">编辑</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
        <p class="mp-note">系统参数修改须填写原因；所有配置变更保留完整前后值对照，可在日志中心查询。</p>
      </template>
    </div>

    <!-- 编辑系统参数（原因必填） -->
    <AppDrawer v-model:visible="cfgEdit.open" :title="'编辑配置 · ' + cfgEdit.name" mode="modal" size="medium">
      <label class="cf-label">配置值</label>
      <AppTextarea v-model="cfgEdit.valueText" :rows="3" />
      <label class="cf-label" style="margin-top: var(--space-3)">变更原因（写入审计）<span style="color: var(--danger-600)">*</span></label>
      <AppTextarea v-model="cfgEdit.reason" :rows="2" placeholder="至少 5 个字，说明为什么调整" />
      <div v-if="cfgEdit.error" class="mp-form-err">{{ cfgEdit.error }}</div>
      <template #footer>
        <AppButton variant="ghost" @click="cfgEdit.open = false">取消</AppButton>
        <AppButton variant="primary" :loading="cfgEdit.submitting" @click="submitConfigEdit">保存并留痕</AppButton>
      </template>
    </AppDrawer>

    <!-- 保存品牌配置：二次确认 -->
    <AppConfirmDialog
      v-model:visible="confirmSaveBrand"
      type="warning"
      title="保存品牌配置？"
      message="品牌项影响全端展示（顶栏 / 登录页 / 水印 / 主色），保存后即时生效并写入审计日志。"
      confirm-text="确认保存并生效"
      require-reason
      reason-label="变更原因"
      :submitting="brandSubmitting"
      @confirm="doSaveBrand"
    />
    <AppConfirmDialog
      v-model:visible="confirmResetBrand"
      type="danger"
      title="恢复默认品牌配置？"
      message="将丢弃当前学校自定义的简称 / 口号 / 主色 / 水印设置，恢复为平台默认值。该操作需系统管理员权限。"
      confirm-text="确认恢复默认"
      require-reason
      reason-label="操作原因"
      :submitting="brandSubmitting"
      @confirm="doResetBrand"
    />
  </ModulePageShell>
</template>

<script>
/**
 * 系统与品牌配置（/admin/system/config）：
 * 品牌配置（查看/编辑/预览/恢复默认/导出）+ 系统参数分组管理（编辑需原因留痕）。
 */
import { ModulePageShell, ModuleToolbar, LoadingState, ErrorState } from '@/components/business'
import { AppButton } from '@/components/ui'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { AppTextarea } from '@/components/common'
import FormFields from '@/modules/system/components/FormFields.vue'
import { systemApi } from '@/modules/system/api/system.api'
import { toast } from '@/utils/toast'

export default {
  name: 'SystemConfigView',
  components: { ModulePageShell, ModuleToolbar, LoadingState, ErrorState, AppButton, AppDrawer, AppConfirmDialog, AppTextarea, FormFields },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      tab: 'brand',
      loading: true,
      error: '',
      brand: {},
      brandForm: {},
      brandErrors: {},
      brandSubmitting: false,
      previewTime: new Date().toLocaleString('zh-CN', { hour12: false }),
      confirmSaveBrand: false,
      confirmResetBrand: false,
      configs: [],
      cfgEdit: { open: false, key: '', name: '', valueText: '', reason: '', error: '', submitting: false }
    }
  },
  computed: {
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [{ key: 'exportSystemConfig', label: '⇩ 导出配置快照' }]
        .filter((a) => pa[a.key] && pa[a.key].visible)
        .map((a) => ({ ...a, disabled: !pa[a.key].allowed, disabledReason: pa[a.key].reason }))
    },
    brandFields() {
      const locked = '（平台核定，学校侧不可修改）'
      return [
        { key: 'schoolName', label: '学校名称', disabled: true, lockNote: locked },
        { key: 'platformDisplayName', label: '平台显示名', disabled: true, lockNote: locked },
        { key: 'schoolShortName', label: '学校简称', required: true },
        { key: 'brandColor', label: '租户主色', type: 'color' },
        { key: 'loginSlogan', label: '登录页口号', full: true },
        { key: 'watermarkText', label: '水印文案', full: true, hint: '实际水印 = 水印文案 · 当前用户 · 时间，淡色克制平铺' },
        { key: 'watermarkDensity', label: '水印密度', full: true },
        { key: 'footerText', label: '页脚说明', full: true }
      ]
    },
    configGroups() {
      const groups = {}
      this.configs.forEach((c) => {
        groups[c.group] = groups[c.group] || { name: c.group, items: [] }
        groups[c.group].items.push(c)
      })
      return Object.values(groups)
    }
  },
  created() {
    this.syncTabFromRoute()
    this.load()
  },
  watch: {
    '$route.query.tab'() {
      this.syncTabFromRoute()
    }
  },
  methods: {
    syncTabFromRoute() {
      const tab = String(this.$route.query.tab || '')
      if (tab === 'brand' || tab === 'system') this.tab = tab
    },
    can(key) {
      const pa = this.ctx.permissionActions[key]
      return !!(pa && pa.visible && pa.allowed)
    },
    reason(key) {
      const pa = this.ctx.permissionActions[key]
      return pa && !pa.allowed ? pa.reason : ''
    },
    async onToolbar(key) {
      if (key === 'exportSystemConfig') {
        const res = await systemApi.exportConfigs()
        if (res.code === 0) toast.success('配置快照已下载：' + res.data.fileName + '（不含密钥），已留痕')
        else toast.error(res.message)
      }
    },
    askSaveBrand() {
      if (!this.can('editBrandConfig')) return
      this.confirmSaveBrand = true
    },
    async doSaveBrand({ reason }) {
      this.brandSubmitting = true
      const res = await systemApi.saveBrandConfig({ ...this.brandForm }, { reason })
      this.brandSubmitting = false
      if (res.code === 0) {
        toast.success('品牌配置已保存并生效，变更明细已写入审计日志')
        this.confirmSaveBrand = false
        this.brand = res.data
      } else {
        toast.error(res.message)
      }
    },
    async doResetBrand({ reason }) {
      this.brandSubmitting = true
      const res = await systemApi.resetBrandConfig({ reason })
      this.brandSubmitting = false
      if (res.code === 0) {
        this.brand = res.data
        this.brandForm = { ...res.data }
        this.confirmResetBrand = false
        toast.success('品牌配置已恢复为平台默认值并生效，操作已留痕')
      } else {
        toast.error(res.message)
      }
    },
    openConfigEdit(c) {
      if (!this.can('editSystemConfig')) return
      this.cfgEdit = { open: true, key: c.key, name: c.name, valueText: c.valueText, reason: '', error: '', submitting: false }
    },
    async submitConfigEdit() {
      if ((this.cfgEdit.reason || '').trim().length < 5) {
        this.cfgEdit.error = '变更原因必填且不少于 5 个字'
        return
      }
      this.cfgEdit.error = ''
      this.cfgEdit.submitting = true
      const res = await systemApi.saveSystemConfig(this.cfgEdit.key, this.cfgEdit.valueText, { reason: this.cfgEdit.reason })
      this.cfgEdit.submitting = false
      if (res.code === 0) {
        toast.success('配置已保存，前后值对照已写入审计日志')
        this.cfgEdit.open = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const [brandRes, cfgRes] = await Promise.all([systemApi.getBrandConfig(), systemApi.getSystemConfigs()])
      if (brandRes.code === 0) {
        this.brand = brandRes.data
        this.brandForm = { ...brandRes.data }
      } else {
        this.error = brandRes.message
      }
      if (cfgRes.code === 0) this.configs = cfgRes.data
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.cf-ops {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-4);
}
.cf-sens {
  display: inline-block;
  margin-left: var(--space-1);
  font-size: 10px;
  color: var(--warning-600);
  background: var(--warning-50);
  border-radius: var(--radius-full);
  padding: 0 var(--space-1);
}
.cf-label {
  display: block;
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);
  color: var(--text-secondary);
  margin-bottom: var(--space-1);
}
.cf-preview {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  overflow: hidden;
  background: var(--bg-page);
}
.cf-preview__top {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  background: rgba(255, 255, 255, 0.8);
  border-bottom: 1px solid var(--border-light);
  backdrop-filter: blur(8px);
}
.cf-preview__logo {
  width: 26px;
  height: 26px;
  border-radius: var(--radius-base);
  background: var(--pv);
  color: #fff;
  font-size: var(--font-size-xs);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.cf-preview__name {
  display: flex;
  flex-direction: column;
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  line-height: 1.2;
}
.cf-preview__name i {
  font-style: normal;
  font-size: 10px;
  color: var(--text-tertiary);
  font-weight: var(--font-weight-normal);
}
.cf-preview__role {
  margin-left: auto;
  font-size: var(--font-size-xs);
  color: var(--pv);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-full);
  padding: 0 var(--space-2);
}
.cf-preview__hero {
  margin: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
  background: linear-gradient(115deg, #0b2352, var(--pv));
  color: #fff;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.cf-preview__hero span {
  font-size: var(--font-size-xs);
  opacity: 0.85;
}
.cf-preview__wm {
  margin: 0 var(--space-3);
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  opacity: 0.6;
  transform: rotate(-2deg);
}
.cf-preview__btn {
  margin: var(--space-3);
  border: none;
  border-radius: var(--radius-base);
  background: var(--pv);
  color: #fff;
  font-size: var(--font-size-sm);
  padding: var(--space-2) var(--space-4);
  cursor: default;
}
</style>
