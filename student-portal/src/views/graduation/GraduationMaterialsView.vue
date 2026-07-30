<template>
  <div class="gsm-page">
    <header class="gsm-hero">
      <div>
        <p>毕业设计材料库</p>
        <h1>查看材料状态并按退回意见重交</h1>
        <span>论文、作品和源代码等大文件请使用本页面上传；完成后的文件版本和审核状态刷新后仍可恢复。</span>
      </div>
      <div><RouterLink class="gsm-btn" to="/graduation">返回毕业设计工作台</RouterLink><button class="gsm-btn gsm-btn--primary" :disabled="loading" @click="load">刷新材料</button></div>
    </header>

    <StateBlock v-if="loading" type="loading" text="正在加载你的毕业设计材料…" />
    <StateBlock v-else-if="error" type="error" :text="error" />
    <template v-else-if="library">
      <section class="gsm-summary">
        <article><span>材料总数</span><strong>{{ library.total || 0 }}</strong></article>
        <article><span>缺失</span><strong class="is-danger">{{ count('MISSING') }}</strong></article>
        <article><span>待审核</span><strong class="is-warning">{{ reviewCount('PENDING') }}</strong></article>
        <article><span>被退回</span><strong class="is-danger">{{ reviewCount('RETURNED') }}</strong></article>
        <article><span>已通过</span><strong class="is-success">{{ reviewCount('APPROVED') }}</strong></article>
      </section>

      <section class="gsm-profile">
        <div><span>姓名</span><strong>{{ library.studentName }}</strong></div><div><span>学号</span><strong>{{ library.studentNo }}</strong></div>
        <div><span>课题</span><strong>{{ library.topicTitle || '待分配' }}</strong></div><div><span>指导教师</span><strong>{{ library.advisorName || '待分配' }}</strong></div>
      </section>

      <section v-for="group in library.groups || []" :key="group.name" class="gsm-group">
        <header><h2>{{ group.name }}</h2><span>{{ group.items.length }} 项</span></header>
        <article v-for="material in group.items" :key="material.materialId" class="gsm-item">
          <div class="gsm-item__head">
            <div><strong>{{ material.materialName }}</strong><span>{{ material.materialCode }} · {{ material.required ? '必交' : '选交' }}</span></div>
            <div class="gsm-tags"><b :class="tone(material.businessStatus)">{{ label(material.businessStatus) }}</b><b>{{ material.reviewStatus }}</b><b>{{ material.archiveStatus }}</b></div>
          </div>
          <p v-if="material.rejectReason" class="gsm-reject">退回原因：{{ material.rejectReason }}</p>
          <p class="gsm-next">下一步：{{ material.nextAction || '无需处理' }}</p>
          <div class="gsm-meta">
            <span>当前版本：{{ material.currentVersion?.versionNo ? `v${material.currentVersion.versionNo}` : '尚未提交' }}</span>
            <span>FileVersion ID：{{ material.currentVersionId || '-' }}</span>
            <span>安全状态：{{ material.currentVersion?.statusText || material.currentVersion?.scanStatus || '-' }}</span>
            <span>上传时间：{{ material.submittedAt || '-' }}</span>
          </div>
          <div v-if="material.currentVersion" class="gsm-file">
            <div><strong>{{ material.currentVersion.fileName }}</strong><span>{{ sizeText(material.currentVersion.sizeBytes) }} · {{ material.currentVersion.statusText }}</span></div>
            <button v-if="material.currentVersion.canPreview" class="gsm-btn" :disabled="busy" @click="preview(material.currentVersion)">安全预览</button>
            <button v-if="material.currentVersion.canDownload" class="gsm-btn" :disabled="busy" @click="download(material.currentVersion)">下载</button>
          </div>
          <details v-if="material.versions?.length" class="gsm-history">
            <summary>历史版本（{{ material.versions.length }}）</summary>
            <div v-for="item in material.versions" :key="item.fileVersionId" class="gsm-version">
              <span>v{{ item.versionNo }} · {{ item.fileName }}</span><span>{{ item.isCurrent ? '当前版本' : item.versionStatus }} · {{ item.submittedAt || '-' }}</span>
              <button v-if="item.canDownload" class="gsm-btn" :disabled="busy" @click="download(item)">下载该版本</button>
            </div>
          </details>
          <div v-if="canUpload(material)" class="gsm-upload">
            <label>选择新文件<input type="file" :accept="acceptText(material)" :disabled="busy" @change="selectFile(material, $event)" /></label>
            <p v-if="pending[material.materialCode]">待提交：{{ pending[material.materialCode].fileName }} · {{ pending[material.materialCode].statusText }}</p>
            <button class="gsm-btn gsm-btn--primary" :disabled="busy || !pending[material.materialCode] || !pending[material.materialCode].readyForBusiness" @click="submit(material)">
              {{ material.businessStatus === 'RETURNED' ? '重交新版本' : '提交材料版本' }}
            </button>
            <small>文件需先完成安全扫描；扫描中、失败或感染时不能提交。</small>
          </div>
        </article>
      </section>

      <section class="gsm-manifest">
        <header><div><h2>归档状态</h2><p>归档后可查看学校冻结的真实文件版本清单。</p></div><button class="gsm-btn" @click="loadManifest">查看 Manifest</button></header>
        <div v-if="manifest"><strong>revision {{ manifest.revision }} · {{ manifest.status }}</strong><code>{{ manifest.manifestSha256 }}</code><p>{{ manifest.itemCount }} 个冻结文件版本</p></div>
      </section>
    </template>
    <StateBlock v-else type="empty" text="尚未建立毕业设计材料库" />
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import StateBlock from '../../components/StateBlock.vue'
import { portalApi } from '../../services/portalApi'
import { useUiStore } from '../../stores/ui'

