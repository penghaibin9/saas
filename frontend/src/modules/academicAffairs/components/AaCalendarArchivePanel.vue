<template>
  <div class="mp-stack">
    <section class="aa-archive-object">
      <div><strong>{{ term.termName || `${term.yearCode} 第 ${term.termNo} 学期` }}</strong><p>校历归档视图 · 学期 {{ term.termId }}</p></div>
      <StatusTag :status="term.status || term.termStatus" />
      <AppButton v-if="canViewArchive" variant="primary" :disabled="loading || evidenceLoading || !!error" @click="loadEvidence">查看归档证据</AppButton>
    </section>
    <AppInlineAlert type="info" description="已封存事实只读。缺失或待治理的证据不能视为通过；更正必须由归档责任岗按正式纠错流程追加版本，保留原封存记录。" />
    <AppSectionCard title="校历归档视图 · 原记录与正式凭证">
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <DataTable v-else :columns="columns" :rows="[record]" row-key="termId">
        <template #cell-termName><strong>{{ term.termName || term.yearCode }}</strong><small class="aa-archive-meta">学期 {{ term.termId }}</small></template>
        <template #cell-calendarVersion><span>{{ record.sealedVersion ? `封存清单 V${record.sealedVersion}` : '尚无封存清单版本' }}</span><small class="aa-archive-meta">当前学期定义版本 {{ workspace?.version ?? '未提供' }}；封存清单与当前定义分别展示</small></template>
        <template #cell-teachingDays>{{ record.derivedTeachingDays ?? '未配置' }} 天<small class="aa-archive-meta">按当前教学周定义推导 · 校历事件 {{ record.calendarEventCount ?? 0 }} 条</small></template>
        <template #cell-publishRecord><span>{{ record.calendarPublishedAt ? formatTime(record.calendarPublishedAt) : '尚无校历发布流水' }}</span><small class="aa-archive-meta">{{ record.calendarPublishedBy || '未记录发布人' }}</small></template>
        <template #cell-archiveBatch><strong>{{ record.archiveBatchId ? `归档批次 ${record.archiveBatchId}` : '尚未建立归档批次' }}</strong><small class="aa-archive-meta">{{ batchLabel(record.archiveBatchStatus) }}{{ record.archivedAt ? ` · ${formatTime(record.archivedAt)}` : '' }}</small></template>
      </DataTable>
      <p class="mp-note">教学日数按当前周定义推导；正式校历发布流水与不可变封存清单分别来自审计和归档版本链。缺少任一来源时按缺失展示，不推测通过。</p>
    </AppSectionCard>
    <AppInlineAlert v-if="!canViewArchive" type="info" description="当前身份没有归档证据查看权限；可查看学期关系，具体证据由归档责任岗核对。" />
    <AppSectionCard v-if="evidenceRequested" :title="sealed || (term.status || term.termStatus) === 'ARCHIVED' ? '历史封存证据' : '当前学期 · 13 域实时预检'">
      <LoadingState v-if="evidenceLoading" />
      <ErrorState v-else-if="evidenceError" :description="evidenceError" @retry="loadEvidence" />
      <template v-else>
        <p class="mp-note">{{ sealed ? `批次 ${batch.batchId}，封存于 ${formatTime(batch.archivedAt)}。以下读取已保存的批次摘要。` : '以下为当前学期的实时检查结果，仅供核对；没有创建批次、执行封存或改变学期状态。' }}</p>
        <AppInlineAlert v-if="manifest" :type="manifest.ok === true ? 'success' : 'warning'" :description="manifest.ok === true ? `封存版本链校验通过，共 ${manifest.versions?.length || 0} 个版本。` : `封存版本链待核：${manifest.reason || '未取得通过结论'}`" />
        <AppInlineAlert v-if="manifestError" type="warning" :description="`封存版本链读取失败：${manifestError}`" />
        <EmptyState v-if="!domains.length" title="尚无完整检查结果" description="没有返回数据域证据，不视为检查通过。" />
        <DataTable v-else :columns="domainColumns" :rows="domains" row-key="domain">
          <template #cell-domainLabel="{ row }">{{ row.domainLabel || row.label || row.domain }}</template>
          <template #cell-result="{ row }"><StatusTag :type="resultType(row.result)" :label="resultLabel(row.result)" /></template>
          <template #cell-recordCount="{ row }">{{ row.recordCount ?? '未提供' }}</template>
          <template #cell-summary="{ row }">{{ row.summary || row.remark || '未提供检查依据' }}</template>
        </DataTable>
      </template>
    </AppSectionCard>
  </div>
</template>

