<template>
  <div class="wf-page">
    <AppSectionHeader title="权限点管理" subtitle="module.resource.action 三段式权限点，供菜单/页面/按钮/数据四级控制消费" />

    <div class="wf-page__filters">
      <select v-model="filters.moduleCode" @change="load">
        <option value="">全部模块</option>
        <option v-for="(label, code) in moduleOptions" :key="code" :value="code">{{ label }}</option>
      </select>
      <select v-model="filters.type" @change="load">
        <option value="">全部类型</option>
        <option v-for="(label, code) in typeOptions" :key="code" :value="code">{{ label }}</option>
      </select>
      <input v-model.trim="filters.keyword" placeholder="搜索权限点 key / 名称" @keyup.enter="load" />
      <AppButton variant="secondary" @click="load">查询</AppButton>
    </div>

    <WorkflowStateBlock :loading="loading" :error="error" :empty="!list.length" :view-state="viewState" @retry="load">
      <AppCard class="wf-page__card">
        <table class="wf-table">
          <thead>
            <tr><th>权限点</th><th>名称</th><th>模块</th><th>类型</th><th>状态</th><th>操作</th></tr>
          </thead>
          <tbody>
            <tr v-for="p in list" :key="p.permissionId">
              <td><PermissionTag :permission-key="p.permissionKey" :type="p.type" /></td>
              <td>{{ p.permissionName }}</td>
              <td>{{ moduleLabel(p.moduleCode) }}</td>
              <td>{{ typeLabel(p.type) }}</td>
              <td>
                <AppBadge :type="p.status === 'ENABLED' ? 'success' : 'neutral'">
                  {{ p.status === 'ENABLED' ? '已启用' : '已停用' }}
                </AppBadge>
              </td>
              <td>
                <AppButton
                  :variant="p.status === 'ENABLED' ? 'warning' : 'primary'"
                  :disabled="readonly || !canToggle"
                  :loading="togglingId === p.permissionId"
                  @click="toggle(p)"
                >
                  {{ p.status === 'ENABLED' ? '停用' : '启用' }}
                </AppButton>
              </td>
            </tr>
          </tbody>
        </table>
      </AppCard>
    </WorkflowStateBlock>
  </div>
</template>

<script>
/** 页面 5：/admin/workflow/permissions 权限点管理 */
import { AppCard, AppButton, AppBadge, AppSectionHeader } from '@/components/ui'
import WorkflowStateBlock from '@/modules/workflow/components/WorkflowStateBlock.vue'
import PermissionTag from '@/modules/workflow/components/PermissionTag.vue'
import { workflowProvider, canClickButton, getModuleLabel, MODULE_LABELS, PERMISSION_TYPE_LABELS } from '@/modules/workflow'
import { toast } from '@/utils/toast'

export default {
  name: 'WorkflowPermissionsView',
  components: { AppCard, AppButton, AppBadge, AppSectionHeader, WorkflowStateBlock, PermissionTag },
  data() {
    return {
      loading: false,
      error: '',
      list: [],
      filters: { moduleCode: '', type: '', keyword: '' },
      togglingId: ''
    }
  },
  computed: {
    moduleOptions: () => MODULE_LABELS,
    typeOptions: () => PERMISSION_TYPE_LABELS,
    viewState() {
      return workflowProvider.getLicenseViewState()
    },
    readonly() {
      return this.viewState === 'READONLY'
    },
    canToggle() {
      return canClickButton('workflow.permission.toggle')
    }
  },
  watch: {
    '$route.query.lv'() {
      this.load()
    }
  },
  created() {
    this.load()
  },
  methods: {
    moduleLabel: getModuleLabel,
    typeLabel(t) {
      return PERMISSION_TYPE_LABELS[t] || t
    },
    async load() {
      this.loading = true
      this.error = ''
      try {
        const res = await workflowProvider.getPermissions({ ...this.filters, pageSize: 100 })
        if (res.code === 0) this.list = res.data.list
        else this.error = res.message
      } catch (e) {
        this.error = e.message || '加载失败'
      } finally {
        this.loading = false
      }
    },
    async toggle(p) {
      this.togglingId = p.permissionId
      try {
        const next = p.status === 'ENABLED' ? 'DISABLED' : 'ENABLED'
        const res = await workflowProvider.updatePermissionStatus(p.permissionId, next)
        if (res.code === 0) {
          toast.success(`权限点「${p.permissionKey}」已${next === 'ENABLED' ? '启用' : '停用'}`)
          await this.load()
        } else {
          toast.warning(res.message)
        }
      } finally {
        this.togglingId = ''
      }
    }
  }
}
</script>

<style scoped>
@import './workflow-page.css';
</style>
