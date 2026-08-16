<template>
  <ModulePageShell
    :title="detail.campaignName || '招聘季详情'"
    :subtitle="pageSubtitle"
    :role-name="roleName"
    :data-scope-name="dataScopeName"
    watermark-purpose="招聘季企业管理"
  >
    <template #actions>
      <AppButton variant="ghost" @click="goBack">← 返回招聘季列表</AppButton>
    </template>

    <ErrorState v-if="error" :description="error" @retry="init" />
    <LoadingState v-else-if="loading" />
    <div v-else class="mp-stack">
      <!-- 招聘季概览 -->
      <section class="mp-card">
        <div class="mp-card__head">
          <span class="mp-card__title">招聘季信息</span>
          <AppStatusTag :type="statusTagType[detail.status] || 'default'" dot>
            {{ statusLabel(detail.status) }}
          </AppStatusTag>
        </div>
        <div class="mp-card__body">
          <dl class="rc-facts">
            <div><dt>编码</dt><dd>{{ detail.campaignCode || '—' }}</dd></div>
            <div><dt>轮次</dt><dd>第 {{ detail.roundNo || 1 }} 轮</dd></div>
            <div><dt>当前阶段</dt><dd>{{ phaseLabel(detail.phase) }}</dd></div>
            <div><dt>企业邀请窗</dt><dd>{{ range(detail.inviteStartAt, detail.inviteEndAt) }}</dd></div>
            <div><dt>岗位报送窗</dt><dd>{{ range(detail.positionSubmitStartAt, detail.positionSubmitEndAt) }}</dd></div>
            <div><dt>学生选岗窗</dt><dd>{{ range(detail.studentSelectStartAt, detail.studentSelectEndAt) }}</dd></div>
            <div><dt>企业决策窗</dt><dd>{{ range(detail.enterpriseDecisionStartAt, detail.enterpriseDecisionEndAt) }}</dd></div>
            <div><dt>学校确认窗</dt><dd>{{ range(detail.schoolConfirmStartAt, detail.schoolConfirmEndAt) }}</dd></div>
            <div><dt>企业访问截止</dt><dd>{{ dateShort(detail.enterpriseAccessEndAt) || '—' }}</dd></div>
          </dl>
        </div>
      </section>

      <AppInlineAlert
        v-if="!canInvite"
        type="warning"
        title="当前不可邀请企业"
        :description="inviteBlockedReason"
      />

      <!-- 企业参与情况 -->
      <section class="mp-card">
        <div class="mp-card__head">
          <span class="mp-card__title">参与企业</span>
          <span class="rc-aside">企业账号只能由此邀请产生，系统不提供企业自注册</span>
        </div>
        <div class="mp-card__body">
          <ModuleToolbar
            :actions="enterpriseToolbarActions"
            :hint="`本页 ${enterpriseRows.length} 家企业 · 邀请后需企业联系人凭邀请链接激活账号`"
            @action="onEnterpriseToolbar"
          />

          <AdvancedFilter v-model="epFilters" :fields="epFilterFields" @search="searchEnterprises" @reset="resetEnterpriseFilters" />

          <LoadingState v-if="epLoading" />
          <ErrorState v-else-if="epError" :description="epError" @retry="loadEnterprises" />
          <EmptyState
            v-else-if="!enterpriseRows.length"
            title="尚未邀请企业"
            description="点击「邀请企业」从企业库中选择合作企业并生成邀请链接"
          />
          <DataTable
            v-else
            :columns="epColumns"
            :rows="enterpriseRows"
            row-key="id"
            :pagination="epPagination"
            :show-total="false"
            @page-change="turnEnterprisePage"
          >
            <template #cell-status="{ row }">
              <AppStatusTag :type="participationTagType[row.status] || 'default'" dot>
                {{ participationLabel(row.status) }}
              </AppStatusTag>
            </template>
            <template #cell-inviteSource="{ row }">
              <span>{{ inviteSourceLabel[row.inviteSource] || row.inviteSource || '—' }}</span>
            </template>
            <template #cell-invitedAt="{ row }">
              <span>{{ dateShort(row.invitedAt) || '—' }}</span>
            </template>
            <template #cell-acceptedAt="{ row }">
              <span>{{ dateShort(row.acceptedAt) || '—' }}</span>
            </template>
            <template #cell-actions="{ row }">
              <TableActionColumn :actions="enterpriseRowActions(row)" @action="(key) => onEnterpriseRowAction(key, row)" />
            </template>
          </DataTable>
        </div>
      </section>

      <!-- 邀请企业 -->
      <AppDrawer
        :visible="inviteVisible"
        title="邀请企业加入招聘季"
        mode="modal"
        size="medium"
        @update:visible="inviteVisible = $event"
      >
        <AppInlineAlert
          type="info"
          title="邀请会为企业联系人开通一个企业协同账号"
          description="提交后生成一次性邀请链接（仅本次显示，系统只保存哈希）。请由学校侧转交企业联系人，对方用手机号校验并自行设置密码后账号才生效。"
        />
        <AppForm ref="inviteForm" :model="inviteModel" :rules="inviteRules" layout="horizontal" label-width="120px">
          <AppFormItem
            label="选择企业"
            prop="companyId"
            required
            hint="置灰企业需先在「企业列表」处理合作状态或资质审核；后端会再次校验准入"
          >
            <AppSelect v-model="inviteModel.companyId" :options="companyOptions" placeholder="选择要邀请的合作企业" />
          </AppFormItem>
          <AppFormItem label="邀请来源" prop="inviteSource">
            <AppSelect v-model="inviteModel.inviteSource" :options="inviteSourceOptions" />
          </AppFormItem>
          <AppFormItem label="联系人姓名" prop="realName" required>
            <AppTextInput v-model="inviteModel.realName" placeholder="企业侧对接人真实姓名" />
          </AppFormItem>
          <AppFormItem label="登录账号" prop="loginName" required hint="企业方登录名，学校内唯一，建议用其手机号或企业简称+工号">
            <AppTextInput v-model="inviteModel.loginName" placeholder="如 hx_hr01" />
          </AppFormItem>
          <AppFormItem label="联系人手机号" prop="phone" required hint="激活时须填写同一手机号校验，请务必核实">
            <AppTextInput v-model="inviteModel.phone" placeholder="11 位手机号" />
          </AppFormItem>
          <AppFormItem label="企业内角色" prop="memberRole">
            <AppSelect v-model="inviteModel.memberRole" :options="memberRoleOptions" />
          </AppFormItem>
        </AppForm>
        <template #footer>
          <AppButton variant="ghost" @click="closeInvite">取消</AppButton>
          <AppButton variant="primary" :loading="inviteSubmitting" @click="submitInvite">生成邀请</AppButton>
        </template>
      </AppDrawer>

      <!-- 邀请结果：一次性链接 -->
      <AppDrawer
        :visible="inviteResultVisible"
        title="邀请已生成"
        mode="modal"
        size="medium"
        @update:visible="inviteResultVisible = $event"
      >
        <AppInlineAlert
          type="warning"
          title="邀请链接仅本次显示，关闭后无法再次查看"
          description="系统只保存该链接的哈希值，无法找回。若丢失，请撤销本次邀请后重新邀请。"
        />
        <div class="rc-invite-result">
          <div class="rc-invite-result__row">
            <span class="rc-invite-result__label">企业激活地址</span>
            <AppCopyableText :text="inviteResult.acceptUrl" />
          </div>
          <div class="rc-invite-result__row">
            <span class="rc-invite-result__label">邀请令牌</span>
            <AppCopyableText :text="inviteResult.inviteToken" />
          </div>
          <div class="rc-invite-result__row">
            <span class="rc-invite-result__label">学校编码</span>
            <AppCopyableText :text="inviteResult.tenantCode" />
          </div>
          <div class="rc-invite-result__row">
            <span class="rc-invite-result__label">邀请有效期至</span>
            <span>{{ dateShort(inviteResult.expiresAt) || '—' }}</span>
          </div>
        </div>
        <template #footer>
          <AppButton variant="primary" @click="inviteResultVisible = false">我已转交，关闭</AppButton>
        </template>
      </AppDrawer>

      <!-- 撤销企业参与资格 -->
      <AppConfirmDialog
        v-model:visible="revokeVisible"
        title="撤销企业参与资格"
        :message="revokeMessage"
        type="danger"
        confirm-text="确认撤销"
        require-reason
        reason-label="撤销原因（≥2 字，将写入审计）"
        @confirm="onRevokeConfirm"
      />
    </div>
  </ModulePageShell>
