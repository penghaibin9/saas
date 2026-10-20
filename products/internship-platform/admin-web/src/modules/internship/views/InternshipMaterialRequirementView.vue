<template>
  <div class="mr-page">
    <header class="mr-head">
      <div>
        <p class="mr-eyebrow">岗位实习 · 材料收件配置</p>
        <h1>自定义材料收件要求</h1>
        <p>不改代码新增材料类型、模板版本和必交人群；学生提交继续走现有文件扫描与版本中心。</p>
      </div>
      <div class="mr-head-actions">
        <button type="button" class="ghost" @click="$router.push('/admin/internship/material-center')">材料与证据中心</button>
        <button type="button" class="primary" :disabled="!batchId || saving" @click="openCreate">新建收件要求</button>
      </div>
    </header>

    <section class="mr-context">
      <label>
        <span>当前实习批次</span>
        <select :value="batchId" :disabled="loading || saving" @change="changeBatch">
          <option value="">请选择批次</option>
          <option v-for="batch in batches" :key="batch.id" :value="String(batch.id)">
            {{ batch.batchName }} · {{ batch.status }}
          </option>
        </select>
      </label>
      <label>
        <span>状态</span>
        <select v-model="status" :disabled="loading || saving" @change="load">
          <option value="ALL">全部</option>
          <option value="DRAFT">草稿</option>
          <option value="PUBLISHED">已发布</option>
          <option value="CLOSED">已关闭</option>
        </select>
      </label>
      <button type="button" class="ghost" :disabled="loading" @click="load">刷新</button>
    </section>

    <p v-if="error" class="mr-error" role="alert">{{ error }}</p>
    <p v-if="loading" class="mr-state">正在读取收件要求…</p>
    <p v-else-if="batchId && !rows.length" class="mr-state">当前批次还没有收件要求。点击“新建收件要求”即可新增，无需改代码。</p>
    <p v-else-if="!batchId" class="mr-state">请先选择实习批次。</p>

    <section v-else class="mr-grid">
      <article v-for="row in rows" :key="row.id" class="mr-card">
        <div class="mr-card-head">
          <div>
            <strong>{{ row.materialName }}</strong>
            <span>{{ row.materialCode }} · {{ row.isRequired ? '必交' : '选交' }}</span>
          </div>
          <span class="mr-status" :class="'is-' + row.status.toLowerCase()">{{ statusText(row.status) }}</span>
        </div>
        <p v-if="row.description" class="mr-desc">{{ row.description }}</p>
        <dl class="mr-facts">
          <div><dt>必交人群</dt><dd>{{ audienceText(row) }}</dd></div>
          <div><dt>允许格式</dt><dd>{{ (row.allowedExtensions || []).join(' / ') || '未限制' }}</dd></div>
          <div><dt>数量</dt><dd>{{ row.minFiles }}～{{ row.maxFiles }} 份</dd></div>
          <div><dt>截止时间</dt><dd>{{ row.dueAt ? fmt(row.dueAt) : '未设置' }}</dd></div>
        </dl>

        <div class="mr-template">
          <div>
            <span class="mr-label">当前模板</span>
            <strong>{{ row.template?.fileName || '尚未上传' }}</strong>
            <small v-if="row.template">V{{ row.template.versionNo }} · SHA-256 {{ shortHash(row.template.sha256) }}</small>
          </div>
          <label class="upload">
            {{ templateBusyId === row.id ? '上传中…' : (row.template ? '上传新版本' : '上传模板') }}
            <input type="file" :disabled="templateBusyId === row.id || saving" @change="pickTemplate($event, row)" />
          </label>
        </div>

        <div v-if="row.coverage" class="mr-coverage">
          <div><strong>{{ row.coverage.requiredStudents }}</strong><span>应交</span></div>
          <div><strong>{{ row.coverage.effectiveSubmittedStudents }}</strong><span>已交</span></div>
          <div class="danger"><strong>{{ row.coverage.missingStudents }}</strong><span>缺交/待重交</span></div>
          <div><strong>{{ row.coverage.pendingReviewStudents }}</strong><span>待审核</span></div>
        </div>

        <div class="mr-actions">
          <button type="button" class="ghost" :disabled="coverageBusyId === row.id" @click="loadCoverage(row)">
            {{ coverageBusyId === row.id ? '统计中…' : '刷新已交/缺交' }}
          </button>
          <button type="button" class="ghost" @click="openStudents(row, 'MISSING')">查看缺交</button>
          <button v-if="row.status === 'DRAFT'" type="button" class="primary" :disabled="saving || !row.template" @click="publish(row)">发布</button>
        </div>
      </article>
    </section>

    <div v-if="form.visible" class="mr-modal" role="presentation" @click.self="closeCreate">
      <section class="mr-dialog" role="dialog" aria-modal="true" aria-label="新建材料收件要求">
        <header><div><h2>新建收件要求</h2><p>先定义业务要求，再上传模板版本并发布。</p></div><button type="button" class="icon" @click="closeCreate">×</button></header>
        <div class="mr-form">
          <label><span>材料编码 *</span><input v-model.trim="form.materialCode" maxlength="80" placeholder="例如 ENTERPRISE_ACCEPTANCE" /></label>
          <label><span>材料名称 *</span><input v-model.trim="form.materialName" maxlength="200" placeholder="例如 企业接收函" /></label>
          <label class="wide"><span>说明</span><textarea v-model="form.description" maxlength="1000" placeholder="告诉学生需要提交什么、注意什么" /></label>
          <label><span>必交人群</span><select v-model="form.audienceType"><option value="ALL">本批次全部学生</option><option value="SELECTED_STUDENTS">指定学生</option><option value="FILTERED">按组织范围</option></select></label>
          <label><span>必交</span><select v-model="form.isRequired"><option :value="true">是</option><option :value="false">否</option></select></label>
          <label><span>允许格式 *</span><input v-model.trim="form.allowedExtensions" placeholder="pdf,docx,jpg,png" /></label>
          <label><span>最少文件数</span><input v-model.number="form.minFiles" type="number" min="0" max="20" /></label>
          <label><span>最多文件数</span><input v-model.number="form.maxFiles" type="number" min="1" max="20" /></label>
          <label><span>截止时间</span><input v-model="form.dueAt" type="datetime-local" /></label>
          <label v-if="form.audienceType === 'SELECTED_STUDENTS'" class="wide"><span>学生ID</span><input v-model.trim="form.studentIds" placeholder="多个学生ID用英文逗号分隔" /></label>
          <template v-if="form.audienceType === 'FILTERED'">
            <label><span>学院ID</span><input v-model.trim="form.collegeIds" placeholder="逗号分隔" /></label>
            <label><span>专业ID</span><input v-model.trim="form.majorIds" placeholder="逗号分隔" /></label>
            <label><span>班级ID</span><input v-model.trim="form.classIds" placeholder="逗号分隔" /></label>
          </template>
        </div>
        <p v-if="form.error" class="mr-error">{{ form.error }}</p>
        <footer><button type="button" class="ghost" :disabled="saving" @click="closeCreate">取消</button><button type="button" class="primary" :disabled="saving" @click="create">{{ saving ? '创建中…' : '创建草稿' }}</button></footer>
      </section>
    </div>

    <div v-if="students.visible" class="mr-modal" role="presentation" @click.self="closeStudents">
      <section class="mr-dialog mr-students" role="dialog" aria-modal="true" aria-label="材料学生名单">
        <header><div><h2>{{ students.requirement?.materialName }} · {{ students.state === 'MISSING' ? '缺交名单' : '学生名单' }}</h2><p>名单按服务端完整应交人群计算，与当前列表分页无关。</p></div><button type="button" class="icon" @click="closeStudents">×</button></header>
        <div class="mr-search"><input v-model.trim="students.keyword" placeholder="搜索姓名/学号/企业" @keyup.enter="loadStudents(true)" /><button type="button" class="ghost" @click="loadStudents(true)">搜索</button></div>
        <p v-if="students.loading" class="mr-state">正在读取名单…</p>
        <p v-else-if="!students.rows.length" class="mr-state">当前没有符合条件的学生。</p>
        <table v-else>
          <thead><tr><th>学生</th><th>企业</th><th>状态</th><th>文件版本</th></tr></thead>
          <tbody><tr v-for="item in students.rows" :key="item.internshipId"><td><strong>{{ item.studentName }}</strong><small>{{ item.studentNo }}</small></td><td>{{ item.enterpriseName || '—' }}</td><td>{{ item.submission?.statusLabel || '未提交' }}</td><td>{{ (item.submission?.files || []).map(f => 'V' + f.versionNo).join(' / ') || '—' }}</td></tr></tbody>
        </table>
        <footer><button type="button" class="ghost" @click="closeStudents">关闭</button><button v-if="students.hasMore" type="button" class="primary" :disabled="students.loading" @click="loadStudents(false)">加载更多</button></footer>
      </section>
    </div>
  </div>
