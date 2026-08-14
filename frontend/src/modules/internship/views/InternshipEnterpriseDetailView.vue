<template>
  <ModulePageShell
    :title="detail ? detail.name : '企业详情'"
    :subtitle="detail ? (detail.creditCode || '无信用代码') + ' · ' + detail.sourceLabel : '加载中'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <button class="mp-btn" @click="$router.push('/admin/internship/enterprises')">← 返回企业库</button>
    </template>

    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <template v-else-if="detail">
      <div class="ed-head">
        <AppStatusTag :type="detail.coopStatusTone" dot>{{ detail.coopStatusLabel }}</AppStatusTag>
        <span v-if="detail.blacklist" class="ed-bl">黑名单 · {{ detail.blacklistReason }}</span>
        <AppStatusTag :type="detail.qualificationStatus === 'PASSED' ? 'success' : (detail.qualificationStatus === 'FAILED' ? 'danger' : 'default')">{{ detail.qualificationLabel }}</AppStatusTag>
        <div class="ed-head__spacer" />
        <AppPermissionButton v-if="detail.coopStatus === 'PENDING'" code="reviewEnterprise" variant="primary" :allowed="can('reviewEnterprise')" :reason="reason('reviewEnterprise')" @click="askReview('APPROVE')">审核通过</AppPermissionButton>
        <AppPermissionButton v-if="detail.coopStatus === 'PENDING'" code="reviewEnterprise" variant="danger" :allowed="can('reviewEnterprise')" :reason="reason('reviewEnterprise')" @click="askReview('REJECT')">审核驳回</AppPermissionButton>
        <AppButton v-else-if="detail.coopStatus === 'ACTIVE'" variant="secondary" @click="askCoop('SUSPEND')">暂停合作</AppButton>
        <AppButton v-else-if="detail.coopStatus === 'SUSPENDED'" variant="secondary" @click="askCoop('RESUME')">恢复合作</AppButton>
        <AppPermissionButton v-if="!detail.blacklist && detail.coopStatus !== 'ARCHIVED'" code="blacklistEnterprise" variant="danger" :allowed="can('blacklistEnterprise')" :reason="reason('blacklistEnterprise')" @click="askBlacklist(true)">拉黑</AppPermissionButton>
        <AppPermissionButton v-if="detail.blacklist" code="blacklistEnterprise" variant="secondary" :allowed="can('blacklistEnterprise')" :reason="reason('blacklistEnterprise')" @click="askBlacklist(false)">移出黑名单</AppPermissionButton>
      </div>

      <nav class="ed-tabs">
        <button v-for="t in tabs" :key="t.key" class="ed-tabs__item" :class="{ 'is-active': tab === t.key }" @click="tab = t.key">{{ t.label }}</button>
      </nav>

      <!-- 主档 -->
      <section v-show="tab === 'basic'" class="mp-card">
        <div class="mp-card__body">
          <AppDescriptionList :items="basicFields" />
        </div>
      </section>

      <!-- 联系人与导师 -->
      <section v-show="tab === 'contacts'" class="mp-card">
        <div class="mp-card__head">
          <span class="mp-card__title">联系人 / 企业导师（{{ contacts.length }}）</span>
          <AppPermissionButton code="manageEnterpriseContact" variant="primary" size="sm" :allowed="can('manageEnterpriseContact')" :reason="reason('manageEnterpriseContact')" @click="openContact(null)">＋ 新增</AppPermissionButton>
        </div>
        <div class="mp-card__body">
          <EmptyState v-if="!contacts.length" title="暂无联系人" description="添加企业 HR / 企业导师，便于实习对接" />
          <table v-else class="ed-tbl">
            <thead><tr><th>类型</th><th>姓名</th><th>职务</th><th>电话(脱敏)</th><th>邮箱</th><th>主联系</th><th>操作</th></tr></thead>
            <tbody>
              <tr v-for="c in contacts" :key="c.id">
                <td>{{ c.contactTypeLabel }}</td><td>{{ c.name }}</td><td>{{ c.title || '—' }}</td>
                <td>{{ c.phoneMasked || '—' }}</td><td>{{ c.email || '—' }}</td>
                <td>{{ c.isPrimary ? '★' : '' }}</td>
                <td>
                  <AppPermissionButton code="manageEnterpriseContact" variant="ghost" size="sm" :allowed="can('manageEnterpriseContact')" :reason="reason('manageEnterpriseContact')" @click="openContact(c)">编辑</AppPermissionButton>
                  <AppPermissionButton code="manageEnterpriseContact" variant="danger" size="sm" :allowed="can('manageEnterpriseContact')" :reason="reason('manageEnterpriseContact')" @click="askDeleteContact(c)">删除</AppPermissionButton>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- 合作与资质 -->
      <section v-show="tab === 'coop'" class="mp-card">
        <div class="mp-card__body">
          <AppDescriptionList :items="coopFields">
            <template #blacklistReason="{ item }"><span class="ed-danger">{{ item.value }}</span></template>
          </AppDescriptionList>
        </div>
      </section>

      <!-- 企业岗位（反向补：岗位库完成后接入） -->
      <section v-show="tab === 'positions'" class="mp-card">
        <div class="mp-card__head">
          <span class="mp-card__title">企业岗位（{{ detail.positionSummary ? detail.positionSummary.total : positions.length }} 个 · 已上架 {{ detail.positionSummary ? detail.positionSummary.published : 0 }}）</span>
          <button class="mp-btn mp-btn--primary mp-btn--sm" @click="$router.push('/admin/internship/positions')">去岗位库</button>
        </div>
        <div class="mp-card__body">
          <EmptyState v-if="!positions.length" title="该企业暂无岗位" description="到岗位库为该企业新增实习岗位" />
          <table v-else class="ed-tbl">
            <thead><tr><th>岗位</th><th>专业要求</th><th>容量</th><th>状态</th><th>操作</th></tr></thead>
            <tbody>
              <tr v-for="p in positions" :key="p.id">
                <td>{{ p.title }}</td><td>{{ p.majorRequirement || '不限' }}</td>
                <td>{{ p.allocatedCount }}/{{ p.headcount }}</td>
                <td><AppStatusTag :type="p.statusTone">{{ p.statusLabel }}</AppStatusTag></td>
                <td><button class="mp-link" @click="$router.push('/admin/internship/positions/' + p.id)">详情</button></td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- 审计 -->
      <section v-show="tab === 'inspections'" class="mp-card">
        <div class="mp-card__head">
          <span class="mp-card__title">企业考察与准入（{{ inspections.length }}）</span>
          <AppPermissionButton code="internship.enterprise.inspection.manage"
            :allowed="canInspect"
            variant="secondary" size="sm" @click="openInspectionCreate">＋ 登记考察</AppPermissionButton>
        </div>
        <div class="mp-card__body">
          <div v-if="inspectionsError" class="ed-state is-err">{{ inspectionsError }}
            <button type="button" class="mp-link" @click="loadInspections">重试</button>
          </div>
          <p v-else-if="!inspections.length" class="ed-state">
            暂无考察记录。企业准入有效期由考察审核结论写入，通过后企业才可继续接收实习生。
          </p>
          <table v-else class="ed-tbl">
            <thead><tr><th>考察方式</th><th>考察日期</th><th>考察人</th><th>结论</th><th>准入有效期</th><th>状态</th><th>审核人</th><th>操作</th></tr></thead>
            <tbody>
              <tr v-for="x in inspections" :key="x.id">
                <td>{{ x.inspectionTypeLabel || x.inspectionType }}</td>
                <td>{{ x.inspectionDate || '—' }}</td>
                <td>{{ x.inspectors || '—' }}</td>
                <td class="ed-cell-wrap">{{ x.conclusion || '—' }}</td>
                <td>{{ x.validUntil || '—' }}</td>
                <td><AppStatusTag :status="x.status">{{ x.statusLabel || x.status }}</AppStatusTag></td>
                <td>{{ x.reviewedByName || '—' }}</td>
                <td class="ed-ops">
                  <AppPermissionButton v-if="x.status === 'DRAFT'" code="internship.enterprise.inspection.manage"
                    :allowed="canInspect" variant="ghost" size="sm"
                    @click="openInspectionAction(x, 'submit')">提交审核</AppPermissionButton>
                  <template v-if="x.status === 'SUBMITTED'">
                    <AppPermissionButton code="internship.enterprise.inspection.manage"
                      :allowed="canInspect" variant="secondary" size="sm"
                      @click="openInspectionAction(x, 'approve')">通过</AppPermissionButton>
                    <AppPermissionButton code="internship.enterprise.inspection.manage"
                      :allowed="canInspect" variant="ghost" size="sm" :danger="true"
                      @click="openInspectionAction(x, 'reject')">驳回</AppPermissionButton>
                  </template>
                  <span v-if="!['DRAFT', 'SUBMITTED'].includes(x.status)" class="ed-muted">—</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section v-show="tab === 'audit'" class="mp-card">
        <div class="mp-card__body">
          <AppAuditTrail :records="auditRecords" :show-ip="false" />
        </div>
      </section>
    </template>

    <!-- 联系人 新增/编辑 -->
    <AppDrawer v-model:visible="contactDrawer" :title="editingContact ? '编辑联系人' : '新增联系人 / 企业导师'" mode="modal" size="large">
      <AppForm layout="vertical" :model="cform" @submit="submitContact">
        <AppFormItem label="类型">
          <AppSelect v-model="cform.contactType" :options="contactTypeOptions" />
        </AppFormItem>
        <AppFormItem label="姓名" required>
          <AppTextInput v-model.trim="cform.name" />
        </AppFormItem>
        <AppFormItem label="职务">
          <AppTextInput v-model.trim="cform.title" />
        </AppFormItem>
        <AppFormItem label="电话" hint="敏感字段，展示脱敏">
          <AppTextInput v-model.trim="cform.phone" placeholder="敏感字段，展示脱敏" />
        </AppFormItem>
        <AppFormItem label="邮箱">
          <AppTextInput v-model.trim="cform.email" />
        </AppFormItem>
        <label class="ie-fld ie-chk"><input v-model="cform.isPrimary" type="checkbox" /> 设为该类型主联系人</label>
        <AppInlineAlert v-if="cformError" type="danger" :description="cformError" />
        <div class="ie-actions">
          <button type="button" class="mp-btn" @click="contactDrawer = false">取消</button>
          <button type="submit" class="mp-btn mp-btn--primary" :disabled="submitting">保存</button>
        </div>
      </AppForm>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="confirm.visible"
      :title="confirm.title"
      :message="confirm.message"
      :type="confirm.type"
      :confirm-text="confirm.confirmText"
      :require-reason="confirm.requireReason"
      :reason-label="confirm.reasonLabel"
      :submitting="submitting"
      @confirm="onConfirm"
    />

    <!-- 企业考察独立确认框：与上面的企业状态机动作互不干扰 -->
    <AppConfirmDialog
      v-if="inspectionDialog"
      :visible="true"
      :title="inspectionDialog.title"
      :message="inspectionDialog.message"
      :danger="inspectionDialog.danger"
      :confirm-text="inspectionDialog.confirmText"
      :require-reason="inspectionDialog.requireReason"
      :reason-label="inspectionDialog.reasonLabel"
      :submitting="inspectionActing"
      @update:visible="inspectionDialog = null"
      @cancel="inspectionDialog = null"
      @confirm="onInspectionConfirm"
    >
      <ConflictNotice :state="conflict" />
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
/** 企业详情（/admin/internship/enterprises/:id）：主档 + 联系人/导师 CRUD + 合作资质 + 审计 + 状态机动作。 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import {
  AppStatusTag, AppPermissionButton, AppAuditTrail, AppInlineAlert,
  AppDescriptionList, AppForm, AppFormItem, AppTextInput, AppSelect
} from '@/components/common'
import { AppDrawer, AppButton } from '@/components/ui'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { positionApi } from '@/modules/internship/api/position.api'
import { complianceApi } from '@/modules/internship/api/compliance.api'
import { canCode } from '@/modules/internship/composables/permission'
import ConflictNotice from './components/ConflictNotice.vue'
import { isConflict, captureConflict, emptyConflict } from '@/modules/internship/composables/conflictGuard'
import { toast } from '@/utils/toast'

const EMPTY_CFORM = () => ({ contactType: 'CONTACT', name: '', title: '', phone: '', email: '', isPrimary: false })
const CONTACT_TYPE_OPTIONS = [{ label: '联系人', value: 'CONTACT' }, { label: '企业导师', value: 'MENTOR' }]

export default {
  name: 'InternshipEnterpriseDetailView',
  components: {
    ModulePageShell, AppStatusTag, LoadingState, ErrorState, EmptyState, AppDrawer, AppButton, AppConfirmDialog,
    AppPermissionButton, AppAuditTrail, AppInlineAlert, AppDescriptionList, AppForm, AppFormItem, AppTextInput, AppSelect,
    ConflictNotice
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', submitting: false, detail: null, tab: 'basic',
      tabs: [
        { key: 'basic', label: '主档' },
        { key: 'contacts', label: '联系人与导师' },
        { key: 'coop', label: '合作与资质' },
        { key: 'positions', label: '企业岗位' },
        { key: 'inspections', label: '考察与准入' },
        { key: 'audit', label: '审计记录' }
      ],
      positions: [], positionsLoaded: false,
      // 企业考察：后端 create/submit/review 一直都在（含并发保护与跨租户守卫），
      // 但此前前端没有任何入口，等于建好的准入链路没人能用。
      inspections: [], inspectionsLoaded: false, inspectionsError: '',
      inspectionActing: false, conflict: emptyConflict(),
      inspectionDialog: null,
      contactDrawer: false, editingContact: null, cform: EMPTY_CFORM(), cformError: '',
      confirm: { visible: false, title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false, reasonLabel: '原因', action: null, extra: null }
    }
  },
  computed: {
    perms() { return this.ctx.permissionActions || {} },
    /** 企业考察用的是后端权限码（require_permission 同一套），
     *  与本页其它按钮走的 permissionActions 动作名不是一个体系，不能混用。 */
    canInspect() { return canCode(this.ctx, 'internship.enterprise.inspection.manage') },
    contacts() { return this.detail ? this.detail.contacts : [] },
    basicFields() {
      const d = this.detail
      return [
        { label: '统一社会信用代码', value: d.creditCode }, { label: '行业', value: d.industry },
        { label: '企业性质', value: d.nature }, { label: '规模', value: d.scale },
        { label: '地区', value: d.region }, { label: '城市', value: d.city },
        { label: '详细地址', value: d.address }, { label: '来源', value: d.sourceLabel },
        { label: '联系人', value: d.contactPerson }, { label: '联系电话(脱敏)', value: d.contactPhoneMasked },
        { label: '累计实习生', value: String(d.internCount) }, { label: '备注', value: d.remark }
      ]
    },
    coopFields() {
      const d = this.detail
      const items = [
        { label: '合作状态', value: d.coopStatusLabel },
        { label: '资质核验', value: d.qualificationLabel },
        { label: '合作级别', value: d.cooperationLevel },
        { label: '累计实习生', value: String(d.internCount) },
        { label: '审核人', value: d.reviewBy },
        { label: '审核时间', value: d.reviewAt },
        { key: 'reviewComment', label: '审核意见', value: d.reviewComment, span: 2 }
      ]
      if (d.blacklist) items.push({ key: 'blacklistReason', label: '黑名单原因', value: d.blacklistReason, span: 2 })
      return items
    },
    auditRecords() {
      const trail = (this.detail && this.detail.auditTrail) || []
      return trail.map((a) => ({ action: a.action, actor: a.operator, at: a.occurredAt }))
    },
    contactTypeOptions() { return CONTACT_TYPE_OPTIONS }
  },
  created() { this.load() },
  watch: {
    tab(next) {
      // 考察记录按企业查，切到该页签时才拉，避免每次进详情都多打一个接口
      if (next === 'inspections' && !this.inspectionsLoaded) this.loadInspections()
    }
  },
  methods: {
    can(key) { const p = this.perms[key]; return !!(p && p.allowed) },
    async loadInspections() {
      this.inspectionsError = ''
      const res = await complianceApi.listInspections(this.$route.params.id)
      this.inspectionsLoaded = true
      if (res.code !== 0) { this.inspectionsError = res.message || '考察记录加载失败'; return }
      this.inspections = Array.isArray(res.data) ? res.data : (res.data && res.data.list) || []
    },
    openInspectionCreate() {
      this.conflict = emptyConflict()
      this.inspectionDialog = {
        mode: 'create', id: '', title: '登记企业考察',
        message: '登记一次企业考察；提交并通过后才会写入企业准入有效期。',
        confirmText: '登记', requireReason: true, reasonLabel: '考察结论（≥5字）', danger: false
      }
    },
    openInspectionAction(row, action) {
      this.conflict = emptyConflict()
      const map = {
        submit: { title: '提交考察审核', message: '提交后进入审核环节，草稿不可再改。',
                  confirmText: '提交', requireReason: false, reasonLabel: '', danger: false },
        approve: { title: '通过企业考察', message: '通过后将写入企业准入有效期，企业方可继续接收实习生。',
                   confirmText: '通过', requireReason: false, reasonLabel: '审核意见（选填）', danger: false },
        reject: { title: '驳回企业考察', message: '驳回后企业准入不会更新，请写明原因。',
                  confirmText: '驳回', requireReason: true, reasonLabel: '驳回原因（≥5字）', danger: true }
      }[action]
      this.inspectionDialog = { mode: action, id: row.id, ...map }
    },
    async onInspectionConfirm({ reason }) {
      const d = this.inspectionDialog
      if (!d) return
      this.inspectionActing = true
      let res
      try {
        if (d.mode === 'create') {
          res = await complianceApi.createInspection({
            companyId: this.$route.params.id, inspectionType: 'DOCUMENT', conclusion: reason
          })
        } else if (d.mode === 'submit') {
          res = await complianceApi.submitInspection(d.id)
        } else {
          res = await complianceApi.reviewInspection(d.id, d.mode, { comment: reason || '' })
        }
      } finally {
        this.inspectionActing = false
      }
      if (isConflict(res)) {
        // 两个管理员同时审同一条考察时，后端条件更新让输家拿 409。
        // 弹窗不关、填的意见不动，把最新状态摆出来让他自己决定。
        this.conflict = await captureConflict({
          res,
          kept: reason || '',
          refresh: () => this.loadInspections(),
          latest: () => {
            const fresh = this.inspections.find((x) => String(x.id) === String(d.id))
            if (!fresh) throw new Error('这条考察记录已不在列表里')
            return [
              { label: '最新状态', value: fresh.statusLabel || fresh.status || '' },
              { label: '审核人', value: fresh.reviewedByName || '' },
              { label: '审核意见', value: fresh.reviewComment || '' }
            ]
          }
        })
        return
      }
      if (!res || res.code !== 0) return toast.error((res && res.message) || '操作失败')
      this.inspectionDialog = null
      this.conflict = emptyConflict()
      toast.success('操作成功，已写审计')
      await this.loadInspections()
    },
    reason(key) { const p = this.perms[key]; return p && !p.allowed ? p.reason : '' },
    async load() {
      this.loading = true; this.error = ''
      const res = await internshipApi.getEnterpriseDetail(this.$route.params.id)
      if (res.code === 0) this.detail = res.data
      else this.error = res.message
      this.loading = false
      if (res.code === 0) {
        const pr = await positionApi.getPositions({ companyId: this.$route.params.id, page: 1, pageSize: 50 })
        if (pr.code === 0) this.positions = pr.data.list
      }
    },
    openContact(c) {
      if (!this.can('manageEnterpriseContact')) return toast.error(this.reason('manageEnterpriseContact'))
      this.editingContact = c
      this.cform = c ? { contactType: c.contactType, name: c.name, title: c.title, phone: '', email: c.email, isPrimary: c.isPrimary } : EMPTY_CFORM()
      this.cformError = ''
      this.contactDrawer = true
    },
    async submitContact() {
      if (!this.cform.name) { this.cformError = '姓名必填'; return }
      this.submitting = true
      try {
        const res = this.editingContact
          ? await internshipApi.updateEnterpriseContact(this.detail.id, this.editingContact.id, this.cform)
          : await internshipApi.addEnterpriseContact(this.detail.id, this.cform)
        if (res.code === 0) { toast.success('已保存'); this.contactDrawer = false; this.load() }
        else this.cformError = res.message
      } finally { this.submitting = false }
    },
    askDeleteContact(c) {
      if (!this.can('manageEnterpriseContact')) return toast.error(this.reason('manageEnterpriseContact'))
      this.confirm = { visible: true, title: '删除联系人', message: `确认删除「${c.name}」？`, type: 'danger', confirmText: '确认删除', requireReason: false, action: 'DELETE_CONTACT', extra: c.id }
    },
    askReview(decision = 'APPROVE') {
      // BUG-002：补齐驳回分支，驳回原因必填（企业凭此整改后重新提交）
      if (!this.can('reviewEnterprise')) return toast.error(this.reason('reviewEnterprise'))
      const reject = decision === 'REJECT'
      this.confirm = {
        visible: true,
        title: reject ? '企业资质驳回' : '企业资质审核通过',
        message: reject ? '确认驳回该企业资质核验？驳回后状态转为「已驳回」，企业需整改后重新提交。'
          : '确认该企业资质核验通过？通过→合作中。',
        type: reject ? 'danger' : 'primary',
        confirmText: reject ? '确认驳回' : '通过（资质合格）',
        requireReason: reject,
        reasonLabel: reject ? '驳回原因（必填）' : '审核意见（选填）',
        action: reject ? 'REVIEW_REJECT' : 'REVIEW_APPROVE',
        extra: null
      }
    },
    askCoop(action) {
      const m = { SUSPEND: { t: '暂停合作', c: '确认暂停', type: 'warning' }, RESUME: { t: '恢复合作', c: '确认恢复', type: 'primary' } }[action]
      this.confirm = { visible: true, title: m.t, message: `确认执行「${m.t}」？`, type: m.type, confirmText: m.c, requireReason: false, action: 'COOP_' + action, extra: null }
    },
    askBlacklist(on) {
      if (!this.can('blacklistEnterprise')) return toast.error(this.reason('blacklistEnterprise'))
      this.confirm = { visible: true, title: on ? '加入黑名单' : '移出黑名单', message: on ? '确认拉黑该企业？拉黑后不再向学生推荐。' : '确认移出黑名单？恢复为合作中。', type: on ? 'danger' : 'primary', confirmText: on ? '确认拉黑' : '确认移出', requireReason: on, reasonLabel: '拉黑原因', action: on ? 'BLACKLIST_ON' : 'BLACKLIST_OFF', extra: null }
    },
    async onConfirm({ reason } = {}) {
      const { action, extra } = this.confirm
      this.submitting = true
      try {
        let res
        if (action === 'DELETE_CONTACT') res = await internshipApi.deleteEnterpriseContact(this.detail.id, extra)
        else if (action === 'REVIEW_APPROVE') res = await internshipApi.reviewEnterprise(this.detail.id, { action: 'APPROVE', comment: reason || '' })
        else if (action === 'REVIEW_REJECT') res = await internshipApi.reviewEnterprise(this.detail.id, { action: 'REJECT', comment: reason || '' })
        else if (action.startsWith('COOP_')) res = await internshipApi.setEnterpriseCooperation(this.detail.id, { action: action.slice(5), reason: reason || '' })
        else if (action === 'BLACKLIST_ON') res = await internshipApi.setEnterpriseBlacklist(this.detail.id, { on: true, reason: reason || '' })
        else if (action === 'BLACKLIST_OFF') res = await internshipApi.setEnterpriseBlacklist(this.detail.id, { on: false })
        if (res && res.code === 0) { toast.success('已更新并写入留痕'); this.confirm.visible = false; this.load() }
        else if (res) toast.error(res.message)
      } finally { this.submitting = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';

.ed-head { display: flex; align-items: center; gap: var(--space-2); margin-bottom: var(--space-3); flex-wrap: wrap; }
.ed-head__spacer { flex: 1; }
.ed-bl { font-size: 12px; color: var(--danger, #dc2626); }
.ed-state { padding: var(--space-4, 16px); color: var(--t3, #64748b); font-size: 13px; }
.ed-state.is-err { color: var(--danger-600, #dc2626); }
.ed-cell-wrap { max-width: 260px; white-space: normal; word-break: break-all; }
.ed-ops { display: flex; gap: 4px; flex-wrap: wrap; }
.ed-muted { color: var(--text-disabled, #94a3b8); }
.ed-tabs { display: flex; gap: var(--space-1); border-bottom: 1px solid var(--line, #e2e8f0); margin-bottom: var(--space-3); }
.ed-tabs__item { padding: 8px 14px; border: none; background: none; cursor: pointer; font-size: 13px; color: var(--t2, #475569); border-bottom: 2px solid transparent; }
.ed-tabs__item.is-active { color: var(--pri, #2563eb); border-bottom-color: var(--pri, #2563eb); font-weight: 600; }
.ed-danger { color: var(--danger, #dc2626); }
.ed-tbl { width: 100%; border-collapse: collapse; font-size: 13px; }
.ed-tbl th, .ed-tbl td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--line, #eef1f6); }
.ed-tbl th { color: var(--t3, #64748b); font-weight: 500; font-size: 12px; }
.mp-btn { padding: 7px 14px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; background: #fff; cursor: pointer; font-size: 13px; }
.mp-btn--primary { background: var(--pri, #2563eb); color: #fff; border-color: var(--pri, #2563eb); }
.mp-btn--danger { color: var(--danger, #dc2626); border-color: var(--danger, #dc2626); }
.mp-btn--sm { padding: 4px 10px; font-size: 12px; }
.mp-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.ie-fld { display: flex; flex-direction: column; gap: 4px; margin-bottom: var(--space-4); }
.ie-chk { flex-direction: row; align-items: center; gap: 6px; font-size: 13px; }
.ie-actions { display: flex; justify-content: flex-end; gap: var(--space-2); }
</style>
