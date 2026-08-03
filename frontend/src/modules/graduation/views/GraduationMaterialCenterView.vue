<template>
  <section class="mc-page">
    <header class="mc-hero">
      <div><span>毕业设计材料中心</span><h2>{{ batchStore.selectedBatchName || '当前批次' }}</h2><p>统一查看真实材料、完整性、待审核与文件安全异常。</p></div>
      <button type="button" :disabled="loading" @click="load">{{ loading ? '刷新中…' : '刷新数据' }}</button>
    </header>

    <div v-if="error" class="mc-error"><strong>加载失败</strong><span>{{ error }}</span><button type="button" @click="load">重试</button></div>
    <div v-else-if="!batchId" class="mc-empty">请先在顶部选择毕业设计批次。</div>
    <template v-else>
      <section class="mc-summary">
        <article v-for="card in cards" :key="card.label"><span>{{ card.label }}</span><strong>{{ card.value }}</strong><small>{{ card.hint }}</small></article>
      </section>

      <nav class="mc-tabs" aria-label="材料视图">
        <button v-for="item in tabs" :key="item.key" type="button" :class="{ active: tab === item.key }" @click="changeTab(item.key)">{{ item.label }}</button>
      </nav>

      <section class="mc-filters">
        <label>关键词<input v-model.trim="filters.keyword" placeholder="姓名、学号、题目或文件名" @keyup.enter="search" /></label>
        <label>材料阶段<select v-model="filters.stage"><option value="">全部</option><option v-for="stage in stages" :key="stage" :value="stage">{{ stage }}</option></select></label>
        <label>审核状态<select v-model="filters.reviewStatus" :disabled="tab === 'pending'"><option value="">全部</option><option value="PENDING">待审核</option><option value="RETURNED">已退回</option><option value="APPROVED">已通过</option><option value="NOT_REQUIRED">无需审核</option></select></label>
        <label>扫描状态<select v-model="filters.scanStatus" :disabled="tab === 'security'"><option value="">全部</option><option value="CLEAN">安全</option><option value="PENDING">待扫描</option><option value="ERROR">失败</option><option value="INFECTED">感染</option></select></label>
        <div><button type="button" class="primary" @click="search">查询</button><button type="button" @click="reset">重置</button></div>
      </section>

      <section class="mc-panel">
        <div v-if="loading" class="mc-empty">正在加载真实材料数据…</div>
        <div v-else-if="!rows.length" class="mc-empty">当前筛选下没有数据。</div>
        <div v-else class="mc-table-wrap">
          <table v-if="tab !== 'students'">
            <thead><tr><th>学生 / 学号</th><th>学院 / 专业 / 班级</th><th>指导教师</th><th>阶段 / 材料</th><th>文件</th><th>版本</th><th>上传人 / 时间</th><th>大小</th><th>扫描</th><th>审核</th><th>归档</th><th>操作</th></tr></thead>
            <tbody><tr v-for="row in rows" :key="row.materialId">
              <td><strong>{{ row.studentName }}</strong><small>{{ row.studentNo }}</small></td>
              <td><span>{{ row.collegeId || '-' }} / {{ row.majorId || '-' }}</span><small>{{ row.className || row.classId || '-' }}</small></td>
              <td>{{ row.advisorName || '-' }}</td>
              <td><span>{{ row.stage }}</span><strong>{{ row.materialName }}</strong><small>{{ row.materialCode }}</small></td>
              <td :title="row.fileName">{{ row.fileName || '尚未提交' }}</td>
              <td><strong>v{{ row.currentVersion || 0 }}</strong><small>历史 {{ row.historyVersionCount || 0 }}</small></td>
              <td><span>{{ row.uploader || '-' }}</span><small>{{ row.uploadedAt || '-' }}</small></td>
              <td>{{ sizeText(row.sizeBytes) }}</td><td><b :class="tone(row.scanStatus)">{{ row.scanStatus }}</b></td>
              <td>{{ row.reviewStatus }}</td><td>{{ row.archiveStatus }}</td>
              <td class="actions"><button v-if="row.readyForBusiness" type="button" @click="preview(row)">预览</button><button v-if="row.readyForBusiness" type="button" @click="download(row)">下载</button><button type="button" @click="history(row)">版本</button><button v-if="row.allowedActions?.includes('review')" type="button" @click="openReview(row)">通过</button><button v-if="row.allowedActions?.includes('review')" type="button" @click="openReject(row)">退回</button></td>
            </tr></tbody>
          </table>
          <table v-else>
            <thead><tr><th>学生 / 学号</th><th>学院 / 专业 / 班级</th><th>指导教师</th><th>题目</th><th>应交</th><th>缺失</th><th>待审</th><th>退回</th><th>安全异常</th><th>归档结论</th><th>操作</th></tr></thead>
            <tbody><tr v-for="row in rows" :key="row.gdStudentId"><td><strong>{{ row.studentName }}</strong><small>{{ row.studentNo }}</small></td><td><span>{{ row.collegeId || '-' }} / {{ row.majorId || '-' }}</span><small>{{ row.className || row.classId || '-' }}</small></td><td>{{ row.advisorName || '-' }}</td><td>{{ row.topicTitle || '-' }}</td><td>{{ row.requiredCount }}</td><td>{{ row.missingCount }}</td><td>{{ row.pendingReviewCount }}</td><td>{{ row.returnedCount }}</td><td>{{ row.scanAbnormalCount }}</td><td><b :class="row.archiveReady ? 'ok' : 'warn'">{{ row.archiveReady ? '可归档' : '未齐全' }}</b></td><td class="actions"><button type="button" @click="router.push(`/admin/graduation/students/${row.gdStudentId}`)">学生档案</button></td></tr></tbody>
          </table>
        </div>
        <footer class="mc-pagebar"><span>共 {{ result.total || 0 }} 条</span><button type="button" :disabled="page <= 1" @click="goto(page - 1)">上一页</button><b>第 {{ page }} 页</b><button type="button" :disabled="page * pageSize >= Number(result.total || 0)" @click="goto(page + 1)">下一页</button></footer>
      </section>
    </template>

    <div v-if="historyVisible" class="mc-modal-mask" @click.self="historyVisible = false"><section class="mc-modal" role="dialog" aria-modal="true"><header><div><strong>{{ historyTitle }}</strong><span>不可变文件版本时间线</span></div><button type="button" @click="historyVisible = false">关闭</button></header><FileVersionTimeline :items="historyItems" @select="preview($event.file)" /></section></div>
    <AppConfirmDialog v-model:visible="reviewVisible" title="审核当前材料版本" :message="reviewMessage" confirm-text="通过当前版本" cancel-text="取消" :submitting="reviewing" @confirm="confirmReview('APPROVE', $event)" />
    <AppConfirmDialog v-model:visible="rejectVisible" title="退回当前材料版本" :message="reviewMessage" danger require-reason reason-label="退回原因" confirm-text="退回材料" :submitting="reviewing" @confirm="confirmReview('REJECT', $event)" />
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import FileVersionTimeline from '@/components/file/FileVersionTimeline.vue'
import { normalizeFile } from '@/services/file/fileSdk'
import { useGraduationBatchStore } from '@/stores/graduationBatch'
import { graduationMaterialCenterApi as api } from '@/modules/graduation/api/graduation-material-center.api'

