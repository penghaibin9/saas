<template>
  <ModulePageShell title="备份恢复验证与灾备" subtitle="机器证据唯一决定生产健康 · 人工登记仅作运维备注"
                   role-name="平台超级管理员" data-scope-name="全平台（跨租户）">
    <template #actions>
      <ModuleToolbar :actions="[{ key: 'schema-check', label: '运行结构自检' }, { key: 'refresh', label: '刷新' }]"
                    @action="onToolbarAction" />
    </template>

    <LoadingState v-if="loading" text="正在加载灾备证据…" />
    <ErrorState v-else-if="error" :text="error" @retry="load" />
    <template v-else-if="ov">
      <AppCard class="pdr__health" :class="`pdr__health--${(ov.machineHealth?.status || 'UNKNOWN').toLowerCase()}`">
        <div>
          <div class="pdr__health-title">生产灾备健康：{{ ov.machineHealth?.status || 'UNKNOWN' }}</div>
          <div class="pdr__health-sub">健康权威：MACHINE_ONLY。人工备份/人工恢复记录不会把本页判成 GREEN。</div>
        </div>
        <div class="pdr__health-grid">
          <span>机器备份：{{ ov.machineHealth?.backup?.status || 'UNKNOWN' }}</span>
          <span>机器恢复：{{ ov.machineHealth?.restore?.status || 'UNKNOWN' }}</span>
          <span>备份新鲜度：{{ ov.machineHealth?.backupFreshnessHours ?? '—' }}h</span>
          <span>恢复演练窗口：{{ ov.machineHealth?.restoreFreshnessDays ?? '—' }}d</span>
        </div>
      </AppCard>

      <div class="pdr__grid">
        <AppCard v-for="(info, type) in ov.byType" :key="type" class="pdr__stat" :class="{ 'pdr__stat--warn': info.stale }">
          <div class="pdr__stat-num">{{ info.daysSinceLastSuccess === null ? '—' : info.daysSinceLastSuccess + ' 天前' }}</div>
          <div class="pdr__stat-label">{{ typeLabel(type) }}</div>
          <div class="pdr__stat-sub">{{ info.stale ? `已超过 ${info.thresholdDays} 天阈值` : '证据在阈值内（仅辅助观察）' }}</div>
        </AppCard>
        <AppCard class="pdr__stat" :class="{ 'pdr__stat--warn': ov.restoreDrill.stale }">
          <div class="pdr__stat-num">{{ ov.restoreDrill.daysSinceLastPassed === null ? '从未' : ov.restoreDrill.daysSinceLastPassed + ' 天前' }}</div>
          <div class="pdr__stat-label">机器恢复演练健康</div>
          <div class="pdr__stat-sub">{{ ov.restoreDrill.stale ? '无有效机器恢复证据或已过期' : '机器恢复证据在有效期内' }}</div>
        </AppCard>
      </div>

      <AppCard v-if="ov.recentFailuresLast7Days.length" class="pdr__panel">
        <AppSectionHeader title="近7天失败记录" />
        <ul class="pdr__list">
          <li v-for="f in ov.recentFailuresLast7Days" :key="f.id">
            {{ typeLabel(f.backupType) }} · {{ f.method }} · {{ f.errorMessage || '无错误说明' }}
          </li>
        </ul>
      </AppCard>

      <AppCard class="pdr__panel">
        <AppSectionHeader title="人工备份备注（不参与 GREEN）" />
        <p class="pdr__note">用于记录云厂商工单、人工 mysqldump 等外部事实，方便审计与交接；这些记录不会改变生产灾备健康结论。真正的 GREEN 只来自部署 runner 的机器证据。</p>
        <div class="pdr__form">
          <select v-model="evidenceForm.backupType" class="pdr__input">
            <option value="DATABASE_DUMP">数据库备份</option>
            <option value="FILE_STORAGE_SYNC">文件存储同步</option>
            <option value="CLOUD_MANAGED">云厂商托管备份</option>
          </select>
          <select v-model="evidenceForm.method" class="pdr__input">
            <option value="MYSQLDUMP">mysqldump</option>
            <option value="MANUAL_CONFIRMED">人工确认</option>
            <option value="CLOUD_MANAGED">云厂商托管</option>
          </select>
          <select v-model="evidenceForm.status" class="pdr__input">
            <option value="SUCCEEDED">成功</option>
            <option value="FAILED">失败</option>
          </select>
          <input v-model.trim="evidenceForm.locationRef" class="pdr__input" placeholder="存放位置/备份ID（成功必填）" />
          <button class="mp-link" @click="submitEvidence">登记备注</button>
        </div>
      </AppCard>

      <AppCard class="pdr__panel">
        <AppSectionHeader title="备份备注列表" />
        <DataTable :columns="evidenceColumns" :rows="evidenceList" row-key="id">
          <template #cell-status="{ row }">
            <StatusTag :type="row.status === 'SUCCEEDED' ? 'success' : 'danger'" :label="platformStatusLabel(row.status)" />
          </template>
        </DataTable>
      </AppCard>

      <AppCard class="pdr__panel">
        <AppSectionHeader title="人工恢复演练备注（不参与 GREEN）" />
        <p class="pdr__note">人工记录保留用于复盘，但不会作为健康权威。请在隔离环境运行 deploy/backup/machine-restore-drill.sh，由恢复脚本真实校验 RPO/RTO、Alembic、表/索引/FK 与文件后自动写入机器证据。</p>
        <div class="pdr__form">
          <select v-model="drillForm.status" class="pdr__input">
            <option value="PASSED">通过</option>
            <option value="FAILED">未通过</option>
          </select>
          <input v-model.trim="drillForm.targetDescription" class="pdr__input" placeholder="人工说明" />
          <button class="mp-link" @click="submitDrill">登记备注</button>
        </div>
        <ul class="pdr__list">
          <li v-for="d in drillList" :key="d.id">
            <StatusTag :type="d.status === 'PASSED' ? 'success' : 'danger'" :label="platformStatusLabel(d.status)" /> {{ d.targetDescription || '（无说明）' }}
          </li>
        </ul>
      </AppCard>
    </template>
  </ModulePageShell>