</template>

<script>
import { internshipMaterialCenterApi } from '@/modules/internship/api/material-center.api'
import { useInternshipBatchStore } from '@/stores/internshipBatch'

const emptyForm = () => ({
  visible: false, error: '', materialCode: '', materialName: '', description: '',
  audienceType: 'ALL', isRequired: true, allowedExtensions: 'pdf,docx,jpg,png',
  minFiles: 1, maxFiles: 1, dueAt: '', studentIds: '', collegeIds: '', majorIds: '', classIds: ''
})
const ids = (value) => String(value || '').split(',').map(v => Number(v.trim())).filter(v => Number.isInteger(v) && v > 0)

export default {
  name: 'InternshipMaterialRequirementView',
  data() {
    return {
      rows: [], loading: false, saving: false, error: '', status: 'ALL',
      templateBusyId: '', coverageBusyId: '', form: emptyForm(),
      students: { visible: false, requirement: null, state: 'ALL', keyword: '', page: 1, rows: [], hasMore: false, loading: false }
    }
  },
  computed: {
    batchStore() { return useInternshipBatchStore() },
    batchId() { return String(this.batchStore.selectedBatchId || '') },
    batches() { return this.batchStore.availableBatches || [] }
  },
  async mounted() {
    await this.batchStore.ensureLoaded({ batchIdFromUrl: String(this.$route.query.batchId || '') })
    await this.load()
  },
  methods: {
    fmt(value) { return String(value || '').slice(0, 16).replace('T', ' ') },
    shortHash(value) { const text = String(value || ''); return text ? text.slice(0, 12) + '…' : '—' },
    statusText(value) { return ({ DRAFT: '草稿', PUBLISHED: '已发布', CLOSED: '已关闭' })[value] || value },
    audienceText(row) {
      if (row.audienceType === 'ALL') return '本批次全部学生'
      if (row.audienceType === 'SELECTED_STUDENTS') return `指定学生 ${(row.audienceFilter?.studentIds || []).length} 人`
      return '按组织范围'
    },
    async changeBatch(event) {
      this.batchStore.selectBatch(event.target.value)
      await this.$router.replace({ path: this.$route.path, query: this.batchStore.withBatchQuery() })
      await this.load()
    },
    async load() {
      this.error = ''; this.rows = []
      if (!this.batchId) return
      this.loading = true
      try {
        this.rows = await internshipMaterialCenterApi.requirements({ batchId: this.batchId, status: this.status }) || []
      } catch (e) { this.error = e?.message || '收件要求加载失败' }
      finally { this.loading = false }
    },
    openCreate() { this.form = { ...emptyForm(), visible: true } },
    closeCreate() { if (!this.saving) this.form = emptyForm() },
    async create() {
      const f = this.form
      if (!/^[A-Za-z0-9][A-Za-z0-9_-]{1,79}$/.test(f.materialCode)) return (f.error = '材料编码需为2-80位字母、数字、下划线或短横线')
      if (String(f.materialName || '').trim().length < 2) return (f.error = '请填写材料名称')
      if (Number(f.minFiles) < 0 || Number(f.maxFiles) < 1 || Number(f.minFiles) > Number(f.maxFiles)) return (f.error = '文件数量范围不合法')
      const audienceFilter = f.audienceType === 'SELECTED_STUDENTS'
        ? { studentIds: ids(f.studentIds) }
        : f.audienceType === 'FILTERED'
          ? { collegeIds: ids(f.collegeIds), majorIds: ids(f.majorIds), classIds: ids(f.classIds) }
          : {}
      if (f.audienceType !== 'ALL' && !Object.values(audienceFilter).some(v => v.length)) return (f.error = '请填写必交人群范围')
      this.saving = true; f.error = ''
      try {
        await internshipMaterialCenterApi.createRequirement({
          batchId: this.batchId,
          materialCode: f.materialCode.toUpperCase(),
          materialName: f.materialName,
          description: f.description,
          isRequired: f.isRequired,
          audienceType: f.audienceType,
          audienceFilter,
          allowedExtensions: f.allowedExtensions.split(',').map(v => v.trim()).filter(Boolean),
          minFiles: Number(f.minFiles),
          maxFiles: Number(f.maxFiles),
          dueAt: f.dueAt || null
        })
        this.form = emptyForm()
        await this.load()
      } catch (e) { f.error = e?.message || '创建收件要求失败' }
      finally { this.saving = false }
    },
    async pickTemplate(event, row) {
      const file = event.target.files?.[0]; event.target.value = ''
      if (!file || this.templateBusyId) return
      this.templateBusyId = row.id; this.error = ''
      try {
        const task = internshipMaterialCenterApi.uploadRequirementTemplate(file)
        const uploaded = await task.promise
        if (!uploaded?.fileId) throw new Error('上传结果缺少文件编号')
        await internshipMaterialCenterApi.attachRequirementTemplate(row.id, uploaded.fileId)
        await this.load()
      } catch (e) { this.error = e?.message || '模板上传失败' }
      finally { this.templateBusyId = '' }
    },
    async publish(row) {
      if (this.saving || !row.template) return
      this.saving = true; this.error = ''
      try { await internshipMaterialCenterApi.publishRequirement(row.id); await this.load() }
      catch (e) { this.error = e?.message || '发布失败' }
      finally { this.saving = false }
    },
    async loadCoverage(row) {
      if (this.coverageBusyId) return
      this.coverageBusyId = row.id
      try {
        row.coverage = await internshipMaterialCenterApi.requirementCoverage(row.id)
        this.rows = [...this.rows]
      } catch (e) { this.error = e?.message || '统计加载失败' }
      finally { this.coverageBusyId = '' }
    },
    openStudents(row, state) {
      this.students = { visible: true, requirement: row, state, keyword: '', page: 1, rows: [], hasMore: false, loading: false }
      this.loadStudents(true)
    },
    closeStudents() { this.students = { visible: false, requirement: null, state: 'ALL', keyword: '', page: 1, rows: [], hasMore: false, loading: false } },
    async loadStudents(reset) {
      const s = this.students
      if (!s.visible || !s.requirement || s.loading) return
      s.loading = true
      try {
        const page = reset ? 1 : s.page + 1
        const data = await internshipMaterialCenterApi.requirementStudents(s.requirement.id, {
          state: s.state, page, pageSize: 50, keyword: s.keyword || undefined
        })
        s.rows = reset ? (data?.list || data?.items || []) : [...s.rows, ...(data?.list || data?.items || [])]
        s.page = page
        s.hasMore = !!data?.hasMore
      } catch (e) { this.error = e?.message || '学生名单加载失败' }
      finally { s.loading = false }
    }
  }
}
</script>

