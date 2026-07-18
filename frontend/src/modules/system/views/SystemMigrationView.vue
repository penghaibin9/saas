<template>
  <ModulePageShell
    title="老系统数据迁移"
    subtitle="数据迁移 · 老系统（教务/学工）历史数据按依赖顺序导入：模板 → 上传校验 → 错误清零 → 整批确认 → 对账"
    :role-name="ctx?.currentRole?.roleName || ''"
    :data-scope-name="ctx?.dataScope?.scopeName || ''"
  >
    <div class="mp-stack">
      <ModuleHero
        title="迁移地图（P1 · 6 域）"
        subtitle="老系统只要能导出 Excel 即可迁移；金智(XH/XM/ZCJ)、正方(xh/kcmc/cj)、强智(中文列名)常见字段名可自动识别，仍以学校真实导出样例为准。"
        :stats="heroStats"
      />

      <section class="mp-card">
        <header class="mp-card__head">
          <span class="mp-card__title">迁移域（按依赖顺序执行）</span>
          <span class="mp-note">灰色域表示前置依赖未完成；确认导入为高风险操作，整批一个事务，全程审计留痕</span>
        </header>
        <div class="mp-card__body smv-domains">
          <div
            v-for="d in domains"
            :key="d.domain"
            class="smv-domain"
            :class="{ 'is-blocked': !d.dependsMet }"
          >
            <div class="smv-domain__head">
              <span class="smv-domain__order">{{ d.order }}</span>
              <span class="smv-domain__label">{{ d.label }}</span>
              <StatusTag
                :type="d.dupPolicy === 'ERROR' ? 'warning' : (d.dupPolicy === 'SKIP' ? 'info' : 'success')"
                :label="dupPolicyLabel(d.dupPolicy)"
              />
            </div>
            <div class="smv-domain__meta">
              <div>目标表：<code>{{ d.targetTable }}</code></div>
              <div>唯一键：{{ d.uniqueKey }}</div>
              <div>
                前置依赖：
                <template v-if="d.dependsOn.length">
                  <span :class="d.dependsMet ? 'smv-ok' : 'smv-bad'">
                    {{ d.dependsOn.map(depLabel).join('、') }}{{ d.dependsMet ? '（已满足）' : '（未满足）' }}
                  </span>
                </template>
                <span v-else>无</span>
              </div>
              <div>
                库内数据：<b>{{ d.recordCount }}</b> 条
                <template v-if="d.lastBatch">
                  · 最近批次
                  <StatusTag
                    :type="d.lastBatch.status === 'SUCCESS' ? 'success' : (d.lastBatch.status === 'DRY_RUN_FAILED' || d.lastBatch.status === 'CONFIRM_FAILED' ? 'danger' : 'info')"
                    :label="batchStatusLabel(d.lastBatch.status)"
                  />
                </template>
              </div>
            </div>
            <div class="smv-domain__actions">
              <AppButton size="sm" variant="ghost" @click="downloadTemplate(d)">下载模板</AppButton>
              <AppButton
                size="sm"
                variant="primary"
                :disabled="!d.dependsMet"
                :title="d.dependsMet ? '' : '请先完成前置依赖域的导入'"
                @click="openImport(d)"
              >上传导入</AppButton>
            </div>
          </div>
        </div>
      </section>

      <section class="mp-card">
        <header class="mp-card__head">
          <span class="mp-card__title">迁移批次记录</span>
          <AppButton size="sm" variant="ghost" :loading="loading" @click="reload">刷新</AppButton>
        </header>
        <div class="mp-card__body">
          <table v-if="batches.length" class="smv-table">
            <thead>
              <tr>
                <th>批次号</th><th>迁移域</th><th>状态</th>
                <th>总行数</th><th>成功</th><th>错误</th><th>时间</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="b in batches" :key="b.batchNo">
                <td><code>{{ b.batchNo }}</code></td>
                <td>{{ b.domainLabel }}</td>
                <td>
                  <StatusTag
                    :type="b.status === 'SUCCESS' ? 'success' : (b.status === 'DRY_RUN_FAILED' || b.status === 'CONFIRM_FAILED' ? 'danger' : 'info')"
                    :label="batchStatusLabel(b.status)"
                  />
                </td>
                <td>{{ b.totalRows }}</td>
                <td>{{ b.successRows }}</td>
                <td>{{ b.errorRows }}</td>
                <td>{{ b.createdAt || '—' }}</td>
              </tr>
            </tbody>
          </table>
          <div v-else class="smv-empty">暂无迁移批次；先在上方选择迁移域并上传老系统导出的数据文件。</div>
        </div>
      </section>

      <section class="mp-card">
        <header class="mp-card__head"><span class="mp-card__title">实施口径（对学校可承诺的验收方式）</span></header>
        <div class="mp-card__body">
          <ul class="smv-list">
            <li>老系统导出的原始文件、映射对照表、每批错误清单、确认回执按学校归档，四件套可追溯。</li>
            <li>预校验存在任何错误行时禁止确认导入；确认阶段整批一个事务，任一行失败全部回滚，不留半批数据。</li>
            <li>历史数据只进终态：不产生待办、不触发工作流；导入行为全部写入安全审计。</li>
            <li>导入完成后按域对账：库内数量与老系统报表逐项核对一致方可签认。</li>
          </ul>
        </div>
      </section>
    </div>

    <AppExcelImportDrawer
      v-if="active"
      :visible="drawerVisible"
      :title="`导入 · ${active.label}`"
      :template-name="`数据迁移-${active.label}模板`"
      :required-fields="requiredFields"
      :preview-fields="previewFields"
      :download-template-fn="() => downloadTemplate(active)"
      :upload-fn="uploadFn"
      :confirm-fn="confirmFn"
      :download-errors-fn="downloadErrorsFn"
      @update:visible="drawerVisible = $event"
      @imported="onImported"
    />
  </ModulePageShell>
