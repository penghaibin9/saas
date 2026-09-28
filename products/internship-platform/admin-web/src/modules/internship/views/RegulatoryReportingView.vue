<template>
  <ModulePageShell
    title="监管上报"
    subtitle="生成、校验并导出两套实习监管数据；没有真实平台回执时只显示“待回执”。"
    role-name="实习管理员"
    data-scope-name="当前学校 / 当前批次"
    :watermark="false"
  >
    <template #actions>
      <AppButton variant="ghost" :disabled="loading" @click="load">刷新</AppButton>
    </template>

    <div class="reporting-stack">
      <section class="truth-banner" aria-label="外部联调状态">
        <div>
          <strong>外部监管平台：{{ externalReady ? '已装配真实回执适配器' : 'BLOCKED_EXTERNAL' }}</strong>
          <p v-if="!externalReady">当前可以完成模板、校验、错误行和正式 Excel；目标平台当年模板与真实回执仍需联调，系统不会伪造“上报成功”。</p>
          <p v-else>仍以真实平台返回的签名/回执为准，不允许人工直接标记 ACCEPTED。</p>
        </div>
        <AppStatusTag :type="externalReady ? 'success' : 'warning'">
          {{ externalReady ? '外部已联通' : '待外部联调' }}
        </AppStatusTag>
      </section>

      <section class="report-grid">
        <article v-for="report in reports" :key="report.code" class="report-card">
          <header>
            <div>
              <span class="eyebrow">{{ report.code }}</span>
              <h2>{{ report.title }}</h2>
            </div>
            <AppStatusTag :type="templateFor(report.code)?.officialVerified ? 'success' : 'warning'">
              {{ templateFor(report.code)?.officialVerified ? '正式模板已核验' : '采购字段基线' }}
            </AppStatusTag>
          </header>
          <p>{{ report.desc }}</p>
          <dl>
            <div><dt>模板版本</dt><dd>V{{ templateFor(report.code)?.versionNo || '—' }}</dd></div>
            <div><dt>字段数</dt><dd>{{ templateFor(report.code)?.fields?.length || 0 }}</dd></div>
            <div><dt>外部状态</dt><dd>{{ templateFor(report.code)?.externalReadiness || 'BLOCKED_EXTERNAL' }}</dd></div>
          </dl>
          <AppButton
            :disabled="!batchId || creatingCode === report.code"
            @click="createTask(report.code)"
          >
            {{ creatingCode === report.code ? '正在生成…' : '按当前批次生成任务' }}
          </AppButton>
        </article>
      </section>

      <div v-if="!batchId" class="notice is-warning" role="status">
        请先在顶部选择一个实习批次，再生成监管上报任务。
      </div>

      <LoadingState v-if="loading" />
      <ErrorState v-else-if="error" :description="error" @retry="load" />

      <section v-else class="task-section" aria-labelledby="reg-task-title">
        <header class="section-head">
          <div>
            <h2 id="reg-task-title">上报任务</h2>
            <p>任务冻结生成时的业务事实；业务数据修正后请新建任务，不覆盖历史快照。</p>
          </div>
        </header>

        <DataTable
          v-if="tasks.length"
          :columns="columns"
          :rows="tasks"
          row-key="id"
        >
          <template #cell-reportCode="{ row }">
            <strong>{{ row.reportCode }}</strong>
          </template>
          <template #cell-status="{ row }">
            <AppStatusTag :type="statusType(row.status)">{{ statusLabel(row.status) }}</AppStatusTag>
          </template>
          <template #cell-counts="{ row }">
            <span>{{ row.validRows || 0 }} 通过 / {{ row.errorRows || 0 }} 错误 / {{ row.totalRows || 0 }} 总行</span>
          </template>
          <template #cell-external="{ row }">
            <span v-if="row.status === 'RECEIPT_PENDING'">待真实平台回执</span>
            <span v-else-if="row.status === 'ACCEPTED'">真实回执：已接收</span>
            <span v-else-if="row.status === 'REJECTED'">真实回执：已拒绝</span>
            <span v-else>—</span>
          </template>
          <template #cell-actions="{ row }">
            <div class="actions">
              <AppButton
                v-if="row.status === 'GENERATED'"
                size="sm"
                variant="secondary"
                :disabled="busyId === row.id"
                @click="validate(row)"
              >校验</AppButton>
              <AppButton
                v-if="row.errorRows > 0"
                size="sm"
                variant="ghost"
                :disabled="busyId === row.id"
                @click="downloadErrors(row)"
              >错误 Excel</AppButton>
              <AppButton
                v-if="['VALIDATED', 'EXPORTED'].includes(row.status)"
                size="sm"
                :disabled="busyId === row.id"
                @click="exportFormal(row)"
              >正式 Excel</AppButton>
              <AppButton
                v-if="row.status === 'EXPORTED'"
                size="sm"
                variant="secondary"
                :disabled="busyId === row.id"
                @click="openSubmission(row)"
              >登记外部提交</AppButton>
            </div>
          </template>
        </DataTable>

        <div v-else class="empty">当前批次还没有监管上报任务。</div>
      </section>

      <section v-if="submissionTask" class="submission-panel" aria-labelledby="submission-title">
        <div>
          <h2 id="submission-title">登记真实外部提交</h2>
          <p>只填写目标平台实际产生的任务号/提交凭据。保存后状态直接进入“待回执”，不会显示“成功”。</p>
        </div>
        <label>
          <span>外部提交凭据</span>
          <input
            v-model.trim="submissionRef"
            maxlength="200"
            placeholder="例如：目标平台返回的任务号"
          />
        </label>
        <div class="submission-actions">
          <AppButton variant="ghost" @click="closeSubmission">取消</AppButton>
          <AppButton
            :disabled="!submissionRef || busyId === submissionTask.id"
            @click="submitExternal"
          >确认已真实提交</AppButton>
        </div>
      </section>

      <div v-if="message" class="notice" :class="{ 'is-error': messageType === 'error' }" role="status">
        {{ message }}
      </div>
    </div>
  </ModulePageShell>
