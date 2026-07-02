<template>
  <div class="wf-page">
    <AppSectionHeader title="角色管理" subtitle="七类基础角色与数据范围绑定（编辑为 mock 操作，P8 接真实权限中心）" />

    <div class="wf-page__filters">
      <input v-model.trim="keyword" placeholder="搜索角色名称 / 编码" @keyup.enter="load" />
      <AppButton variant="secondary" @click="load">查询</AppButton>
    </div>

    <WorkflowStateBlock :loading="loading" :error="error" :empty="!list.length" :view-state="viewState" @retry="load">
      <div class="wf-page__split">
        <AppCard class="wf-page__card">
          <table class="wf-table">
            <thead>
              <tr><th>角色</th><th>编码</th><th>用户数</th><th>权限数</th><th>数据范围</th></tr>
            </thead>
            <tbody>
              <tr
                v-for="r in list"
                :key="r.roleId"
                class="wf-roles__row"
                :class="{ 'is-active': activeRole && activeRole.roleId === r.roleId }"
                @click="selectRole(r)"
              >
                <td>{{ r.roleName }}</td>
                <td><code class="wf-roles__code">{{ r.roleCode }}</code></td>
                <td>{{ r.userCount }}</td>
                <td>{{ r.permissionKeys.length }}</td>
                <td><DataScopeTag :scope="r.dataScope" /></td>
              </tr>
            </tbody>
          </table>
        </AppCard>

        <RolePermissionPanel
          :role="activeRole"
          :all-permissions="allPermissions"
          :readonly="readonly"
          :can-edit="canEdit"
          :submitting="submitting"
          @save="onSave"
        />
      </div>
    </WorkflowStateBlock>
  </div>
</template>

<script>
/** 页面 4：/admin/workflow/roles 角色管理 */
import { AppCard, AppButton, AppSectionHeader } from '@/components/ui'
import WorkflowStateBlock from '@/modules/workflow/components/WorkflowStateBlock.vue'
import DataScopeTag from '@/modules/workflow/components/DataScopeTag.vue'
import RolePermissionPanel from '@/modules/workflow/components/RolePermissionPanel.vue'
import { workflowProvider, canClickButton } from '@/modules/workflow'
import { toast } from '@/utils/toast'

export default {
  name: 'WorkflowRolesView',
  components: { AppCard, AppButton, AppSectionHeader, WorkflowStateBlock, DataScopeTag, RolePermissionPanel },
  data() {
    return {
      loading: false,
      error: '',
      list: [],
      allPermissions: [],
      activeRole: null,
      keyword: '',
      submitting: false
    }
  },
  computed: {
    viewState() {
      return workflowProvider.getLicenseViewState()
    },
    readonly() {
      return this.viewState === 'READONLY'
    },
    canEdit() {
      return canClickButton('workflow.role.edit')
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
    async load() {
      this.loading = true
      this.error = ''
      try {
        const [rolesRes, permsRes] = await Promise.all([
          workflowProvider.getRoles({ keyword: this.keyword }),
          workflowProvider.getPermissions({ pageSize: 100 })
        ])
        if (rolesRes.code === 0) {
          this.list = rolesRes.data.list
          const keep = this.activeRole && this.list.find((r) => r.roleId === this.activeRole.roleId)
          this.activeRole = keep || this.list[0] || null
        } else {
          this.error = rolesRes.message
        }
        if (permsRes.code === 0) this.allPermissions = permsRes.data.list
      } catch (e) {
        this.error = e.message || '加载失败'
      } finally {
        this.loading = false
      }
    },
    async selectRole(r) {
      const res = await workflowProvider.getRoleDetail(r.roleId)
      this.activeRole = res.code === 0 ? res.data : r
    },
    async onSave({ roleId, permissionKeys, dataScope }) {
      this.submitting = true
      try {
        const res = await workflowProvider.updateRolePermissions(roleId, { permissionKeys, dataScope })
        if (res.code === 0) {
          toast.success('角色权限已更新（mock），操作已写入审计')
          this.activeRole = res.data
          await this.load()
        } else {
          toast.warning(res.message)
        }
      } finally {
        this.submitting = false
      }
    }
  }
}
</script>

<style scoped>
@import './workflow-page.css';
.wf-roles__row { cursor: pointer; }
.wf-roles__row.is-active td { background: var(--primary-50); }
.wf-roles__code { font-size: var(--font-size-xs); color: var(--text-tertiary); }
</style>