const route = useRoute(); const router = useRouter(); const batchStore = useGraduationBatchStore()
const batchId = computed(() => batchStore.selectedBatchId)
const tabs = [{ key: 'files', label: '全部材料' }, { key: 'students', label: '学生完整性' }, { key: 'pending', label: '待审核' }, { key: 'security', label: '安全异常' }]
const stages = ['TOPIC','TASKBOOK','PROPOSAL','GUIDANCE','MIDTERM','FINAL_DRAFT','FINAL_APPROVED','PLAGIARISM','REVIEW','DEFENSE','GRADE','ARCHIVE']
const tab = ref(tabs.some(x => x.key === route.query.tab) ? route.query.tab : 'files')
const loading = ref(false); const error = ref(''); const result = ref({ items: [], total: 0 }); const summary = ref({ filteredSummary: {}, archiveSummary: {} })
const page = ref(Math.max(1, Number(route.query.page || 1))); const pageSize = 20
const filters = reactive({ keyword: String(route.query.keyword || ''), stage: String(route.query.stage || ''), reviewStatus: String(route.query.reviewStatus || ''), scanStatus: String(route.query.scanStatus || '') })
const historyVisible = ref(false); const historyTitle = ref(''); const historyItems = ref([])
const reviewVisible = ref(false); const rejectVisible = ref(false); const reviewRow = ref(null); const reviewing = ref(false)
const rows = computed(() => result.value.items || [])
const effective = computed(() => ({ ...filters, reviewStatus: tab.value === 'pending' ? 'PENDING' : filters.reviewStatus, scanStatus: tab.value === 'security' ? 'ABNORMAL' : filters.scanStatus }))
const cards = computed(() => { const f = summary.value.filteredSummary || {}; const a = summary.value.archiveSummary || {}; return [
  { label: '筛选学生', value: f.expectedStudents || 0, hint: '随当前条件变化' }, { label: '缺材料', value: f.missingStudents || 0, hint: '筛选口径' },
  { label: '待审核', value: f.pendingReviewStudents || 0, hint: '筛选口径' }, { label: '安全异常', value: f.scanAbnormalStudents || 0, hint: '筛选口径' },
  { label: '全规则可归档', value: a.archiveReadyStudents || 0, hint: '不受材料筛选污染' }, { label: '已归档', value: a.archivedStudents || 0, hint: '完整冻结规则口径' }
] })
const reviewMessage = computed(() => reviewRow.value ? `${reviewRow.value.studentName} · ${reviewRow.value.materialName} · v${reviewRow.value.currentVersion}` : '')

