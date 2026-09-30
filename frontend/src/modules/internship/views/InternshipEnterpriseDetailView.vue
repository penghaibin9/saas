<template>
  <ModulePageShell
    class="enterprise-detail"
    :title="detail ? detail.name : '企业详情'"
    :subtitle="detail ? (detail.creditCode || '无信用代码') + ' · ' + detail.sourceLabel : '加载中'"
  >
    <template #actions>
      <AppButton variant="ghost" @click="goBack">{{ backLocation ? '返回上一页' : '返回企业库' }}</AppButton>
      <AppButton v-if="detail && !loading && !error && can('editEnterprise') && detail.coopStatus !== 'ARCHIVED'" variant="primary" @click="$router.push({ path: `/admin/internship/enterprises/${detail.id}/edit`, query: $route.query })">编辑资料</AppButton>
    </template>

    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <template v-else-if="detail">
      <div class="ed-head">
        <AppStatusTag :type="detail.coopStatusTone" dot>{{ detail.coopStatusLabel }}</AppStatusTag>
        <span v-if="detail.blacklist" class="ed-bl">黑名单 · {{ detail.blacklistReason }}</span>
        <AppStatusTag :type="detail.qualificationStatus === 'PASSED' ? 'success' : (detail.qualificationStatus === 'FAILED' ? 'danger' : 'default')">{{ detail.qualificationLabel }}</AppStatusTag>
        <div class="ed-head__spacer" />
        <RouterLink v-if="tab !== 'coop'" :to="sectionLink('coop')" class="mp-link">{{ detail.coopStatus === 'PENDING' ? '办理资质审核' : '查看合作与资质' }}</RouterLink>
      </div>

      <nav class="ed-tabs" aria-label="企业详情分区">
        <RouterLink v-for="t in tabs" :key="t.key" :to="sectionLink(t.key)" class="ed-tabs__item" :class="{ 'is-active': tab === t.key }" :aria-current="tab === t.key ? 'page' : undefined">{{ t.label }}</RouterLink>
      </nav>

      <div v-if="tab === 'coop'" class="ed-head">
        <AppPermissionButton v-if="detail.coopStatus === 'PENDING'" code="reviewEnterprise" variant="primary" :allowed="can('reviewEnterprise')" :reason="reason('reviewEnterprise')" @click="askReview('APPROVE')">审核通过</AppPermissionButton>
        <AppPermissionButton v-if="detail.coopStatus === 'PENDING'" code="reviewEnterprise" variant="danger" :allowed="can('reviewEnterprise')" :reason="reason('reviewEnterprise')" @click="askReview('REJECT')">审核驳回</AppPermissionButton>
        <AppButton v-else-if="detail.coopStatus === 'ACTIVE' && canManageCooperation" variant="secondary" @click="askCoop('SUSPEND')">暂停合作</AppButton>
        <AppButton v-else-if="detail.coopStatus === 'SUSPENDED' && canManageCooperation" variant="secondary" @click="askCoop('RESUME')">恢复合作</AppButton>
        <AppPermissionButton v-if="!detail.blacklist && detail.coopStatus !== 'ARCHIVED'" code="blacklistEnterprise" variant="danger" :allowed="can('blacklistEnterprise')" :reason="reason('blacklistEnterprise')" @click="askBlacklist(true)">拉黑</AppPermissionButton>
        <AppPermissionButton v-if="detail.blacklist" code="blacklistEnterprise" variant="secondary" :allowed="can('blacklistEnterprise')" :reason="reason('blacklistEnterprise')" @click="askBlacklist(false)">移出黑名单</AppPermissionButton>
      </div>

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
          <RouterLink class="mp-btn mp-btn--primary mp-btn--sm" :to="{ path: '/admin/internship/positions', query: { batchId: $route.query.batchId, companyId: detail.id } }">当前批次岗位库</RouterLink>
        </div>
        <div class="mp-card__body">
          <LoadingState v-if="positionsLoading" />
          <ErrorState v-else-if="positionsError" :description="positionsError" @retry="loadPositions" />
          <EmptyState v-else-if="!positions.length" title="该企业暂无岗位" description="到岗位库为该企业新增实习岗位" />
          <table v-else class="ed-tbl">
            <thead><tr><th>岗位</th><th>专业要求</th><th>容量</th><th>状态</th><th>操作</th></tr></thead>
            <tbody>
              <tr v-for="p in positions" :key="p.id">
                <td>{{ p.title }}</td><td>{{ p.majorRequirement || '不限' }}</td>
                <td>{{ p.allocatedCount }}/{{ p.headcount }}</td>
                <td><AppStatusTag :type="p.statusTone">{{ p.statusLabel }}</AppStatusTag></td>
                <td><RouterLink class="mp-link" :to="{ path: '/admin/internship/positions/' + p.id, query: { batchId: p.batchId || $route.query.batchId, companyId: detail.id, returnTo: $route.fullPath } }">详情</RouterLink></td>
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
          <LoadingState v-if="inspectionsLoading" />
          <div v-else-if="inspectionsError" class="ed-state is-err">{{ inspectionsError }}
            <button type="button" class="mp-link" @click="loadInspections">重试</button>
          </div>
          <p v-else-if="!inspections.length" class="ed-state">
            暂无考察记录。请根据本批次要求登记并提交考察，审核通过后更新企业准入有效期。
          </p>
          <table v-else class="ed-tbl">
            <thead><tr><th>考察记录</th><th>结论</th><th>准入有效期至</th><th>状态</th><th>操作</th></tr></thead>
            <tbody>
              <tr v-for="x in inspections" :key="x.id">
                <td><RouterLink class="mp-link" :to="inspectionLink(x.id)">{{ x.inspectionTypeLabel || x.inspectionType }}</RouterLink><small class="ed-subline">{{ dateTime(x.inspectionDate) }} · {{ x.inspectors || '未登记人员' }}</small></td>
                <td class="ed-cell-wrap">{{ x.conclusion || '—' }}</td>
                <td>{{ dateTime(x.validUntil, '未设置到期日') }}</td>
                <td><AppStatusTag :type="inspectionTone(x.status)">{{ recordStatusLabel(x.status, x.statusLabel) }}</AppStatusTag><small v-if="x.reviewedByName" class="ed-subline">{{ x.reviewedByName }}</small></td>
                <td class="ed-ops">
                  <RouterLink class="mp-link" :to="inspectionLink(x.id)">{{ x.status === 'DRAFT' && canInspect ? '编辑' : '详情' }}</RouterLink>
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
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <AppInlineAlert v-if="inspectionRequested && !inspectionsLoading && !inspectionsError && !inspectionForm" type="warning" title="无法打开这条考察" description="记录不属于当前企业，或你没有登记权限。请从本企业考察列表重新选择。" />
      <EnterpriseInspectionForm v-if="inspectionForm" :key="`${detail.id}:${$route.query.inspectionId}`"
        :company-id="String(detail.id)" :company-name="detail.name" :batch-id="String($route.query.batchId || '')"
        :record="inspectionForm.record" :can-manage="canInspect" @close="closeInspectionForm" @saved="inspectionSaved" />

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
      :type="inspectionDialog.danger ? 'danger' : 'primary'"
      :confirm-text="inspectionDialog.confirmText"
      :require-reason="inspectionDialog.requireReason"
      :reason-label="inspectionDialog.reasonLabel"
      :submitting="inspectionActing"
      @update:visible="inspectionDialog = null"
      @cancel="inspectionDialog = null"
      @confirm="onInspectionConfirm"
    >
      <AppFormItem v-if="inspectionDialog.mode === 'approve'" v-slot="{ id }" label="准入有效期至" hint="按审核结论确认；留空使用登记时的有效期">
        <AppTextInput :id="id" v-model="inspectionValidUntil" type="datetime-local" :disabled="inspectionActing" />
      </AppFormItem>
      <AppFormItem v-if="inspectionDialog.mode === 'approve'" v-slot="{ id }" label="审核意见（选填）">
        <AppTextInput :id="id" v-model="inspectionReviewComment" :disabled="inspectionActing" />
      </AppFormItem>
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
import { formatDateTime } from '@/utils/dateUtils'
import EnterpriseInspectionForm from './components/EnterpriseInspectionForm.vue'

