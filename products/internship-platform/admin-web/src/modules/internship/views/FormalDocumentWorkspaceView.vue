<template>
  <ModulePageShell
    class="fdw"
    title="正式文书"
    subtitle="按已审核、已发布的正式业务事实生成版本化 PDF；源数据变化会生成新版本，历史文件不覆盖。"
  >
    <section class="mp-card">
      <div class="mp-card__head">
        <div>
          <span class="mp-card__title">选择学生实习记录</span>
          <p class="fdw-sub">只显示当前批次和当前账号数据范围内的学生。</p>
        </div>
      </div>
      <div class="mp-card__body fdw-select">
        <AppInternshipStudentPicker
          v-model="internshipId"
          :query="{ batchId }"
          placeholder="按学号 / 姓名搜索实习学生"
          data-scope-hint="仅显示当前批次、当前权限范围内学生"
          @change="onStudentChange"
        />
        <div v-if="student" class="fdw-student">
          <strong>{{ student.name || student.studentName || '学生' }}</strong>
          <span>{{ student.studentNo || '—' }} · {{ student.className || '班级未登记' }}</span>
          <span>{{ student.enterpriseName || '未落实企业' }} · {{ student.positionName || '未落实岗位' }}</span>
        </div>
      </div>
    </section>

    <div v-if="!batchId" class="fdw-notice">请先在顶部选择实习批次。</div>
    <LoadingState v-else-if="loading" />
    <ErrorState v-else-if="error" :description="error" @retry="loadSelected" />

    <template v-else-if="internshipId && student">
      <section class="fdw-grid">
        <article v-for="item in readinessItems" :key="item.documentType" class="mp-card fdw-doc">
          <div class="mp-card__head">
            <div>
              <span class="mp-card__title">{{ item.documentTypeLabel }}</span>
              <p class="fdw-sub">{{ documentHint(item.documentType) }}</p>
            </div>
            <AppStatusTag :type="item.ready ? (item.upToDate ? 'success' : 'warning') : 'danger'">
              {{ item.ready ? (item.upToDate ? '最新版已生成' : '可生成新版本') : '暂不可生成' }}
            </AppStatusTag>
          </div>
          <div class="mp-card__body fdw-doc__body">
            <div v-if="item.ready" class="fdw-facts">
              <span>当前源数据哈希</span>
              <code>{{ item.currentSourceHash || '—' }}</code>
            </div>
            <div v-if="item.latestVersion" class="fdw-facts">
              <span>最新文书</span>
              <strong>V{{ item.latestVersion }} · {{ item.latestStatus || '—' }}</strong>
              <code v-if="item.latestFileSha256">{{ item.latestFileSha256 }}</code>
            </div>
            <p v-if="!item.ready" class="fdw-blocker">{{ item.reason || '正式业务事实尚不完整。' }}</p>
            <p v-else-if="item.upToDate" class="fdw-ready">当前正式事实与最新 PDF 一致，无需重复生成。</p>
            <p v-else class="fdw-ready is-warning">当前正式事实已满足条件，且与历史版本不同，可生成新版本。</p>
            <div class="fdw-actions">
              <AppButton
                v-if="item.latestDocumentId"
                size="sm"
                variant="ghost"
                :disabled="busyType === item.documentType"
                @click="downloadLatest(item)"
              >下载最新 V{{ item.latestVersion }}</AppButton>
              <AppButton
                v-if="item.ready && !item.upToDate"
                size="sm"
                :disabled="!canGenerate || !!busyType"
                @click="generate(item)"
              >{{ busyType === item.documentType ? '正在生成…' : '生成新版本' }}</AppButton>
            </div>
          </div>
        </article>
      </section>

      <section class="mp-card">
        <div class="mp-card__head">
          <div>
            <span class="mp-card__title">历史版本</span>
            <p class="fdw-sub">每次正式事实变化后重新生成都会形成新版本，旧 PDF 永不覆盖。</p>
          </div>
          <AppButton size="sm" variant="ghost" :disabled="loading" @click="loadSelected">刷新</AppButton>
        </div>
        <div class="mp-card__body">
          <EmptyState v-if="!documents.length" title="尚未生成正式文书" description="上方满足条件的文书可直接生成。" />
          <DataTable v-else :columns="columns" :rows="documents" row-key="id">
            <template #cell-type="{ row }">
              <div class="fdw-cell"><strong>{{ row.documentTypeLabel }}</strong><span>{{ row.documentType }}</span></div>
            </template>
            <template #cell-version="{ row }">V{{ row.documentVersion }}</template>
            <template #cell-file="{ row }">
              <div class="fdw-cell"><span>fileId {{ row.fileId || '—' }}</span><code>{{ row.fileSha256 || '—' }}</code></div>
            </template>
            <template #cell-status="{ row }">
              <AppStatusTag :type="row.status === 'GENERATED' ? 'success' : 'default'">{{ row.status }}</AppStatusTag>
            </template>
            <template #cell-actions="{ row }">
              <AppButton size="sm" variant="ghost" :disabled="downloadingId === String(row.id)" @click="download(row)">
                {{ downloadingId === String(row.id) ? '下载中…' : '下载 PDF' }}
              </AppButton>
            </template>
          </DataTable>
        </div>
      </section>
    </template>

    <EmptyState
      v-else-if="batchId"
      title="请选择学生"
      description="选择学生后，系统会先检查企业评价、实习结束事实、最终成绩和实习总结是否满足正式文书生成条件。"
    />
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, LoadingState, ErrorState, EmptyState, DataTable } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppInternshipStudentPicker, AppStatusTag } from '@/components/common'
import { useInternshipBatchStore } from '@/stores/internshipBatch'
import { internStudentApi } from '@/modules/internship/api/internship-student.api'
import { formalDocumentApi } from '@/modules/internship/api/formal-document.api'
import { canCode } from '@/modules/internship/composables/permission'
import { toast } from '@/utils/toast'

