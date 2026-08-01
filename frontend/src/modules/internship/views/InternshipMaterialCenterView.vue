<template>
  <ModulePageShell
    title="材料与证据中心"
    subtitle="统一查看协议、保险、过程报告、指导巡访和风险证据的安全状态、真实版本与归档清单"
    role-name="指导教师 / 学院管理员 / 学校管理员"
    data-scope-name="仅显示当前批次且在本人数据范围内的学生"
    :watermark="false"
  >
    <template #actions>
      <AppButton variant="ghost" :loading="loading" @click="load">刷新</AppButton>
      <AppButton
        v-if="selected"
        variant="secondary"
        :loading="syncing"
        @click="syncCurrent"
      >同步旧材料</AppButton>
    </template>

    <section class="summary-grid">
      <article><span>当前学生</span><strong>{{ total }}</strong></article>
      <article><span>安全可用材料</span><strong>{{ summary.ready }}</strong></article>
      <article><span>待处理材料</span><strong :class="{ danger: summary.unsafe > 0 }">{{ summary.unsafe }}</strong></article>
      <article><span>真实版本累计</span><strong>{{ summary.versionCount }}</strong></article>
    </section>

    <section class="filter-bar">
      <AppSearchBox v-model="keyword" placeholder="学生姓名或学号" @search="reload" />
      <select v-model="safetyStatus" @change="reload">
        <option value="">全部安全状态</option>
        <option value="READY">全部安全可用</option>
        <option value="UNSAFE">存在待扫描或风险</option>
        <option value="NOT_SYNCED">尚未同步材料</option>
      </select>
      <span class="filter-hint">批次：{{ batchStore.selectedBatchName || batchStore.selectedBatchId || '未选择' }}</span>
    </section>

    <div v-if="error" class="state error-state">
      {{ error }}
      <button type="button" @click="load">重新加载</button>
    </div>

    <section v-else class="workspace">
      <div class="student-panel">
        <div v-if="loading" class="state">正在读取材料安全状态…</div>
        <div v-else-if="!rows.length" class="state">当前筛选条件下暂无学生</div>
        <button
          v-for="row in rows"
          v-else
          :key="row.internshipId"
          type="button"
          class="student-row"
          :class="{ active: selectedId === row.internshipId }"
          @click="openStudent(row)"
        >
          <div>
            <strong>{{ row.studentName || '未命名学生' }}</strong>
            <span>{{ row.studentNo || '-' }} · {{ row.enterpriseName || '未分配企业' }}</span>
          </div>
          <div class="row-status">
            <AppStatusTag :type="statusTone(row.safetyStatus)" size="sm">
              {{ statusText(row.safetyStatus) }}
            </AppStatusTag>
            <small>{{ row.readyCount }}/{{ row.materialCount }} 可用</small>
          </div>
        </button>
        <footer v-if="total > pageSize" class="pager">
          <button type="button" :disabled="page <= 1" @click="changePage(page - 1)">上一页</button>
          <span>{{ page }} / {{ pageCount }}</span>
          <button type="button" :disabled="page >= pageCount" @click="changePage(page + 1)">下一页</button>
        </footer>
      </div>

      <div class="detail-panel">
        <div v-if="detailLoading" class="state">正在加载文件版本…</div>
        <div v-else-if="!selected" class="state">从左侧选择一名学生查看材料版本</div>
        <template v-else>
          <header class="detail-head">
            <div>
              <strong>{{ selected.studentName }}（{{ selected.studentNo }}）</strong>
              <span>{{ selected.enterpriseName || '未分配企业' }} · 指导教师：{{ selected.advisorName || '-' }}</span>
            </div>
            <AppStatusTag :type="selected.summary.unsafe ? 'danger' : 'success'">
              {{ selected.summary.unsafe ? `存在 ${selected.summary.unsafe} 项待处理` : '材料安全门通过' }}
            </AppStatusTag>
          </header>

          <section class="section-card">
            <div class="section-title">
              <div><strong>安全文件</strong><span>仅扫描通过且当前版本有效的材料允许预览或下载</span></div>
            </div>
            <SecureFileList
              :items="selected.items"
              :loading="detailLoading"
              empty-text="尚未登记材料；点击“同步旧材料”从现有业务记录建立版本链"
              @preview="previewFile"
              @download="downloadFile"
              @refresh="refreshDetail"
            />
          </section>

          <section class="section-card">
            <div class="section-title">
              <div><strong>真实版本清单</strong><span>归档引用 versionId，不引用可被覆盖的临时路径</span></div>
            </div>
            <div class="table-scroll">
              <table>
                <thead><tr><th>材料</th><th>版本</th><th>versionId</th><th>文件</th><th>扫描</th><th>审核</th><th>SHA-256</th></tr></thead>
                <tbody>
                  <tr v-for="item in selected.items" :key="item.versionId">
                    <td>{{ item.categoryLabel }}</td>
                    <td>v{{ item.versionNo }}</td>
                    <td class="mono">{{ item.versionId }}</td>
                    <td :title="item.fileName">{{ item.fileName }}</td>
                    <td><AppStatusTag :type="item.readyForBusiness ? 'success' : 'danger'" size="sm">{{ item.scanStatus }}</AppStatusTag></td>
                    <td>{{ item.reviewStatus || '-' }}</td>
                    <td class="mono hash" :title="item.sha256">{{ shortHash(item.sha256) }}</td>
                  </tr>
                  <tr v-if="!selected.items.length"><td colspan="7" class="empty-cell">暂无文件版本</td></tr>
                </tbody>
              </table>
            </div>
          </section>

          <section class="section-card manifest-card">
            <div class="section-title">
              <div><strong>归档 Manifest</strong><span>归档时冻结文件名、大小、哈希、扫描结论和真实版本号</span></div>
              <AppStatusTag v-if="selected.manifest" :type="manifestTone(selected.manifest.status)">
                {{ selected.manifest.status }}
              </AppStatusTag>
            </div>
            <div v-if="!selected.manifest" class="state compact">尚未生成归档版本清单</div>
            <template v-else>
              <dl class="manifest-meta">
                <div><dt>清单版本</dt><dd>revision {{ selected.manifest.revision }}</dd></div>
                <div><dt>Manifest ID</dt><dd class="mono">{{ selected.manifest.id }}</dd></div>
                <div><dt>文件版本数</dt><dd>{{ selected.manifest.items.length }}</dd></div>
                <div><dt>Manifest SHA-256</dt><dd class="mono" :title="selected.manifest.manifestSha256">{{ selected.manifest.manifestSha256 }}</dd></div>
              </dl>
              <div class="manifest-list">
                <div v-for="item in selected.manifest.items" :key="`${item.versionId}-${item.materialCode}`">
                  <span>{{ item.materialCode }}</span>
                  <strong>v{{ item.versionId }}</strong>
                  <small>{{ item.scanResult }} · {{ shortHash(item.sha256) }}</small>
                </div>
              </div>
            </template>
          </section>
        </template>
      </div>
    </section>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSearchBox, AppStatusTag } from '@/components/common'