<style scoped>
.mr-page{padding:24px;max-width:1440px;margin:0 auto;color:#1f2937}.mr-head{display:flex;align-items:flex-start;justify-content:space-between;gap:24px;margin-bottom:18px}.mr-head h1{margin:3px 0 6px;font-size:26px}.mr-head p{margin:0;color:#64748b;font-size:13px}.mr-eyebrow{color:#2563eb!important;font-weight:700;letter-spacing:.04em}.mr-head-actions,.mr-actions,.mr-search,footer{display:flex;gap:10px;align-items:center}.mr-context{display:flex;align-items:flex-end;gap:12px;padding:14px;border:1px solid #dbe5f1;border-radius:12px;background:#fff;margin-bottom:16px}.mr-context label{display:flex;flex-direction:column;gap:6px;min-width:220px}.mr-context span,.mr-label{font-size:11px;color:#64748b}.mr-context select,input,textarea,.mr-form select{box-sizing:border-box;border:1px solid #cbd8e6;border-radius:8px;padding:9px 10px;background:#fff;color:#1f2937}.primary,.ghost,.upload{min-height:38px;padding:0 14px;border-radius:8px;font-size:13px;cursor:pointer}.primary{border:1px solid #2563eb;background:#2563eb;color:#fff}.ghost,.upload{border:1px solid #cbd8e6;background:#fff;color:#1d4ed8}.primary:disabled,.ghost:disabled{opacity:.5;cursor:not-allowed}.mr-error{padding:10px 12px;border-radius:8px;background:#fef2f2;color:#b91c1c}.mr-state{padding:28px;border:1px dashed #cbd8e6;border-radius:12px;text-align:center;color:#64748b;background:#fff}.mr-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:14px}.mr-card{padding:16px;border:1px solid #dbe5f1;border-radius:12px;background:#fff;box-shadow:0 2px 8px rgba(15,23,42,.04)}.mr-card-head,.mr-template{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}.mr-card-head strong,.mr-template strong{display:block}.mr-card-head span,.mr-template small{display:block;margin-top:4px;font-size:11px;color:#64748b}.mr-status{padding:4px 8px!important;border-radius:999px;background:#f1f5f9;color:#475569!important}.mr-status.is-published{background:#ecfdf5;color:#047857!important}.mr-status.is-draft{background:#fff7ed;color:#c2410c!important}.mr-desc{font-size:13px;color:#475569}.mr-facts{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:12px 0}.mr-facts div{padding:9px;border-radius:8px;background:#f8fafc}.mr-facts dt{font-size:10px;color:#64748b}.mr-facts dd{margin:4px 0 0;font-size:12px;font-weight:600}.mr-template{padding:10px;border:1px solid #e2e8f0;border-radius:8px}.upload{display:flex;align-items:center;position:relative;overflow:hidden}.upload input{position:absolute;inset:0;opacity:0;cursor:pointer}.mr-coverage{display:grid;grid-template-columns:repeat(4,1fr);margin-top:12px;border-radius:8px;overflow:hidden;background:#f8fafc}.mr-coverage div{padding:10px;text-align:center;border-left:1px solid #e2e8f0}.mr-coverage div:first-child{border-left:0}.mr-coverage strong,.mr-coverage span{display:block}.mr-coverage strong{font-size:20px}.mr-coverage span{font-size:10px;color:#64748b}.mr-coverage .danger strong{color:#dc2626}.mr-actions{margin-top:12px;justify-content:flex-end}.mr-modal{position:fixed;inset:0;z-index:2000;display:flex;align-items:center;justify-content:center;padding:24px;background:rgba(15,23,42,.48)}.mr-dialog{width:min(760px,100%);max-height:88vh;overflow:auto;border-radius:14px;background:#fff;box-shadow:0 28px 80px rgba(15,23,42,.28)}.mr-dialog>header{display:flex;align-items:flex-start;justify-content:space-between;padding:18px 20px;border-bottom:1px solid #e2e8f0}.mr-dialog h2{margin:0 0 4px}.mr-dialog header p{margin:0;color:#64748b;font-size:12px}.icon{border:0;background:transparent;font-size:24px;cursor:pointer}.mr-form{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:18px 20px}.mr-form label{display:flex;flex-direction:column;gap:6px}.mr-form label span{font-size:12px;color:#475569;font-weight:600}.mr-form .wide{grid-column:1/-1}.mr-form textarea{min-height:90px;resize:vertical}.mr-dialog>footer{justify-content:flex-end;padding:14px 20px;border-top:1px solid #e2e8f0}.mr-students{width:min(980px,100%)}.mr-search{padding:14px 20px}.mr-search input{flex:1}.mr-students table{width:calc(100% - 40px);margin:0 20px 16px;border-collapse:collapse}.mr-students th,.mr-students td{padding:10px;border-bottom:1px solid #e2e8f0;text-align:left;font-size:12px}.mr-students td small{display:block;margin-top:3px;color:#64748b}@media(max-width:800px){.mr-head,.mr-context{flex-direction:column;align-items:stretch}.mr-grid,.mr-form{grid-template-columns:1fr}.mr-form .wide{grid-column:auto}}
</style>
