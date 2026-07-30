<template>
  <section class="gm-page">
    <header class="gm-hero">
      <div>
        <span class="gm-eyebrow">毕业设计材料中心</span>
        <h2>{{ batchStore.selectedBatchName || '当前批次' }}材料与归档</h2>
        <p>先处理扫描异常、缺材料和待审核，再冻结真实版本 Manifest 并生成 ZIP/XLSX 归档任务。</p>
      </div>
      <div class="gm-hero__actions">
        <button class="gm-btn" :disabled="loading" @click="loadAll">刷新</button>
        <button class="gm-btn gm-btn--primary" :disabled="!batchId || exporting" @click="createBatchExport">
          {{ exporting ? '正在生成…' : '生成批次 ZIP/XLSX' }}
        </button>
      </div>
    </header>

    <div v-if="error" class="gm-alert gm-alert--danger">
      <strong>材料中心加载失败</strong><span>{{ error }}</span><button @click="loadAll">重试</button>
    </div>
    <div v-else-if="!batchId" class="gm-alert">
      <strong>请先选择毕业设计批次</strong><span>顶部批次条选择后，系统才会按真实数据范围统计材料。</span>
    </div>

    <template v-else>
      <section class="gm-summary" aria-label="材料业务结论">
        <article v-for="card in summaryCards" :key="card.key" :class="['gm-summary__card', `is-${card.tone}`]">
          <span>{{ card.label }}</span><strong>{{ card.value }}</strong><small>{{ card.hint }}</small>
        </article>
      </section>

      <section class="gm-panel gm-filters">
        <label>关键词<input v-model.trim="filters.keyword" placeholder="姓名/学号/题目" @keyup.enter="search" /></label>
        <label>材料阶段
          <select v-model="filters.stage">
            <option value="">全部阶段</option><option value="TOPIC">题目</option><option value="TASKBOOK">任务书</option>
            <option value="PROPOSAL">开题</option><option value="GUIDANCE">指导</option><option value="MIDTERM">中期</option>
            <option value="FINAL_DRAFT">初稿</option><option value="FINAL_APPROVED">定稿与成果</option>
            <option value="PLAGIARISM">查重</option><option value="REVIEW">评阅</option>
            <option value="DEFENSE">答辩</option><option value="GRADE">成绩</option><option value="ARCHIVE">归档</option>
          </select>
        </label>
        <label>审核状态
          <select v-model="filters.reviewStatus"><option value="">全部</option><option value="PENDING">待审核</option><option value="RETURNED">已退回</option><option value="APPROVED">已通过</option></select>
        </label>
        <label>扫描状态
          <select v-model="filters.scanStatus"><option value="">全部</option><option value="PENDING">等待扫描</option><option value="RUNNING">扫描中</option><option value="ERROR">扫描失败</option><option value="INFECTED">感染</option><option value="CLEAN">安全可用</option></select>
        </label>
        <label>归档状态
          <select v-model="filters.archiveStatus"><option value="">全部</option><option value="ELIGIBLE">可归档</option><option value="FROZEN">已冻结</option><option value="ARCHIVED">已归档</option></select>
        </label>
        <label class="gm-check"><input v-model="missingOnly" type="checkbox" /> 只看缺材料</label>
        <div class="gm-filters__actions"><button class="gm-btn gm-btn--primary" @click="search">查询</button><button class="gm-btn" @click="resetFilters">重置</button></div>
      </section>

      <div class="gm-workspace">
        <section class="gm-panel gm-queue">
          <header><div><strong>学生材料队列</strong><span>共 {{ overview.total || 0 }} 人</span></div></header>
          <div v-if="loading" class="gm-state">正在按数据范围加载…</div>
          <div v-else-if="!overview.items?.length" class="gm-state">当前筛选下没有学生</div>
          <button v-for="student in overview.items || []" :key="student.gdStudentId" type="button"
            :class="['gm-student', { 'is-active': selectedId === student.gdStudentId }]" @click="selectStudent(student)">
            <span class="gm-student__name"><strong>{{ student.studentName }}</strong><small>{{ student.studentNo }}</small></span>
            <span class="gm-student__status">
              <b v-if="student.missingCount" class="is-danger">缺 {{ student.missingCount }}</b>
              <b v-if="student.pendingReviewCount" class="is-warning">待审 {{ student.pendingReviewCount }}</b>
              <b v-if="student.returnedCount" class="is-danger">退回 {{ student.returnedCount }}</b>
              <b v-if="student.archiveReady" class="is-success">可归档</b>
            </span>
            <small>{{ student.className || '未设置班级' }} · {{ student.advisorName || '未分配导师' }}</small>
          </button>
          <footer class="gm-pagination">
            <button class="gm-btn" :disabled="page <= 1" @click="changePage(page - 1)">上一页</button>
            <span>第 {{ page }} 页</span>
            <button class="gm-btn" :disabled="page * pageSize >= Number(overview.total || 0)" @click="changePage(page + 1)">下一页</button>
          </footer>
        </section>

        <section class="gm-panel gm-detail">
          <div v-if="libraryLoading" class="gm-state">正在加载学生材料版本…</div>
          <div v-else-if="!library" class="gm-state">从左侧选择学生，查看材料状态、当前版本和历史版本</div>
          <template v-else>
            <header class="gm-detail__head">
              <div><strong>{{ library.studentName }} · {{ library.studentNo }}</strong><span>{{ library.topicTitle || '未分配题目' }} · {{ library.advisorName || '未分配导师' }}</span></div>
              <div class="gm-detail__actions">
                <button class="gm-btn" @click="openStudentDetail">学生档案</button>
                <button class="gm-btn" @click="loadManifest">查看 Manifest</button>
                <button class="gm-btn gm-btn--primary" @click="freezeManifest">冻结当前版本</button>
              </div>
            </header>

            <section v-for="group in library.groups || []" :key="group.name" class="gm-group">
              <h3>{{ group.name }} <span>{{ group.items.length }} 项</span></h3>
              <article v-for="material in group.items" :key="material.materialId" class="gm-material">
                <header>
                  <div><strong>{{ material.materialName }}</strong><span>{{ material.materialCode }} · {{ material.required ? '必交' : '选交' }}</span></div>
                  <div class="gm-tags"><b :class="statusTone(material.businessStatus)">{{ statusText(material.businessStatus) }}</b><b>{{ material.reviewStatus }}</b><b>{{ material.archiveStatus }}</b></div>
                </header>
                <p v-if="material.rejectReason" class="gm-reject">退回原因：{{ material.rejectReason }}</p>
                <div class="gm-meta">
                  <span>Asset ID：{{ material.assetId || '-' }}</span><span>当前 FileVersion ID：{{ material.currentVersionId || '-' }}</span>
                  <span>审核人：{{ material.reviewer || '-' }}</span><span>审核时间：{{ material.reviewedAt || '-' }}</span>
                </div>
                <SecureFileList :items="normalizedFiles(material)" empty-text="当前尚未提交文件" @preview="previewFile" @download="downloadFile" @refresh="refreshLibrary" />
                <details v-if="material.versions?.length" class="gm-history">
                  <summary>历史版本（{{ material.versions.length }}）</summary>
                  <FileVersionTimeline :items="timelineItems(material)" @select="selectHistory" />
                </details>
                <div v-if="material.currentVersionId && material.reviewStatus === 'PENDING'" class="gm-review-actions">
                  <button class="gm-btn gm-btn--primary" @click="reviewMaterial(material, 'APPROVE')">通过当前版本</button>
                  <button class="gm-btn gm-btn--danger" @click="reviewMaterial(material, 'REJECT')">退回当前版本</button>
                </div>
              </article>
            </section>
          </template>
        </section>
      </div>

      <section class="gm-bottom-grid">
        <article class="gm-panel">
          <header class="gm-section-head"><div><strong>真实归档 Manifest</strong><span>冻结文件名、大小、SHA-256、扫描与审核结论</span></div></header>
          <div v-if="!manifest" class="gm-state">选择学生后点击“查看 Manifest”</div>
          <template v-else>
            <div class="gm-manifest-head"><b>revision {{ manifest.revision }}</b><span>{{ manifest.status }}</span><code>{{ manifest.manifestSha256 }}</code></div>
            <div class="gm-table-wrap"><table><thead><tr><th>材料</th><th>文件</th><th>版本</th><th>大小</th><th>SHA-256</th><th>扫描</th><th>审核</th></tr></thead>
              <tbody><tr v-for="item in manifest.items || []" :key="item.fileVersionId"><td>{{ item.materialCode }}</td><td>{{ item.fileName }}</td><td>{{ item.fileVersionId }}</td><td>{{ sizeText(item.sizeBytes) }}</td><td><code>{{ item.sha256 }}</code></td><td>{{ item.scanResult }}</td><td>{{ item.reviewStatus }}</td></tr></tbody>
            </table></div>
          </template>
        </article>

        <article class="gm-panel">
          <header class="gm-section-head"><div><strong>归档导出任务</strong><span>刷新后仍可查询，过期或撤销后不可下载</span></div></header>
          <div v-if="!exportJob" class="gm-state">尚未创建本次归档任务</div>
          <div v-else class="gm-job">
            <div><strong>{{ exportJob.status }}</strong><span>进度 {{ exportJob.progress }}% · {{ exportJob.rowCount }} 条材料</span></div>
            <code>{{ exportJob.result?.zipSha256 || '-' }}</code>
            <div><button class="gm-btn" @click="refreshJob">刷新状态</button><button class="gm-btn gm-btn--primary" :disabled="exportJob.status !== 'SUCCEEDED'" @click="downloadJob">下载 ZIP</button><button class="gm-btn gm-btn--danger" :disabled="['REVOKED','EXPIRED'].includes(exportJob.status)" @click="revokeJob">撤销任务</button></div>
          </div>
        </article>
      </section>

      <section class="gm-panel gm-templates">
        <header class="gm-section-head"><div><strong>模板资产与版本</strong><span>DOCX / PDF / XLSX / PPTX，更新模板只新增 FileVersion</span></div><button class="gm-btn" @click="loadTemplates">刷新模板</button></header>
        <div v-if="!templates.length" class="gm-state">当前批次尚未发布公共模板资产</div>
        <div v-else class="gm-table-wrap"><table><thead><tr><th>模板代码</th><th>模板名称</th><th>范围</th><th>状态</th><th>当前版本</th><th>历史版本</th></tr></thead>
          <tbody><tr v-for="item in templates" :key="item.policyId"><td><code>{{ item.templateCode }}</code></td><td>{{ item.templateName }}</td><td>{{ item.collegeId || '全校' }} / {{ item.majorId || '全部专业' }}</td><td>{{ item.status }}</td><td>{{ item.currentVersionId || '-' }}</td><td>{{ item.versions?.length || 0 }}</td></tr></tbody>
        </table></div>
      </section>
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useGraduationBatchStore } from '@/stores/graduationBatch'
import SecureFileList from '@/components/file/SecureFileList.vue'
import FileVersionTimeline from '@/components/file/FileVersionTimeline.vue'
import { normalizeFile } from '@/services/file/fileSdk'
import { graduationMaterialCenterApi as api } from '@/modules/graduation/api/graduation-material-center.api'

