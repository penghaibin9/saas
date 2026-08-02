<template>
  <ModulePageShell
    title="组织结构管理"
    subtitle="院系 / 专业 / 班级 / 职能部门 · 数据范围计算的组织基座"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <div class="mp-stack">
      <div class="mp-tabs">
        <button class="mp-tab" :class="{ 'is-active': tab === 'tree' }" @click="tab = 'tree'">组织树</button>
        <button class="mp-tab" :class="{ 'is-active': tab === 'positions' }" @click="tab = 'positions'">岗位管理</button>
        <button class="mp-tab" :class="{ 'is-active': tab === 'versions' }" @click="switchToVersions">变更版本</button>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />

      <template v-else-if="tab === 'tree'">
        <EmptyState v-if="!tree.length" title="暂无组织数据" description="请前往实施中心「数据导入与智能匹配」初始化院系 / 专业 / 班级结构" />
        <section v-else class="mp-card">
          <div class="mp-card__body" style="padding-top: var(--space-2)">
            <table class="og-table">
              <thead>
                <tr><th>组织</th><th style="width: 110px">类型</th><th style="width: 110px">编码</th><th style="width: 90px">成员数</th><th style="width: 210px">操作</th></tr>
              </thead>
              <tbody>
                <template v-for="node in flatTree" :key="node.id">
                  <tr>
                    <td :style="{ paddingLeft: 12 + node.depth * 24 + 'px' }">
                      <span v-if="node.depth" class="og-branch">├</span>
                      <b v-if="node.depth === 0">{{ node.name }}</b>
                      <span v-else>{{ node.name }}</span>
                    </td>
                    <td><StatusTag :type="node.depth === 0 ? 'info' : node.type === 'CLASS' ? 'processing' : 'default'" :label="node.typeLabel" /></td>
                    <td class="mp-cell-sub">{{ node.code }}</td>
                    <td class="mp-cell-sub">{{ node.memberCount }}</td>
                    <td>
                      <button class="mp-link" :class="{ 'is-disabled': !can('createOrg') }" :title="reason('createOrg')" @click="openEdit(null, node)">＋ 下级</button>
                      <button class="mp-link" :class="{ 'is-disabled': !can('editOrg') }" :title="reason('editOrg')" @click="openEdit(node, null)">编辑</button>
                      <button class="mp-link og-danger" :class="{ 'is-disabled': !can('deprecateOrg') }" :title="reason('deprecateOrg')" @click="askDeprecate(node)">作废</button>
                    </td>
                  </tr>
                </template>
              </tbody>
            </table>
          </div>
        </section>
        <p class="mp-note">组织节点作废为逻辑删除：历史归属关系保留；如节点下仍有在册成员，需先转移成员再作废。</p>
      </template>

      <template v-else-if="tab === 'positions'">
        <EmptyState v-if="!positions.length" title="暂无岗位" description="岗位用于批量绑定角色与数据范围" />
        <DataTable v-else :columns="posColumns" :rows="positions" row-key="id">
          <template #cell-status="{ row }">
            <StatusTag :type="row.status === 'ENABLED' ? 'success' : 'default'" :label="row.statusLabel" dot />
          </template>
        </DataTable>
        <p class="mp-note">岗位与账号的绑定在「用户账号管理」中维护；岗位仅作为角色 / 数据范围的批量配置入口。</p>
      </template>

      <!-- SYS-04：组织调整先进版本草稿，激活时才落到组织树，可排期、可回滚 -->
      <template v-else>
        <section class="mp-card">
          <header class="mp-card__head">
            <span class="mp-card__title">组织变更版本</span>
            <AppButton variant="primary" size="small" @click="openVersionCreate">新建变更版本</AppButton>
          </header>
          <div class="mp-card__body" style="padding-top: 0">
            <table class="og-table">
              <thead>
                <tr>
                  <th>版本</th>
                  <th style="width: 110px">状态</th>
                  <th style="width: 150px">计划生效</th>
                  <th style="width: 150px">实际激活</th>
                  <th style="width: 230px">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="v in versions" :key="v.versionId">
                  <td>
                    <b>{{ v.versionName || v.versionCode }}</b>
                    <span class="mp-cell-sub">{{ v.versionCode }}</span>
                  </td>
                  <td><StatusTag :type="versionTagType(v.status)" :label="versionLabel(v.status)" /></td>
                  <td class="mp-cell-sub">{{ fmtTime(v.effectiveAt) }}</td>
                  <td class="mp-cell-sub">{{ fmtTime(v.activatedAt) }}</td>
                  <td>
                    <button class="mp-link" @click="openVersionDetail(v)">详情</button>
                    <button
                      v-for="target in v.allowedTransitions"
                      :key="target"
                      class="mp-link"
                      :class="{ 'og-danger': target === 'ROLLED_BACK' }"
                      @click="openVersionTransition(v, target)"
                    >{{ versionActionLabel(target) }}</button>
                  </td>
                </tr>
              </tbody>
            </table>
            <EmptyState
              v-if="!versions.length"
              title="暂无组织变更版本"
              description="学院改名、专业调整院系、班级停用等成批调整可在这里排期，激活前不影响当前组织"
            />
          </div>
        </section>
        <p class="mp-note">草稿与排期状态下变更不会写入组织树；激活后可回滚到变更前的名称与归属。</p>
      </template>
    </div>

    <!-- 新建变更版本 -->
    <AppDrawer v-model:visible="versionForm.open" title="新建组织变更版本">
      <label class="og-label">版本名称<span class="og-required">*</span></label>
      <input v-model="versionForm.versionName" class="mp-input" placeholder="如：2027 级院系调整" />
      <label class="og-label">变更原因<span class="og-required">*</span></label>
      <textarea v-model="versionForm.reason" class="mp-textarea" rows="2" placeholder="至少 5 个字" />
      <div v-if="versionForm.error" class="mp-form-err">{{ versionForm.error }}</div>
      <template #footer>
        <AppButton variant="ghost" @click="versionForm.open = false">取消</AppButton>
        <AppButton variant="primary" :loading="versionForm.submitting" @click="submitVersionCreate">创建草稿</AppButton>
      </template>
    </AppDrawer>

    <!-- 版本详情：变更项 + 添加变更 -->
    <AppDrawer v-model:visible="versionDetail.open" :title="versionDetail.title">
      <LoadingState v-if="versionDetail.loading" />
      <template v-else-if="versionDetail.data">
        <h4 class="og-section">变更项</h4>
        <table v-if="versionDetail.data.items.length" class="og-table">
          <thead><tr><th style="width: 90px">动作</th><th>对象</th><th>目标值</th></tr></thead>
          <tbody>
            <tr v-for="i in versionDetail.data.items" :key="i.itemId">
              <td>{{ changeLabel(i.changeType) }}</td>
              <td>{{ i.orgNodeId ? orgLabel(i.orgType, i.orgNodeId) : '（新建）' }}</td>
              <td class="mp-cell-sub">{{ describePayload(i) }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else class="mp-note">还没有变更项，先在下面添加。</p>

        <template v-if="versionDetail.data.status === 'DRAFT'">
          <h4 class="og-section">添加变更</h4>
          <label class="og-label">动作</label>
          <select v-model="changeForm.changeType" class="mp-input">
            <option value="RENAME">改名</option>
            <option value="MOVE">调整上级</option>
            <option value="DISABLE">停用</option>
            <option value="ENABLE">启用</option>
          </select>
          <label class="og-label">目标组织<span class="og-required">*</span></label>
          <select v-model="changeForm.orgKey" class="mp-input">
            <option value="">请选择组织</option>
            <option v-for="opt in orgOptions" :key="opt.key" :value="opt.key">{{ opt.label }}</option>
          </select>
          <template v-if="changeForm.changeType === 'RENAME'">
            <label class="og-label">新名称<span class="og-required">*</span></label>
            <input v-model="changeForm.name" class="mp-input" />
          </template>
          <template v-if="changeForm.changeType === 'MOVE'">
            <label class="og-label">新的上级<span class="og-required">*</span></label>
            <select v-model="changeForm.parentKey" class="mp-input">
              <option value="">请选择上级</option>
              <option v-for="opt in parentOptions" :key="opt.key" :value="opt.key">{{ opt.label }}</option>
            </select>
          </template>
          <div v-if="changeForm.error" class="mp-form-err">{{ changeForm.error }}</div>
          <AppButton
            variant="secondary"
            size="small"
            style="margin-top: var(--space-3)"
            :loading="changeForm.submitting"
            @click="submitChange"
          >加入草稿</AppButton>
        </template>

        <template v-if="versionDetail.data.impact && versionDetail.data.impact.items">
          <h4 class="og-section">影响面（校验时算出）</h4>
          <p v-for="(im, idx) in versionDetail.data.impact.items" :key="idx" class="mp-note">
            {{ orgLabel(im.orgType, im.orgNodeId) }}：影响 {{ im.affectedMajors }} 个专业 /
            {{ im.affectedClasses }} 个班级 / {{ im.affectedStudents }} 名学生 /
            {{ im.affectedAssignments }} 条在任任职
          </p>
        </template>
      </template>
    </AppDrawer>

    <!-- 版本状态流转 -->
    <AppDrawer v-model:visible="versionAction.open" :title="versionAction.title">
      <p class="mp-note">{{ versionAction.tip }}</p>
      <template v-if="versionAction.target === 'SCHEDULED'">
        <label class="og-label">计划生效时间<span class="og-required">*</span></label>
        <input v-model="versionAction.effectiveAt" type="datetime-local" class="mp-input" />
      </template>
      <label class="og-label">原因<span class="og-required">*</span></label>
      <textarea v-model="versionAction.reason" class="mp-textarea" rows="2" placeholder="至少 5 个字" />
      <div v-if="versionAction.error" class="mp-form-err">{{ versionAction.error }}</div>
      <template #footer>
        <AppButton variant="ghost" @click="versionAction.open = false">取消</AppButton>
        <AppButton variant="primary" :loading="versionAction.submitting" @click="submitVersionTransition">
          确认
        </AppButton>
      </template>
    </AppDrawer>

    <!-- 新增 / 编辑组织节点 -->
    <AppDrawer v-model:visible="form.open" :title="form.id ? '编辑组织节点' : '新增下级组织'">
      <FormFields v-model="form.value" :fields="formFields" :errors="form.errors" />
      <p v-if="form.parentName" class="mp-note" style="margin-top: var(--space-2)">上级组织：{{ form.parentName }}</p>
      <template #footer>
        <AppButton variant="ghost" @click="form.open = false">取消</AppButton>
        <AppButton variant="primary" :loading="form.submitting" @click="submitForm">保存并留痕</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="confirmDeprecate"
      type="danger"
      :title="'作废组织「' + (deprecateRow ? deprecateRow.name : '') + '」？'"
      :message="deprecateRow && deprecateRow.memberCount > 0
        ? '该组织下仍有 ' + deprecateRow.memberCount + ' 名成员；后端会校验在籍学生和下级组织，存在引用时将拒绝停用。'
        : '作废为逻辑删除，历史归属关系保留可追溯。'"
      confirm-text="确认作废并留痕"
      require-reason
      reason-label="作废原因"
      :submitting="deprecateSubmitting"
      @confirm="doDeprecate"
    />
  </ModulePageShell>
</template>

<script>
/**
 * 组织结构管理（/admin/system/org）：
 * 组织树（学院/专业/班级/部门）增改 / 作废留痕 / 导出；岗位列表来自教职工归属。
 * 组织导入统一走实施中心「数据导入与智能匹配」。
 */
import { ModulePageShell, ModuleToolbar, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import FormFields from '@/modules/system/components/FormFields.vue'
import { systemApi } from '@/modules/system/api/system.api'
import { toast } from '@/utils/toast'

const ORG_TYPES = [
  { value: 'COLLEGE', label: '学院' },
  { value: 'MAJOR', label: '专业' },
  { value: 'CLASS', label: '班级' }
]

export default {
  name: 'SystemOrgView',
  components: {
    ModulePageShell, ModuleToolbar, DataTable, StatusTag, LoadingState, ErrorState, EmptyState,
    AppButton, AppDrawer, AppConfirmDialog, FormFields
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      api: systemApi,
      tab: 'tree',
      loading: true,
      error: '',
      tree: [],
      positions: [],
      posColumns: [
        { key: 'name', title: '岗位' },
        { key: 'orgName', title: '所属组织' },
        { key: 'memberCount', title: '成员数' },
        { key: 'remark', title: '说明' },
        { key: 'status', title: '状态' }
      ],
      form: { open: false, id: '', parentName: '', value: {}, errors: {}, submitting: false },
      confirmDeprecate: false,
      deprecateRow: null,
      deprecateSubmitting: false,
      // ── SYS-04 组织变更版本 ──
      versions: [],
      versionForm: { open: false, versionName: '', reason: '', error: '', submitting: false },
      versionDetail: { open: false, loading: false, title: '', data: null, versionId: '' },
      versionAction: {
        open: false, versionId: '', target: '', title: '', tip: '',
        reason: '', effectiveAt: '', expectedVersion: 0, error: '', submitting: false
      },
      changeForm: {
        changeType: 'RENAME', orgKey: '', parentKey: '', name: '', error: '', submitting: false
      }
    }
  },
  computed: {
    flatTree() {
      const out = []
      const walk = (nodes, depth) => {
        nodes.forEach((n) => {
          out.push({ ...n, depth })
          if (n.children && n.children.length) walk(n.children, depth + 1)
        })
      }
      walk(this.tree, 0)
      return out
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [
        { key: 'createOrg', label: '＋ 新增学院/部门', variant: 'primary' },
        { key: 'importOrg', label: '⇪ 数据导入与匹配' },
        { key: 'exportOrg', label: '⇩ 导出组织结构' }
      ]
        .filter((a) => pa[a.key] && pa[a.key].visible)
        .map((a) => ({ ...a, disabled: !pa[a.key].allowed, disabledReason: pa[a.key].reason }))
    },
    formFields() {
      return [
        { key: 'name', label: '组织名称', required: true },
        { key: 'code', label: '组织编码', required: true, disabled: !!this.form.id, lockNote: this.form.id ? '（不可修改）' : '' },
        { key: 'type', label: '组织类型', type: 'select', required: true, options: ORG_TYPES }
      ]
    },
    /** 变更版本里可选的组织（扁平化组织树） */
    orgOptions() {
      return this.flatTree.map((n) => ({
        key: `${n.type}:${n.id}`,
        label: `${'　'.repeat(n.depth)}${n.name}（${n.typeLabel}）`
      }))
    },
    /** 调整上级时可选的父节点：专业挂学院、班级挂专业 */
    parentOptions() {
      const childType = (this.changeForm.orgKey || '').split(':')[0]
      const wanted = childType === 'MAJOR' ? 'COLLEGE' : childType === 'CLASS' ? 'MAJOR' : ''
      if (!wanted) return []
      return this.flatTree
        .filter((n) => n.type === wanted)
        .map((n) => ({ key: `${n.type}:${n.id}`, label: `${n.name}（${n.typeLabel}）` }))
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
      const q = String(this.$route.query.tab || '')
      if (q === 'positions') this.tab = 'positions'
      else if (q === 'versions') this.tab = 'versions'
      else if (q === 'college' || q === 'major' || q === 'class' || q === 'tree') this.tab = 'tree'
    },

    // ── SYS-04 组织变更版本 ────────────────────────────────────────────
    fmtTime(v) { return v ? String(v).replace('T', ' ').slice(0, 16) : '—' },
    versionLabel(s) {
      return ({ DRAFT: '草稿', VALIDATED: '已校验', SCHEDULED: '已排期', ACTIVATED: '已生效', ROLLED_BACK: '已回滚' })[s] || s
    },
    versionActionLabel(s) {
      return ({ DRAFT: '退回草稿', VALIDATED: '校验', SCHEDULED: '排期', ACTIVATED: '立即激活', ROLLED_BACK: '回滚' })[s] || s
    },
    versionTagType(s) {
      if (s === 'ACTIVATED') return 'success'
      if (s === 'SCHEDULED') return 'processing'
      if (s === 'ROLLED_BACK') return 'danger'
      return 'default'
    },
    changeLabel(s) {
      return ({ CREATE: '新建', RENAME: '改名', MOVE: '调整上级', DISABLE: '停用', ENABLE: '启用' })[s] || s
    },
    orgLabel(type, id) {
      const hit = this.flatTree.find((n) => n.type === type && String(n.id) === String(id))
      return hit ? `${hit.name}（${hit.typeLabel}）` : `${type}:${id}`
    },
    describePayload(item) {
      const p = item.payload || {}
      if (item.changeType === 'RENAME') return `改名为「${p.name}」`
      if (item.changeType === 'MOVE') return `移动到 ${this.orgLabel(item.orgType === 'MAJOR' ? 'COLLEGE' : 'MAJOR', p.parentId)}`
      if (item.changeType === 'CREATE') return `新建「${p.name}」`
      return '—'
    },

    async switchToVersions() {
      this.tab = 'versions'
      await this.loadVersions()
    },

    async loadVersions() {
      const res = await this.api.getOrgVersions()
      if (res.code === 0) this.versions = (res.data || {}).items || []
      else toast.error(res.message)
    },

    openVersionCreate() {
      this.versionForm = { open: true, versionName: '', reason: '', error: '', submitting: false }
    },

    async submitVersionCreate() {
      if (!this.versionForm.versionName.trim()) { this.versionForm.error = '请填写版本名称'; return }
      if (this.versionForm.reason.trim().length < 5) { this.versionForm.error = '变更原因不少于 5 个字'; return }
      this.versionForm.submitting = true
      const res = await this.api.createOrgVersion({
        versionName: this.versionForm.versionName.trim(),
        reason: this.versionForm.reason.trim()
      })
      this.versionForm.submitting = false
      if (res.code === 0) {
        toast.success('变更版本草稿已创建')
        this.versionForm.open = false
        await this.loadVersions()
        this.openVersionDetail(res.data)
      } else {
        this.versionForm.error = res.message
      }
    },

    async openVersionDetail(v) {
      this.versionDetail = {
        open: true, loading: true, title: `${v.versionName || v.versionCode} · 详情`,
        data: null, versionId: v.versionId
      }
      this.changeForm = { changeType: 'RENAME', orgKey: '', parentKey: '', name: '', error: '', submitting: false }
      const res = await this.api.getOrgVersionDetail(v.versionId)
      this.versionDetail.loading = false
      if (res.code === 0) this.versionDetail.data = res.data
      else toast.error(res.message)
    },

    async submitChange() {
      if (!this.changeForm.orgKey) { this.changeForm.error = '请选择目标组织'; return }
      if (this.changeForm.changeType === 'RENAME' && !this.changeForm.name.trim()) {
        this.changeForm.error = '请填写新名称'
        return
      }
      if (this.changeForm.changeType === 'MOVE' && !this.changeForm.parentKey) {
        this.changeForm.error = '请选择新的上级'
        return
      }
      const [orgType, orgNodeId] = this.changeForm.orgKey.split(':')
      const payload = {}
      if (this.changeForm.changeType === 'RENAME') payload.name = this.changeForm.name.trim()
      if (this.changeForm.changeType === 'MOVE') payload.parentId = Number(this.changeForm.parentKey.split(':')[1])

      this.changeForm.submitting = true
      this.changeForm.error = ''
      const res = await this.api.addOrgVersionChange(this.versionDetail.versionId, {
        changeType: this.changeForm.changeType,
        orgType,
        orgNodeId: Number(orgNodeId),
        payload
      })
      this.changeForm.submitting = false
      if (res.code === 0) {
        toast.success('变更项已加入草稿')
        this.changeForm.name = ''
        this.openVersionDetail({
          versionId: this.versionDetail.versionId,
          versionName: this.versionDetail.title.replace(' · 详情', '')
        })
      } else {
        this.changeForm.error = res.message
      }
    },

    openVersionTransition(v, target) {
      const tips = {
        VALIDATED: '校验会算出影响面，但不会改动组织树。',
        SCHEDULED: '排期后到点自动生效；生效前组织树保持不变。',
        ACTIVATED: '激活会把全部变更真正写入组织树，之后可回滚。',
        ROLLED_BACK: '回滚会把组织恢复到变更前的名称与归属。',
        DRAFT: '退回草稿以便继续调整变更项。'
      }
      this.versionAction = {
        open: true, versionId: v.versionId, target,
        title: `${this.versionActionLabel(target)} · ${v.versionName || v.versionCode}`,
        tip: tips[target] || '', reason: '', effectiveAt: '',
        expectedVersion: v.version, error: '', submitting: false
      }
    },

    async submitVersionTransition() {
      if (this.versionAction.reason.trim().length < 5) { this.versionAction.error = '原因不少于 5 个字'; return }
      if (this.versionAction.target === 'SCHEDULED' && !this.versionAction.effectiveAt) {
        this.versionAction.error = '请填写计划生效时间'
        return
      }
      this.versionAction.submitting = true
      this.versionAction.error = ''
      const res = await this.api.transitionOrgVersion(this.versionAction.versionId, {
        targetStatus: this.versionAction.target,
        reason: this.versionAction.reason.trim(),
        expectedVersion: this.versionAction.expectedVersion,
        effectiveAt: this.versionAction.effectiveAt
          ? new Date(this.versionAction.effectiveAt).toISOString()
          : null
      })
      this.versionAction.submitting = false
      if (res.code === 0) {
        toast.success('组织版本状态已更新')
        this.versionAction.open = false
        await this.loadVersions()
        // 激活/回滚会改动组织树，刷新树保证页面与库一致
        if (['ACTIVATED', 'ROLLED_BACK'].includes(this.versionAction.target)) await this.load()
      } else {
        this.versionAction.error = res.message
      }
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
      if (key === 'createOrg') this.openEdit(null, null)
      if (key === 'importOrg') {
        toast.info('组织导入请前往实施中心「数据导入与智能匹配」')
        this.$router.push('/admin/system/implementation/data-mapping')
        return
      }
      if (key === 'exportOrg') {
        const res = await systemApi.exportOrg()
        if (res.code === 0) toast.success('组织结构已下载：' + res.data.fileName + '（含水印），已留痕')
        else toast.error(res.message)
      }
    },
    openEdit(node, parent) {
      const key = node ? 'editOrg' : 'createOrg'
      if (!this.can(key)) return
      this.form = {
        open: true,
        id: node ? node.id : '',
        parentId: parent ? parent.id : '',
        parentName: parent ? parent.name : node ? '' : '（顶级）',
        value: node ? { name: node.name, code: node.code, type: node.type } : { name: '', code: '', type: parent ? (parent.type === 'COLLEGE' ? 'MAJOR' : parent.type === 'MAJOR' ? 'CLASS' : 'DEPT') : 'COLLEGE' },
        errors: {},
        submitting: false
      }
    },
    async submitForm() {
      const errors = FormFields.validateRequired(this.formFields, this.form.value)
      this.form.errors = errors
      if (Object.keys(errors).length) return
      this.form.submitting = true
      const typeLabel = (ORG_TYPES.find((t) => t.value === this.form.value.type) || {}).label
      const res = await systemApi.saveOrgNode({ id: this.form.id || undefined, parentId: this.form.parentId || undefined, ...this.form.value, typeLabel })
      this.form.submitting = false
      if (res.code === 0) {
        toast.success('组织节点已保存并留痕')
        this.form.open = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    askDeprecate(node) {
      if (!this.can('deprecateOrg')) return
      this.deprecateRow = node
      this.confirmDeprecate = true
    },
    async doDeprecate({ reason }) {
      this.deprecateSubmitting = true
      const res = await systemApi.deprecateOrgNode(this.deprecateRow.id, { type: this.deprecateRow.type, reason })
      this.deprecateSubmitting = false
      if (res.code === 0) {
        toast.success('组织节点已停用（逻辑操作，可恢复），原因已留痕')
        this.confirmDeprecate = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const [treeRes, posRes] = await Promise.all([systemApi.getDepartmentTree(), systemApi.getPositions()])
      if (treeRes.code === 0) this.tree = treeRes.data
      else this.error = treeRes.message
      if (posRes.code === 0) this.positions = posRes.data
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.og-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--font-size-sm);
}
.og-table th {
  text-align: left;
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  background: var(--bg-section-blue);
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border-base);
}
.og-table td {
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border-light);
}
.og-branch {
  color: var(--text-tertiary);
  margin-right: var(--space-1);
}
.og-danger {
  color: var(--danger-600);
}
.mp-link + .mp-link {
  margin-left: var(--space-2);
}
/* SYS-04 组织变更版本 */
.og-label {
  display: block;
  margin-top: var(--space-3);
  margin-bottom: var(--space-1);
  font-size: var(--font-size-sm);
}
.og-required {
  color: var(--danger-600);
}
.og-section {
  margin: var(--space-4) 0 var(--space-2);
  font-size: var(--font-size-sm);
}
</style>