const EMPTY_CFORM = () => ({ contactType: 'CONTACT', name: '', title: '', phone: '', email: '', isPrimary: false })
const CONTACT_TYPE_OPTIONS = [{ label: '联系人', value: 'CONTACT' }, { label: '企业导师', value: 'MENTOR' }]

export default {
  name: 'InternshipEnterpriseDetailView',
  components: {
    ModulePageShell, AppStatusTag, LoadingState, ErrorState, EmptyState, AppDrawer, AppButton, AppConfirmDialog,
    AppPermissionButton, AppAuditTrail, AppInlineAlert, AppDescriptionList, AppForm, AppFormItem, AppTextInput, AppSelect,
    ConflictNotice, EnterpriseInspectionForm
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', submitting: false, detail: null, loadSequence: 0,
      tabs: [
        { key: 'basic', label: '主档' },
        { key: 'contacts', label: '联系人与导师' },
        { key: 'coop', label: '合作与资质' },
        { key: 'positions', label: '企业岗位' },
        { key: 'inspections', label: '考察与准入' },
        { key: 'audit', label: '审计记录' }
      ],
      positions: [], positionsLoading: false, positionsError: '',
      // 企业考察：后端 create/submit/review 一直都在（含并发保护与跨租户守卫），
      // 但此前前端没有任何入口，等于建好的准入链路没人能用。
      inspections: [], inspectionsLoaded: false, inspectionsLoading: false, inspectionsError: '',
      inspectionActing: false, conflict: emptyConflict(),
      inspectionDialog: null, inspectionValidUntil: '', inspectionReviewComment: '',
      contactDrawer: false, editingContact: null, cform: EMPTY_CFORM(), cformError: '',
      confirm: { visible: false, title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false, reasonLabel: '原因', action: null, extra: null }
    }
  },
  computed: {
    tab() { return this.tabs.some((item) => item.key === this.$route.query.section) ? this.$route.query.section : 'basic' },
    listQuery() {
      const { section: _section, inspectionId: _inspectionId, returnTo: _returnTo, ...query } = this.$route.query
      return query
    },
    backLocation() {
      const ref = this.$route.query.returnTo
      if (typeof ref !== 'string' || !/^\/admin\/internship\/(?:students|positions)(?:\/\d+)?(?:\?|$)/.test(ref)) return ''
      const batchId = this.detail?.batchId || this.$route.query.batchId
      const refBatchId = new URL(ref, 'https://local.invalid').searchParams.get('batchId')
      return !batchId || !refBatchId || refBatchId === String(batchId) ? ref : ''
    },
    canManageCooperation() { return canCode(this.ctx, 'internship.enterprise.manage') },
    perms() { return this.ctx.permissionActions || {} },
    /** 企业考察用的是后端权限码（require_permission 同一套），
     *  与本页其它按钮走的 permissionActions 动作名不是一个体系，不能混用。 */
    canInspect() { return canCode(this.ctx, 'internship.enterprise.inspection.manage') },
    inspectionRequested() { return this.tab === 'inspections' && !!this.$route.query.inspectionId },
    inspectionForm() {
      if (!this.inspectionRequested || !this.detail || this.loading) return null
      if (this.$route.query.inspectionId === 'new') return this.canInspect ? { record: null } : null
      const record = this.inspections.find((row) => String(row.id) === String(this.$route.query.inspectionId))
      return record ? { record } : null
    },
    contacts() { return this.detail?.contacts || [] },
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
        { label: '企业准入有效期至', value: formatDateTime(d.accessValidUntil, '未设置到期日') },
        { label: '合作级别', value: d.cooperationLevel },
        { label: '累计实习生', value: String(d.internCount) },
        { label: '审核人', value: d.reviewBy },
        { label: '审核时间', value: formatDateTime(d.reviewAt) },
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
  mounted() { this.focusHeading() },
  beforeUnmount() { this.loadSequence++ },
  watch: {
    '$route.params.id'() {
      this.contactDrawer = false; this.editingContact = null; this.cform = EMPTY_CFORM(); this.cformError = ''
      this.inspectionDialog = null; this.conflict = emptyConflict(); this.confirm.visible = false
      this.load()
      this.focusHeading()
    },
    tab(next) {
      // 考察记录按企业查，切到该页签时才拉，避免每次进详情都多打一个接口
      if (next === 'inspections' && this.detail && !this.inspectionsLoaded && !this.inspectionsLoading) this.loadInspections()
    }
  },
  methods: {
    goBack() {
      if (this.backLocation) return this.$router.push(this.backLocation)
      this.$router.push({ path: '/admin/internship/enterprises', query: this.listQuery })
    },
    focusHeading() {
      this.$nextTick(() => {
        const heading = this.$el?.querySelector('h1')
        if (!heading) return
        heading.setAttribute('tabindex', '-1')
        heading.style.scrollMarginTop = '170px'
        heading.focus({ preventScroll: true })
        heading.scrollIntoView({ block: 'start', behavior: 'instant' })
      })
    },
    dateTime: formatDateTime,
    inspectionTone(status) { return ({ DRAFT: 'default', SUBMITTED: 'warning', APPROVED: 'success', REJECTED: 'danger', EXPIRED: 'warning' })[status] || 'default' },
    inspectionLink(inspectionId) { return { path: this.$route.path, query: { ...this.$route.query, section: 'inspections', inspectionId } } },
    closeInspectionForm() {
      const { inspectionId: _inspectionId, ...query } = this.$route.query
      this.$router.replace({ path: this.$route.path, query })
    },
    async inspectionSaved() { this.closeInspectionForm(); await this.loadInspections(); toast.success('考察草稿已保存，可继续提交审核') },
    sectionLink(section) {
      const { inspectionId, ...query } = this.$route.query
      return { path: this.$route.path, query: { ...query, section, ...(section === 'inspections' && inspectionId ? { inspectionId } : {}) } }
    },
    recordStatusLabel(status, providedLabel = '') { return providedLabel || (status ? '状态待确认' : '—') },
    can(key) { const p = this.perms[key]; return !!(p && p.allowed) },
    async loadInspections() {
      const sequence = this.loadSequence
      const id = this.$route.params.id
      this.inspectionsLoading = true
      this.inspectionsError = ''
      const res = await complianceApi.listInspections(id)
      if (sequence !== this.loadSequence || id !== this.$route.params.id) return
      this.inspectionsLoading = false
      this.inspectionsLoaded = res.code === 0
      if (res.code !== 0) { this.inspectionsError = res.message || '考察记录加载失败'; return }
      this.inspections = Array.isArray(res.data) ? res.data : (res.data && res.data.list) || []
    },
    openInspectionCreate() {
      if (!this.canInspect || this.loading || !this.detail) return
      this.$router.push(this.inspectionLink('new'))
    },
    openInspectionAction(row, action) {
      if (!this.canInspect || this.loading || !this.detail) return
      this.conflict = emptyConflict()
      const map = {
        submit: { title: '提交考察审核', message: '提交后进入审核环节，草稿不可再改。',
                  confirmText: '提交', requireReason: false, reasonLabel: '', danger: false },
        approve: { title: '通过企业考察', message: '审核通过后更新企业准入有效期；岗位发布仍须满足本批次的其他条件。未设置到期日不会自动推导为永久准入。',
                   confirmText: '通过', requireReason: false, reasonLabel: '审核意见（选填）', danger: false },
        reject: { title: '驳回企业考察', message: '驳回后企业准入不会更新，请写明原因。',
                  confirmText: '驳回', requireReason: true, reasonLabel: '驳回原因（≥5字）', danger: true }
      }[action]
      this.inspectionValidUntil = formatDateTime(row.validUntil, '').replace(' ', 'T')
      this.inspectionReviewComment = ''
      this.inspectionDialog = { mode: action, id: row.id, expectedVersion: row.version, ...map }
    },
    async onInspectionConfirm({ reason }) {
      const d = this.inspectionDialog
      if (!d || this.inspectionActing || !this.canInspect || this.loading || !this.detail) return
      const sequence = this.loadSequence
      this.inspectionActing = true
      let res
      try {
        if (d.mode === 'submit') {
          res = await complianceApi.submitInspection(d.id, { expectedVersion: d.expectedVersion })
        } else {
          res = await complianceApi.reviewInspection(d.id, d.mode, {
            expectedVersion: d.expectedVersion, comment: d.mode === 'approve' ? this.inspectionReviewComment : reason || '',
            validUntil: d.mode === 'approve' && this.inspectionValidUntil ? new Date(this.inspectionValidUntil).toISOString() : null
          })
        }
      } catch (error) {
        res = { code: -1, message: error.message || '考察办理失败，请重试' }
      } finally {
        this.inspectionActing = false
      }
      if (sequence !== this.loadSequence) return
      if (isConflict(res)) {
        // 两个管理员同时审同一条考察时，后端条件更新让输家拿 409。
        // 弹窗不关、填的意见不动，把最新状态摆出来让他自己决定。
        const conflict = await captureConflict({
          res,
          kept: d.mode === 'approve' ? this.inspectionReviewComment : reason || '',
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
        if (sequence === this.loadSequence) this.conflict = conflict
        return
      }
      if (!res || res.code !== 0) return toast.error((res && res.message) || '操作失败')
      this.inspectionDialog = null
      this.conflict = emptyConflict()
      toast.success('操作成功，已写审计')
      await this.load()
    },
    reason(key) { const p = this.perms[key]; return p && !p.allowed ? p.reason : '' },
    async load() {
      const sequence = ++this.loadSequence
      const id = this.$route.params.id
      this.loading = true; this.error = ''; this.detail = null
      this.positions = []; this.positionsError = ''; this.positionsLoading = false
      this.inspections = []; this.inspectionsLoaded = false; this.inspectionsLoading = false; this.inspectionsError = ''
      const res = await internshipApi.getEnterpriseDetail(id)
      if (sequence !== this.loadSequence || id !== this.$route.params.id) return
      if (res.code === 0) this.detail = res.data
      else this.error = res.message || '企业详情加载失败'
      this.loading = false
      if (res.code === 0) {
        await Promise.all([this.loadPositions(), this.tab === 'inspections' ? this.loadInspections() : Promise.resolve()])
      }
    },
    async loadPositions() {
      const sequence = this.loadSequence
      const id = this.$route.params.id
      this.positionsLoading = true; this.positionsError = ''
      const res = await positionApi.getPositions({ companyId: id, page: 1, pageSize: 50 })
      if (sequence !== this.loadSequence || id !== this.$route.params.id) return
      this.positionsLoading = false
      if (res.code === 0) this.positions = res.data.list || []
      else this.positionsError = res.message || '企业岗位加载失败'
    },
    openContact(c) {
      if (!this.can('manageEnterpriseContact')) return toast.error(this.reason('manageEnterpriseContact'))
      this.editingContact = c
      this.cform = c ? { contactType: c.contactType, name: c.name, title: c.title, phone: '', email: c.email, isPrimary: c.isPrimary } : EMPTY_CFORM()
      this.cformError = ''
      this.contactDrawer = true
    },
    async submitContact() {
      if (this.submitting || this.loading || !this.detail || !this.can('manageEnterpriseContact')) return
      const sequence = this.loadSequence
      if (!this.cform.name) { this.cformError = '姓名必填'; return }
      this.submitting = true
      try {
        const res = this.editingContact
          ? await internshipApi.updateEnterpriseContact(this.detail.id, this.editingContact.id, { ...this.cform, expectedVersion: this.editingContact.version })
          : await internshipApi.addEnterpriseContact(this.detail.id, this.cform)
        if (sequence !== this.loadSequence) return
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
      if (!this.canManageCooperation) return toast.error('当前角色没有企业合作维护权限')
      const m = { SUSPEND: { t: '暂停合作', c: '确认暂停', type: 'warning' }, RESUME: { t: '恢复合作', c: '确认恢复', type: 'primary' } }[action]
      this.confirm = { visible: true, title: m.t, message: `确认执行「${m.t}」？`, type: m.type, confirmText: m.c, requireReason: false, action: 'COOP_' + action, extra: null }
    },
    askBlacklist(on) {
      if (!this.can('blacklistEnterprise')) return toast.error(this.reason('blacklistEnterprise'))
      this.confirm = { visible: true, title: on ? '加入黑名单' : '移出黑名单', message: on ? '确认拉黑该企业？拉黑后不再向学生推荐。' : '确认移出黑名单？系统将恢复拉黑前状态，缺少历史状态时回到待审核。', type: on ? 'danger' : 'primary', confirmText: on ? '确认拉黑' : '确认移出', requireReason: on, reasonLabel: '拉黑原因', action: on ? 'BLACKLIST_ON' : 'BLACKLIST_OFF', extra: null }
    },
    async onConfirm({ reason } = {}) {
      const { action, extra } = this.confirm
      if (!action || !this.confirm.visible || this.submitting || this.loading || !this.detail) return
      const permission = action === 'DELETE_CONTACT' ? this.can('manageEnterpriseContact')
        : action.startsWith('REVIEW_') ? this.can('reviewEnterprise')
          : action.startsWith('COOP_') ? this.canManageCooperation : this.can('blacklistEnterprise')
      if (!permission) return
      const sequence = this.loadSequence
      this.submitting = true
      try {
        let res
        if (action === 'DELETE_CONTACT') res = await internshipApi.deleteEnterpriseContact(this.detail.id, extra)
        else if (action === 'REVIEW_APPROVE') res = await internshipApi.reviewEnterprise(this.detail.id, { action: 'APPROVE', comment: reason || '', expectedVersion: this.detail.version })
        else if (action === 'REVIEW_REJECT') res = await internshipApi.reviewEnterprise(this.detail.id, { action: 'REJECT', comment: reason || '', expectedVersion: this.detail.version })
        else if (action.startsWith('COOP_')) res = await internshipApi.setEnterpriseCooperation(this.detail.id, { action: action.slice(5), reason: reason || '', expectedVersion: this.detail.version })
        else if (action === 'BLACKLIST_ON') res = await internshipApi.setEnterpriseBlacklist(this.detail.id, { on: true, reason: reason || '', expectedVersion: this.detail.version })
        else if (action === 'BLACKLIST_OFF') res = await internshipApi.setEnterpriseBlacklist(this.detail.id, { on: false, expectedVersion: this.detail.version })
        if (sequence !== this.loadSequence) return
        if (res && res.code === 0) { toast.success('已更新并写入留痕'); this.confirm.visible = false; this.load() }
        else if (res) toast.error(res.message)
      } finally { this.submitting = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';

.enterprise-detail { gap: 12px; }
.ed-head { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
.ed-head__spacer { flex: 1; }
.ed-bl { font-size: 12px; color: var(--danger, #dc2626); }
.ed-state { padding: var(--space-4, 16px); color: var(--t3, #64748b); font-size: 13px; }
.ed-state.is-err { color: var(--danger-600, #dc2626); }
.ed-cell-wrap { max-width: 260px; white-space: normal; overflow-wrap: anywhere; }
.ed-subline { display: block; margin-top: 5px; color: var(--text-secondary); font-size: 12px; }
.ed-ops { display: flex; gap: 4px; flex-wrap: wrap; }
.ed-muted { color: var(--text-disabled, #94a3b8); }
.ed-tabs { display: flex; gap: var(--space-1); border-bottom: 1px solid var(--line, #e2e8f0); overflow-x: auto; }
.ed-tabs__item { padding: 10px 14px; text-decoration: none; white-space: nowrap; border: none; background: none; cursor: pointer; font-size: 13px; color: var(--t2, #475569); border-bottom: 2px solid transparent; }
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