function params() { return { batchId: batchId.value, page: page.value, pageSize, ...effective.value } }
function syncUrl() { router.replace({ query: { tab: tab.value, page: page.value > 1 ? page.value : undefined, keyword: filters.keyword || undefined, stage: filters.stage || undefined, reviewStatus: filters.reviewStatus || undefined, scanStatus: filters.scanStatus || undefined } }) }
async function load() { if (!batchId.value) return; loading.value = true; error.value = ''; try { const p = params(); const request = tab.value === 'students' ? api.students(p) : api.files(p); [result.value, summary.value] = await Promise.all([request, api.summary(p)]); syncUrl() } catch (e) { error.value = e?.message || '材料中心加载失败' } finally { loading.value = false } }
function changeTab(value) { tab.value = value; page.value = 1; load() }
function search() { page.value = 1; load() }
function reset() { Object.assign(filters, { keyword: '', stage: '', reviewStatus: '', scanStatus: '' }); search() }
function goto(value) { page.value = value; load() }
function sizeText(value) { const n = Number(value || 0); return n >= 1048576 ? `${(n / 1048576).toFixed(1)} MB` : n >= 1024 ? `${(n / 1024).toFixed(1)} KB` : `${n} B` }
function tone(value) { return ['CLEAN','PASSED','NOT_REQUIRED'].includes(String(value).toUpperCase()) ? 'ok' : 'danger' }
function fileRow(row) { return normalizeFile({ fileId: row.fileId, fileName: row.fileName, sizeBytes: row.sizeBytes, scanStatus: row.scanStatus, readyForBusiness: row.readyForBusiness, allowedActions: row.allowedActions || [] }) }
async function preview(row) { try { await api.previewMaterial(row.file ? row.file : fileRow(row)) } catch (e) { error.value = e?.message || '预览失败' } }
async function download(row) { try { await api.downloadMaterial(fileRow(row)) } catch (e) { error.value = e?.message || '下载失败' } }
async function history(row) { try { const library = await api.studentLibrary(row.gdStudentId, true); const material = (library.items || []).find(item => item.materialId === row.materialId); historyTitle.value = `${row.studentName} · ${row.materialName}`; historyItems.value = (material?.versions || []).map(v => ({ bindingId: v.bindingId || v.versionId, versionNo: v.versionNo, isCurrent: v.isCurrent, boundAt: v.submittedAt, file: normalizeFile(v) })); historyVisible.value = true } catch (e) { error.value = e?.message || '版本历史加载失败' } }
function openReview(row) { reviewRow.value = row; reviewVisible.value = true }
function openReject(row) { reviewRow.value = row; rejectVisible.value = true }
async function confirmReview(action, payload) { if (!reviewRow.value) return; reviewing.value = true; try { await api.reviewMaterial(reviewRow.value.materialId, { fileVersionId: reviewRow.value.currentVersionId, expectedVersion: reviewRow.value.version, action, comment: payload?.reason || '' }); reviewVisible.value = false; rejectVisible.value = false; await load() } catch (e) { error.value = e?.message || '审核失败' } finally { reviewing.value = false } }
watch(batchId, () => { page.value = 1; load() })
onMounted(async () => { await batchStore.ensureLoaded(); await load() })
</script>

