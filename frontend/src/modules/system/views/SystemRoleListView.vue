<template>
  <ModulePageShell
    title="角色权限管理"
    :subtitle="'共 ' + pagination.total + ' 个角色 · 内置角色不可作废，自定义角色作废需留痕'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <div class="mp-stack">
      <!--
        SYS-06 通配权限退役队列。
        真实鉴权目前读代码常量 ROLE_PERMISSIONS，里面还有 SCHOOL_ADMIN: {"*"} 这类全权通配。
        通配不能一夜删掉（删了管理员立刻失去全部权限），所以先让它可见、可排期。
      -->
      <section v-if="governance.wildcards.length" class="mp-card rl-wildcard">
        <header class="mp-card__head">
          <span class="mp-card__title">通配权限退役队列</span>
          <span class="mp-card__actions">
            <span class="mp-note">{{ governance.disclaimer }}</span>
            <button class="mp-link" @click="governance.expanded = !governance.expanded">
              {{ governance.expanded ? '收起' : '展开' }}
            </button>
          </span>
        </header>
        <div v-if="governance.expanded" class="mp-card__body" style="padding-top: 0">
          <table class="mp-audit">
            <thead>
              <tr>
                <th style="width: 200px">角色</th>
                <th style="width: 180px">通配权限</th>
                <th style="width: 130px">覆盖权限码数</th>
                <th style="width: 100px">状态</th>
                <th>说明</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="w in governance.wildcards" :key="w.roleCode + w.wildcardCode">
                <td class="is-who">{{ w.roleCode }}</td>
                <td>
                  <code class="rl-code">{{ w.wildcardCode }}</code>
                </td>
                <td :class="{ 'rl-danger': w.wildcardCode === '*' }">
                  {{ w.expandedCount }}
                  <!-- 展开为 0 = 全部来源里都没有该前缀的权限码，实际未放开任何东西 -->
                  <span v-if="w.deadWildcard" class="rl-dead">可安全退役</span>
                </td>
                <td>
                  <StatusTag
                    :type="w.status === 'RETIRED' ? 'success' : 'warning'"
                    :label="wildcardStatusLabel(w.status)"
                  />
                </td>
                <td class="mp-cell-sub">{{ w.note }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState
        v-else-if="!rows.length"
        title="没有符合条件的角色"
        description="可调整筛选条件，或通过「新增角色 / 复制角色」创建"
      />
      <DataTable
        v-else
        :columns="columns"
        :rows="rows"
        row-key="id"
        :pagination="pagination"
        @page-change="onPageChange"
      >
        <template #cell-role="{ row }">
          <div class="mp-cell-main">{{ row.name }}</div>
          <div class="mp-cell-sub">{{ row.code }} · {{ row.typeLabel }}</div>
        </template>
        <template #cell-scopeName="{ row }">
          <StatusTag type="info" :label="row.scopeName" />
        </template>
        <template #cell-memberCount="{ row }">
          <button
            class="mp-link rl-member-link"
            :aria-label="`查看${row.name}的 ${row.memberCount} 名成员`"
            @click="openMembers(row)"
          >
            {{ row.memberCount }} 人
          </button>
        </template>
        <template #cell-status="{ row }">
          <StatusTag
            :type="row.status === 'ENABLED' ? 'success' : 'default'"
            :label="row.statusLabel"
            dot
          />
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="openDetail(row)">查看</button>
          <button
            class="mp-link"
            :class="{ 'is-disabled': !can('configRolePermission') }"
            :title="reason('configRolePermission')"
            @click="openPermission(row)"
          >
            配置权限
          </button>
          <button
            class="mp-link"
            :class="{ 'is-disabled': !can('editRole') }"
            :title="reason('editRole')"
            @click="openEdit(row)"
          >
            编辑
          </button>
          <button
            class="mp-link"
            :class="{ 'is-disabled': !can('copyRole') }"
            :title="reason('copyRole')"
            @click="doCopy(row)"
          >
            复制
          </button>
          <button
            class="mp-link"
            :class="{ 'is-disabled': !can('exportRoleConfig') }"
            :title="reason('exportRoleConfig')"
            @click="doExport(row)"
          >
            导出配置
          </button>
          <span
            v-if="row.type === 'BUILTIN'"
            class="mp-note"
            title="内置角色不允许作废（平台冻结规则）"
            >内置</span
          >
          <button
            v-else-if="row.status === 'ENABLED'"
            class="mp-link rl-danger"
            :class="{ 'is-disabled': !can('deprecateRole') }"
            :title="reason('deprecateRole')"
            @click="askDeprecate(row)"
          >
            作废
          </button>
        </template>
      </DataTable>
    </div>

    <!-- 新增 / 编辑角色 -->
    <AppDrawer
      v-model:visible="form.open"
      :title="form.id ? '编辑角色' : '新增角色'"
      mode="modal"
      size="medium"
    >
      <FormFields v-model="form.value" :fields="formFields" :errors="form.errors" />
      <p class="mp-note" style="margin-top: var(--space-3)">
        新角色默认无菜单权限，创建后请在「配置权限」中授权；角色编码创建后不可修改。
      </p>
      <template #footer>
        <AppButton variant="ghost" @click="form.open = false">取消</AppButton>
        <AppButton variant="primary" :loading="form.submitting" @click="submitForm">{{
          form.id ? '保存修改' : '创建角色'
        }}</AppButton>
      </template>
    </AppDrawer>

    <!-- 角色详情 -->
    <AppDrawer
      v-model:visible="detail.open"
      :title="'角色详情 · ' + (detail.data ? detail.data.name : '')"
      mode="modal"
      size="xlarge"
    >
      <LoadingState v-if="detail.loading" />
      <template v-else-if="detail.data">
        <div class="mp-kv">
          <span class="mp-kv__k">角色编码</span><span class="mp-kv__v">{{ detail.data.code }}</span>
        </div>
        <div class="mp-kv">
          <span class="mp-kv__k">类型 / 状态</span
          ><span class="mp-kv__v">{{ detail.data.typeLabel }} · {{ detail.data.statusLabel }}</span>
        </div>
        <div class="mp-kv">
          <span class="mp-kv__k">数据范围</span
          ><span class="mp-kv__v">{{ detail.data.scopeName }}</span>
        </div>
        <div class="mp-kv">
          <span class="mp-kv__k">说明</span
          ><span class="mp-kv__v">{{ detail.data.description || '—' }}</span>
        </div>
        <div class="mp-kv">
          <span class="mp-kv__k">已授权</span
          ><span class="mp-kv__v"
            >菜单 {{ detail.data.menuKeys.length }} 个 · 按钮
            {{ detail.data.buttonKeys.length }} 个</span
          >
        </div>

        <h4 class="rl-sec">成员（{{ detail.data.members.length }}）</h4>
        <EmptyState
          v-if="!detail.data.members.length"
          title="暂无成员"
          description="可在用户账号管理中为用户分配该角色"
        />
        <div v-for="m in detail.data.members" :key="m.id" class="mp-kv">
          <span class="mp-kv__k">{{ m.name }}</span
          ><span class="mp-kv__v">{{ m.orgName }}</span>
        </div>

        <h4 class="rl-sec">操作留痕</h4>
        <table class="mp-audit">
          <thead>
            <tr>
              <th>操作人</th>
              <th>动作</th>
              <th>影响</th>
              <th>时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(a, i) in detail.data.auditTrail" :key="i">
              <td class="is-who">{{ a.who }}</td>
              <td>{{ auditActionLabel(a) }}</td>
              <td>{{ a.affected }}</td>
              <td>{{ a.time }}</td>
            </tr>
          </tbody>
        </table>
      </template>
    </AppDrawer>

    <!-- 角色成员：人数入口使用独立的分页接口，避免详情预览截断时无法查看全部成员。 -->
    <AppDrawer
      v-model:visible="members.open"
      :title="(members.mode === 'add' ? '添加成员 · ' : '角色成员 · ') + members.roleName"
      :subtitle="members.roleCode + ' · 数据范围 ' + members.scopeCode"
      mode="modal"
      size="large"
    >
      <template v-if="members.mode === 'list'">
        <div class="rl-members-toolbar">
          <span class="mp-note">共 {{ members.pagination.total }} 位有效成员</span>
          <AppButton v-if="can('assignRole')" variant="primary" @click="openMemberAdd"
            >添加成员</AppButton
          >
        </div>
        <div v-if="memberScopeNeedsFollowup" class="rl-scope-warning">
          <strong>需要继续核对岗位数据范围</strong>
          <span>{{ memberScopeMessage }}</span>
        </div>
        <LoadingState v-if="members.loading" />
        <ErrorState v-else-if="members.error" :description="members.error" @retry="loadMembers" />
        <EmptyState
          v-else-if="!members.rows.length"
          title="暂无在职成员"
          description="点击「添加成员」可按姓名或工号批量选择老师"
        />
        <DataTable
          v-else
          :columns="memberColumns"
          :rows="members.rows"
          row-key="id"
          :pagination="members.pagination"
          @page-change="onMembersPageChange"
        >
          <template #cell-member="{ row }">
            <div class="mp-cell-main">{{ row.name }}</div>
            <div class="mp-cell-sub">{{ row.loginName }}</div>
          </template>
          <template #cell-memberStatus="{ row }">
            <StatusTag
              :type="row.status === 'ACTIVE' ? 'success' : 'default'"
              :label="row.status === 'ACTIVE' ? '启用' : row.status"
              dot
            />
          </template>
        </DataTable>
      </template>

      <template v-else>
        <button class="mp-link rl-back" @click="backToMembers">← 返回成员清单</button>
        <div class="rl-candidate-search">
          <label class="rl-field rl-field--grow">
            <span>搜索老师</span>
            <input
              v-model.trim="memberAdd.keyword"
              class="rl-input"
              placeholder="输入姓名或工号"
              @keyup.enter="searchMemberCandidates"
            />
          </label>
          <AppButton variant="secondary" @click="searchMemberCandidates">查询</AppButton>
        </div>

        <LoadingState v-if="memberAdd.loading" />
        <ErrorState
          v-else-if="memberAdd.error"
          :description="memberAdd.error"
          @retry="loadMemberCandidates"
        />
        <EmptyState
          v-else-if="!memberAdd.rows.length"
          title="没有可添加的老师"
          description="已自动排除学生、停用账号和当前角色已有成员"
        />
        <DataTable
          v-else
          v-model:selected="memberAdd.selected"
          :columns="candidateColumns"
          :rows="memberAdd.rows"
          row-key="id"
          selectable
          :pagination="memberAdd.pagination"
          @page-change="onCandidatePageChange"
        >
          <template #cell-candidate="{ row }">
            <div class="mp-cell-main">{{ row.name }}</div>
            <div class="mp-cell-sub">{{ row.loginName }}</div>
          </template>
          <template #cell-candidateStatus>
            <StatusTag type="success" label="启用中" dot />
          </template>
        </DataTable>

        <div class="rl-selection-summary">
          已选择 <strong>{{ memberAdd.selected.length }}</strong> 位老师，单次最多 100 人
        </div>
        <div v-if="memberScopeNeedsFollowup" class="rl-scope-warning">
          <strong>角色授权与岗位范围是两类事实</strong>
          <span>{{ memberScopeMessage }}</span>
        </div>
        <div class="rl-add-form">
          <label class="rl-field">
            <span>授权原因 <b>*</b></span>
            <textarea
              v-model.trim="memberAdd.reason"
              class="rl-input rl-textarea"
              maxlength="500"
              placeholder="如：2026 秋季学期辅导员岗位安排，至少 5 个字"
            />
          </label>
          <label class="rl-field">
            <span>到期日期</span>
            <input v-model="memberAdd.expiresAt" class="rl-input" type="date" />
            <small>留空表示长期有效；到期后系统自动回收角色。</small>
          </label>
        </div>
      </template>

      <template v-if="members.mode === 'add'" #footer>
        <span class="mp-note" style="margin-right: auto">本次操作将写入关键审计日志</span>
        <AppButton variant="ghost" @click="backToMembers">取消</AppButton>
        <AppButton
          variant="primary"
          :loading="memberAdd.submitting"
          :disabled="!memberAdd.selected.length || memberAdd.selected.length > 100"
          @click="submitMemberAdd"
          >确认添加 {{ memberAdd.selected.length }} 人</AppButton
        >
      </template>
    </AppDrawer>

    <!-- 配置权限（菜单 / 按钮 / 数据范围） -->
    <AppDrawer
      v-model:visible="perm.open"
      :title="'配置权限 · ' + perm.name"
      mode="modal"
      size="large"
    >
      <LoadingState v-if="perm.loading" />
      <template v-else>
        <h4 class="rl-sec" style="margin-top: 0">数据范围</h4>
        <AppSelect v-model="perm.scopeCode" :options="ctx.statusOptions.scopeTypes" />
        <p class="mp-note">
          数据范围决定该角色能看到哪些学生 / 账号；调整后影响所有成员，将写入审计日志并通知复核。
        </p>

        <h4 class="rl-sec">菜单与按钮权限</h4>
        <PermissionTreeEditor
          :tree="perm.tree"
          v-model:menu-keys="perm.menuKeys"
          v-model:button-keys="perm.buttonKeys"
        />
        <section v-if="perm.readOnlyPreserved.length" class="preserved-box">
          <h4>保留权限（只读）</h4>
          <p class="mp-note">这些权限不会被本次保存静默删除；原因逐项可见。</p>
          <div v-for="item in perm.readOnlyPreserved" :key="item.permissionCode" class="preserved-row">
            <code>{{ item.permissionCode }}</code><span>{{ item.reason }}</span>
          </div>
        </section>
        <label class="reason-field">变更原因
          <textarea v-model.trim="perm.reason" rows="3" minlength="5" placeholder="说明职责调整原因，至少 5 个字符" />
        </label>
      </template>
      <template #footer>
        <span class="mp-note" style="margin-right: auto">保存后即时生效并留痕</span>
        <AppButton variant="ghost" @click="perm.open = false">取消</AppButton>
        <AppButton variant="primary" :loading="perm.submitting" @click="submitPermission"
          >保存权限配置</AppButton
        >
      </template>
    </AppDrawer>

    <!-- 作废角色（逻辑删除） -->
    <AppConfirmDialog
      v-model:visible="confirmDeprecate"
      type="danger"
      :title="'作废角色「' + (deprecateRow ? deprecateRow.name : '') + '」？'"
      message="作废为逻辑删除：历史授权记录保留可追溯，该角色不可再分配；如有成员需先移除。"
      confirm-text="确认作废并留痕"
      require-reason
      reason-label="作废原因"
      reason-placeholder="如：临时角色到期 / 职责合并，至少 5 个字"
      :submitting="deprecateSubmitting"
      @confirm="doDeprecate"
    />
  </ModulePageShell>
</template>

<script>
/**
 * 角色权限管理（/admin/system/roles）：
 * 新增 / 查看 / 编辑 / 复制 / 作废（逻辑删除+原因留痕）/ 配置菜单按钮权限 / 配置数据范围 / 导出角色配置。
 */
import {
  ModulePageShell,
  ModuleToolbar,
  AdvancedFilter,
  DataTable,
  StatusTag,
  LoadingState,
  ErrorState,
  EmptyState
} from '@/components/business'
import { AppButton } from '@/components/ui'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { AppSelect } from '@/components/common'
import FormFields from '@/modules/system/components/FormFields.vue'
import PermissionTreeEditor from '@/modules/system/components/PermissionTreeEditor.vue'
import { systemApi } from '@/modules/system/api/system.api'
import { schoolIamApi } from '@/modules/system/api/schoolIam.api'
import { toast } from '@/utils/toast'
import { presentAuditRecord } from '@/utils/presentationSafety'

const EMPTY_FILTERS = () => ({ keyword: '', type: '', status: '' })

export default {
  name: 'SystemRoleListView',
  components: {
    ModulePageShell,
    ModuleToolbar,
    AdvancedFilter,
    DataTable,
    StatusTag,
    LoadingState,
    ErrorState,
    EmptyState,
    AppButton,
    AppDrawer,
    AppConfirmDialog,
    AppSelect,
    FormFields,
    PermissionTreeEditor
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      routeTab: '',
      loading: true,
      error: '',
      rows: [],
      // SYS-06 权限治理：通配退役队列（默认收起，不干扰既有角色管理）
      governance: { wildcards: [], disclaimer: '', expanded: false },
      filters: EMPTY_FILTERS(),
      pagination: { page: 1, pageSize: 10, total: 0 },
      columns: [
        { key: 'role', title: '角色' },
        { key: 'scopeName', title: '数据范围' },
        { key: 'memberCount', title: '成员' },
        { key: 'description', title: '说明' },
        { key: 'status', title: '状态' },
        { key: 'updatedAt', title: '最近更新' },
        { key: 'actions', title: '操作', width: '300px' }
      ],
      form: { open: false, id: '', value: {}, errors: {}, submitting: false },
      detail: { open: false, loading: false, data: null },
      members: {
        open: false,
        mode: 'list',
        loading: false,
        error: '',
        roleId: '',
        roleName: '',
        roleCode: '',
        scopeCode: '',
        rows: [],
        pagination: { page: 1, pageSize: 50, total: 0 }
      },
      memberAdd: {
        loading: false,
        error: '',
        keyword: '',
        rows: [],
        selected: [],
        reason: '',
        expiresAt: '',
        submitting: false,
        pagination: { page: 1, pageSize: 20, total: 0 }
      },
      memberColumns: [
        { key: 'member', title: '成员' },
        { key: 'memberStatus', title: '账号状态' }
      ],
      candidateColumns: [
        { key: 'candidate', title: '老师' },
        { key: 'userType', title: '账号类型' },
        { key: 'candidateStatus', title: '账号状态' }
      ],
      perm: {
        open: false,
        loading: false,
        id: '',
        name: '',
        tree: [],
        menuKeys: [],
        buttonKeys: [],
        scopeCode: 'COLLEGE',
        version: 0,
        reason: '',
        readOnlyPreserved: [],
        submitting: false
      },
      confirmDeprecate: false,
      deprecateRow: null,
      deprecateSubmitting: false
    }
  },
  computed: {
    filterFields() {
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '角色名称 / 编码' },
        {
          key: 'type',
          label: '角色类型',
          type: 'select',
          options: this.ctx.statusOptions.roleType
        },
        { key: 'status', label: '状态', type: 'select', options: this.ctx.statusOptions.roleStatus }
      ]
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [{ key: 'createRole', label: '＋ 新增角色', variant: 'primary' }]
        .filter((a) => pa[a.key] && pa[a.key].visible)
        .map((a) => ({ ...a, disabled: !pa[a.key].allowed, disabledReason: pa[a.key].reason }))
    },
    formFields() {
      return [
        { key: 'name', label: '角色名称', required: true, placeholder: '如：教学质量督导' },
        {
          key: 'code',
          label: '角色编码',
          disabled: !!this.form.id,
          lockNote: this.form.id ? '（不可修改）' : '',
          placeholder: '大写字母与下划线，留空自动生成'
        },
        {
          key: 'scopeCode',
          label: '默认数据范围',
          type: 'select',
          options: this.ctx.statusOptions.scopeTypes
        },
        {
          key: 'description',
          label: '角色说明',
          type: 'textarea',
          full: true,
          placeholder: '该角色的职责与可见范围说明'
        }
      ]
    },
    memberScopeNeedsFollowup() {
      return !['SCHOOL', 'SELF'].includes(String(this.members.scopeCode || '').toUpperCase())
    },
    memberScopeMessage() {
      const code = String(this.members.scopeCode || '').toUpperCase()
      const messages = {
        COUNSELOR_CLASSES: '添加辅导员角色后，还需在「教职工任职归属」中确认其负责班级。',
        CLASS: '添加角色后，还需确认老师对应的班级范围。',
        DORM_BUILDING: '添加宿管角色后，还需确认老师负责的宿舍楼栋。',
        COLLEGE: '添加角色后，还需核对老师所属或获指派的学院。',
        MAJOR: '添加角色后，还需核对老师所属或获指派的专业。',
        DEPARTMENT: '添加角色后，还需核对老师所属部门。',
        GD_STUDENTS: '可见学生范围来自毕业设计指导关系，请在毕设业务中维护。',
        INTERN_STUDENTS: '可见学生范围来自实习指导关系，请在实习业务中维护。',
        ASSIGNED: '该角色按对象指派数据范围，授权后需继续配置具体对象。',
        CUSTOM: '该角色使用自定义数据范围，授权后需核对范围规则。'
      }
      return messages[code] || `该角色使用 ${code || '待确认'} 数据范围，授权后请继续核对岗位关系。`
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
    auditActionLabel(row) { return presentAuditRecord(row).displayAction },
    syncTabFromRoute() {
      const tab = String(this.$route.query.tab || '')
      if (tab === 'templates' || tab === 'members' || tab === 'permissions') this.routeTab = tab
    },
    can(key) {
      const pa = this.ctx.permissionActions[key]
      return !!(pa && pa.visible && pa.allowed)
    },
    reason(key) {
      const pa = this.ctx.permissionActions[key]
      return pa && !pa.allowed ? pa.reason : ''
    },
    onPageChange(page) {
      this.pagination.page = page
      this.load()
    },
    search() {
      this.pagination.page = 1
      this.load()
    },
    reset() {
      this.filters = EMPTY_FILTERS()
      this.load()
    },
    onToolbar(key) {
      if (key === 'createRole') this.openEdit(null)
    },
    openEdit(row) {
      if (row && !this.can('editRole')) return
      this.form = {
        open: true,
        id: row ? row.id : '',
        value: row
          ? {
              name: row.name,
              code: row.code,
              scopeCode: row.scopeCode,
              description: row.description
            }
          : { name: '', code: '', scopeCode: 'COLLEGE', description: '' },
        errors: {},
        submitting: false
      }
    },
    async submitForm() {
      const errors = FormFields.validateRequired(this.formFields, this.form.value)
      this.form.errors = errors
      if (Object.keys(errors).length) return
      this.form.submitting = true
      const res = this.form.id
        ? await systemApi.updateRole(this.form.id, this.form.value)
        : await systemApi.createRole(this.form.value)
      this.form.submitting = false
      if (res.code === 0) {
        toast.success((this.form.id ? '角色已更新' : '角色已创建') + '，已写入审计日志')
        this.form.open = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async openDetail(row) {
      this.detail = { open: true, loading: true, data: null }
      const res = await systemApi.getRoleDetail(row.id)
      this.detail.loading = false
      if (res.code === 0) this.detail.data = res.data
      else {
        toast.error(res.message)
        this.detail.open = false
      }
    },
    openMembers(row) {
      this.members = {
        open: true,
        mode: 'list',
        loading: true,
        error: '',
        roleId: row.id,
        roleName: row.name,
        roleCode: row.code,
        scopeCode: row.scopeCode,
        rows: [],
        pagination: { page: 1, pageSize: 50, total: row.memberCount || 0 }
      }
      this.loadMembers()
    },
    openMemberAdd() {
      if (!this.can('assignRole')) return
      this.members.mode = 'add'
      this.memberAdd = {
        loading: true,
        error: '',
        keyword: '',
        rows: [],
        selected: [],
        reason: '',
        expiresAt: '',
        submitting: false,
        pagination: { page: 1, pageSize: 20, total: 0 }
      }
      this.loadMemberCandidates()
    },
    backToMembers() {
      this.members.mode = 'list'
      this.memberAdd.error = ''
    },
    onMembersPageChange(page) {
      this.members.pagination.page = page
      this.loadMembers()
    },
    async loadMembers() {
      if (!this.members.roleId) return
      this.members.loading = true
      this.members.error = ''
      const { page, pageSize } = this.members.pagination
      const res = await schoolIamApi.roleMembers(this.members.roleId, page, pageSize)
      if (res.code === 0) {
        const data = res.data || {}
        this.members.rows = data.items || []
        this.members.pagination = {
          page: data.page || page,
          pageSize: data.pageSize || pageSize,
          total: data.total || 0
        }
      } else {
        this.members.error = res.message
      }
      this.members.loading = false
    },
    searchMemberCandidates() {
      this.memberAdd.pagination.page = 1
      this.loadMemberCandidates()
    },
    onCandidatePageChange(page) {
      this.memberAdd.pagination.page = page
      this.loadMemberCandidates()
    },
    async loadMemberCandidates() {
      if (!this.members.roleId || !this.can('assignRole')) return
      this.memberAdd.loading = true
      this.memberAdd.error = ''
      const { page, pageSize } = this.memberAdd.pagination
      const res = await schoolIamApi.roleMemberCandidates(this.members.roleId, {
        keyword: this.memberAdd.keyword,
        page,
        pageSize
      })
      if (res.code === 0) {
        const data = res.data || {}
        this.memberAdd.rows = data.items || []
        this.memberAdd.pagination = {
          page: data.page || page,
          pageSize: data.pageSize || pageSize,
          total: data.total || 0
        }
      } else {
        this.memberAdd.error = res.message
      }
      this.memberAdd.loading = false
    },
    async submitMemberAdd() {
      if (!this.can('assignRole')) return
      if (!this.memberAdd.selected.length) return toast.error('请至少选择一位老师')
      if (this.memberAdd.selected.length > 100) return toast.error('单次最多添加 100 位老师')
      if (this.memberAdd.reason.length < 5) return toast.error('授权原因不少于 5 个字')
      if (this.memberAdd.expiresAt) {
        const expiresAt = new Date(`${this.memberAdd.expiresAt}T23:59:59`)
        if (Number.isNaN(expiresAt.getTime()) || expiresAt.getTime() <= Date.now()) {
          return toast.error('到期日期必须晚于今天')
        }
      }
      this.memberAdd.submitting = true
      const res = await schoolIamApi.batchAddRoleMembers(this.members.roleId, {
        userIds: this.memberAdd.selected,
        reason: this.memberAdd.reason,
        effectiveAt: null,
        expiresAt: this.memberAdd.expiresAt || null,
        sourceType: 'MANUAL'
      })
      this.memberAdd.submitting = false
      if (res.code !== 0) return toast.error(res.message)
      const added = Number(res.data?.addedCount || 0)
      const skipped = Number(res.data?.skippedCount || 0)
      const suffix = skipped ? `，${skipped} 人已是成员并跳过` : ''
      toast.success(`已添加 ${added} 位角色成员${suffix}`)
      this.members.mode = 'list'
      this.members.pagination.page = 1
      await Promise.all([this.loadMembers(), this.load()])
    },
    async openPermission(row) {
      if (!this.can('configRolePermission')) return
      if (row.type === 'BUILTIN') {
        toast.error('预设角色由平台模板维护；请复制为自定义角色后再裁剪权限')
        return
      }
      this.perm = {
        open: true,
        loading: true,
        id: row.id,
        name: row.name,
        tree: [],
        menuKeys: [],
        buttonKeys: [],
        scopeCode: row.scopeCode,
        version: Number(row.version || 0),
        reason: '',
        readOnlyPreserved: [],
        submitting: false
      }
      const [treeRes, detailRes] = await Promise.all([
        systemApi.getPermissionTree(),
        systemApi.getRoleDetail(row.id)
      ])
      this.perm.loading = false
      if (treeRes.code === 0) this.perm.tree = treeRes.data
      if (detailRes.code === 0) {
        this.perm.menuKeys = detailRes.data.menuKeys || []
        this.perm.buttonKeys = detailRes.data.buttonKeys || []
        this.perm.scopeCode = detailRes.data.scopeCode || row.scopeCode
        this.perm.version = Number(detailRes.data.version || row.version || 0)
        this.perm.readOnlyPreserved = detailRes.data.readOnlyPreservedPermissions || []
      }
    },
    async submitPermission() {
      if (this.perm.reason.length < 5) return toast.error('权限变更原因至少 5 个字符')
      this.perm.submitting = true
      const rawId = Math.random().toString(16).slice(2).padEnd(32, '0').slice(0, 32)
      const requestId = globalThis.crypto?.randomUUID?.() || `${rawId.slice(0, 8)}-${rawId.slice(8, 12)}-4${rawId.slice(13, 16)}-8${rawId.slice(17, 20)}-${rawId.slice(20, 32)}`
      const res = await systemApi.saveRolePermissions(this.perm.id, {
        menuKeys: this.perm.menuKeys,
        buttonKeys: this.perm.buttonKeys,
        scopeCode: this.perm.scopeCode,
        expectedVersion: this.perm.version,
        reason: this.perm.reason,
        requestId
      })
      this.perm.submitting = false
      if (res.code === 0) {
        toast.success('权限配置已保存并留痕（变更已通知复核人）')
        this.perm.open = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async doCopy(row) {
      if (!this.can('copyRole')) return
      const res = await systemApi.copyRole(row.id)
      if (res.code === 0) {
        toast.success('已复制为「' + res.data.name + '」（成员不复制），已留痕')
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async doExport(row) {
      if (!this.can('exportRoleConfig')) return
      const res = await systemApi.exportRoleConfig(row.id)
      if (res.code === 0) toast.success('角色配置已下载：' + res.data.fileName + '，已留痕')
      else toast.error(res.message)
    },
    askDeprecate(row) {
      if (!this.can('deprecateRole')) return
      this.deprecateRow = row
      this.confirmDeprecate = true
    },
    async doDeprecate({ reason }) {
      this.deprecateSubmitting = true
      const res = await systemApi.deprecateRole(this.deprecateRow.id, { reason })
      this.deprecateSubmitting = false
      if (res.code === 0) {
        toast.success('角色已作废（逻辑删除），原因已留痕')
        this.confirmDeprecate = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await systemApi.getRoles({
        ...this.filters,
        page: this.pagination.page,
        pageSize: this.pagination.pageSize
      })
      if (res.code === 0) {
        this.rows = res.data.list
        this.pagination.total = res.data.total
      } else {
        this.error = res.message
      }
      this.loading = false
      this.loadGovernance()
    },

    wildcardStatusLabel(s) {
      return { PENDING: '待处理', PLANNED: '已排期', RETIRED: '已退役' }[s] || (s ? '状态待确认' : '—')
    },

    /**
     * SYS-06 通配退役队列。首次访问时先幂等固化交付模板与权限包，
     * 失败不阻断角色列表——这块是治理增强，不能让它拖垮主功能。
     */
    async loadGovernance() {
      const res = await systemApi.getWildcardRetirement()
      if (res.code !== 0) return
      let data = res.data || {}
      if (!(data.items || []).length) {
        const boot = await systemApi.bootstrapPermissionGovernance()
        if (boot.code === 0) {
          const again = await systemApi.getWildcardRetirement()
          if (again.code === 0) data = again.data || {}
        }
      }
      this.governance.wildcards = data.items || []
      this.governance.disclaimer = data.disclaimer || ''
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.rl-sec {
  margin: var(--space-4) 0 var(--space-2);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
}
.rl-danger {
  color: var(--danger-600);
}
.rl-select {
  height: 34px;
  width: 100%;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  font: inherit;
  font-size: var(--font-size-sm);
  padding: 0 var(--space-2);
  background: var(--bg-card);
}
.mp-link + .mp-link {
  margin-left: var(--space-2);
}
.rl-member-link {
  margin-left: 0;
  font-size: inherit;
  white-space: nowrap;
}
.rl-members-toolbar,
.rl-candidate-search {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}
.rl-back {
  margin-bottom: var(--space-3);
}
.rl-field {
  display: grid;
  gap: 6px;
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
}
.rl-field--grow {
  flex: 1;
}
.rl-field b {
  color: var(--danger-600);
}
.rl-field small {
  color: var(--text-tertiary);
}
.rl-input {
  width: 100%;
  min-height: 38px;
  padding: 8px 10px;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-md);
  background: var(--bg-card);
  color: var(--text-primary);
  font: inherit;
  box-sizing: border-box;
}
.rl-textarea {
  min-height: 76px;
  resize: vertical;
}
.rl-add-form {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(220px, 1fr);
  gap: var(--space-3);
  margin-top: var(--space-3);
}
.rl-selection-summary {
  margin-top: var(--space-3);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
}
.rl-scope-warning {
  display: grid;
  gap: 4px;
  margin-bottom: var(--space-3);
  padding: var(--space-3);
  border: 1px solid var(--warning-300, #f5d08a);
  border-radius: var(--radius-md);
  background: var(--warning-50, #fffaf0);
  color: var(--warning-700, #9a6700);
  font-size: var(--font-size-sm);
}
@media (max-width: 720px) {
  .rl-add-form {
    grid-template-columns: 1fr;
  }
}
/* SYS-06 通配退役队列 */
.rl-wildcard {
  border-left: 3px solid var(--warning-500, var(--danger-600));
}
.rl-dead {
  margin-left: var(--space-1);
  padding: 0 var(--space-1);
  border-radius: var(--radius-sm);
  background: var(--fill-secondary);
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.rl-code {
  padding: 0 var(--space-1);
  border-radius: var(--radius-sm);
  background: var(--fill-secondary);
  font-size: var(--font-size-xs);
}
</style>
