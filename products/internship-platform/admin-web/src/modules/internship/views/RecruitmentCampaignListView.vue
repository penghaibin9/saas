<template>
  <ModulePageShell
    class="rc-list"
    title="招聘与邀请"
    subtitle="当前批次的招聘轮次、时间安排与企业参与情况"
    watermark-purpose="招聘季管理"
  >
    <template #actions><ModuleToolbar v-if="!noPermission" :actions="toolbarActions" @action="onToolbar" /></template>
    <NoPermissionState v-if="noPermission" @back="$router.back()" />
    <template v-else>
      <div class="rc-list-toolbar"><span>{{ loading ? '正在读取招聘轮次…' : error ? '招聘轮次暂不可用' : `本页 ${rows.length} 个招聘季` }}</span><AppButton variant="ghost" size="sm" :disabled="loading" @click="load">刷新列表</AppButton></div>

      <LoadingState v-if="loading" />
      <ErrorState v-else-if="error" :description="error" @retry="load" />
      <EmptyState
        v-else-if="!rows.length"
        :title="page > 1 ? '本页没有招聘季' : '当前批次尚未安排招聘'"
        :description="page > 1 ? '记录可能已调整，请返回上一页查看。' : '负责人新建招聘季并配置时间，开启后即可邀请企业。'"
      />
      <AppButton v-if="!loading && !error && !rows.length && page > 1" variant="ghost" @click="turnPage(page - 1)">返回上一页</AppButton>
      <DataTable
        v-if="!loading && !error && rows.length"
        :columns="tableColumns"
        :rows="rows"
        row-key="id"
        :pagination="paginationConf"
        :show-total="false"
        @page-change="turnPage"
      >
        <template #cell-campaignName="{ row }"><RouterLink class="rc-list-name" :to="detailLink(row)">{{ row.campaignName }}</RouterLink><div class="rc-list-meta">{{ row.campaignCode }} · 第 {{ row.roundNo }} 轮</div></template>
        <template #cell-status="{ row }">
          <AppStatusTag :type="statusTagType[row.status] || 'default'" dot>{{ statusLabel(row.status) }}</AppStatusTag>
          <div class="rc-list-meta">{{ phaseLabel(row.phase) }}</div>
        </template>
        <template #cell-inviteWindow="{ row }">
          <div>{{ dateShort(row.inviteStartAt) || '未配置' }}</div><div class="rc-list-meta">至 {{ dateShort(row.inviteEndAt) || '未配置' }}</div>
        </template>
        <template #cell-accessEnd="{ row }">
          <span>{{ dateShort(row.enterpriseAccessEndAt) || '—' }}</span>
        </template>
        <template #cell-actions="{ row }">
          <TableActionColumn :actions="rowActions(row)" @action="(key) => onRowAction(key, row)" />
        </template>
      </DataTable>

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
import { ModulePageShell, ModuleToolbar, DataTable, EmptyState, LoadingState, ErrorState } from '@/components/business'
import { AppStatusTag } from '@/components/common'
import { AppButton } from '@/components/ui'
import { TableActionColumn, NoPermissionState } from '@/modules/internship/components'
import { recruitmentCampaignApi } from '@/modules/internship/api/recruitment-campaign.api'
import {
  CAMPAIGN_STATUS_TAG, CAMPAIGN_PHASE_LABEL,
  campaignStatusLabel
} from '@/modules/internship/constants/recruitmentCampaign.constants'
import { formatDate } from '@/utils/dateUtils'
import { canCode } from '@/modules/internship/composables/permission'