</template>

<script>
import { DataTable, ErrorState, LoadingState, ModulePageShell } from '@/components/business'
import { AppStatusTag } from '@/components/common'
import { AppButton } from '@/components/ui'
import { regulatoryReportingApi } from '@/modules/internship/api/regulatoryReporting.api'
import { useInternshipBatchStore } from '@/stores/internshipBatch'

export default {
  name: 'RegulatoryReportingView',
  components: { ModulePageShell, DataTable, ErrorState, LoadingState, AppStatusTag, AppButton },
  data() {
    return {
      reports: [
        {
          code: 'RP01',
          title: '职业学校学生实习监管上报',
          desc: '按学生实习事实生成教育主管部门监管字段，包含企业、地点、保险、协议、专业对口与备案等信息。'
        },
        {
          code: 'RP02',
          title: '人才培养工作状态数据上报',
          desc: '生成专业、班级、岗位、指导教师、企业导师、报酬、保险和跨省/境外实习等状态数据。'
        }
      ],
      columns: [
        { key: 'taskNo', title: '任务号', width: '220px' },
        { key: 'reportCode', title: '类型', width: '80px' },
        { key: 'status', title: '状态', width: '120px' },
        { key: 'counts', title: '校验结果', width: '210px' },
        { key: 'external', title: '外部回执', width: '150px' },
        { key: 'actions', title: '操作', width: '330px' }
      ],
      templates: [],
      tasks: [],
      loading: false,
      error: '',
      message: '',
      messageType: '',
      busyId: '',
      creatingCode: '',
      submissionTask: null,
      submissionRef: ''
    }
  },
  computed: {
    batchStore() { return useInternshipBatchStore() },
    batchId() { return this.batchStore.selectedBatchId || '' },
    externalReady() {
      return this.tasks.some(item => item.externalReadiness === 'READY')
    }
  },
  watch: {
    'batchStore.selectedBatchId'() {
      this.closeSubmission()
      this.load()
    }
  },
  created() {
    this.load()
  },
  methods: {
    templateFor(code) {
      return this.templates.find(item => item.reportCode === code && item.status === 'ACTIVE')
        || this.templates.find(item => item.reportCode === code)
    },
    statusLabel(status) {
      return {
        GENERATED: '已生成待校验',
        VALIDATED: '校验通过',
        EXPORTED: '已导出',
        SUBMITTED_EXTERNAL: '已提交外部',
        RECEIPT_PENDING: '待真实回执',
        ACCEPTED: '真实回执已接收',
        REJECTED: '真实回执已拒绝'
      }[status] || status || '—'
    },
    statusType(status) {
      if (status === 'ACCEPTED') return 'success'
      if (status === 'REJECTED') return 'danger'
      if (status === 'RECEIPT_PENDING') return 'warning'
      return 'default'
    },
    showMessage(text, type = '') {
      this.message = text || ''
      this.messageType = type
    },
    async load() {
      this.loading = true
      this.error = ''
      this.message = ''
      const [templates, tasks] = await Promise.all([
        regulatoryReportingApi.listTemplates(),
        this.batchId
          ? regulatoryReportingApi.listTasks({ batchId: this.batchId })
          : Promise.resolve({ code: 0, data: [] })
      ])
      this.loading = false
      if (templates.code !== 0) {
        this.error = templates.message || '模板加载失败'
        return
      }
      if (tasks.code !== 0) {
        this.error = tasks.message || '任务加载失败'
        return
      }
      this.templates = templates.data || []
      this.tasks = tasks.data || []
    },
    async createTask(reportCode) {
      if (!this.batchId) return
      this.creatingCode = reportCode
      this.showMessage('')
      const res = await regulatoryReportingApi.createTask(reportCode, this.batchId)
      this.creatingCode = ''
      if (res.code !== 0) {
        this.showMessage(res.message || '任务生成失败', 'error')
        return
      }
      this.showMessage('任务已生成。下一步执行校验；缺字段会进入错误 Excel，不会用假值补齐。')
      await this.load()
    },
    async validate(row) {
      this.busyId = row.id
      this.showMessage('')
      const res = await regulatoryReportingApi.validateTask(row.id)
      this.busyId = ''
      if (res.code !== 0) {
        this.showMessage(res.message || '校验失败', 'error')
        return
      }
      const result = res.data || {}
      this.showMessage(
        result.validationPassed
          ? '全部数据校验通过，可以生成正式上报 Excel。'
          : `发现 ${result.errorRows || 0} 行错误，请下载错误 Excel 并回到正式业务数据中修正后重新生成任务。`,
        result.validationPassed ? '' : 'error'
      )
      await this.load()
    },
    async downloadErrors(row) {
      this.busyId = row.id
      const res = await regulatoryReportingApi.downloadErrors(row)
      this.busyId = ''
      if (res.code !== 0) this.showMessage(res.message || '错误 Excel 下载失败', 'error')
    },
    async exportFormal(row) {
      this.busyId = row.id
      const res = await regulatoryReportingApi.exportFormal(row)
      this.busyId = ''
      if (res.code !== 0) {
        this.showMessage(res.message || '正式 Excel 生成失败', 'error')
        return
      }
      this.showMessage('正式上报 Excel 已生成并下载，系统已记录文件 SHA-256 与导出审计。')
      await this.load()
    },
    openSubmission(row) {
      this.submissionTask = row
      this.submissionRef = ''
      this.showMessage('')
    },
    closeSubmission() {
      this.submissionTask = null
      this.submissionRef = ''
    },
    async submitExternal() {
      if (!this.submissionTask || !this.submissionRef) return
      const task = this.submissionTask
      this.busyId = task.id
      const res = await regulatoryReportingApi.markSubmitted(task.id, this.submissionRef)
      this.busyId = ''
      if (res.code !== 0) {
        this.showMessage(res.message || '外部提交登记失败', 'error')
        return
      }
      this.closeSubmission()
      this.showMessage('已登记真实外部提交。当前状态为“待真实回执”，不会显示“上报成功”。')
      await this.load()
    }
  }
}
</script>

