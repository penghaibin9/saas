<template>
  <ModulePageShell
    title="学生实习材料"
    :subtitle="studentTitle"
    role-name="指导教师 / 学院管理员 / 学校管理员"
    data-scope-name="仅当前账号有权访问的学生材料"
    :watermark="false"
  >
    <template #actions>
      <AppButton variant="ghost" @click="$router.back()">返回</AppButton>
      <AppButton v-if="canSync" variant="secondary" :loading="syncing" :disabled="!detail" @click="sync">同步旧材料</AppButton>
      <AppButton variant="ghost" :loading="loading" @click="load">刷新</AppButton>
    </template>

    <div v-if="loading" class="ism-state">正在读取真实材料版本…</div>
    <div v-else-if="error" class="ism-state is-error">
      <strong>学生材料读取失败</strong>
      <p>{{ error }}</p>
      <AppButton variant="primary" @click="load">重试</AppButton>
    </div>
    <template v-else-if="detail">
      <section class="ism-summary">
        <article><span>安全可用</span><strong>{{ detail.summary?.ready || 0 }}</strong></article>
        <article><span>待处理</span><strong>{{ detail.summary?.unsafe || 0 }}</strong></article>
        <article><span>版本累计</span><strong>{{ detail.summary?.versionCount || 0 }}</strong></article>
        <article><span>安全结论</span><strong class="is-small">{{ detail.summary?.unsafe ? '存在待处理项' : '材料安全门通过' }}</strong></article>
      </section>

      <section v-if="activePreviewFile" class="ism-card ism-reader-card">
        <header>
          <div>
            <h3>站内材料 Reader</h3>
            <p>{{ activePreviewFile.categoryLabel || activePreviewFile.title }} · 当前 v{{ activePreviewFile.versionNo }} · FileVersion {{ activePreviewFile.versionId }}</p>
          </div>
          <AppStatusTag type="success">只读当前安全版本</AppStatusTag>
        </header>
        <AppDocumentViewer
          :descriptor="previewDescriptor"
          :provider="previewProvider"
          :files="previewFiles"
          :versions="[activePreviewFile]"
          :active-file-key="activePreviewFile.fileId"
          :active-version-id="activePreviewFile.versionId"
          :canonical-version-id="activePreviewFile.versionId"
          :allow-download="Boolean(activePreviewFile.canDownload)"
          :show-version-bar="false"
          :show-file-switcher="previewFiles.length > 1"
          @select-file="preview"
          @download="downloadPreview"
          @preview-error="previewError"
        />
      </section>

      <section class="ism-card">
        <header>
          <div>
            <h3>{{ detail.studentName || '学生' }}（{{ detail.studentNo || '—' }}）</h3>
            <p>{{ detail.enterpriseName || '未分配企业' }} · 指导教师：{{ detail.advisorName || '—' }}</p>
          </div>
          <AppStatusTag :type="detail.summary?.unsafe ? 'danger' : 'success'">
            {{ detail.summary?.unsafe ? `待处理 ${detail.summary.unsafe} 项` : '安全可用' }}
          </AppStatusTag>
        </header>

        <SecureFileList
          :items="detail.items || []"
          :loading="loading"
          empty-text="尚未登记真实材料版本；有归档管理权限的账号可执行“同步旧材料”建立版本链。"
          @preview="preview"
          @download="download"
          @refresh="load"
        />
      </section>

      <section class="ism-card">
        <header>
          <div>
            <h3>真实版本与归档证据</h3>
            <p>下载与归档只认安全扫描通过的真实 versionId，不使用临时路径。</p>
          </div>
        </header>
        <div class="ism-table-wrap">
          <table>
            <thead><tr><th>材料</th><th>版本</th><th>versionId</th><th>扫描</th><th>审核</th><th>文件</th></tr></thead>
            <tbody>
              <tr v-for="item in detail.items || []" :key="item.versionId">
                <td>{{ item.categoryLabel || item.materialCode }}</td>
                <td>v{{ item.versionNo }}</td>
                <td class="mono">{{ item.versionId }}</td>
                <td>{{ item.scanStatus }}</td>
                <td>{{ item.reviewStatus || '—' }}</td>
                <td>{{ item.fileName }}</td>
              </tr>
              <tr v-if="!(detail.items || []).length"><td colspan="6" class="ism-empty">暂无真实文件版本</td></tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag } from '@/components/common'
import AppDocumentViewer from '@/components/file/viewer/AppDocumentViewer.vue'
import SecureFileList from '@/components/file/SecureFileList.vue'
import { internshipMaterialCenterApi } from '@/modules/internship/api/material-center.api'
import { canCode } from '@/modules/internship/composables/permission'
import { toast } from '@/utils/toast'

