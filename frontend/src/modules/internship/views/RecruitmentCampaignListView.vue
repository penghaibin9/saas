<template>
  <ModulePageShell
    title="招聘季与企业邀请"
    :subtitle="pageSubtitle"
    :role-name="roleName"
    :data-scope-name="dataScopeName"
    watermark-purpose="招聘季管理"
  >
    <NoPermissionState v-if="noPermission" @back="$router.back()" />
    <template v-else>
      <ModuleSummaryStrip :metrics="summaryMetrics" />
      <ModuleToolbar
        :actions="toolbarActions"
        hint="招聘季是企业参与实习招募的时间骨架：开启后才能邀请企业、企业才能报岗位"
        @action="onToolbar"
      />

      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <LoadingState v-if="loading" />
      <ErrorState v-else-if="error" :description="error" @retry="load" />
      <EmptyState
        v-else-if="!rows.length"
        title="暂无招聘季"
        description="点击「新建招聘季」为某个实习批次创建企业招募轮次"
      />
      <DataTable
        v-else
        :columns="tableColumns"
        :rows="rows"
        row-key="id"
        row-clickable
        :pagination="paginationConf"
        :show-total="false"
        @page-change="turnPage"
        @row-click="openDetail"
      >
        <template #cell-status="{ row }">
          <AppStatusTag :type="statusTagType[row.status] || 'default'" dot>{{ statusLabel(row.status) }}</AppStatusTag>
        </template>
        <template #cell-phase="{ row }">
          <span>{{ phaseLabel(row.phase) }}</span>
        </template>
        <template #cell-inviteWindow="{ row }">
          <span>{{ dateShort(row.inviteStartAt) || '—' }} ~ {{ dateShort(row.inviteEndAt) || '—' }}</span>
        </template>
        <template #cell-accessEnd="{ row }">
          <span>{{ dateShort(row.enterpriseAccessEndAt) || '—' }}</span>
        </template>
        <template #cell-actions="{ row }">
          <TableActionColumn :actions="rowActions(row)" @action="(key) => onRowAction(key, row)" />
        </template>
      </DataTable>

      <!-- 新建招聘季 -->
      <AppDrawer
        :visible="createVisible"
        title="新建招聘季"
        mode="modal"
        size="large"
        @update:visible="createVisible = $event"
      >
        <AppInlineAlert
          type="info"
          title="时间窗决定企业能做什么"
          description="邀请窗控制何时能邀请企业；企业访问截止时间决定企业账号最晚可用到哪天。两者未填时后端会拒绝邀请企业。"
        />
        <AppForm ref="createForm" :model="createModel" :rules="createRules" layout="horizontal" label-width="132px">
          <AppFormItem label="所属实习批次" prop="batchId" required>
            <AppSelect
              v-model="createModel.batchId"
              :options="batchOptions"
              placeholder="选择本次招募依附的实习批次"
            />
          </AppFormItem>
          <AppFormItem label="招聘季编码" prop="campaignCode" required hint="学校内唯一，建议如 2026-SPRING-R1">
            <AppTextInput v-model="createModel.campaignCode" placeholder="如 2026-SPRING-R1" />
          </AppFormItem>
          <AppFormItem label="招聘季名称" prop="campaignName" required>
            <AppTextInput v-model="createModel.campaignName" placeholder="如 2026春季实习企业招募第一轮" />
          </AppFormItem>
          <AppFormItem label="轮次" prop="roundNo">
            <AppNumberInput v-model="createModel.roundNo" :min="1" :max="99" />
          </AppFormItem>
          <AppFormItem label="企业邀请窗" prop="inviteRange" required hint="仅此区间内可邀请企业">
            <AppDateRangePicker v-model="createModel.inviteRange" />
          </AppFormItem>
          <AppFormItem label="岗位报送窗" prop="positionRange">
            <AppDateRangePicker v-model="createModel.positionRange" />
          </AppFormItem>
          <AppFormItem label="学生选岗窗" prop="studentRange">
            <AppDateRangePicker v-model="createModel.studentRange" />
          </AppFormItem>
          <AppFormItem label="企业决策窗" prop="decisionRange">
            <AppDateRangePicker v-model="createModel.decisionRange" />
          </AppFormItem>
          <AppFormItem label="学校确认窗" prop="confirmRange">
            <AppDateRangePicker v-model="createModel.confirmRange" />
          </AppFormItem>
          <AppFormItem
            label="企业访问截止"
            prop="enterpriseAccessEndAt"
            required
            hint="企业账号最晚可登录使用到该时间，须晚于邀请窗结束"
          >
            <AppDatePicker v-model="createModel.enterpriseAccessEndAt" />
          </AppFormItem>
          <AppFormItem label="备注" prop="remark">
            <AppTextarea v-model="createModel.remark" :rows="2" placeholder="选填" />
          </AppFormItem>
        </AppForm>
        <template #footer>
          <AppButton variant="ghost" @click="createVisible = false">取消</AppButton>
          <AppButton variant="primary" :loading="submitting" @click="submitCreate">创建（草稿）</AppButton>
        </template>
      </AppDrawer>

      <!-- 开启 / 冻结 / 关闭 / 归档 二次确认 -->
      <AppConfirmDialog
        v-model:visible="confirmVisible"
        :title="confirmConf.title"
        :message="confirmConf.message"
        :type="confirmConf.type"
        :confirm-text="confirmConf.confirmText"
        @confirm="onConfirm"
      />
    </template>
  </ModulePageShell>