import SecureFileList from '@/components/file/SecureFileList.vue'
import { fileSdk } from '@/services/file/fileSdk'
import { internshipMaterialCenterApi } from '@/modules/internship/api/material-center.api'
import { useInternshipBatchStore } from '@/stores/internshipBatch'
import { toast } from '@/utils/toast'

export default {
  name: 'InternshipMaterialCenterView',
  components: { ModulePageShell, AppButton, AppSearchBox, AppStatusTag, SecureFileList },
  data() {
    return {
      rows: [], total: 0, page: 1, pageSize: 20,
      keyword: '', safetyStatus: '', loading: false, detailLoading: false,
      syncing: false, error: '', selectedId: '', selected: null
    }
  },
  computed: {
    batchStore() { return useInternshipBatchStore() },
    pageCount() { return Math.max(1, Math.ceil(this.total / this.pageSize)) },
    summary() {
      return this.selected?.summary || { ready: 0, unsafe: 0, versionCount: 0 }
    }
  },
  watch: {
    'batchStore.selectedBatchId'() {
      this.page = 1
      this.selectedId = ''
      this.selected = null
      this.load()
    }
  },
  created() { this.load() },
  methods: {
    async load() {
      this.loading = true
      this.error = ''
      try {
        const data = await internshipMaterialCenterApi.list({
          page: this.page, pageSize: this.pageSize,
          batchId: this.batchStore.selectedBatchId || undefined,
          keyword: this.keyword || undefined,
          safetyStatus: this.safetyStatus || undefined
        })
        this.rows = data?.items || []
        this.total = Number(data?.total || 0)
        if (this.selectedId && !this.rows.some((row) => row.internshipId === this.selectedId)) {
          this.selectedId = ''
          this.selected = null
        }
      } catch (error) {
        this.error = error?.message || '材料与证据中心加载失败'
      } finally {
        this.loading = false
      }
    },
    reload() { this.page = 1; this.load() },
    changePage(page) { this.page = page; this.load() },
    async openStudent(row) {
      this.selectedId = row.internshipId
      await this.refreshDetail()
    },
    async refreshDetail() {
      if (!this.selectedId) return
      this.detailLoading = true
      try {
        this.selected = await internshipMaterialCenterApi.detail(this.selectedId)
      } catch (error) {
        toast.error(error?.message || '学生材料详情加载失败')
      } finally {
        this.detailLoading = false
      }
    },
    async syncCurrent() {
      if (!this.selectedId) return
      this.syncing = true
      try {
        const result = await internshipMaterialCenterApi.sync(this.selectedId)
        const unsafe = (result?.unsafe || []).length
        if (unsafe) toast.warning(`材料已同步，仍有 ${unsafe} 项等待扫描或处理`)
        else toast.success('材料版本已同步，安全状态正常')
        await Promise.all([this.load(), this.refreshDetail()])
      } catch (error) {
        toast.error(error?.message || '同步材料失败')
      } finally {
        this.syncing = false
      }
    },
    previewFile(item) {
      fileSdk.preview(item.fileId).catch((error) => toast.error(error?.message || '文件预览失败'))
    },
    downloadFile(item) {
      fileSdk.download(item.fileId, item.fileName).catch((error) => toast.error(error?.message || '文件下载失败'))
    },
    shortHash(value) {
      const text = String(value || '')
      return text ? `${text.slice(0, 10)}…${text.slice(-8)}` : '-'
    },
    statusText(value) {
      return { READY: '安全可用', UNSAFE: '存在待处理', NOT_SYNCED: '尚未同步' }[value] || value || '未知'
    },
    statusTone(value) {
      return { READY: 'success', UNSAFE: 'danger', NOT_SYNCED: 'default' }[value] || 'default'
    },
    manifestTone(value) {
      return ['FROZEN', 'PACKAGED'].includes(value) ? 'success' : (value === 'REVOKED' ? 'danger' : 'warning')
    }
  }
}
</script>