export default {
  name: 'RecruitmentCampaignListView',
  props: { ctx: { type: Object, required: true } },
  components: {
    ModulePageShell, ModuleToolbar, DataTable, EmptyState, LoadingState, ErrorState,
    AppStatusTag, AppButton,
    TableActionColumn, NoPermissionState
  },
  data() {
    return {
      alive: true,
      loadSequence: 0,
      loading: true,
      error: '',
      rows: [],
      page: 1,
      pageSize: 10,
      hasMore: false,
      statusTagType: CAMPAIGN_STATUS_TAG
    }
  },
  computed: {
    batchId() { return typeof this.$route.query.batchId === 'string' ? this.$route.query.batchId : '' },
    listQuery() { return { batchId: this.batchId || undefined, page: String(this.page) } },
    listQueryKey() { return JSON.stringify([this.$route.query.batchId || '', this.$route.query.page || '1']) },
    noPermission() {
      return this.ctx && !this.allowed('internship.recruitment.view', 'internship.enterprise.view')
    },
    toolbarActions() {
      return this.batchId && this.allowed('internship.recruitment.manage', 'internship.enterprise.manage') ? [{ key: 'create', label: '新建招聘季', variant: 'primary' }] : []
    },
    tableColumns() {
      return [
        { key: 'campaignName', title: '招聘季 / 轮次', width: '32%' },
        { key: 'status', title: '状态 / 当前阶段', width: '140px' },
        { key: 'inviteWindow', title: '企业邀请窗' },
        { key: 'accessEnd', title: '企业访问截止' },
        { key: 'actions', title: '操作', width: '170px' }
      ]
    },
    paginationConf() {
      // 后端按页查询，只返回 hasMore，没有 total。
      // 这里给分页器一个「下界估值」仅用于驱动上一页/下一页可点性，
      // 同时对 DataTable 传 show-total=false，避免把估值当成真实总数展示。
      const known = (this.page - 1) * this.pageSize + this.rows.length
      return {
        page: this.page,
        pageSize: this.pageSize,
        total: this.hasMore ? known + 1 : known
      }
    }
  },
  created() { this.restoreQuery(); this.load() },
  watch: {
    listQueryKey() { this.restoreQuery(); this.load() },
    ctx: { deep: true, handler() { this.load() } }
  },
  beforeUnmount() { this.alive = false; this.loadSequence++ },
  methods: {
    restoreQuery() { this.page = Math.min(1000000, Math.max(1, Number.parseInt(this.$route.query.page, 10) || 1)) },
    writeQuery() {
      const next = JSON.stringify([this.batchId, String(this.page)])
      if (next === this.listQueryKey) return this.load()
      return this.$router.replace({ path: this.$route.path, query: this.listQuery })
    },
    allowed(...codes) { return Array.isArray(this.ctx?.permissionPatterns) && codes.some((code) => canCode(this.ctx, code)) },
    statusLabel: campaignStatusLabel,
    phaseLabel(phase) {
      return CAMPAIGN_PHASE_LABEL[phase] || phase || '—'
    },
    dateShort(v) {
      return formatDate(v, '')
    },
    async load() {
      const sequence = ++this.loadSequence
      this.loading = true
      this.error = ''
      this.rows = []; this.hasMore = false
      if (this.noPermission) { this.loading = false; return }
      if (!this.batchId) { this.loading = false; this.error = '请在上方选择实习批次'; return }
      try {
        const params = { page: this.page, pageSize: this.pageSize, batchId: this.batchId }
        const res = await recruitmentCampaignApi.getCampaigns(params)
        if (sequence !== this.loadSequence) return
        if (res.code === 0) {
          this.rows = res.data.list
          this.hasMore = res.data.hasMore
        } else this.error = res.message || '招聘季读取失败，请重试'
      } catch (e) {
        if (sequence !== this.loadSequence) return
        this.error = e.message || '加载失败'
      } finally {
        if (sequence === this.loadSequence) this.loading = false
      }
    },
    turnPage(p) {
      this.page = p
      this.writeQuery()
    },
    onToolbar(key) {
      if (key === 'create' && this.batchId && this.allowed('internship.recruitment.manage', 'internship.enterprise.manage')) {
        this.$router.push({ path: '/admin/internship/recruitment-campaigns/new', query: this.listQuery })
      }
    },
    detailLink(row, section = 'enterprises') { return { path: `/admin/internship/recruitment-campaigns/${row.id}`, query: { ...this.listQuery, section } } },
    openDetail(row, section = 'enterprises') { this.$router.push(this.detailLink(row, section)) },
    rowActions(row) {
      void row
      return [
        { key: 'detail', label: '参与企业' },
        ...(this.allowed('internship.recruitment.manage', 'internship.recruitment.close', 'internship.enterprise.manage') ? [{ key: 'lifecycle', label: '状态办理' }] : [])
      ]
    },
    onRowAction(key, row) {
      if (key === 'detail') return this.openDetail(row)
      if (key === 'lifecycle' && this.rowActions(row).some((action) => action.key === key)) return this.openDetail(row, key)
    }
  }
}
</script>
<style scoped>
.rc-list :deep(.dt__table) { min-width: 900px; }
.rc-list-toolbar { display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:12px; color:var(--text-secondary); font-size:13px; }
.rc-list-name { display:inline-block; font-weight:600; line-height:1.6; color:var(--text-primary); text-decoration:none; }
.rc-list-name:hover { color:var(--primary-500); text-decoration:underline; }
.rc-list-name:focus-visible { outline:2px solid var(--primary-500); outline-offset:3px; }
.rc-list-meta { margin-top:5px; color:var(--t3); font-size:12px; }
</style>