const COLUMNS = [
  { key: 'type', title: '文书类型', width: '220px' },
  { key: 'version', title: '版本', width: '80px' },
  { key: 'generatedByName', title: '生成人', width: '130px' },
  { key: 'generatedAt', title: '生成时间', width: '170px' },
  { key: 'file', title: '冻结文件 / SHA-256' },
  { key: 'status', title: '状态', width: '100px' },
  { key: 'actions', title: '操作', width: '110px' }
]

export default {
  name: 'FormalDocumentWorkspaceView',
  props: { ctx: { type: Object, required: true } },
  components: {
    ModulePageShell, LoadingState, ErrorState, EmptyState, DataTable,
    AppButton, AppInternshipStudentPicker, AppStatusTag
  },
  data() {
    return {
      internshipId: '',
      student: null,
      readinessItems: [],
      documents: [],
      loading: false,
      error: '',
      busyType: '',
      downloadingId: '',
      loadSeq: 0,
      columns: COLUMNS
    }
  },
  computed: {
    batchStore() { return useInternshipBatchStore() },
    batchId() { return this.batchStore.selectedBatchId || '' },
    canGenerate() { return canCode(this.ctx, 'internship.archive.execute') }
  },
  watch: {
    'batchStore.selectedBatchId'() {
      this.loadSeq++
      this.internshipId = ''
      this.student = null
      this.readinessItems = []
      this.documents = []
      this.error = ''
    }
  },
  beforeUnmount() { this.loadSeq++ },
  methods: {
    documentHint(type) {
      return {
        ENTERPRISE_EVALUATION: '基于已审核企业评价生成企业实习鉴定表。',
        INTERNSHIP_CERTIFICATE: '基于已结束实习事实和考勤事实生成学生实习证明。',
        FINAL_ASSESSMENT: '基于已发布且完整的最终成绩生成实习考核成绩表。',
        SUMMARY_REPORT: '基于已通过批阅的不可变实习总结版本生成正式总结报告。'
      }[type] || ''
    },
    async onStudentChange(value) {
      this.internshipId = String(value || '')
      await this.loadSelected()
    },
    async loadSelected() {
      const recordId = String(this.internshipId || '')
      const batchId = String(this.batchId || '')
      if (!recordId || !batchId) return
      const seq = ++this.loadSeq
      this.loading = true
      this.error = ''
      this.student = null
      this.readinessItems = []
      this.documents = []
      try {
        const [detailRes, readyRes, docsRes] = await Promise.all([
          internStudentApi.getStudentDetail(recordId),
          formalDocumentApi.readiness(recordId),
          formalDocumentApi.list(recordId)
        ])
        if (seq !== this.loadSeq || recordId !== String(this.internshipId) || batchId !== String(this.batchId)) return
        if (detailRes.code !== 0) throw new Error(detailRes.message || '学生实习档案读取失败')
        if (String(detailRes.data?.batchId || '') !== batchId) throw new Error('学生记录不属于当前选择批次')
        if (readyRes.code !== 0) throw new Error(readyRes.message || '正式文书生成条件读取失败')
        if (docsRes.code !== 0) throw new Error(docsRes.message || '正式文书版本读取失败')
        this.student = detailRes.data
        this.readinessItems = readyRes.data?.items || []
        this.documents = docsRes.data || []
      } catch (error) {
        if (seq === this.loadSeq) this.error = error?.message || '正式文书工作区加载失败'
      } finally {
        if (seq === this.loadSeq) this.loading = false
      }
    },
    latestDocument(item) {
      return this.documents
        .filter((row) => row.documentType === item.documentType)
        .sort((a, b) => Number(b.documentVersion || 0) - Number(a.documentVersion || 0))[0] || null
    },
    async generate(item) {
      if (!item?.ready || item.upToDate || !this.canGenerate || this.busyType) return
      const recordId = String(this.internshipId || '')
      this.busyType = item.documentType
      const res = await formalDocumentApi.generate(recordId, item.documentType)
      this.busyType = ''
      if (recordId !== String(this.internshipId)) return
      if (res.code !== 0) {
        toast.error(res.message || '正式文书生成失败')
        await this.loadSelected()
        return
      }
      toast.success(res.data?.reused ? '当前正式文书已是最新版本' : '正式文书新版本已生成并冻结')
      await this.loadSelected()
      const latest = this.documents.find((row) => String(row.id) === String(res.data?.id))
      if (latest) await this.download(latest)
    },
    async downloadLatest(item) {
      const row = this.latestDocument(item)
      if (row) await this.download(row)
    },
    async download(row) {
      if (!row?.id || this.downloadingId) return
      this.downloadingId = String(row.id)
      const res = await formalDocumentApi.download(row)
      this.downloadingId = ''
      if (res.code !== 0) toast.error(res.message || '正式文书下载失败')
    }
  }
}
</script>

