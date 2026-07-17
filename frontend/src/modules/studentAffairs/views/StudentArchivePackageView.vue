<template>
  <AppPageShell title="学生档案包" subtitle="按归档批次浏览每生档案包与缺项清单。敏感原文默认不入包，下载走导出审批。"
    role-name="学工处 / 学院" data-scope-name="归档范围" watermark-purpose="学生档案包浏览">
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="加载中..." @retry="load"
                    @back="$router.push('/admin/student-affairs/archive')">
      <div class="ap-bar">
        <label class="ap-label">归档批次
          <AppSelect v-model="selBatch" class="ap-pick" :options="batchOptions" placeholder="（选择批次）" @change="loadBatch" />
        </label>
      </div>
      <AppSectionCard :title="selBatch ? '档案包清单' : '请选择批次'">
        <table v-if="selBatch" class="sa-table">
          <thead><tr><th>学生</th><th>状态</th><th>缺项</th></tr></thead>
          <tbody>
            <tr v-for="p in packages" :key="p.packageId">
              <td><strong>{{ p.realName || ('学生#'+p.studentId) }}</strong></td>
              <td><StatusTag :type="pkgType(p.status)" :label="pkgLabel(p.status)" dot /></td>
              <td class="ap-miss">{{ missText(p) }}</td>
            </tr>
            <tr v-if="!packages.length"><td colspan="3" class="sa-empty">该批次暂无档案包（可在归档批次页圈定学生生成）</td></tr>
          </tbody>
        </table>
        <p v-else class="ap-hint">从上方选择一个归档批次查看其学生档案包。</p>
      </AppSectionCard>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import { AppGlobalState, AppPageShell, AppSectionCard, AppSelect, AppStatusTag } from '@/components/common'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'

const PKG = { PENDING: '待收集', READY: '完整', MISSING: '有缺项', ARCHIVED: '已归档', COLLECTING: '收集中' }

export default {
  name: 'StudentArchivePackageView',
  components: { AppGlobalState, AppPageShell, AppSectionCard, AppSelect, StatusTag: AppStatusTag },
  data() { return { loading: true, errorMessage: '', batches: [], selBatch: '', packages: [] } },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    batchOptions() {
      return this.batches.map((b) => ({
        value: b.batchId,
        label: `${b.batchName || ('批次#' + b.batchId)}（${b.status} · ${b.packageCount != null ? b.packageCount + '包' : ''}）`
      }))
    }
  },
  mounted() { this.load() },
  methods: {
    async load() {
      this.loading = true; this.errorMessage = ''
      const res = await studentAffairsApi.getArchiveBatches({ pageSize: 100 })
      if (res.code === 0 && res.data) this.batches = res.data.items || []
      else this.errorMessage = res.message || '加载失败'
      this.loading = false
    },
    async loadBatch() {
      this.packages = []
      if (!this.selBatch) return
      const res = await studentAffairsApi.getArchiveBatch(this.selBatch)
      if (res.code === 0 && res.data) this.packages = res.data.packages || []
    },
    pkgLabel(s) { return PKG[s] || s || '—' },
    pkgType(s) { return ({ READY: 'success', ARCHIVED: 'success', MISSING: 'warning', PENDING: 'default', COLLECTING: 'processing' })[s] || 'default' },
    missText(p) {
      const m = p.missingItems || p.missing || p.missingList
      if (Array.isArray(m)) return m.length ? m.join('、') : '无'
      return m || (p.status === 'MISSING' ? '有缺项' : '无')
    }
  }
}
</script>

<style scoped>
.ap-bar { margin-bottom: var(--space-4); }
.ap-label { display: inline-flex; align-items: center; gap: var(--space-2); font-size: var(--font-size-sm); }
.ap-pick { width: 320px; }
.sa-table { width: 100%; border-collapse: collapse; }
.sa-table th, .sa-table td { border-bottom: 1px solid var(--border-light); padding: var(--space-2) var(--space-3); text-align: left; }
.sa-empty, .ap-hint { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
.ap-miss { color: var(--text-secondary); font-size: var(--font-size-sm); }
</style>
