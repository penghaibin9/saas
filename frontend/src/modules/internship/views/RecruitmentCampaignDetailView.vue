<template>
  <ModulePageShell
    :title="detail.campaignName || '招聘季详情'"
    subtitle="按本轮时间安排邀请企业，跟进参与情况"
    watermark-purpose="招聘季企业管理"
  >
    <template #actions>
      <AppButton v-if="!loading && !error && detail.status === 'DRAFT' && allowed('internship.recruitment.manage', 'internship.enterprise.manage')" variant="primary" @click="editSettings">编辑草稿</AppButton>
      <AppButton variant="ghost" @click="goBack">返回招聘与邀请</AppButton>
    </template>

    <ErrorState v-if="error" :description="error" @retry="init" />
    <LoadingState v-else-if="loading" />
    <div v-else class="mp-stack">
      <div class="rc-context"><AppStatusTag :type="statusTagType[detail.status] || 'default'" dot>{{ statusLabel(detail.status) }}</AppStatusTag><span>{{ detail.campaignCode }} · 第 {{ detail.roundNo }} 轮</span><RouterLink :to="{ path: '/admin/internship/batches/' + detail.batchId, query: { batchId: detail.batchId } }">所属批次 {{ detail.batchId }}</RouterLink><span>{{ phaseLabel(detail.phase) }}</span></div>
      <nav class="rc-tabs" aria-label="招聘季详情分区"><RouterLink v-for="item in tabs" :key="item.key" :to="sectionLink(item.key)" :class="{ active: section === item.key }" :aria-current="section === item.key ? 'page' : undefined">{{ item.label }}</RouterLink></nav>
      <!-- 招聘季概览 -->
      <section v-if="section === 'schedule'" class="mp-card">
        <div class="mp-card__head">
          <h2 class="mp-card__title">时间安排</h2>
          <AppStatusTag :type="statusTagType[detail.status] || 'default'" dot>
            {{ statusLabel(detail.status) }}
          </AppStatusTag>
        </div>
        <div class="mp-card__body">
          <dl class="rc-facts">
            <div><dt>企业邀请窗</dt><dd>{{ range(detail.inviteStartAt, detail.inviteEndAt) }}</dd></div>
            <div><dt>岗位报送窗</dt><dd>{{ range(detail.positionSubmitStartAt, detail.positionSubmitEndAt) }}</dd></div>
            <div><dt>学生选岗窗</dt><dd>{{ range(detail.studentSelectStartAt, detail.studentSelectEndAt) }}</dd></div>
            <div><dt>企业决策窗</dt><dd>{{ range(detail.enterpriseDecisionStartAt, detail.enterpriseDecisionEndAt) }}</dd></div>
            <div><dt>学校确认窗</dt><dd>{{ range(detail.schoolConfirmStartAt, detail.schoolConfirmEndAt) }}</dd></div>
            <div><dt>企业访问截止</dt><dd>{{ dateShort(detail.enterpriseAccessEndAt) || '—' }}</dd></div>
            <div><dt>备注</dt><dd>{{ detail.remark || '未填写' }}</dd></div>
          </dl>
        </div>
      </section>

      <section v-if="section === 'rules'" class="mp-card">
        <div class="mp-card__head"><h2 class="mp-card__title">投递与确认规则</h2></div>
        <div class="mp-card__body"><dl class="rc-facts">
          <div><dt>个人资料</dt><dd>{{ materialPolicy.profileRequired ? '投递前须建立个人资料' : '未要求先建立资料' }}</dd></div>
          <div><dt>必填资料内容</dt><dd>{{ policyLabels(materialPolicy.requiredSections, materialSections) }}</dd></div>
          <div><dt>必备材料类型</dt><dd>{{ policyLabels(materialPolicy.requiredItemTypes, materialTypes) }}</dd></div>
          <div><dt>岗位申请说明</dt><dd>{{ materialPolicy.applicationStatementRequired ? '必填' : '未单独设为必填' }} · 最少 {{ materialPolicy.minStatementLength || 0 }} 字</dd></div>
          <div><dt>简历 PDF</dt><dd>{{ materialPolicy.resumePdfEnabled ? '允许生成' : '不允许生成' }}</dd></div>
          <div><dt>可选联系方式共享方式</dt><dd>{{ policyLabels(materialPolicy.allowedContactSharingModes, contactModes, '未开放，学生无法正式投递') }}</dd></div>
          <div><dt>企业录用意向</dt><dd>{{ detail.enterpriseConfirmRequired ? '学校确认前必须具备' : '未设为学校确认的必要条件' }}</dd></div>
          <div><dt>教师确认时限</dt><dd>{{ detail.teacherConfirmSlaHours ?? 48 }} 小时（录用意向锁定后）</dd></div>
        </dl><template v-if="legacyPolicy"><p class="rc-aside">本轮另含旧版材料规则，以下为原配置；以服务端核验结果为准。</p><pre class="rc-legacy-policy">{{ JSON.stringify(detail.applicationMaterialPolicy, null, 2) }}</pre></template></div>
      </section>

      <AppInlineAlert
        v-if="section === 'enterprises' && !canInvite"
        type="warning"
        title="当前不可邀请企业"
        :description="inviteBlockedReason"
      />

      <!-- 企业参与情况 -->
      <section v-if="section === 'enterprises'" class="rc-enterprises">
        <div>
          <ModuleToolbar
            :actions="enterpriseToolbarActions"
            hint="跟进企业接受情况；生成邀请后，将本次邀请链接交给企业联系人。"
            @action="onEnterpriseToolbar"
          />

          <form class="rc-participation-filter" @submit.prevent="searchEnterprises"><label>参与状态<select v-model="epFilters.status"><option value="">全部状态</option><option v-for="option in participationOptions" :key="option.value" :value="option.value">{{ option.label }}</option></select></label><AppButton type="submit" variant="primary" size="sm">查询</AppButton><AppButton variant="ghost" size="sm" @click="resetEnterpriseFilters">重置</AppButton><span>{{ epLoading ? '正在读取…' : epError ? '参与情况暂不可用' : `本页 ${enterpriseRows.length} 家企业` }}</span></form>

          <LoadingState v-if="epLoading" />
          <ErrorState v-else-if="epError" :description="epError" @retry="loadEnterprises" />
          <EmptyState
            v-else-if="!enterpriseRows.length"
            :title="epPage > 1 ? '本页没有企业' : $route.query.epStatus ? '没有符合条件的企业' : '尚未邀请企业'"
            :description="epPage > 1 ? '参与记录可能已调整，请返回上一页查看。' : $route.query.epStatus ? '可以调整参与状态筛选。' : '学校邀请后，企业在此显示接受进度。'"
          />
          <AppButton v-if="!epLoading && !epError && !enterpriseRows.length && epPage > 1" variant="ghost" @click="turnEnterprisePage(epPage - 1)">返回上一页</AppButton>
          <DataTable
            v-if="!epLoading && !epError && enterpriseRows.length"
            class="rc-enterprise-table"
            :columns="epColumns"
            :rows="enterpriseRows"
            row-key="id"
            :pagination="epPagination"
            :show-total="false"
            @page-change="turnEnterprisePage"
          >
            <template #cell-companyName="{ row }"><strong>{{ row.companyName }}</strong><div class="rc-aside">{{ inviteSourceLabel[row.inviteSource] || row.inviteSource || '—' }}</div></template>
            <template #cell-status="{ row }">
              <AppStatusTag :type="participationTagType[row.status] || 'default'" dot>
                {{ participationLabel(row.status) }}
              </AppStatusTag>
              <p v-if="row.revokeReason" class="rc-reason">{{ row.revokeReason }}</p>
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

      <section v-if="section === 'lifecycle'" class="mp-card"><div class="mp-card__head"><h2 class="mp-card__title">状态办理</h2></div><div class="mp-card__body rc-lifecycle"><p>{{ lifecycleHint }}</p><div class="rc-actions"><AppButton v-for="action in lifecycleActions" :key="action.key" :variant="action.key === 'open' ? 'primary' : 'ghost'" @click="askTransition(action.key)">{{ action.label }}</AppButton><AppButton variant="ghost" @click="init">重新核对</AppButton></div><p class="rc-aside">冻结后不能重新开启；关闭后仅保留历史查询，关闭后可以归档。</p></div></section>

      <!-- 邀请企业 -->
      <AppDrawer
        :visible="inviteVisible"
        title="邀请企业加入招聘季"
        mode="modal"
        size="medium"
        @update:visible="!$event && closeInvite()"
      >
        <AppInlineAlert
          type="info"
          title="邀请联系人参加本轮招募"
          description="新联系人首次激活账号；本企业已有有效成员使用原账号登录接受邀请，保留原角色和密码。链接仅本次显示。"
        />
        <p v-if="inviteError" role="alert" class="rc-error">{{ inviteError }}</p>
        <div class="rc-company-search"><label for="campaign-company-search">搜索企业</label><div class="rc-search-controls"><AppTextInput id="campaign-company-search" v-model="companyKeyword" :disabled="inviteSubmitting" placeholder="输入企业名称缩小选择范围" /><AppButton variant="ghost" :disabled="inviteSubmitting" @click="loadCompanyOptions">搜索</AppButton></div><p v-if="companyOptions.length >= 200" class="rc-aside">当前展示前 200 家，请按名称缩小范围。</p></div>
        <AppForm ref="inviteForm" class="rc-invite-form" :model="inviteModel" :rules="inviteRules" layout="vertical">
          <AppFormItem
            v-slot="{ id }"
            label="选择企业"
            prop="companyId"
            required
          >
            <AppSelect :id="id" v-model="inviteModel.companyId" :disabled="inviteSubmitting" :options="companyOptions" placeholder="选择要邀请的合作企业" />
          </AppFormItem>
          <AppFormItem v-slot="{ id }" label="邀请来源" prop="inviteSource">
            <AppSelect :id="id" v-model="inviteModel.inviteSource" :disabled="inviteSubmitting" :options="inviteSourceOptions" />
          </AppFormItem>
          <AppFormItem v-slot="{ id }" label="联系人姓名" prop="realName" required>
            <AppTextInput :id="id" v-model="inviteModel.realName" :disabled="inviteSubmitting" placeholder="企业侧对接人真实姓名" />
          </AppFormItem>
          <AppFormItem v-slot="{ id }" label="登录账号" prop="loginName" required hint="使用学校内唯一的企业登录名">
            <AppTextInput :id="id" v-model="inviteModel.loginName" :disabled="inviteSubmitting" placeholder="如 hx_hr01" />
          </AppFormItem>
          <AppFormItem v-slot="{ id }" label="联系人手机号" prop="phone" required hint="用于激活验证，请核实">
            <AppTextInput :id="id" v-model="inviteModel.phone" :disabled="inviteSubmitting" placeholder="11 位手机号" />
          </AppFormItem>
          <AppFormItem v-slot="{ id }" label="企业内角色" prop="memberRole">
            <AppSelect :id="id" v-model="inviteModel.memberRole" :disabled="inviteSubmitting" :options="memberRoleOptions" />
          </AppFormItem>
        </AppForm>
        <template #footer>
          <AppButton variant="ghost" :disabled="inviteSubmitting" @click="closeInvite">取消</AppButton>
          <AppButton variant="primary" :disabled="!canInvite" :loading="inviteSubmitting" @click="submitInvite">生成邀请</AppButton>
        </template>
      </AppDrawer>

      <!-- 邀请结果：一次性链接 -->
      <AppDrawer
        :visible="inviteResultVisible"
        title="邀请已生成"
        mode="modal"
        size="medium"
        @update:visible="!$event && closeInviteResult()"
      >
        <AppInlineAlert
          type="warning"
          title="邀请链接仅本次显示，关闭后无法再次查看"
          description="请在关闭前复制并妥善转交。同一联系人新链接生成后，之前未使用的邀请链接失效。不要通过撤销参与资格补发链接；撤销会终止本轮参与。"
        />
        <div class="rc-invite-result">
          <p class="rc-aside">{{ inviteResult.inviteMode === 'EXISTING_MEMBER' ? '已生成新轮邀请。请由该联系人使用原企业账号登录接受，原有角色与密码保持不变。' : '请由该联系人核对受邀手机号并完成首次账号激活。' }}</p>
          <p v-if="inviteResult.memberRole" class="rc-aside">成员身份：{{ memberRoleOptions.find(item => item.value === inviteResult.memberRole)?.label || inviteResult.memberRole }}</p>
          <div class="rc-invite-result__row">
            <span class="rc-invite-result__label">企业接受邀请地址</span>
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
          <AppButton variant="primary" @click="closeInviteResult">关闭邀请结果</AppButton>
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
        :submitting="revokeSubmitting"
        :confirm-disabled="!!revokeError"
        @confirm="onRevokeConfirm"
      ><p v-if="revokeError" class="rc-error" role="alert">{{ revokeError }}。请关闭弹窗，重新核对后再办理。</p></AppConfirmDialog>
      <AppConfirmDialog v-model:visible="transition.visible" :title="transition.title" :message="transition.message" :confirm-text="transition.title" :submitting="transitionSubmitting" :confirm-disabled="!!transitionError" @confirm="confirmTransition"><p v-if="transitionError" class="rc-error" role="alert">{{ transitionError }}。请重新核对招聘季后再办理。</p></AppConfirmDialog>
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
import { ModulePageShell, ModuleToolbar, DataTable, EmptyState, LoadingState, ErrorState } from '@/components/business'
import {
  AppConfirmDialog, AppStatusTag, AppInlineAlert, AppCopyableText,
  AppForm, AppFormItem, AppTextInput, AppSelect
} from '@/components/common'
import { AppButton, AppDrawer } from '@/components/ui'
import { TableActionColumn } from '@/modules/internship/components'
import { recruitmentCampaignApi } from '@/modules/internship/api/recruitment-campaign.api'
import { canCode } from '@/modules/internship/composables/permission'
import { positionApi } from '@/modules/internship/api/position.api'
import {
  CAMPAIGN_STATUS_TAG, CAMPAIGN_PHASE_LABEL, PARTICIPATION_STATUS_OPTIONS, PARTICIPATION_STATUS_TAG,
  INVITE_SOURCE_LABEL, MEMBER_ROLE_OPTIONS,
  campaignStatusLabel, participationStatusLabel, canTransition
} from '@/modules/internship/constants/recruitmentCampaign.constants'
import { ENTERPRISE_LOGIN_URL } from '@/config/portalConfig'
import { currentUserFromToken } from '@/services/http/client'
import { defaultMaterialPolicy, unsupportedMaterialPolicy, localCampaignTime, MATERIAL_SECTIONS, MATERIAL_TYPES, CONTACT_MODES } from '@/modules/internship/utils/campaignForm'
import { toast } from '@/utils/toast'

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
  props: { ctx: { type: Object, required: true } },
  components: {
    ModulePageShell, ModuleToolbar, DataTable, EmptyState, LoadingState, ErrorState,
    AppConfirmDialog, AppStatusTag, AppInlineAlert, AppCopyableText,
    AppForm, AppFormItem, AppTextInput, AppSelect, AppButton, AppDrawer,
    TableActionColumn
  },
  data() {
    return {
      loadSequence: 0,
      enterpriseSequence: 0,
      optionSequence: 0,
      companyKeyword: '',
      now: Date.now(),
      clockId: null,
      inviteSequence: 0,
      materialSections: MATERIAL_SECTIONS, materialTypes: MATERIAL_TYPES, contactModes: CONTACT_MODES,
      tabs: [{ key: 'enterprises', label: '参与企业' }, { key: 'schedule', label: '时间安排' }, { key: 'rules', label: '投递与确认' }, { key: 'lifecycle', label: '状态办理' }],
      inviteError: '',
      revokeError: '',
      revokeSubmitting: false,
      transition: { visible: false },
      transitionSubmitting: false,
      transitionError: '',
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
    contextKey() { return JSON.stringify([this.$route.params.id, this.$route.query.batchId || '', this.ctx?.ctxKey || '', this.ctx?.permissionPatterns || []]) },
    participationOptions() { return PARTICIPATION_STATUS_OPTIONS },
    enterpriseQueryKey() { return JSON.stringify([this.$route.query.epStatus || '', this.$route.query.epPage || '1']) },
    materialPolicy() { return { ...defaultMaterialPolicy(), ...this.detail.applicationMaterialPolicy } },
    legacyPolicy() { return unsupportedMaterialPolicy(this.detail.applicationMaterialPolicy || {}) },
    section() { return this.tabs.some((item) => item.key === this.$route.query.section) ? this.$route.query.section : 'enterprises' },
    listQuery() { const query = { ...this.$route.query }; delete query.section; delete query.epStatus; delete query.epPage; return query },
    canInvitePermission() { return this.allowed('internship.recruitment.invite', 'internship.enterprise.manage') },
    lifecycleActions() {
      return [['open', '开启招聘季', 'manage', 'OPEN'], ['freeze', '冻结招聘季', 'manage', 'FROZEN'], ['close', '关闭招聘季', 'close', 'CLOSED'], ['archive', '归档招聘季', 'close', 'ARCHIVED']]
        .filter(([, , permission, target]) => this.allowed('internship.recruitment.' + permission, 'internship.enterprise.manage') && canTransition(this.detail.status, target))
        .map(([key, label]) => ({ key, label }))
    },
    lifecycleHint() { return { DRAFT: '当前为草稿。请核对时间安排，开启后才能在邀请窗内邀请企业。', OPEN: '本轮已开启，各方按照对应时间窗办理。', FROZEN: '本轮已冻结，暂停企业操作；冻结后只能关闭，不能重新开启。', CLOSED: '本轮已关闭，企业参与与招聘资料保留查询。', ARCHIVED: '本轮已归档，保留历史资料。' }[this.detail.status] || '请先核对当前招聘季状态。' },
    campaignId() {
      return this.$route.params.id
    },
    /** 学校编码：企业激活时必填，取自当前登录令牌（JWT tid） */
    tenantCode() {
      return currentUserFromToken()?.tenantCode || ''
    },
    /** 后端邀请前置条件：招聘季 OPEN + 处于邀请窗 + 已配置企业访问截止时间 */
    canInvite() {
      if (!this.canInvitePermission || this.loading || this.error) return false
      if (this.detail.status !== 'OPEN') return false
      if (!this.detail.enterpriseAccessEndAt) return false
      const now = this.now
      const start = this.detail.inviteStartAt ? new Date(this.detail.inviteStartAt).getTime() : null
      const end = this.detail.inviteEndAt ? new Date(this.detail.inviteEndAt).getTime() : null
      if (start === null || end === null) return false
      if (new Date(this.detail.enterpriseAccessEndAt).getTime() <= now) return false
      return now >= start && now <= end
    },
    inviteBlockedReason() {
      if (!this.canInvitePermission) return '当前身份可查看参与情况；邀请和撤销由有权限的负责人办理。'
      if (this.detail.status === 'DRAFT') return '招聘季仍是草稿，请先核对时间安排，再到「状态办理」开启招聘季。'
      if (['FROZEN', 'CLOSED', 'ARCHIVED'].includes(this.detail.status)) {
        return `招聘季已${campaignStatusLabel(this.detail.status)}，不再接受新的企业邀请。`
      }
      if (!this.detail.inviteStartAt || !this.detail.inviteEndAt) return '尚未配置企业邀请时间，请先核对时间安排。'
      if (!this.detail.enterpriseAccessEndAt) return '尚未配置企业访问截止时间，请先核对时间安排。'
      const now = this.now
      if (new Date(this.detail.enterpriseAccessEndAt).getTime() <= now) return '企业访问期已结束，无法再邀请企业。'
      if (now < new Date(this.detail.inviteStartAt).getTime()) return '尚未进入企业邀请窗，请等待邀请窗开始。'
      return '企业邀请窗已结束，无法再邀请企业。'
    },
    enterpriseToolbarActions() {
      if (!this.canInvitePermission) return []
      return [
        {
          key: 'invite',
          label: '邀请企业',
          variant: 'primary',
          disabled: !this.canInvite,
          disabledReason: this.inviteBlockedReason
        }
      ]
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
        { key: 'companyName', title: '企业名称', width: '30%' },
        { key: 'status', title: '参与状态' },
        { key: 'invitedAt', title: '邀请时间' },
        { key: 'acceptedAt', title: '接受时间' },
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
      return `撤销「${r.companyName}」后，该企业不能继续参与本轮招聘。撤销是本轮终态，不能通过重新邀请恢复，请填写原因。`
    }
  },
  created() { this.clockId = setInterval(() => { this.now = Date.now() }, 30000); this.init() },
  mounted() { this.focusHeading() },
  watch: {
    contextKey() { this.init(); this.focusHeading() },
    enterpriseQueryKey() { this.restoreEnterpriseQuery(); this.loadEnterprises() }
  },
  beforeUnmount() { clearInterval(this.clockId); this.loadSequence++; this.enterpriseSequence++; this.optionSequence++; this.inviteSequence++; this.inviteResult = {} },
  methods: {
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
    allowed(...codes) { return Array.isArray(this.ctx?.permissionPatterns) && codes.some((code) => canCode(this.ctx, code)) },
    sectionLink(section) { return { path: this.$route.path, query: { ...this.$route.query, section } } },
    restoreEnterpriseQuery() { this.epFilters = { status: this.$route.query.epStatus || '' }; this.epPage = Math.max(1, Number(this.$route.query.epPage) || 1) },
    writeEnterpriseQuery() {
      if (JSON.stringify([this.epFilters.status || '', String(this.epPage)]) === this.enterpriseQueryKey) return this.loadEnterprises()
      return this.$router.replace({ path: this.$route.path, query: { ...this.$route.query, epStatus: this.epFilters.status || undefined, epPage: this.epPage > 1 ? String(this.epPage) : undefined } })
    },
    statusLabel: campaignStatusLabel,
    participationLabel: participationStatusLabel,
    phaseLabel(phase) {
      return CAMPAIGN_PHASE_LABEL[phase] || phase || '—'
    },
    dateShort(v) {
      return localCampaignTime(v).replace('T', ' ')
    },
    range(start, end) {
      if (!start && !end) return '未配置'
      return `${this.dateShort(start) || '—'} ~ ${this.dateShort(end) || '—'}`
    },
    policyLabels(values, options, empty = '未设置') { return !Array.isArray(values) ? '原规则格式需核对' : values.map((value) => options.find((option) => option.value === value)?.label || value).join('、') || empty },
    editSettings() {
      return this.$router.push({ path: '/admin/internship/recruitment-campaigns/' + this.detail.id + '/edit', query: { ...this.$route.query, batchId: this.detail.batchId } })
    },
    goBack() {
      this.$router.push({ path: '/admin/internship/recruitment-campaigns', query: this.listQuery })
    },
    async init() {
      const sequence = ++this.loadSequence, id = this.campaignId
      this.enterpriseSequence++; this.optionSequence++; this.inviteSequence++
      this.inviteVisible = false; this.inviteSubmitting = false; this.inviteResultVisible = false; this.inviteResult = {}
      this.revokeVisible = false; this.revokeSubmitting = false; this.transition = { visible: false }; this.transitionSubmitting = false
      this.detail = {}; this.enterpriseRows = []; this.companyOptions = []; this.inviteModel = EMPTY_INVITE(); this.companyKeyword = ''; this.epHasMore = false; this.epError = ''; this.restoreEnterpriseQuery()
      this.loading = true
      this.error = ''
      if (!this.allowed('internship.recruitment.view', 'internship.enterprise.view')) { this.loading = false; this.error = '当前身份没有查看招聘季的权限'; return }
      try {
        const res = await recruitmentCampaignApi.getCampaignDetail(id)
        if (sequence !== this.loadSequence || id !== this.campaignId) return
        if (res.code === 0) {
          if (this.$route.query.batchId && String(res.data?.batchId) !== String(this.$route.query.batchId)) {
            this.error = '该招聘季不属于当前批次，请返回列表重新选择。'
            return
          }
          this.detail = res.data || {}
        } else {
          this.error = res.message
          return
        }
      } catch (e) {
        if (sequence !== this.loadSequence) return
        this.error = e.message || '加载失败'
        return
      } finally {
        if (sequence === this.loadSequence) this.loading = false
      }
      await this.loadEnterprises()
    },
    async loadEnterprises() {
      if (this.loading || this.error || !this.detail.id) return
      const sequence = ++this.enterpriseSequence, id = this.campaignId
      this.epLoading = true
      this.epError = ''
      this.enterpriseRows = []; this.epHasMore = false
      try {
        const params = { page: this.epPage, pageSize: this.epPageSize }
        if (this.$route.query.epStatus) params.status = this.$route.query.epStatus
        const res = await recruitmentCampaignApi.getCampaignEnterprises(id, params)
        if (sequence !== this.enterpriseSequence || id !== this.campaignId) return
        if (res.code === 0) {
          this.enterpriseRows = res.data.list
          this.epHasMore = res.data.hasMore
        } else this.epError = res.message
      } catch (e) {
        if (sequence !== this.enterpriseSequence) return
        this.epError = e.message || '加载失败'
      } finally {
        if (sequence === this.enterpriseSequence) this.epLoading = false
      }
    },
    searchEnterprises() {
      this.epPage = 1
      this.writeEnterpriseQuery()
    },
    resetEnterpriseFilters() {
      this.epFilters = { status: '' }
      this.epPage = 1
      this.writeEnterpriseQuery()
    },
    turnEnterprisePage(p) {
      this.epFilters.status = this.$route.query.epStatus || ''
      this.epPage = p
      this.writeEnterpriseQuery()
    },
    async onEnterpriseToolbar(key) {
      this.now = Date.now()
      if (key !== 'invite' || !this.canInvite) return
      this.inviteSequence++
      this.inviteModel = EMPTY_INVITE()
      this.companyOptions = []; this.companyKeyword = ''
      this.inviteError = ''
      this.inviteVisible = true
      await this.loadCompanyOptions()
    },
    /**
     * 企业下拉：不可邀请的企业不隐藏，而是置灰并在名称后标明原因，
     * 让老师知道「这家企业存在但需要先处理什么」，而不是莫名找不到。
     * 判定口径与后端 _get_company(require_admission=True) 一致。
     */
    async loadCompanyOptions() {
      const sequence = ++this.optionSequence, id = this.campaignId
      try {
        const res = await positionApi.getEnterpriseOptions(this.companyKeyword.trim(), 200)
        if (sequence !== this.optionSequence || id !== this.campaignId) return
        if (res.code !== 0) throw new Error(res.message || '企业列表加载失败')
        this.companyOptions = (res.data || []).map((c) => {
        const blocked = this.admissionBlockReason(c)
        return {
          value: String(c.id),
          label: blocked ? `${c.name}（${blocked}）` : c.name,
          disabled: !!blocked
        }
        })
      } catch (e) { if (sequence === this.optionSequence) this.inviteError = e.message || '企业列表加载失败，请关闭后重试' }
    },
    /** 返回阻断原因；可邀请时返回空串 */
    admissionBlockReason(c) {
      if (c.status && c.status !== 'ACTIVE') return '企业已停用'
      if (c.blacklist || c.coopStatus === 'BLACKLIST') return '黑名单企业'
      if (c.coopStatus !== 'ACTIVE') return `合作状态：${c.coopStatusLabel || c.coopStatus || '未知'}`
      if (c.qualificationStatus !== 'PASSED') return `资质：${c.qualificationLabel || c.qualificationStatus || '未核验'}`
      if (c.accessValidUntil && new Date(c.accessValidUntil).getTime() < Date.now()) return '企业准入已过期'
      return ''
    },
    closeInvite() {
      if (this.inviteSubmitting) return
      this.inviteSequence++; this.optionSequence++
      this.inviteVisible = false
    },
    closeInviteResult() { this.inviteResultVisible = false; this.inviteResult = {} },
    async submitInvite() {
      this.now = Date.now()
      if (!this.canInvite || this.inviteSubmitting || !this.inviteVisible) return
      const sequence = this.inviteSequence, id = this.campaignId
      const m = { ...this.inviteModel }, tenantCode = this.tenantCode
      const form = this.$refs.inviteForm
      if (!form || typeof form.validate !== 'function') return
      this.inviteSubmitting = true
      this.inviteError = ''
      try {
        const result = await form.validate()
        if (!result?.valid || sequence !== this.inviteSequence || id !== this.campaignId || !this.canInvite || !this.inviteVisible) return
        const res = await recruitmentCampaignApi.inviteEnterprise(id, {
          companyId: String(m.companyId),
          inviteSource: m.inviteSource,
          loginName: m.loginName.trim(),
          realName: m.realName.trim(),
          phone: m.phone.trim(),
          memberRole: m.memberRole
        })
        if (sequence !== this.inviteSequence || id !== this.campaignId) return
        if (res.code === 0) {
          const token = res.data?.inviteToken || ''
          this.inviteResult = {
            inviteToken: token,
            inviteMode: res.data?.inviteMode || 'NEW_MEMBER',
            memberRole: res.data?.memberRole || '',
            tenantCode,
            expiresAt: res.data?.expiresAt || '',
            acceptUrl: this.buildAcceptUrl(token, tenantCode)
          }
          this.inviteVisible = false
          this.inviteResultVisible = true
          this.epPage = 1
          await this.writeEnterpriseQuery()
        } else {
          this.inviteError = res.message || '邀请失败'
        }
      } catch (e) {
        if (sequence === this.inviteSequence) this.inviteError = e.message || '邀请失败，请核对参与列表后再尝试'
      } finally {
        if (sequence === this.inviteSequence) this.inviteSubmitting = false
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
      if (!this.canInvitePermission || ['CLOSED', 'ARCHIVED'].includes(this.detail.status)) return []
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
      if (key === 'revoke' && this.enterpriseRowActions(row).some((action) => !action.disabled)) {
        this.revokeRow = { ...row, campaignId: this.campaignId, sequence: this.loadSequence }
        this.revokeError = ''
        this.revokeVisible = true
      }
    },
    async onRevokeConfirm(payload) {
      const row = this.revokeRow
      if (!row || !this.canInvitePermission || this.revokeSubmitting || this.revokeError || row.campaignId !== this.campaignId || row.sequence !== this.loadSequence) return
      const reason = (payload && payload.reason) || ''
      this.revokeSubmitting = true
      try {
      const res = await recruitmentCampaignApi.revokeEnterprise(row.campaignId, row.companyId, {
        expectedVersion: row.version,
        reason
      })
      if (row.sequence !== this.loadSequence || row.campaignId !== this.campaignId) return
      if (res.code === 0) {
        toast.success('企业参与资格已撤销')
        this.revokeVisible = false
        await this.loadEnterprises()
      } else {
        this.revokeError = res.message || '撤销失败'
      }
      } catch (e) { if (row.sequence === this.loadSequence) this.revokeError = e.message || '撤销失败' }
      finally { if (row.sequence === this.loadSequence) this.revokeSubmitting = false }
    },
    askTransition(key) {
      const action = this.lifecycleActions.find((item) => item.key === key)
      if (!action || this.loading || this.error) return
      const descriptions = { open: '开启后，各方按配置的时间窗办理；关键资料将不能再编辑。', freeze: '冻结后暂停企业操作，只能继续关闭，不能重新开启。', close: '关闭后本轮只读，不再接受新的招聘办理。', archive: '归档后保留历史资料，不能再变更。' }
      this.transition = { visible: true, key, title: action.label, message: `「${this.detail.campaignName}」：${descriptions[key]}`, id: this.campaignId, version: this.detail.version, sequence: this.loadSequence }
      this.transitionError = ''
    },
    async confirmTransition() {
      const action = { ...this.transition }
      if (!action.visible || this.transitionSubmitting || this.transitionError || action.id !== this.campaignId || action.sequence !== this.loadSequence || !this.lifecycleActions.some((item) => item.key === action.key)) return
      this.transitionSubmitting = true
      try {
        const result = await recruitmentCampaignApi.transitionCampaign(action.id, action.key, action.version)
        if (action.sequence !== this.loadSequence || action.id !== this.campaignId) return
        if (result.code !== 0) { this.transitionError = result.message || '状态办理失败'; return }
        toast.success(action.title + '成功'); this.transition.visible = false; await this.init()
      } catch (e) { if (action.sequence === this.loadSequence) this.transitionError = e.message || '状态办理失败' }
      finally { if (action.sequence === this.loadSequence) this.transitionSubmitting = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.mp-card__title { margin:0; }
.rc-enterprise-table :deep(.dt__table) { min-width:760px; }
.rc-participation-filter { display:flex; flex-wrap:wrap; align-items:center; gap:12px; margin:16px 0; font-size:13px; }
.rc-participation-filter label { display:flex; align-items:center; gap:10px; color:var(--text-secondary); }
.rc-participation-filter select { min-height:34px; padding:6px 10px; font:inherit; color:var(--text-primary); background:var(--field-bg); border:1px solid var(--border-base); border-radius:6px; }
.rc-participation-filter select:focus-visible { outline:2px solid var(--primary-500); outline-offset:2px; }
.rc-participation-filter > span { margin-left:auto; color:var(--text-secondary); }
.rc-legacy-policy { white-space:pre-wrap; overflow-wrap:anywhere; font-size:12px; color:var(--t2); }
.rc-context { display:flex; flex-wrap:wrap; gap:12px; align-items:center; color:var(--t2); font-size:13px; }
.rc-context a { color:var(--primary); }
.rc-tabs { display:flex; gap:24px; border-bottom:1px solid var(--line, #e3e8ef); }
.rc-tabs a { padding:12px 2px; color:var(--t2); border-bottom:2px solid transparent; text-decoration:none; font-size:14px; }
.rc-tabs a.active { color:var(--primary); border-color:var(--primary); font-weight:600; }
.rc-tabs a:focus-visible { outline:2px solid var(--primary); outline-offset:2px; }
.rc-lifecycle { max-width:820px; line-height:1.8; }
.rc-actions { display:flex; flex-wrap:wrap; gap:12px; margin:20px 0; }
.rc-search-controls { display:flex; gap:12px; margin:8px 0; }
.rc-search-controls > :first-child { flex:1; min-width:0; }
.rc-invite-form { display:grid; grid-template-columns:1fr 1fr; gap:0 20px; }
@media(max-width:640px) { .rc-invite-form { grid-template-columns:1fr; } }
.rc-error { color:var(--danger, #b42318); line-height:1.7; }
.rc-reason { max-width:260px; margin:6px 0 0; color:var(--t3); font-size:12px; white-space:normal; overflow-wrap:anywhere; }
.rc-facts {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 380px), 1fr));
  gap: 28px 32px;
  margin: 0;
}
.rc-facts > div {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}
.rc-facts dt {
  flex: none;
  color: var(--t3, #6b7280);
  font-size: 12px;
  line-height: 1.7;
}
.rc-facts dd {
  margin: 0;
  font-size: 14px;
  line-height: 1.7;
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