</template>

<script>
import { AppCard, AppSectionHeader } from '@/components/ui'
import { DataTable, ErrorState, LoadingState, ModulePageShell, ModuleToolbar, StatusTag } from '@/components/business'
import { platformControlApi } from '@/modules/platform/api/platformControl.api'
import { platformStatusLabel } from '@/modules/platform/constants/platform-display.constants'
import { toast } from '@/utils/toast'

const TYPE_LABELS = {
  DATABASE_DUMP: '数据库备份备注', SCHEMA_INTEGRITY: '表结构自检',
  FILE_STORAGE_SYNC: '文件存储同步备注', CLOUD_MANAGED: '云厂商托管备注'
}

export default {
  name: 'PlatformDisasterRecoveryView',
  components: { AppCard, AppSectionHeader, DataTable, ErrorState, LoadingState, ModulePageShell, ModuleToolbar, StatusTag },
  data() {
    return {
      loading: true,
      error: '',
      ov: null,
      evidenceList: [],
      drillList: [],
      evidenceForm: { backupType: 'DATABASE_DUMP', method: 'MANUAL_CONFIRMED', status: 'SUCCEEDED', locationRef: '' },
      drillForm: { status: 'PASSED', targetDescription: '' },
      evidenceColumns: [
        { key: 'backupType', title: '类型' },
        { key: 'method', title: '方式' },
        { key: 'status', title: '结果' },
        { key: 'locationRef', title: '位置/备份ID' }
      ]
    }
  },
  created() {
    this.load()
  },
  methods: {
    platformStatusLabel,
    typeLabel(type) {
      return TYPE_LABELS[type] || type
    },
    onToolbarAction(key) {
      if (key === 'schema-check') this.runSchemaCheck()
      if (key === 'refresh') this.load()
    },
    async load() {
      this.loading = true
      this.error = ''
      const [ovRes, evRes, drillRes] = await Promise.all([
        platformControlApi.getDisasterRecoveryOverview(),
        platformControlApi.listBackupEvidence(),
        platformControlApi.listRestoreDrills()
      ])
      this.loading = false
      if (ovRes.code === 0) this.ov = ovRes.data
      else this.error = ovRes.message
      if (evRes.code === 0) this.evidenceList = evRes.data.items || []
      if (drillRes.code === 0) this.drillList = drillRes.data.items || []
    },
    async runSchemaCheck() {
      const res = await platformControlApi.runSchemaIntegrityCheck()
      if (res.code === 0) {
        toast[res.data.status === 'SUCCEEDED' ? 'success' : 'error'](
          res.data.status === 'SUCCEEDED' ? '结构自检通过（辅助证据）' : `结构自检未通过：${res.data.errorMessage}`
        )
        this.load()
      } else toast.error(res.message)
    },
    async submitEvidence() {
      if (this.evidenceForm.status === 'SUCCEEDED' && !this.evidenceForm.locationRef) {
        toast.error('登记成功的备份必须填写存放位置/备份ID')
        return
      }
      const res = await platformControlApi.createBackupEvidence({ ...this.evidenceForm })
      if (res.code === 0) {
        toast.success('人工备注已登记，不影响机器健康结论')
        this.evidenceForm.locationRef = ''
        this.load()
      } else toast.error(res.message)
    },
    async submitDrill() {
      const res = await platformControlApi.createRestoreDrill({
        drillType: 'MANUAL_CONFIRMED', ...this.drillForm
      })
      if (res.code === 0) {
        toast.success('人工演练备注已登记，不影响机器健康结论')
        this.drillForm.targetDescription = ''
        this.load()
      } else toast.error(res.message)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.pdr__health {
  padding: var(--space-4);
  margin-bottom: var(--space-3);
  border-width: 2px;
}
.pdr__health--green { border-color: var(--color-success, #16a34a); }
.pdr__health--red { border-color: var(--color-danger, #dc2626); }
.pdr__health--unknown { border-color: var(--color-warning, #d97706); }
.pdr__health-title { font-size: 20px; font-weight: var(--font-weight-bold); color: var(--t1); }
.pdr__health-sub { margin-top: 4px; font-size: 12px; color: var(--text-secondary); }
.pdr__health-grid { display: flex; flex-wrap: wrap; gap: var(--space-3); margin-top: var(--space-3); font-size: 13px; color: var(--text-secondary); }
.pdr__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--space-3);
}
.pdr__stat { padding: var(--space-4); }
.pdr__stat--warn { border-color: var(--color-warning, #d97706); }
.pdr__stat-num { font-size: 22px; font-weight: var(--font-weight-bold); color: var(--t1); }
.pdr__stat-label { margin-top: 2px; font-size: var(--font-size-sm); color: var(--text-secondary); }
.pdr__stat-sub { margin-top: 4px; font-size: 12px; color: var(--text-tertiary); }
.pdr__panel { margin-top: var(--space-3); padding: var(--space-4); }
.pdr__note { margin-top: var(--space-2); font-size: 12px; color: var(--text-tertiary); line-height: 1.6; }
.pdr__form { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-top: var(--space-2); }
.pdr__input { padding: 6px 10px; border: 1px solid var(--border-light); border-radius: var(--radius-sm, 4px); font-size: var(--font-size-sm); }
.pdr__list { list-style: none; margin: var(--space-2) 0 0; padding: 0; display: flex; flex-direction: column; gap: var(--space-2); font-size: var(--font-size-sm); color: var(--text-secondary); }
</style>