<style scoped>
.mc-page{display:grid;gap:16px;min-width:0}.mc-hero,.mc-panel,.mc-filters{background:#fff;border:1px solid #dfe7f3;border-radius:14px}.mc-hero{display:flex;justify-content:space-between;align-items:center;padding:20px 24px;background:linear-gradient(135deg,#f7fbff,#eef5ff)}.mc-hero span{color:#1769e0;font-size:12px;font-weight:700;letter-spacing:.1em}.mc-hero h2{margin:5px 0}.mc-hero p{margin:0;color:#69768b}.mc-page button{border:1px solid #ccd8e8;border-radius:8px;background:#fff;color:#29415f;padding:7px 11px;cursor:pointer}.mc-page button:disabled{opacity:.45}.mc-page .primary{background:#1769e0;border-color:#1769e0;color:#fff}.mc-error,.mc-empty{padding:24px;text-align:center;color:#69768b}.mc-error{display:flex;gap:12px;align-items:center;text-align:left;border-radius:12px;background:#fff1f1;color:#a61b1b}.mc-error button{margin-left:auto}.mc-summary{display:grid;grid-template-columns:repeat(6,minmax(110px,1fr));gap:10px}.mc-summary article{display:grid;gap:4px;padding:14px;border:1px solid #e2e8f2;border-radius:12px;background:#fff}.mc-summary strong{font-size:24px}.mc-summary small,td small{display:block;color:#7b8798}.mc-tabs{display:flex;gap:4px;border-bottom:1px solid #dfe7f3}.mc-tabs button{border:0;border-radius:8px 8px 0 0;padding:10px 18px}.mc-tabs button.active{background:#1769e0;color:#fff}.mc-filters{display:grid;grid-template-columns:1.6fr repeat(3,1fr) auto;gap:12px;align-items:end;padding:14px}.mc-filters label{display:grid;gap:5px;color:#526176;font-size:13px}.mc-filters input,.mc-filters select{min-width:0;border:1px solid #ccd8e8;border-radius:8px;padding:8px;background:#fff}.mc-filters>div{display:flex;gap:7px}.mc-panel{overflow:hidden}.mc-table-wrap{overflow:auto;max-height:66vh}table{width:100%;min-width:1480px;border-collapse:collapse}th,td{padding:10px 12px;border-bottom:1px solid #edf1f7;text-align:left;vertical-align:top;font-size:13px}th{position:sticky;top:0;z-index:1;background:#f7f9fc;color:#526176;white-space:nowrap}td strong,td span{display:block}.actions{white-space:nowrap}.actions button{border:0;padding:4px 6px;color:#1769e0}.ok,.warn,.danger{display:inline-block!important;padding:2px 7px;border-radius:999px}.ok{color:#137a43;background:#eafaf1}.warn{color:#9a5b00;background:#fff7df}.danger{color:#b42318;background:#fff0f0}.mc-pagebar{display:flex;justify-content:flex-end;align-items:center;gap:10px;padding:12px 16px}.mc-pagebar span{margin-right:auto;color:#69768b}.mc-modal-mask{position:fixed;inset:0;z-index:1000;display:flex;align-items:center;justify-content:center;padding:24px;background:rgba(15,23,42,.42)}.mc-modal{width:min(680px,100%);max-height:80vh;overflow:auto;padding:20px;border-radius:14px;background:#fff;box-shadow:0 18px 60px rgba(15,23,42,.2)}.mc-modal>header{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:18px}.mc-modal>header div{display:grid;gap:4px}.mc-modal>header span{color:#69768b;font-size:13px}@media(max-width:1100px){.mc-summary{grid-template-columns:repeat(3,1fr)}.mc-filters{grid-template-columns:repeat(2,1fr)}}@media(max-width:700px){.mc-hero{display:grid;gap:12px}.mc-summary{grid-template-columns:repeat(2,1fr)}.mc-filters{grid-template-columns:1fr}.mc-tabs{overflow:auto}}
</style>