<style scoped>
.summary-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 16px; }
.summary-grid article { display: grid; gap: 7px; padding: 16px; border: 1px solid #e2e8f2; border-radius: 14px; background: #fff; }
.summary-grid span { color: #758197; font-size: 13px; }
.summary-grid strong { color: #1e2b45; font-size: 25px; }
.summary-grid .danger { color: #c73333; }
.filter-bar { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
.filter-bar select { min-height: 38px; padding: 0 12px; border: 1px solid #d8e1ed; border-radius: 9px; background: #fff; color: #34425a; }
.filter-hint { margin-left: auto; color: #758197; font-size: 13px; }
.workspace { display: grid; grid-template-columns: minmax(270px, 0.34fr) minmax(0, 1fr); gap: 16px; align-items: start; }
.student-panel, .detail-panel { min-height: 360px; border: 1px solid #dfe7f1; border-radius: 14px; background: #fff; overflow: hidden; }
.student-row { width: 100%; display: flex; justify-content: space-between; align-items: center; gap: 14px; padding: 15px 16px; border: 0; border-bottom: 1px solid #edf1f6; background: #fff; text-align: left; cursor: pointer; }
.student-row:hover, .student-row.active { background: #f3f8ff; }
.student-row > div:first-child { min-width: 0; display: grid; gap: 5px; }
.student-row strong { color: #25324a; }
.student-row span, .student-row small { overflow: hidden; color: #758197; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.row-status { display: grid; justify-items: end; gap: 5px; flex: none; }
.pager { display: flex; justify-content: center; align-items: center; gap: 12px; padding: 12px; }
.pager button, .state button { border: 0; background: transparent; color: #1769e0; cursor: pointer; }
.pager button:disabled { color: #aab4c3; cursor: not-allowed; }
.detail-panel { padding: 16px; background: #f8fafc; }
.detail-head { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 14px; padding: 16px; border: 1px solid #dfe7f1; border-radius: 12px; background: #fff; }
.detail-head > div { display: grid; gap: 6px; }
.detail-head span { color: #758197; font-size: 13px; }
.section-card { margin-top: 14px; padding: 15px; border: 1px solid #dfe7f1; border-radius: 12px; background: #fff; }
.section-title { display: flex; justify-content: space-between; align-items: center; gap: 14px; margin-bottom: 12px; }
.section-title > div { display: grid; gap: 4px; }
.section-title span { color: #758197; font-size: 12px; }
.table-scroll { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; min-width: 760px; }
th, td { padding: 11px 10px; border-bottom: 1px solid #edf1f6; text-align: left; font-size: 13px; }
th { color: #637086; background: #f8fafc; }
td { max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #34425a; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; }
.hash { max-width: 150px; }
.manifest-meta { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin: 0; }
.manifest-meta div { min-width: 0; padding: 10px; border-radius: 9px; background: #f7f9fc; }
.manifest-meta dt { color: #758197; font-size: 12px; }
.manifest-meta dd { margin: 5px 0 0; overflow-wrap: anywhere; color: #27354d; }
.manifest-list { display: grid; gap: 7px; margin-top: 12px; }
.manifest-list div { display: grid; grid-template-columns: minmax(0, 1fr) 90px 190px; gap: 12px; padding: 9px 10px; border: 1px solid #e7edf5; border-radius: 8px; }
.manifest-list small { color: #758197; }
.state { padding: 40px 20px; text-align: center; color: #758197; }
.state.compact { padding: 22px; }
.error-state { border: 1px solid #f1c7c7; border-radius: 12px; background: #fff7f7; color: #b42b2b; }
.empty-cell { padding: 25px; text-align: center; color: #8490a2; }
@media (max-width: 1100px) { .summary-grid { grid-template-columns: repeat(2, 1fr); } .workspace { grid-template-columns: 1fr; } }
@media (max-width: 680px) { .summary-grid { grid-template-columns: 1fr; } .filter-bar { align-items: stretch; flex-direction: column; } .filter-hint { margin-left: 0; } .manifest-meta { grid-template-columns: 1fr; } }
</style>