const ui = useUiStore()
const loading = ref(true); const busy = ref(false); const error = ref(''); const library = ref(null); const manifest = ref(null)
const pending = reactive({})
const LARGE_CODES = new Set(['THESIS_DRAFT', 'THESIS_FINAL', 'DESIGN_WORK', 'SOURCE_CODE', 'WORK_DESCRIPTION'])

async function load() { loading.value = true; error.value = ''; try { library.value = await portalApi.graduationMaterialLibrary() } catch (e) { error.value = e?.message || '材料库加载失败' } finally { loading.value = false } }
function count(status) { return (library.value?.items || []).filter(item => item.businessStatus === status).length }
function reviewCount(status) { return (library.value?.items || []).filter(item => item.reviewStatus === status).length }
function label(value) { return ({ MISSING: '缺失', SUBMITTED: '已提交', RETURNED: '已退回', APPROVED: '已通过', ARCHIVED: '已归档' })[value] || value || '未知' }
function tone(value) { return { 'is-danger': ['MISSING', 'RETURNED'].includes(value), 'is-warning': value === 'SUBMITTED', 'is-success': ['APPROVED', 'ARCHIVED'].includes(value) } }
function sizeText(value) { const n = Number(value || 0); return n >= 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)} MB` : n >= 1024 ? `${(n / 1024).toFixed(1)} KB` : `${n} B` }
function canUpload(material) { return ['STUDENT', 'MENTOR'].includes(material.ownerRole) && !['ARCHIVED'].includes(material.businessStatus) && material.materialCode !== 'FINAL_ARCHIVE_PACKAGE' }
function acceptText(material) { const map = { SOURCE_CODE: '.zip', THESIS_DRAFT: '.pdf,.doc,.docx', THESIS_FINAL: '.pdf,.doc,.docx', DESIGN_WORK: '.pdf,.zip,.png,.jpg,.jpeg,.mp4', WORK_DESCRIPTION: '.pdf,.doc,.docx' }; return map[material.materialCode] || '.pdf,.doc,.docx,.xlsx,.pptx,.png,.jpg,.jpeg,.zip' }
async function selectFile(material, event) { const file = event.target.files?.[0]; event.target.value = ''; if (!file) return; busy.value = true; try { const uploaded = await portalApi.uploadGraduationMaterial(file); pending[material.materialCode] = uploaded; ui.notify(uploaded.readyForBusiness ? '上传完成，可以提交材料版本' : '上传完成，等待安全扫描后再提交') } catch (e) { ui.notify(e?.message || '文件上传失败') } finally { busy.value = false } }
async function submit(material) { const file = pending[material.materialCode]; if (!file?.fileId) return; busy.value = true; try { await portalApi.submitGraduationMaterial(material.materialCode, file.fileId, material.version); delete pending[material.materialCode]; ui.notify('材料新版本已提交'); await load() } catch (e) { ui.notify(e?.message || '材料提交失败') } finally { busy.value = false } }
async function preview(file) { busy.value = true; try { await portalApi.previewGraduationMaterial(file.fileId, file.fileName) } catch (e) { ui.notify(e?.message || '文件暂不可预览') } finally { busy.value = false } }
async function download(file) { busy.value = true; try { await portalApi.downloadGraduationMaterial(file.fileId, file.fileName) } catch (e) { ui.notify(e?.message || '文件暂不可下载') } finally { busy.value = false } }
async function loadManifest() { try { manifest.value = await portalApi.graduationMaterialManifest() } catch (e) { ui.notify(e?.message || '学校尚未冻结归档清单') } }
onMounted(load)
</script>

<style scoped>
.gsm-page{display:grid;gap:16px}.gsm-hero,.gsm-profile,.gsm-group,.gsm-manifest,.gsm-summary article{background:#fff;border:1px solid #dfe7f3;border-radius:16px}.gsm-hero{padding:22px;display:flex;justify-content:space-between;gap:20px;background:linear-gradient(135deg,#f6fbff,#eef5ff)}.gsm-hero p{margin:0;color:#1769e0;font-size:12px;font-weight:700;letter-spacing:.1em}.gsm-hero h1{margin:7px 0}.gsm-hero span,.gsm-item span,.gsm-meta,.gsm-upload small{color:#6b778c}.gsm-hero>div:last-child{display:flex;gap:8px;align-items:flex-start}.gsm-btn{display:inline-flex;border:1px solid #cbd7e7;background:#fff;border-radius:9px;padding:8px 12px;color:#29415f;text-decoration:none;cursor:pointer}.gsm-btn--primary{background:#1769e0;color:#fff;border-color:#1769e0}.gsm-btn:disabled{opacity:.5}.gsm-summary{display:grid;grid-template-columns:repeat(5,1fr);gap:10px}.gsm-summary article{display:grid;gap:5px;padding:14px}.gsm-summary strong{font-size:24px}.is-danger{color:#b42318!important}.is-warning{color:#a15c00!important}.is-success{color:#168349!important}.gsm-profile{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;padding:16px}.gsm-profile div{display:grid;gap:4px}.gsm-profile span{font-size:12px;color:#78859a}.gsm-group{padding:18px}.gsm-group>header,.gsm-manifest>header{display:flex;justify-content:space-between;align-items:center}.gsm-group h2,.gsm-manifest h2{margin:0}.gsm-group>header span{color:#78859a}.gsm-item{border:1px solid #e5eaf2;border-radius:12px;padding:14px;margin-top:12px}.gsm-item__head{display:flex;justify-content:space-between;gap:10px}.gsm-item__head>div:first-child{display:grid;gap:3px}.gsm-tags{display:flex;gap:6px;flex-wrap:wrap}.gsm-tags b{padding:3px 7px;border-radius:999px;background:#f1f4f8;font-size:12px}.gsm-reject{background:#fff1f1;color:#a61b1b;padding:9px;border-radius:8px}.gsm-next{font-weight:600}.gsm-meta{display:flex;gap:12px;flex-wrap:wrap;font-size:12px}.gsm-file,.gsm-version{display:flex;align-items:center;gap:10px;margin-top:10px;padding:10px;background:#f7f9fc;border-radius:9px}.gsm-file>div{display:grid;gap:3px;margin-right:auto}.gsm-history{margin-top:10px}.gsm-history summary{cursor:pointer;color:#1769e0}.gsm-version span:first-child{margin-right:auto}.gsm-upload{margin-top:12px;border-top:1px solid #edf1f7;padding-top:12px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}.gsm-upload label{display:grid;gap:4px}.gsm-upload input{max-width:280px}.gsm-manifest{padding:18px}.gsm-manifest header p{margin:4px 0;color:#6b778c}.gsm-manifest>div{display:grid;gap:6px;margin-top:14px}.gsm-manifest code{word-break:break-all;font-size:11px}
@media(max-width:800px){.gsm-hero{display:grid}.gsm-summary{grid-template-columns:repeat(2,1fr)}.gsm-profile{grid-template-columns:repeat(2,1fr)}.gsm-item__head,.gsm-file,.gsm-version{display:grid}}
</style>