const router = useRouter()
const batchStore = useGraduationBatchStore()
const batchId = computed(() => batchStore.selectedBatchId)
const loading = ref(false); const libraryLoading = ref(false); const exporting = ref(false); const error = ref('')
const overview = ref({ summary: {}, items: [], total: 0 }); const library = ref(null); const manifest = ref(null)
const selectedId = ref(''); const templates = ref([]); const exportJob = ref(null)
const page = ref(1); const pageSize = 20; const missingOnly = ref(false)
const filters = reactive({ keyword: '', stage: '', reviewStatus: '', scanStatus: '', archiveStatus: '' })

const summaryCards = computed(() => {
  const s = overview.value.summary || {}
  return [
    ['expected', '应交学生', s.expectedStudents || 0, '当前数据范围', 'normal'],
    ['complete', '已齐全', s.completeStudents || 0, '无缺项与待处理', 'success'],
    ['missing', '缺材料', s.missingStudents || 0, '优先催交', 'danger'],
    ['scan', '安全异常', s.scanAbnormalStudents || 0, '不可审核或归档', 'danger'],
    ['pending', '待审核', s.pendingReviewStudents || 0, '逐版本处理', 'warning'],
    ['returned', '被退回', s.returnedStudents || 0, '等待学生重交', 'warning'],
    ['ready', '可归档', s.archiveReadyStudents || 0, '可冻结 Manifest', 'success'],
    ['archived', '已归档', s.archivedStudents || 0, '版本证据已冻结', 'normal']
  ].map(([key, label, value, hint, tone]) => ({ key, label, value, hint, tone }))
})