<style scoped>
.reporting-stack { display: grid; gap: 18px; }
.truth-banner, .submission-panel { display: flex; justify-content: space-between; gap: 18px; align-items: flex-start; padding: 18px; border: 1px solid var(--border-base); border-radius: 12px; background: var(--bg-card); }
.truth-banner strong { color: var(--text-primary); }
.truth-banner p, .submission-panel p, .section-head p, .report-card p { margin: 6px 0 0; color: var(--text-secondary); font-size: 13px; line-height: 1.65; }
.report-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.report-card { display: grid; gap: 16px; padding: 18px; border: 1px solid var(--border-base); border-radius: 12px; background: var(--bg-card); }
.report-card header { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
.eyebrow { font-size: 12px; color: var(--text-secondary); }
h2 { margin: 4px 0 0; font-size: 17px; color: var(--text-primary); }
.report-card dl { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); margin: 0; border-top: 1px solid var(--border-base); border-bottom: 1px solid var(--border-base); }
.report-card dl > div { padding: 12px 8px; }
.report-card dt { color: var(--text-secondary); font-size: 12px; }
.report-card dd { margin: 5px 0 0; font-size: 13px; word-break: break-word; }
.task-section { overflow: hidden; border: 1px solid var(--border-base); border-radius: 12px; background: var(--bg-card); }
.section-head { padding: 18px; }
.actions { display: flex; flex-wrap: wrap; gap: 6px; }
.empty, .notice { padding: 18px; color: var(--text-secondary); }
.notice { border: 1px solid var(--border-base); border-radius: 10px; background: var(--bg-card); }
.notice.is-warning { color: #8a5b00; }
.notice.is-error { color: #a61b1b; }
.submission-panel { display: grid; grid-template-columns: minmax(260px, 1fr) minmax(260px, 1fr) auto; align-items: end; }
.submission-panel label { display: grid; gap: 7px; font-size: 12px; color: var(--text-secondary); }
.submission-panel input { height: 38px; padding: 0 10px; border: 1px solid var(--border-base); border-radius: 7px; background: var(--bg-card); color: var(--text-primary); }
.submission-actions { display: flex; gap: 8px; }
@media (max-width: 980px) {
  .report-grid { grid-template-columns: 1fr; }
  .submission-panel { grid-template-columns: 1fr; }
}
</style>