</template>

<script>
/**
 * 老系统数据迁移工作台（系统管理 · 数据迁移，P1 · 6 域）。
 * 后端：/api/v1/system/migration/*（dry-run → 行级错误 → confirm 整批事务；批次留痕）。
 * 复用公共 Excel 导入抽屉；本页只做迁移地图编排与批次展示，不自建导入通道。
 */
import { ModulePageShell, ModuleHero, StatusTag } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppExcelImportDrawer } from '@/components/common/excel'
import { systemApi } from '@/modules/system/api/system.api'
import { toast } from '@/utils/toast'

const DUP_LABELS = { ERROR: '重复即报错', SKIP: '重复跳过', OVERWRITE: '重复覆盖' }
const BATCH_LABELS = {
  DRY_RUN_PASSED: '校验通过', DRY_RUN_FAILED: '校验失败',
  SUCCESS: '导入成功', CONFIRM_FAILED: '确认失败'
}

export default {
  name: 'SystemMigrationView',
  components: { ModulePageShell, ModuleHero, StatusTag, AppButton, AppExcelImportDrawer },
  props: { ctx: { type: Object, default: null } },
  data() {
    return {
      loading: false,
      studentCount: 0,
      domains: [],
      batches: [],
      active: null,
      drawerVisible: false,
      pendingBatchNo: ''
    }
  },
  computed: {
    heroStats() {
      const done = this.domains.filter((d) => d.recordCount > 0).length
      return [
        { label: '学生主档', value: String(this.studentCount), tone: 'info' },
        { label: '已有数据域', value: `${done}/${this.domains.length || 6}`, tone: 'primary' },
        { label: '迁移批次', value: String(this.batches.length), tone: 'success' }
      ]
    },
    requiredFields() {
      return (this.active?.columns || []).filter((c) => c.required).map((c) => c.title)
    },
    previewFields() {
      return (this.active?.columns || []).map((c) => c.key)
    }
  },
  created() {
    this.reload()
  },
  methods: {
    dupPolicyLabel(p) {
      return DUP_LABELS[p] || p
    },
    batchStatusLabel(s) {
      return BATCH_LABELS[s] || s
    },
    depLabel(dep) {
      if (dep === 'student-profile') return '学生主档'
      return this.domains.find((d) => d.domain === dep)?.label || dep
    },
    async reload() {
      this.loading = true
      try {
        const [ov, bs] = await Promise.all([
          systemApi.getMigrationOverview(),
          systemApi.getMigrationBatches()
        ])
        if (ov.code === 0) {
          this.studentCount = ov.data.studentCount || 0
          this.domains = ov.data.domains || []
        } else {
          toast.error(ov.message || '迁移总览加载失败')
        }
        if (bs.code === 0) this.batches = bs.data || []
      } finally {
        this.loading = false
      }
    },
    downloadTemplate(d) {
      return systemApi.downloadMigrationTemplate(d.domain, d.label)
    },
    openImport(d) {
      this.active = d
      this.pendingBatchNo = ''
      this.drawerVisible = true
    },
    async uploadFn(file) {
      const res = await systemApi.validateMigrationFile(this.active.domain, file)
      if (res.code !== 0) return res
      const d = res.data
      this.pendingBatchNo = d.batchNo
      // 适配公共抽屉的统一预校验结构；skippedRows 提示到 message
      if (d.skippedRows) toast.info(`有 ${d.skippedRows} 行与现有数据相同/重复，将按策略跳过`)
      return {
        code: 0,
        data: {
          total: d.totalRows, validRows: d.okRows, invalidRows: d.errorRows,
          passed: d.status === 'DRY_RUN_PASSED', rows: d.rows || [], errors: d.errors || []
        }
      }
    },
    confirmFn() {
      if (!this.pendingBatchNo) return Promise.resolve({ code: 1, message: '批次已失效，请重新上传校验' })
      return systemApi.confirmMigrationBatch(this.pendingBatchNo)
    },
    downloadErrorsFn({ rows, errors }) {
      return systemApi.downloadMigrationErrors(this.active.domain, rows, errors)
    },
    onImported() {
      this.reload()
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.smv-domains { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: var(--space-4); }
.smv-domain {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  background: var(--bg-page);
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.smv-domain.is-blocked { opacity: 0.65; }
.smv-domain__head { display: flex; align-items: center; gap: var(--space-2); }
.smv-domain__order {
  width: 22px; height: 22px; border-radius: var(--radius-full);
  background: var(--primary-50); color: var(--primary-600);
  font-size: var(--font-size-xs); font-weight: var(--font-weight-semibold);
  display: inline-flex; align-items: center; justify-content: center;
}
.smv-domain__label { font-weight: var(--font-weight-semibold); flex: 1; }
.smv-domain__meta { font-size: var(--font-size-xs); color: var(--text-secondary); display: grid; gap: 4px; }
.smv-domain__meta code { font-size: var(--font-size-xs); }
.smv-domain__actions { display: flex; gap: var(--space-2); justify-content: flex-end; }
.smv-ok { color: var(--success-600); }
.smv-bad { color: var(--danger-600, #d4380d); }
.smv-table { width: 100%; border-collapse: collapse; font-size: var(--font-size-sm); }
.smv-table th, .smv-table td { text-align: left; padding: var(--space-2) var(--space-3); border-bottom: 1px solid var(--border-light); }
.smv-table th { color: var(--text-tertiary); font-weight: var(--font-weight-medium); }
.smv-empty { padding: var(--space-5); text-align: center; color: var(--text-tertiary); font-size: var(--font-size-sm); }
.smv-list { margin: 0; padding-left: 1.2em; display: grid; gap: var(--space-2); font-size: var(--font-size-sm); color: var(--text-secondary); }
</style>