function params() { return { batchId: batchId.value, page: page.value, pageSize, keyword: filters.keyword, stage: filters.stage, reviewStatus: filters.reviewStatus, scanStatus: filters.scanStatus, archiveStatus: filters.archiveStatus, missingStatus: missingOnly.value ? 'MISSING' : '' } }
async function loadOverview() { if (!batchId.value) return; overview.value = await api.overview(params()) }
async function loadTemplates() { if (!batchId.value) return; const data = await api.templateCatalog(batchId.value); templates.value = data.items || [] }
async function loadAll() { loading.value = true; error.value = ''; try { await Promise.all([loadOverview(), loadTemplates()]); if (selectedId.value) await refreshLibrary() } catch (e) { error.value = e?.message || '材料中心加载失败' } finally { loading.value = false } }
async function selectStudent(student) { selectedId.value = String(student.gdStudentId); manifest.value = null; await refreshLibrary() }
async function refreshLibrary() { if (!selectedId.value) return; libraryLoading.value = true; try { library.value = await api.studentLibrary(selectedId.value, true) } catch (e) { error.value = e?.message || '学生材料加载失败' } finally { libraryLoading.value = false } }
function search() { page.value = 1; loadOverview() }
function resetFilters() { Object.assign(filters, { keyword: '', stage: '', reviewStatus: '', scanStatus: '', archiveStatus: '' }); missingOnly.value = false; search() }
function changePage(next) { page.value = next; loadOverview() }
function normalizedFiles(material) { return (material.currentVersion ? [material.currentVersion] : []).map(normalizeFile) }
function timelineItems(material) { return (material.versions || []).map(v => ({ bindingId: v.bindingId || v.fileVersionId, versionNo: v.versionNo, isCurrent: v.isCurrent, boundAt: v.submittedAt, file: normalizeFile(v) })) }
function selectHistory(item) { if (item?.file) previewFile(item.file) }
async function previewFile(item) { try { await api.previewMaterial(item) } catch (e) { error.value = e?.message || '文件暂不可预览' } }
async function downloadFile(item) { try { await api.downloadMaterial(item) } catch (e) { error.value = e?.message || '文件暂不可下载' } }
async function reviewMaterial(material, action) { let comment = ''; if (action === 'REJECT') { comment = window.prompt('请输入不少于5字的退回原因') || ''; if (comment.trim().length < 5) return } try { await api.reviewMaterial(material.materialId, { fileVersionId: material.currentVersionId, action, comment }); await Promise.all([refreshLibrary(), loadOverview()]) } catch (e) { error.value = e?.message || '审核失败' } }
async function loadManifest() { if (!selectedId.value) return; try { manifest.value = await api.manifest(selectedId.value) } catch (e) { error.value = e?.message || '尚未生成 Manifest' } }
async function freezeManifest() { if (!selectedId.value) return; const archiveNo = window.prompt('请输入归档批次号', `GDARCH-${batchId.value}`); if (!archiveNo) return; try { manifest.value = await api.freezeManifest(selectedId.value, archiveNo); await refreshLibrary() } catch (e) { error.value = e?.message || 'Manifest 冻结失败' } }
async function createBatchExport() { exporting.value = true; try { exportJob.value = await api.createExport({ batchId: batchId.value, scopeType: 'BATCH', scopeValue: '' }) } catch (e) { error.value = e?.message || '归档任务生成失败' } finally { exporting.value = false } }
async function refreshJob() { if (exportJob.value?.id) exportJob.value = await api.exportJob(exportJob.value.id) }
async function downloadJob() { try { await api.downloadExport(exportJob.value) } catch (e) { error.value = e?.message || '归档包不可下载' } }
async function revokeJob() { const reason = window.prompt('请输入不少于5字的撤销原因') || ''; if (reason.trim().length < 5) return; try { exportJob.value = await api.revokeExport(exportJob.value.id, exportJob.value.version, reason) } catch (e) { error.value = e?.message || '撤销失败' } }
function openStudentDetail() { if (selectedId.value) router.push(`/admin/graduation/students/${selectedId.value}`) }
function sizeText(value) { const n = Number(value || 0); return n >= 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)} MB` : n >= 1024 ? `${(n / 1024).toFixed(1)} KB` : `${n} B` }
function statusText(value) { return ({ MISSING: '缺失', SUBMITTED: '已提交', RETURNED: '已退回', APPROVED: '已通过', ARCHIVED: '已归档', SCANNING: '扫描中' })[value] || value || '未知' }
function statusTone(value) { return { 'is-danger': ['MISSING', 'RETURNED'].includes(value), 'is-warning': ['SUBMITTED', 'SCANNING'].includes(value), 'is-success': ['APPROVED', 'ARCHIVED'].includes(value) } }
watch(batchId, () => { page.value = 1; selectedId.value = ''; library.value = null; manifest.value = null; loadAll() })
onMounted(async () => { await batchStore.ensureLoaded(); await loadAll() })
</script>

<style scoped>
.gm-page { display: grid; gap: 16px; min-width: 0; }
.gm-hero, .gm-panel { background: #fff; border: 1px solid #dfe7f3; border-radius: 16px; }
.gm-hero { display: flex; justify-content: space-between; gap: 24px; padding: 22px 24px; background: linear-gradient(135deg,#f7fbff,#eef5ff); }
.gm-eyebrow { color: #1769e0; font-size: 12px; font-weight: 700; letter-spacing: .12em; }
.gm-hero h2 { margin: 6px 0; color: #18253a; }.gm-hero p,.gm-section-head span,.gm-student small,.gm-detail__head span { margin: 0; color: #69768b; }
.gm-hero__actions,.gm-detail__actions,.gm-review-actions,.gm-filters__actions,.gm-job>div:last-child { display:flex; gap:8px; flex-wrap:wrap; align-items:center; }
.gm-btn { border:1px solid #ccd8e8; background:#fff; color:#29415f; border-radius:9px; padding:8px 13px; cursor:pointer; }.gm-btn:disabled{opacity:.5;cursor:not-allowed}.gm-btn--primary{background:#1769e0;border-color:#1769e0;color:#fff}.gm-btn--danger{border-color:#fecaca;color:#b42318;background:#fff7f7}
.gm-summary { display:grid; grid-template-columns:repeat(8,minmax(110px,1fr)); gap:10px; }.gm-summary__card{display:grid;gap:5px;padding:15px;border:1px solid #e2e8f2;border-radius:13px;background:#fff}.gm-summary__card strong{font-size:25px}.gm-summary__card small{color:#7b8798}.gm-summary__card.is-danger strong{color:#c53030}.gm-summary__card.is-warning strong{color:#b7791f}.gm-summary__card.is-success strong{color:#17834a}
.gm-alert{display:flex;gap:12px;align-items:center;padding:14px 16px;border-radius:12px;background:#fff7e6;color:#7a4d00}.gm-alert--danger{background:#fff1f1;color:#a61b1b}.gm-alert button{margin-left:auto}
.gm-filters{padding:14px;display:grid;grid-template-columns:1.4fr repeat(4,1fr) auto auto;gap:10px;align-items:end}.gm-filters label{display:grid;gap:5px;color:#526176;font-size:13px}.gm-filters input,.gm-filters select{min-width:0;border:1px solid #ccd8e8;border-radius:8px;padding:8px;background:#fff}.gm-check{display:flex!important;align-items:center;gap:6px;padding-bottom:8px}
.gm-workspace{display:grid;grid-template-columns:minmax(260px,330px) minmax(0,1fr);gap:16px}.gm-queue,.gm-detail{min-width:0;overflow:hidden}.gm-queue>header,.gm-detail__head,.gm-section-head{display:flex;justify-content:space-between;gap:14px;align-items:center;padding:16px 18px;border-bottom:1px solid #edf1f7}.gm-queue>header div,.gm-section-head div,.gm-detail__head>div:first-child{display:grid;gap:4px}.gm-queue>header span{color:#7b8798;font-size:13px}
.gm-student{display:grid;width:100%;gap:7px;padding:14px 16px;border:0;border-bottom:1px solid #edf1f7;background:#fff;text-align:left;cursor:pointer}.gm-student:hover,.gm-student.is-active{background:#f1f7ff}.gm-student__name,.gm-student__status{display:flex;justify-content:space-between;gap:8px}.gm-student__status{justify-content:flex-start;flex-wrap:wrap}.gm-student__status b,.gm-tags b{font-size:12px;padding:2px 7px;border-radius:999px;background:#eef2f7;color:#526176}.is-danger{color:#b42318!important;background:#fff0f0!important}.is-warning{color:#9a5b00!important;background:#fff7df!important}.is-success{color:#137a43!important;background:#eafaf1!important}.gm-pagination{display:flex;justify-content:center;align-items:center;gap:10px;padding:12px}
.gm-detail{max-height:1200px;overflow:auto}.gm-group{padding:0 18px 18px}.gm-group h3{display:flex;justify-content:space-between;margin:18px 0 10px;color:#253550}.gm-group h3 span{font-size:12px;color:#7b8798}.gm-material{border:1px solid #e2e8f2;border-radius:12px;padding:14px;margin-bottom:12px}.gm-material>header{display:flex;justify-content:space-between;gap:10px;margin-bottom:10px}.gm-material>header>div:first-child{display:grid;gap:3px}.gm-material>header span,.gm-meta{color:#7b8798;font-size:12px}.gm-tags{display:flex;gap:5px;flex-wrap:wrap}.gm-meta{display:flex;gap:12px;flex-wrap:wrap;margin:8px 0}.gm-reject{padding:9px 11px;border-radius:8px;background:#fff3f3;color:#a61b1b}.gm-history{margin-top:10px}.gm-history summary{cursor:pointer;color:#1769e0;margin-bottom:10px}.gm-review-actions{margin-top:10px}
.gm-bottom-grid{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(300px,.6fr);gap:16px}.gm-manifest-head,.gm-job{display:grid;gap:10px;padding:16px}.gm-manifest-head code,.gm-job code,.gm-table-wrap code{font-size:11px;word-break:break-all}.gm-table-wrap{overflow:auto;padding:0 16px 16px}.gm-table-wrap table{width:100%;border-collapse:collapse;min-width:760px}.gm-table-wrap th,.gm-table-wrap td{padding:10px;border-bottom:1px solid #edf1f7;text-align:left;vertical-align:top;font-size:13px}.gm-table-wrap th{position:sticky;top:0;background:#f7f9fc;color:#526176}.gm-state{padding:30px;text-align:center;color:#7b8798}.gm-templates{overflow:hidden}
@media(max-width:1200px){.gm-summary{grid-template-columns:repeat(4,1fr)}.gm-filters{grid-template-columns:repeat(3,1fr)}.gm-workspace{grid-template-columns:1fr}.gm-queue{max-height:420px;overflow:auto}.gm-bottom-grid{grid-template-columns:1fr}}
@media(max-width:720px){.gm-hero{display:grid}.gm-summary{grid-template-columns:repeat(2,1fr)}.gm-filters{grid-template-columns:1fr}.gm-material>header,.gm-detail__head{display:grid}}
</style>