</template>

<script>
/**
 * /admin/internship/recruitment-campaigns/:id 招聘季详情与参与企业管理。
 *
 * 这是学校侧「邀请企业 / 审核企业参与状态 / 撤销资格」的唯一正式入口，
 * 对应后端 /internship/recruitment-campaigns/{id}/enterprises*。
 * 邀请返回的一次性 token 只在本次响应内展示，不做任何本地持久化（后端只存哈希）。
 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, EmptyState, LoadingState, ErrorState } from '@/components/business'
import {
  AppConfirmDialog, AppStatusTag, AppInlineAlert, AppCopyableText,
  AppForm, AppFormItem, AppTextInput, AppSelect
} from '@/components/common'
import { AppButton, AppDrawer } from '@/components/ui'
import { TableActionColumn } from '@/modules/internship/components'
import { recruitmentCampaignApi } from '@/modules/internship/api/recruitment-campaign.api'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { positionApi } from '@/modules/internship/api/position.api'
import {
  CAMPAIGN_STATUS_TAG, CAMPAIGN_PHASE_LABEL, PARTICIPATION_STATUS_OPTIONS, PARTICIPATION_STATUS_TAG,
  INVITE_SOURCE_LABEL, MEMBER_ROLE_OPTIONS,
  campaignStatusLabel, participationStatusLabel
} from '@/modules/internship/constants/recruitmentCampaign.constants'
import { ENTERPRISE_LOGIN_URL } from '@/config/portalConfig'
import { currentUserFromToken } from '@/services/http/client'
import { toast } from '@/utils/toast'
import { formatDate } from '@/utils/dateUtils'

const EMPTY_INVITE = () => ({
  companyId: '',
  inviteSource: 'MANUAL',
  realName: '',
  loginName: '',
  phone: '',
  memberRole: 'COMPANY_ADMIN'
})

export default {
  name: 'RecruitmentCampaignDetailView',
  components: {
    ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, EmptyState, LoadingState, ErrorState,
    AppConfirmDialog, AppStatusTag, AppInlineAlert, AppCopyableText,
    AppForm, AppFormItem, AppTextInput, AppSelect, AppButton, AppDrawer,
    TableActionColumn
  },
  data() {
    return {
      ctx: null,
      loading: true,
      error: '',
      detail: {},
      enterpriseRows: [],
      epLoading: false,
      epError: '',
      epPage: 1,
      epPageSize: 10,
      epHasMore: false,
      epFilters: { status: '' },
      companyOptions: [],
      inviteVisible: false,
      inviteSubmitting: false,
      inviteModel: EMPTY_INVITE(),
      inviteResultVisible: false,
      inviteResult: {},
      revokeVisible: false,
      revokeRow: null,
      statusTagType: CAMPAIGN_STATUS_TAG,
      participationTagType: PARTICIPATION_STATUS_TAG,
      inviteSourceLabel: INVITE_SOURCE_LABEL,
      memberRoleOptions: MEMBER_ROLE_OPTIONS,
      inviteSourceOptions: [
        { value: 'MANUAL', label: '学校手动邀请' },
        { value: 'REUSE', label: '沿用往期合作' },
        { value: 'PUBLIC_REQUEST', label: '企业主动申请' }
      ]
    }
  },
  computed: {
    campaignId() {
      return this.$route.params.id
    },
    /** 学校编码：企业激活时必填，取自当前登录令牌（JWT tid） */
    tenantCode() {
      return currentUserFromToken()?.tenantCode || ''
    },
    roleName() {
      return this.ctx?.currentRole?.roleName || ''
    },
    dataScopeName() {
      return this.ctx?.dataScope?.name || ''
    },
    pageSubtitle() {
      return '管理本招聘季的参与企业：邀请、查看接受情况、撤销资格'
    },
    /** 后端邀请前置条件：招聘季 OPEN + 处于邀请窗 + 已配置企业访问截止时间 */
    canInvite() {
      if (this.detail.status !== 'OPEN') return false
      if (!this.detail.enterpriseAccessEndAt) return false
      const now = Date.now()
      const start = this.detail.inviteStartAt ? new Date(this.detail.inviteStartAt).getTime() : null
      const end = this.detail.inviteEndAt ? new Date(this.detail.inviteEndAt).getTime() : null
      if (start === null || end === null) return false
      if (new Date(this.detail.enterpriseAccessEndAt).getTime() <= now) return false
      return now >= start && now <= end
    },
    inviteBlockedReason() {
      if (this.detail.status === 'DRAFT') return '招聘季仍是草稿，请先在列表页「开启」后才能邀请企业。'
      if (['FROZEN', 'CLOSED', 'ARCHIVED'].includes(this.detail.status)) {
        return `招聘季已${campaignStatusLabel(this.detail.status)}，不再接受新的企业邀请。`
      }
      if (!this.detail.inviteStartAt || !this.detail.inviteEndAt) return '本招聘季未配置企业邀请时间窗，后端会拒绝邀请。'
      if (!this.detail.enterpriseAccessEndAt) return '本招聘季未配置企业访问截止时间，后端会拒绝邀请。'
      const now = Date.now()
      if (new Date(this.detail.enterpriseAccessEndAt).getTime() <= now) return '企业访问期已结束，无法再邀请企业。'
      if (now < new Date(this.detail.inviteStartAt).getTime()) return '尚未进入企业邀请窗，请等待邀请窗开始。'
      return '企业邀请窗已结束，无法再邀请企业。'
    },
    enterpriseToolbarActions() {
      return [
        {
          key: 'invite',
          label: '邀请企业',
          disabled: !this.canInvite,
          disabledReason: this.inviteBlockedReason
        }
      ]
    },
    epFilterFields() {
      return [{ key: 'status', label: '参与状态', type: 'select', options: PARTICIPATION_STATUS_OPTIONS }]
    },
    /** 参与企业同为游标分页（只返回 hasMore），估值仅驱动翻页，不展示总数 */
    epPagination() {
      const known = (this.epPage - 1) * this.epPageSize + this.enterpriseRows.length
      return {
        page: this.epPage,
        pageSize: this.epPageSize,
        total: this.epHasMore ? known + 1 : known
      }
    },
    epColumns() {
      return [
        { key: 'companyName', title: '企业名称' },
        { key: 'status', title: '参与状态' },
        { key: 'inviteSource', title: '邀请来源' },
        { key: 'invitedAt', title: '邀请时间' },
        { key: 'acceptedAt', title: '接受时间' },
        { key: 'revokeReason', title: '撤销原因' },
        { key: 'actions', title: '操作' }
      ]
    },
    inviteRules() {
      return {
        companyId: [{ required: true, message: '请选择要邀请的企业' }],
        realName: [{ required: true, message: '请填写企业联系人姓名' }],
        loginName: [{ required: true, message: '请填写企业方登录账号' }],
        phone: [
          { required: true, message: '请填写联系人手机号' },
          { pattern: /^1[3-9]\d{9}$/, message: '请填写 11 位有效手机号' }
        ]
      }
    },
    revokeMessage() {
      const r = this.revokeRow
      if (!r) return ''
      return `撤销「${r.companyName}」在本招聘季的参与资格后，其企业账号将无法继续访问本招聘季数据。此操作会写入审计且需重新邀请才能恢复。`
    }
  },
  async created() {
    await this.init()
  },
  methods: {
    statusLabel: campaignStatusLabel,
    participationLabel: participationStatusLabel,
    phaseLabel(phase) {
      return CAMPAIGN_PHASE_LABEL[phase] || phase || '—'
    },
    dateShort(v) {
      return formatDate(v, '')
    },
    range(start, end) {
      if (!start && !end) return '未配置'
      return `${this.dateShort(start) || '—'} ~ ${this.dateShort(end) || '—'}`
    },
    goBack() {
      this.$router.push('/admin/internship/recruitment-campaigns')
    },
    async init() {
      this.loading = true
      this.error = ''
      try {
        const ctx = await internshipApi.getContext()
        if (ctx.code === 0) this.ctx = ctx.data
        const res = await recruitmentCampaignApi.getCampaignDetail(this.campaignId)
        if (res.code === 0) {
          this.detail = res.data || {}
        } else {
          this.error = res.message
          return
        }
      } catch (e) {
        this.error = e.message || '加载失败'
        return
      } finally {
        this.loading = false
      }
      await this.loadEnterprises()
    },
    async loadEnterprises() {
      this.epLoading = true
      this.epError = ''
      try {
        const params = { page: this.epPage, pageSize: this.epPageSize }
        if (this.epFilters.status) params.status = this.epFilters.status
        const res = await recruitmentCampaignApi.getCampaignEnterprises(this.campaignId, params)
        if (res.code === 0) {
          this.enterpriseRows = res.data.list
          this.epHasMore = res.data.hasMore
        } else this.epError = res.message
      } catch (e) {
        this.epError = e.message || '加载失败'
      } finally {
        this.epLoading = false
      }
    },
    searchEnterprises() {
      this.epPage = 1
      this.loadEnterprises()
    },
    resetEnterpriseFilters() {
      this.epFilters = { status: '' }
      this.epPage = 1
      this.loadEnterprises()
    },
    turnEnterprisePage(p) {
      this.epPage = p
      this.loadEnterprises()
    },
    async onEnterpriseToolbar(key) {
      if (key !== 'invite' || !this.canInvite) return
      this.inviteModel = EMPTY_INVITE()
      if (!this.companyOptions.length) await this.loadCompanyOptions()
      this.inviteVisible = true
    },
    /**
     * 企业下拉：不可邀请的企业不隐藏，而是置灰并在名称后标明原因，
     * 让老师知道「这家企业存在但需要先处理什么」，而不是莫名找不到。
     * 判定口径与后端 _get_company(require_admission=True) 一致。
     */
    async loadCompanyOptions() {
      const res = await positionApi.getEnterpriseOptions('', 200)
      if (res.code !== 0) {
        toast.error(res.message || '企业列表加载失败')
        return
      }
      this.companyOptions = (res.data || []).map((c) => {
        const blocked = this.admissionBlockReason(c)
        return {
          value: String(c.id),
          label: blocked ? `${c.name}（${blocked}）` : c.name,
          disabled: !!blocked
        }
      })
    },
    /** 返回阻断原因；可邀请时返回空串 */
    admissionBlockReason(c) {
      if (c.blacklist || c.coopStatus === 'BLACKLIST') return '黑名单企业'
      if (c.coopStatus !== 'ACTIVE') return `合作状态：${c.coopStatusLabel || c.coopStatus || '未知'}`
      if (c.qualificationStatus !== 'PASSED') return `资质：${c.qualificationLabel || c.qualificationStatus || '未核验'}`
      return ''
    },
    closeInvite() {
      this.inviteVisible = false
    },
    async submitInvite() {
      const form = this.$refs.inviteForm
      if (form && typeof form.validate === 'function') {
        const valid = await form.validate()
        if (!valid) return
      }
      this.inviteSubmitting = true
      try {
        const m = this.inviteModel
        const res = await recruitmentCampaignApi.inviteEnterprise(this.campaignId, {
          companyId: String(m.companyId),
          inviteSource: m.inviteSource,
          loginName: m.loginName.trim(),
          realName: m.realName.trim(),
          phone: m.phone.trim(),
          memberRole: m.memberRole
        })
        if (res.code === 0) {
          const token = res.data?.inviteToken || ''
          const tenantCode = this.tenantCode
          this.inviteResult = {
            inviteToken: token,
            tenantCode,
            expiresAt: res.data?.expiresAt || '',
            acceptUrl: this.buildAcceptUrl(token, tenantCode)
          }
          this.inviteVisible = false
          this.inviteResultVisible = true
          this.epPage = 1
          await this.loadEnterprises()
        } else {
          toast.error(res.message || '邀请失败')
        }
      } finally {
        this.inviteSubmitting = false
      }
    },
    /**
     * 企业激活地址：指向企业协同端 /invite/accept（见 enterprise-portal/src/router/index.js），
     * base 复用门户统一配置的企业登录地址，去掉尾部 /login 得到应用根。
     * 带上 tenantCode 可让企业少填一项，激活时后端仍会用手机号二次校验。
     */
    buildAcceptUrl(token, tenantCode) {
      if (!token) return ''
      const root = String(ENTERPRISE_LOGIN_URL || '').replace(/\/login\/?$/, '') || '/enterprise'
      const origin = /^https?:\/\//i.test(root) ? '' : window.location.origin
      const q = `token=${encodeURIComponent(token)}${tenantCode ? `&tenantCode=${encodeURIComponent(tenantCode)}` : ''}`
      return `${origin}${root}/invite/accept?${q}`
    },
    enterpriseRowActions(row) {
      return [
        {
          key: 'revoke',
          label: '撤销资格',
          danger: true,
          disabled: !['INVITED', 'ACCEPTED', 'SUSPENDED'].includes(row.status),
          disabledReason: '仅待接受、已入驻或已暂停的企业可撤销'
        }
      ]
    },
    onEnterpriseRowAction(key, row) {
      if (key === 'revoke') {
        this.revokeRow = row
        this.revokeVisible = true
      }
    },
    async onRevokeConfirm(payload) {
      const row = this.revokeRow
      if (!row) return
      const reason = (payload && payload.reason) || ''
      const res = await recruitmentCampaignApi.revokeEnterprise(this.campaignId, row.companyId, {
        expectedVersion: row.version,
        reason
      })
      if (res.code === 0) {
        toast.success('企业参与资格已撤销')
        this.revokeVisible = false
        await this.loadEnterprises()
      } else {
        toast.error(res.message || '撤销失败')
      }
    }
  }
}
</script>

<style scoped>
.rc-facts {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px 24px;
  margin: 0;
}
.rc-facts > div {
  display: flex;
  gap: 10px;
  align-items: baseline;
}
.rc-facts dt {
  flex: 0 0 96px;
  color: var(--t3, #6b7280);
  font-size: 13px;
}
.rc-facts dd {
  margin: 0;
  font-size: 13px;
}
.rc-aside {
  font-size: 12px;
  color: var(--t3, #6b7280);
}
.rc-invite-result {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-top: 16px;
}
.rc-invite-result__row {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.rc-invite-result__label {
  font-size: 12px;
  color: var(--t3, #6b7280);
}
</style>
