<template>
  <ModulePageShell title="备份恢复验证与灾备" subtitle="按类型看最近一次成功备份 · 恢复演练是否过期 · 只读结构自检"
                   role-name="平台超级管理员" data-scope-name="全平台（跨租户）">
    <template #actions>
      <ModuleToolbar :actions="[{ key: 'schema-check', label: '运行结构自检' }, { key: 'refresh', label: '刷新' }]"
                    @action="onToolbarAction" />
    </template>

    <LoadingState v-if="loading" text="正在加载灾备证据…" />
    <ErrorState v-else-if="error" :text="error" @retry="load" />
    <template v-else-if="ov">
      <div class="pdr__grid">
        <AppCard v-for="(info, type) in ov.byType" :key="type" class="pdr__stat" :class="{ 'pdr__stat--warn': info.stale }">
          <div class="pdr__stat-num">{{ info.daysSinceLastSuccess === null ? '—' : info.daysSinceLastSuccess + ' 天前' }}</div>
          <div class="pdr__stat-label">{{ typeLabel(type) }}</div>
          <div class="pdr__stat-sub">{{ info.stale ? `已超过 ${info.thresholdDays} 天阈值` : '在阈值内' }}</div>
        </AppCard>
        <AppCard class="pdr__stat" :class="{ 'pdr__stat--warn': ov.restoreDrill.stale }">
          <div class="pdr__stat-num">{{ ov.restoreDrill.daysSinceLastPassed === null ? '从未' : ov.restoreDrill.daysSinceLastPassed + ' 天前' }}</div>
          <div class="pdr__stat-label">最近一次通过的恢复演练</div>
          <div class="pdr__stat-sub">{{ ov.restoreDrill.stale ? `已超过 ${ov.restoreDrill.thresholdDays} 天阈值` : '在阈值内' }}</div>
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
        <AppSectionHeader title="人工登记备份证据" />
        <p class="pdr__note">用于登记本系统之外真实发生的备份（比如云数据库自带的自动备份、运维手动跑的 mysqldump）——本页不会替你执行备份，只记录"确实发生过"这件事。</p>
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
          <button class="mp-link" @click="submitEvidence">登记</button>
        </div>
      </AppCard>

      <AppCard class="pdr__panel">
        <AppSectionHeader title="备份证据列表" />
        <DataTable :columns="evidenceColumns" :rows="evidenceList" row-key="id">
          <template #cell-status="{ row }">
            <StatusTag :type="row.status === 'SUCCEEDED' ? 'success' : 'danger'" :label="row.status" />
          </template>
        </DataTable>
      </AppCard>

      <AppCard class="pdr__panel">
        <AppSectionHeader title="人工登记恢复演练" />
        <p class="pdr__note">真的在隔离环境用备份做过一次恢复、核对过数据之后，登记在这里——这是唯一能证明"备份真的能用"的证据，光有备份文件不算。</p>
        <div class="pdr__form">
          <select v-model="drillForm.status" class="pdr__input">
            <option value="PASSED">通过</option>
            <option value="FAILED">未通过</option>
          </select>
          <input v-model.trim="drillForm.targetDescription" class="pdr__input" placeholder="演练说明（如：在测试服恢复2026-08备份并核对学生数）" />
          <button class="mp-link" @click="submitDrill">登记</button>
        </div>
        <ul class="pdr__list">
          <li v-for="d in drillList" :key="d.id">
            <StatusTag :type="d.status === 'PASSED' ? 'success' : 'danger'" :label="d.status" /> {{ d.targetDescription || '（无说明）' }}
          </li>
        </ul>
      </AppCard>
    </template>
  </ModulePageShell>
</template>

<script>
/** PLAT-12 备份恢复验证与灾备：证据登记 + 只读结构自检，不执行真实备份/恢复动作。 */
import { AppCard, AppSectionHeader } from '@/components/ui'
import { DataTable, ErrorState, LoadingState, ModulePageShell, ModuleToolbar, StatusTag } from '@/components/business'
import { platformControlApi } from '@/modules/platform/api/platformControl.api'
import { toast } from '@/utils/toast'

const TYPE_LABELS = {
  DATABASE_DUMP: '数据库备份', SCHEMA_INTEGRITY: '表结构自检',
  FILE_STORAGE_SYNC: '文件存储同步', CLOUD_MANAGED: '云厂商托管备份'
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
          res.data.status === 'SUCCEEDED' ? '结构自检通过' : `结构自检未通过：${res.data.errorMessage}`
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
        toast.success('已登记')
        this.evidenceForm.locationRef = ''
        this.load()
      } else toast.error(res.message)
    },
    async submitDrill() {
      const res = await platformControlApi.createRestoreDrill({
        drillType: 'MANUAL_CONFIRMED', ...this.drillForm
      })
      if (res.code === 0) {
        toast.success('已登记')
        this.drillForm.targetDescription = ''
        this.load()
      } else toast.error(res.message)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.pdr__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--space-3);
}
.pdr__stat {
  padding: var(--space-4);
}
.pdr__stat--warn {
  border-color: var(--color-warning, #d97706);
}
.pdr__stat-num {
  font-size: 22px;
  font-weight: var(--font-weight-bold);
  color: var(--t1);
}
.pdr__stat-label {
  margin-top: 2px;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.pdr__stat-sub {
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-tertiary);
}
.pdr__panel {
  margin-top: var(--space-3);
  padding: var(--space-4);
}
.pdr__note {
  margin-top: var(--space-2);
  font-size: 12px;
  color: var(--text-tertiary);
  line-height: 1.6;
}
.pdr__form {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-2);
}
.pdr__input {
  padding: 6px 10px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm, 4px);
  font-size: var(--font-size-sm);
}
.pdr__list {
  list-style: none;
  margin: var(--space-2) 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
</style>