export default {
  name: 'InternshipStudentMaterialEntryView',
  components: { ModulePageShell, AppButton, AppStatusTag, AppDocumentViewer, SecureFileList },
  props: { ctx: { type: Object, default: null } },
  data() {
    return {
      detail: null, loading: false, syncing: false, error: '', activePreviewFileId: '',
      previewProvider: internshipMaterialCenterApi.createPreviewProvider()
    }
  },
  computed: {
    internshipId() { return String(this.$route.params.id || '') },
    canSync() { return canCode(this.ctx, 'internship.archive.manage') },
    studentTitle() {
      return this.detail
        ? `${this.detail.studentName || '学生'} · ${this.detail.studentNo || '—'} · 真实材料版本链`
        : `实习记录 #${this.internshipId}`
    },
    previewFiles() {
      return (this.detail?.items || []).filter((item) => item.canPreview && item.readyForBusiness)
    },
    activePreviewFile() {
      return this.previewFiles.find((item) => String(item.fileId) === String(this.activePreviewFileId)) || null
    },
    previewDescriptor() {
      return this.activePreviewFile ? internshipMaterialCenterApi.previewDescriptor(this.activePreviewFile) : null
    }
  },
  created() { this.load() },
  methods: {
    async load() {
      this.loading = true
      this.error = ''
      try {
        this.detail = await internshipMaterialCenterApi.detail(this.internshipId)
        const available = (this.detail?.items || []).filter((item) => item.canPreview && item.readyForBusiness)
        if (!available.some((item) => String(item.fileId) === String(this.activePreviewFileId))) {
          this.activePreviewFileId = String(available[0]?.fileId || '')
        }
      } catch (error) {
        this.detail = null
        this.activePreviewFileId = ''
        this.error = error?.message || '无权访问、记录不存在或服务异常'
      } finally {
        this.loading = false
      }
    },
    async sync() {
      if (!this.canSync || !this.detail || this.syncing) return
      this.syncing = true
      try {
        const result = await internshipMaterialCenterApi.sync(this.internshipId)
        const unsafe = Array.isArray(result?.unsafe) ? result.unsafe.length : 0
        if (unsafe) toast.warning(`材料已同步，仍有 ${unsafe} 项待扫描或处理`)
        else toast.success('材料版本已同步')
        await this.load()
      } catch (error) {
        toast.error(error?.message || '同步材料失败')
      } finally {
        this.syncing = false
      }
    },
    preview(item) {
      if (!item?.fileId || !item?.canPreview || !item?.readyForBusiness) {
        toast.warning('当前材料尚未通过安全门禁，不能预览')
        return
      }
      this.activePreviewFileId = String(item.fileId)
    },
    downloadPreview(descriptor) {
      const item = (this.detail?.items || []).find((row) => String(row.fileId) === String(descriptor?.fileId))
      if (item) this.download(item)
    },
    download(item) {
      internshipMaterialCenterApi.downloadMaterial(item).catch((error) => toast.error(error?.message || '文件下载失败'))
    },
    previewError(error) {
      toast.error(error?.message || '站内预览失败，请刷新材料状态后重试')
    }
  }
}
</script>

<style scoped>
.ism-state { max-width: 760px; margin: 48px auto; padding: 28px; border: 1px solid #e2e8f0; border-radius: 14px; background: #fff; color: #475569; }
.ism-state.is-error { border-color: rgba(220,38,38,.24); }
.ism-state strong { display: block; color: #991b1b; margin-bottom: 8px; }
.ism-summary { display: grid; grid-template-columns: repeat(4,minmax(0,1fr)); gap: 12px; margin-bottom: 16px; }
.ism-summary article { padding: 16px; border: 1px solid #e2e8f0; border-radius: 14px; background: #fff; display: grid; gap: 7px; }
.ism-summary span { color: #64748b; font-size: 13px; }
.ism-summary strong { font-size: 24px; color: #0f172a; }
.ism-summary .is-small { font-size: 15px; }
.ism-card { margin-bottom: 16px; padding: 18px; border: 1px solid #e2e8f0; border-radius: 14px; background: #fff; }
.ism-card header { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 16px; }
.ism-card h3 { margin: 0 0 5px; color: #0f172a; }
.ism-card p { margin: 0; color: #64748b; font-size: 13px; }
.ism-reader-card :deep(.document-viewer__body) { min-height: 560px; }
.ism-table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; min-width: 760px; }
th, td { padding: 11px 10px; border-bottom: 1px solid #edf2f7; text-align: left; font-size: 13px; }
th { color: #64748b; font-weight: 600; }
td { color: #334155; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.ism-empty { text-align: center; color: #94a3b8; padding: 30px; }
@media (max-width: 900px) { .ism-summary { grid-template-columns: repeat(2,minmax(0,1fr)); } }
</style>