<style scoped>
.fdw{gap:14px}.fdw-sub{margin:5px 0 0;color:var(--text-secondary);font-size:12px;line-height:1.6}.fdw-select{display:grid;grid-template-columns:minmax(280px,520px) 1fr;gap:18px;align-items:center}.fdw-student{display:grid;gap:4px;padding:11px 13px;border:1px solid var(--border-base);border-radius:9px;background:var(--bg-page);font-size:12px}.fdw-student strong{font-size:14px;color:var(--text-primary)}.fdw-student span{color:var(--text-secondary)}.fdw-notice{padding:14px 16px;border:1px solid #f5d48b;border-radius:10px;background:#fffbeb;color:#8a5b00;font-size:13px}.fdw-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.fdw-doc{min-width:0}.fdw-doc__body{display:grid;gap:10px}.fdw-facts{display:grid;gap:4px;font-size:12px}.fdw-facts span{color:var(--text-secondary)}.fdw-facts code{font-size:10px;color:var(--text-tertiary);overflow-wrap:anywhere}.fdw-blocker,.fdw-ready{margin:0;padding:10px 12px;border-radius:8px;font-size:12px;line-height:1.6}.fdw-blocker{background:#fef2f2;color:#b91c1c}.fdw-ready{background:#f0fdf4;color:#166534}.fdw-ready.is-warning{background:#fffbeb;color:#92400e}.fdw-actions{display:flex;gap:8px;flex-wrap:wrap}.fdw-cell{display:grid;gap:3px;min-width:0}.fdw-cell span{color:var(--text-secondary);font-size:11px}.fdw-cell code{font-size:10px;color:var(--text-tertiary);overflow-wrap:anywhere}@media(max-width:980px){.fdw-grid{grid-template-columns:1fr}.fdw-select{grid-template-columns:1fr}}
</style>