<script>
import { DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSectionCard, AppInlineAlert } from '@/components/common'
import { academicAffairsApi, academicAffairsArchiveApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { academicAffairsTermDetailApi } from '@/modules/academicAffairs/api/academic-affairs-term-detail.api'
import { academicArchiveCorrectionApi } from '@/modules/academicAffairs/api/academic-archive-correction.api'
import { matchPermission } from '@/config/navPlan'

export default {
  name: 'AaCalendarArchivePanel',
  components: { DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppButton, AppSectionCard, AppInlineAlert },
  props: { term: { type: Object, required: true }, ctx: { type: Object, required: true } },
  data() {
    return { loading: false, error: '', workspace: null, record: {}, loadVersion: 0, evidenceVersion: 0, disposed: false,
      evidenceRequested: false, evidenceLoading: false, evidenceError: '', domains: [], batch: null, manifest: null, manifestError: '',
      columns: [{ key: 'termName', title: '学期' }, { key: 'calendarVersion', title: '校历版本' }, { key: 'teachingDays', title: '教学日数' }, { key: 'publishRecord', title: '发布记录' }, { key: 'archiveBatch', title: '封存关联' }],
      domainColumns: [{ key: 'domainLabel', title: '数据域' }, { key: 'result', title: '检查结论' }, { key: 'recordCount', title: '记录数' }, { key: 'summary', title: '正式依据' }]
    }
  },
  computed: {
    contextKey() { return JSON.stringify([this.term.termId, this.ctx.currentRole, this.ctx.dataScope, this.ctx.permissionPatterns]) },
    canViewArchive() { return matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.archive.view') },
    canVerifyManifest() { return matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.archive.manage') },
    sealed() { return this.batch?.status === 'ARCHIVED' }
  },
  created() { this.load() },
  watch: { contextKey() { this.load() } },
  beforeUnmount() { this.disposed = true; this.loadVersion++; this.evidenceVersion++ },
  methods: {
    formatTime(value) { return value ? String(value).replace('T', ' ').slice(0, 16) : '未提供' },
    batchLabel(status) { return { DRAFT: '草稿', CHECKING: '检查中', READY: '预检通过待封存', MISSING_ITEMS: '有阻断', ARCHIVED: '已封存', CANCELLED: '已取消' }[status] || (status ? '状态待核' : '') },
    resultLabel(result) { return { PASS: '通过', BLOCKED: '阻断', UNKNOWN: '待治理', NOT_APPLICABLE: '不适用' }[result] || '待核 · 未知' },
    resultType(result) { return { PASS: 'success', BLOCKED: 'danger', UNKNOWN: 'warning', NOT_APPLICABLE: 'info' }[result] || 'warning' },
    async load() {
      const version = ++this.loadVersion, context = this.contextKey, termId = String(this.term.termId)
      this.evidenceVersion++; this.evidenceRequested = false; this.evidenceLoading = false
      this.domains = []; this.batch = null; this.manifest = null; this.manifestError = ''; this.evidenceError = ''
      this.loading = true; this.error = ''; this.record = {}; this.workspace = null
      try {
        const [detail, overview] = await Promise.all([academicAffairsTermDetailApi.get(termId), academicAffairsApi.getTermArchiveOverview()])
        if (version !== this.loadVersion || context !== this.contextKey || this.disposed) return
        if (detail.code !== 0 || overview.code !== 0) { this.error = (detail.code !== 0 ? detail.message : overview.message) || '归档来源读取失败'; return }
        const record = Array.isArray(overview.data) ? overview.data.find(row => String(row.termId) === termId) : null
        if (String(detail.data?.termId) !== termId || !record) { this.error = '归档来源与所选学期不一致，请刷新核对。'; return }
        this.workspace = detail.data; this.record = record
      } catch (error) {
        if (version === this.loadVersion && !this.disposed) this.error = error.message || '归档来源读取失败'
      } finally { if (version === this.loadVersion && !this.disposed) this.loading = false }
    },
    async loadEvidence() {
      if (!this.canViewArchive || this.loading || this.evidenceLoading || this.error) return
      const version = ++this.evidenceVersion, context = this.contextKey, termId = String(this.term.termId)
      const current = () => version === this.evidenceVersion && context === this.contextKey && !this.disposed
      this.evidenceRequested = true; this.evidenceLoading = true; this.evidenceError = ''; this.domains = []; this.batch = null; this.manifest = null; this.manifestError = ''
      try {
        if ((this.term.status || this.term.termStatus) === 'ARCHIVED' && this.record.archiveBatchStatus !== 'ARCHIVED') {
          this.evidenceError = '学期已归档，但未找到对应封存批次；不能用实时预检替代历史封存证据。'; return
        }
        if (this.record.archiveBatchId && this.record.archiveBatchStatus === 'ARCHIVED') {
          const batchId = String(this.record.archiveBatchId)
          const res = await academicAffairsArchiveApi.getBatch(batchId)
          if (!current()) return
          if (res.code !== 0) { this.evidenceError = res.message || '封存批次读取失败'; return }
          if (String(res.data?.termId) !== termId || String(res.data?.batchId) !== batchId || res.data?.status !== 'ARCHIVED') { this.evidenceError = '封存批次身份或状态已变化，请刷新来源。'; return }
          this.batch = res.data; this.domains = res.data.items || []
          if (!this.canVerifyManifest) { this.manifestError = '当前身份无封存版本链核验权限，请归档管理岗核对。'; return }
          const manifest = await academicArchiveCorrectionApi.verifyManifest(batchId)
          if (!current()) return
          if (manifest.code === 0) this.manifest = manifest.data
          else this.manifestError = manifest.message || '读取失败'
        } else {
          const res = await academicAffairsArchiveApi.precheck(termId)
          if (!current()) return
          if (res.code !== 0) { this.evidenceError = res.message || '归档预检读取失败'; return }
          if (String(res.data?.termId) !== termId) { this.evidenceError = '检查结果与所选学期不一致，请刷新核对。'; return }
          this.domains = res.data.domains || []
        }
      } catch (error) { if (current()) this.evidenceError = error.message || '归档证据读取失败' }
      finally { if (current()) this.evidenceLoading = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-archive-object { display: flex; align-items: center; gap: 18px; padding: 18px; border: 1px solid var(--border-base); border-left: 3px solid var(--pri); border-radius: 10px; background: var(--bg-card); flex-wrap: wrap; }
.aa-archive-object > div { flex: 1; min-width: 220px; }
.aa-archive-object strong { font-size: 16px; }
.aa-archive-object p, .aa-archive-meta { color: var(--text-secondary); font-size: 12px; line-height: 1.7; }
.aa-archive-object p { margin: 6px 0 0; }
.aa-archive-meta { display: block; margin-top: 6px; }
</style>