</template>

<script>
/**
 * /admin/internship/recruitment-campaigns 招聘季列表。
 * 真实接口 /internship/recruitment-campaigns（见后端 routers/internship_recruitment_campaign.py）。
 *
 * 招聘季是「学校邀请企业参与实习招募」的唯一正式入口：草稿 → 开启后进入邀请窗 →
 * 企业接受邀请后才能报岗位。企业账号也只能由此产生（不提供企业自注册）。
 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, EmptyState, LoadingState, ErrorState } from '@/components/business'
import {
  AppConfirmDialog, AppStatusTag, AppInlineAlert,
  AppForm, AppFormItem, AppTextInput, AppTextarea, AppSelect, AppNumberInput,
  AppDatePicker, AppDateRangePicker
} from '@/components/common'
import { AppButton, AppDrawer } from '@/components/ui'
import { TableActionColumn, NoPermissionState } from '@/modules/internship/components'
import ModuleSummaryStrip from './components/ModuleSummaryStrip.vue'
import { recruitmentCampaignApi } from '@/modules/internship/api/recruitment-campaign.api'
import { internshipApi } from '@/modules/internship/api/internship.api'
import {
  CAMPAIGN_STATUS_TAG, CAMPAIGN_PHASE_LABEL,
  campaignStatusLabel, canTransition, toIsoStart, toIsoEnd
} from '@/modules/internship/constants/recruitmentCampaign.constants'
import { toast } from '@/utils/toast'
import { formatDate } from '@/utils/dateUtils'

const EMPTY_FILTERS = () => ({ batchId: '' })
const EMPTY_CREATE = () => ({
  batchId: '',
  campaignCode: '',
  campaignName: '',
  roundNo: 1,
  inviteRange: [],
  positionRange: [],
  studentRange: [],
  decisionRange: [],
  confirmRange: [],
  enterpriseAccessEndAt: '',
  remark: ''
})

export default {
  name: 'RecruitmentCampaignListView',
  components: {
    ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, EmptyState, LoadingState, ErrorState,
    AppConfirmDialog, AppStatusTag, AppInlineAlert,
    AppForm, AppFormItem, AppTextInput, AppTextarea, AppSelect, AppNumberInput,
    AppDatePicker, AppDateRangePicker, AppButton, AppDrawer,
    TableActionColumn, NoPermissionState, ModuleSummaryStrip
  },
  data() {
    return {
      ctx: null,
      loading: true,
      error: '',
      rows: [],
      page: 1,
      pageSize: 10,
      hasMore: false,
      filters: EMPTY_FILTERS(),
      batchOptions: [],
      createVisible: false,
      submitting: false,
      createModel: EMPTY_CREATE(),
      confirmVisible: false,
      confirmMode: '',
      confirmRow: null,
      statusTagType: CAMPAIGN_STATUS_TAG
    }
  },
  computed: {
    roleName() {
      return this.ctx?.currentRole?.roleName || ''
    },
    dataScopeName() {
      return this.ctx?.dataScope?.name || ''
    },
    noPermission() {
      return false
    },
    pageSubtitle() {
      return '按实习批次组织企业招募轮次，管理邀请窗、岗位报送窗与企业访问期限 · 企业账号由此邀请产生'
    },
    toolbarActions() {
      return [{ key: 'create', label: '新建招聘季' }]
    },
    filterFields() {
      return [{ key: 'batchId', label: '实习批次', type: 'select', options: this.batchOptions }]
    },
    tableColumns() {
      return [
        { key: 'campaignName', title: '招聘季名称' },
        { key: 'campaignCode', title: '编码' },
        { key: 'roundNo', title: '轮次' },
        { key: 'status', title: '状态' },
        { key: 'phase', title: '当前阶段' },
        { key: 'inviteWindow', title: '企业邀请窗' },
        { key: 'accessEnd', title: '企业访问截止' },
        { key: 'actions', title: '操作' }
      ]
    },
    paginationConf() {
      // 后端招聘季列表是游标式分页：只返回 hasMore，没有 total。
      // 这里给分页器一个「下界估值」仅用于驱动上一页/下一页可点性，
      // 同时对 DataTable 传 show-total=false，避免把估值当成真实总数展示。
      const known = (this.page - 1) * this.pageSize + this.rows.length
      return {
        page: this.page,
        pageSize: this.pageSize,
        total: this.hasMore ? known + 1 : known
      }
    },
    summaryMetrics() {
      if (this.loading || this.error) return []
      const m = [{ label: '本页招聘季', value: this.rows.length }]
      const open = this.rows.filter((r) => r.status === 'OPEN').length
      if (open) m.push({ label: '进行中', value: open, tone: 'good' })
      return m
    },
    createRules() {
      return {
        batchId: [{ required: true, message: '请选择所属实习批次' }],
        campaignCode: [{ required: true, message: '请填写招聘季编码' }],
        campaignName: [{ required: true, message: '请填写招聘季名称' }],
        inviteRange: [{ required: true, message: '请设置企业邀请窗，否则无法邀请企业' }],
        enterpriseAccessEndAt: [{ required: true, message: '请设置企业访问截止时间' }]
      }
    },
    confirmConf() {
      const r = this.confirmRow
      const name = r ? r.campaignName : ''
      if (this.confirmMode === 'open') {
        return { title: '开启招聘季', message: `开启「${name}」后进入邀请窗，可开始邀请企业参与。`, type: 'primary', confirmText: '确认开启' }
      }
      if (this.confirmMode === 'freeze') {
        return { title: '冻结招聘季', message: `冻结「${name}」后暂停企业侧操作，可再次开启。`, type: 'danger', confirmText: '确认冻结' }
      }
      if (this.confirmMode === 'close') {
        return { title: '关闭招聘季', message: `关闭「${name}」后不再接受企业与学生新操作，关闭后才可归档。`, type: 'danger', confirmText: '确认关闭' }
      }
      if (this.confirmMode === 'archive') {
        return { title: '归档招聘季', message: `归档「${name}」后进入只读台账，不可再变更。`, type: 'danger', confirmText: '确认归档' }
      }
      return { title: '', message: '', type: 'primary', confirmText: '确认' }
    }
  },
  async created() {
    const ctx = await internshipApi.getContext()
    if (ctx.code === 0) this.ctx = ctx.data
    await this.loadBatchOptions()
    await this.load()
  },
  methods: {
    statusLabel: campaignStatusLabel,
    phaseLabel(phase) {
      return CAMPAIGN_PHASE_LABEL[phase] || phase || '—'
    },
    dateShort(v) {
      return formatDate(v, '')
    },
    async loadBatchOptions() {
      const res = await internshipApi.getBatches({ page: 1, pageSize: 200 })
      if (res.code === 0) {
        this.batchOptions = (res.data.list || []).map((b) => ({ value: String(b.id), label: b.batchName }))
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      try {
        const params = { page: this.page, pageSize: this.pageSize }
        if (this.filters.batchId) params.batchId = this.filters.batchId
        const res = await recruitmentCampaignApi.getCampaigns(params)
        if (res.code === 0) {
          this.rows = res.data.list
          this.hasMore = res.data.hasMore
        } else this.error = res.message
      } catch (e) {
        this.error = e.message || '加载失败'
      } finally {
        this.loading = false
      }
    },
    search() {
      this.page = 1
      this.load()
    },
    reset() {
      this.filters = EMPTY_FILTERS()
      this.page = 1
      this.load()
    },
    turnPage(p) {
      this.page = p
      this.load()
    },
    onToolbar(key) {
      if (key === 'create') {
        this.createModel = EMPTY_CREATE()
        if (this.filters.batchId) this.createModel.batchId = this.filters.batchId
        this.createVisible = true
      }
    },
    openDetail(row) {
      this.$router.push(`/admin/internship/recruitment-campaigns/${row.id}`)
    },
    rowActions(row) {
      const s = row.status
      // 可用性严格按后端状态机（见 recruitmentCampaign.constants.js CAMPAIGN_TRANSITIONS）：
      // FROZEN 不能回到 OPEN，冻结后只能关闭。
      return [
        { key: 'detail', label: '详情与企业' },
        { key: 'open', label: '开启', disabled: !canTransition(s, 'OPEN'), disabledReason: '仅草稿可开启；冻结后不能重新开启' },
        { key: 'freeze', label: '冻结', disabled: !canTransition(s, 'FROZEN'), disabledReason: '仅进行中可冻结' },
        { key: 'close', label: '关闭', danger: true, disabled: !canTransition(s, 'CLOSED'), disabledReason: '仅进行中或已冻结可关闭' },
        { key: 'archive', label: '归档', danger: true, disabled: !canTransition(s, 'ARCHIVED'), disabledReason: '仅已关闭可归档' }
      ]
    },
    onRowAction(key, row) {
      if (key === 'detail') return this.openDetail(row)
      this.confirmMode = key
      this.confirmRow = row
      this.confirmVisible = true
    },
    async onConfirm() {
      const row = this.confirmRow
      if (!row) return
      const res = await recruitmentCampaignApi.transitionCampaign(row.id, this.confirmMode, row.version)
      if (res.code === 0) {
        toast.success('操作成功')
        this.confirmVisible = false
        await this.load()
      } else {
        toast.error(res.message || '操作失败')
      }
    },
    buildCreateBody() {
      const m = this.createModel
      const body = {
        batchId: String(m.batchId),
        campaignCode: m.campaignCode.trim(),
        campaignName: m.campaignName.trim(),
        roundNo: Number(m.roundNo) || 1
      }
      const ranges = [
        ['inviteRange', 'inviteStartAt', 'inviteEndAt'],
        ['positionRange', 'positionSubmitStartAt', 'positionSubmitEndAt'],
        ['studentRange', 'studentSelectStartAt', 'studentSelectEndAt'],
        ['decisionRange', 'enterpriseDecisionStartAt', 'enterpriseDecisionEndAt'],
        ['confirmRange', 'schoolConfirmStartAt', 'schoolConfirmEndAt']
      ]
      ranges.forEach(([key, startField, endField]) => {
        const v = m[key]
        if (Array.isArray(v) && v[0] && v[1]) {
          body[startField] = toIsoStart(v[0])
          body[endField] = toIsoEnd(v[1])
        }
      })
      if (m.enterpriseAccessEndAt) body.enterpriseAccessEndAt = toIsoEnd(m.enterpriseAccessEndAt)
      if (m.remark) body.remark = m.remark.trim()
      return body
    },
    async submitCreate() {
      const form = this.$refs.createForm
      if (form && typeof form.validate === 'function') {
        const valid = await form.validate()
        if (!valid) return
      }
      this.submitting = true
      try {
        const res = await recruitmentCampaignApi.createCampaign(this.buildCreateBody())
        if (res.code === 0) {
          toast.success('招聘季已创建（草稿），开启后即可邀请企业')
          this.createVisible = false
          this.page = 1
          await this.load()
        } else {
          toast.error(res.message || '创建失败')
        }
      } finally {
        this.submitting = false
      }
    }
  }
}
</script>
