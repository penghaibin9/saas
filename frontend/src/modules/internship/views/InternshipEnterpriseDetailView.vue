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
        <AppPermissionButton v-if="detail.coopStatus === 'PENDING'" code="reviewEnterprise" variant="primary" :allowed="can('reviewEnterprise')" :reason="reason('reviewEnterprise')" @click="askReview">审核</AppPermissionButton>
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
      <section v-show="tab === 'audit'" class="mp-card">
        <div class="mp-card__body">
          <AppAuditTrail :records="auditRecords" :show-ip="false" />
        </div>
      </section>
    </template>

    <!-- 联系人 新增/编辑 -->
    <AppDrawer v-model:visible="contactDrawer" :title="editingContact ? '编辑联系人' : '新增联系人 / 企业导师'">
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
import { toast } from '@/utils/toast'

const EMPTY_CFORM = () => ({ contactType: 'CONTACT', name: '', title: '', phone: '', email: '', isPrimary: false })
const CONTACT_TYPE_OPTIONS = [{ label: '联系人', value: 'CONTACT' }, { label: '企业导师', value: 'MENTOR' }]

export default {
  name: 'InternshipEnterpriseDetailView',
  components: {
    ModulePageShell, AppStatusTag, LoadingState, ErrorState, EmptyState, AppDrawer, AppButton, AppConfirmDialog,
    AppPermissionButton, AppAuditTrail, AppInlineAlert, AppDescriptionList, AppForm, AppFormItem, AppTextInput, AppSelect
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
        { key: 'audit', label: '审计记录' }
      ],
      positions: [], positionsLoaded: false,
      contactDrawer: false, editingContact: null, cform: EMPTY_CFORM(), cformError: '',
      confirm: { visible: false, title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false, reasonLabel: '原因', action: null, extra: null }
    }
  },
  computed: {
    perms() { return this.ctx.permissionActions || {} },
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
  methods: {
    can(key) { const p = this.perms[key]; return !!(p && p.allowed) },
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
    askReview() {
      if (!this.can('reviewEnterprise')) return toast.error(this.reason('reviewEnterprise'))
      this.confirm = { visible: true, title: '企业资质审核', message: '确认该企业资质核验通过？通过→合作中。', type: 'primary', confirmText: '通过（资质合格）', requireReason: false, reasonLabel: '审核意见', action: 'REVIEW_APPROVE', extra: null }
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
