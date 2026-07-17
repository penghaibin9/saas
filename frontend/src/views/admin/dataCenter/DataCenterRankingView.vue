<template>
  <ModulePageShell
    title="排行分析"
    :subtitle="ranking ? '统计范围：' + ranking.scopeName + ' · 学生数合计 ' + ranking.totalCount + ' 人' : '学院 / 专业 / 班级多层级横向对比'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <AppGlobalState
      v-if="!viewAllowed"
      state="forbidden"
      :description="viewReason"
      @back="$router.push('/admin/data-center')"
    />
    <div v-else class="mp-stack">
      <div class="mp-tabs">
        <button
          v-for="l in ctx.filterOptions.rankLevels"
          :key="l.value"
          type="button"
          class="mp-tab"
          :class="{ 'is-active': level === l.value }"
          @click="setLevel(l.value)"
        >
          {{ l.label }}
        </button>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!ranking || !ranking.rows.length" title="暂无排行数据" description="当前维度下没有可对比的组织单元" />
      <template v-else>
        <DataTable
          :columns="columns"
          :rows="ranking.rows"
          row-key="id"
          row-clickable
          @row-click="onRowClick"
        >
          <template #cell-rank="{ row }">
            <span class="dcr-rank" :class="{ 'is-top': row.rank <= 3 }">{{ row.rank }}</span>
          </template>
          <template #cell-name="{ row }">
            <div class="mp-cell-main">{{ row.name }}</div>
            <div class="mp-cell-sub">在册 {{ row.studentCount }} 人</div>
          </template>
          <template #cell-completion="{ row }">
            <div class="dcr-bar">
              <div class="dcr-bar__track">
                <div class="dcr-bar__fill" :style="{ width: row.completionRate + '%' }" />
              </div>
              <span class="dcr-bar__value">{{ row.completionRate }}%</span>
            </div>
          </template>
          <template #cell-employmentRate="{ row }">
            <span class="dcr-num">{{ row.employmentRate }}%</span>
          </template>
          <template #cell-risk="{ row }">
            <StatusTag :type="row.riskCount > 25 ? 'danger' : row.riskCount > 10 ? 'warning' : 'default'" :label="row.riskCount + ' 条'" />
          </template>
          <template #cell-delta="{ row }">
            <span class="dcr-delta" :class="'is-' + (row.deltaQuality || 'neutral')">{{ row.delta }}</span>
          </template>
        </DataTable>
        <p class="mp-note">{{ ranking.note }}；点击任意一行可下钻查看该组织的重点关注学生。</p>
      </template>
    </div>

    <AppDrawer v-model:visible="drill.visible" :title="drill.row ? drill.row.name + ' · 下钻明细' : '下钻明细'">
      <div v-if="drill.row" class="mp-stack">
        <section class="mp-card">
          <div class="mp-card__body">
            <div class="mp-kv"><span class="mp-kv__k">当前名次</span><span class="mp-kv__v">第 {{ drill.row.rank }} 名（较上期 {{ drill.row.delta }}）</span></div>
            <div class="mp-kv"><span class="mp-kv__k">在册学生</span><span class="mp-kv__v">{{ drill.row.studentCount }} 人</span></div>
            <div class="mp-kv"><span class="mp-kv__k">综合完成率</span><span class="mp-kv__v">{{ drill.row.completionRate }}%</span></div>
            <div class="mp-kv"><span class="mp-kv__k">去向落实率</span><span class="mp-kv__v">{{ drill.row.employmentRate }}%</span></div>
            <div class="mp-kv"><span class="mp-kv__k">风险预警</span><span class="mp-kv__v">{{ drill.row.riskCount }} 条</span></div>
          </div>
        </section>
        <p class="mp-note">重点关注学生样本（学号 / 手机号已脱敏，查询已留痕）：</p>
        <ErrorState v-if="drill.error" :description="drill.error" @retry="loadDrill" />
        <LoadingState v-else-if="drill.loading" text="正在加载学生清单…" />
        <EmptyState
          v-else-if="!drill.rows.length"
          title="该组织暂无重点关注学生"
          description="演示数据集未包含该组织的学生样本"
        />
        <DataTable
          v-else
          :columns="drillColumns"
          :rows="drill.rows"
          row-key="id"
          :pagination="drill.pagination"
          @page-change="onDrillPage"
        >
          <template #cell-student="{ row }">
            <div class="mp-cell-main">{{ row.name }}</div>
            <div class="mp-cell-sub">{{ maskNo(row.studentNo) }} · {{ maskPhone(row.phone) }}</div>
          </template>
          <template #cell-stage="{ row }">
            <div class="mp-cell-main" style="font-size: var(--font-size-sm)">{{ row.stageLabel }}</div>
            <div class="mp-cell-sub">{{ row.className }}</div>
          </template>
          <template #cell-status="{ row }">
            <StatusTag :type="row.tone" :label="row.statusLabel" />
          </template>
        </DataTable>
      </div>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="exportVisible"
      type="primary"
      title="导出排行分析数据"
      :message="ctx.exportOptions.policyNote"
      confirm-text="确认导出"
      :submitting="exporting"
      @confirm="onExportConfirm"
    >
      <div class="mp-note" style="margin-bottom: var(--space-2)">导出用途（必选，写入审计日志）</div>
      <div
        v-for="p in ctx.exportOptions.purposes"
        :key="p.value"
        class="mp-radio"
        :class="{ 'is-active': exportPurpose === p.value }"
        @click="exportPurpose = p.value"
      >
        <input type="radio" :checked="exportPurpose === p.value" style="margin-top: 3px" />
        <div>
          <div class="mp-radio__title">{{ p.label }}</div>
          <div class="mp-radio__desc">{{ p.desc }}</div>
        </div>
      </div>
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
/**
 * 排行分析（/admin/data-center/rankings）。
 * 学院 / 专业 / 班级三级切换；完成率以纯 CSS 横向条呈现；
 * 行点击下钻组织重点学生（脱敏），导出需确认用途并留痕。
 */
import {
  ModulePageShell,
  ModuleToolbar,
  DataTable,
  StatusTag,
  LoadingState,
  ErrorState,
  EmptyState
} from '@/components/business'
import { AppGlobalState, AppConfirmDialog } from '@/components/common'
import { AppDrawer } from '@/components/ui'
import { dataCenterApi } from '@/modules/dataCenter/api/dataCenter.api'
import { toast } from '@/utils/toast'

const LEVEL_ORG_PARAM = { COLLEGE: 'collegeId', MAJOR: 'majorId', CLASS: 'classId' }

export default {
  name: 'DataCenterRankingView',
  components: {
    ModulePageShell,
    ModuleToolbar,
    DataTable,
    StatusTag,
    LoadingState,
    ErrorState,
    EmptyState,
    AppGlobalState,
    AppConfirmDialog,
    AppDrawer
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      level: 'COLLEGE',
      ranking: null,
      columns: [
        { key: 'rank', title: '名次', width: '70px' },
        { key: 'name', title: '组织单元' },
        { key: 'completion', title: '综合完成率', width: '220px' },
        { key: 'employmentRate', title: '去向落实率', width: '110px' },
        { key: 'risk', title: '风险预警', width: '110px' },
        { key: 'delta', title: '较上期', width: '90px' }
      ],
      drill: {
        visible: false,
        row: null,
        loading: false,
        error: '',
        rows: [],
        pagination: { page: 1, pageSize: 5, total: 0 }
      },
      drillColumns: [
        { key: 'student', title: '学生' },
        { key: 'stage', title: '阶段 / 班级' },
        { key: 'status', title: '状态' }
      ],
      exportVisible: false,
      exportPurpose: 'INTERNAL_ANALYSIS',
      exporting: false
    }
  },
  computed: {
    viewAllowed() {
      const pa = this.ctx.permissionActions.viewRankings
      return !!(pa && pa.visible && pa.allowed)
    },
    viewReason() {
      const pa = this.ctx.permissionActions.viewRankings
      return (pa && pa.reason) || '当前角色未开通排行分析查看权限'
    },
    canDrill() {
      const pa = this.ctx.permissionActions.drilldownStudents
      return !!(pa && pa.visible && pa.allowed)
    },
    drillReason() {
      const pa = this.ctx.permissionActions.drilldownStudents
      return pa && !pa.allowed ? pa.reason : ''
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [{ key: 'exportRanking', label: '导出排行数据', variant: 'primary' }]
        .filter((a) => pa[a.key] && pa[a.key].visible)
        .map((a) => ({ ...a, disabled: !pa[a.key].allowed, disabledReason: pa[a.key].reason }))
    }
  },
  created() {
    this.load()
  },
  methods: {
    maskPhone(v) {
      return v ? v.slice(0, 3) + '****' + v.slice(-4) : '未登记'
    },
    maskNo(v) {
      return v ? v.slice(0, -4) + '**' + v.slice(-2) : ''
    },
    setLevel(value) {
      if (value === this.level) return
      this.level = value
      this.load()
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await dataCenterApi.getRankings({ level: this.level })
      if (res.code === 0) this.ranking = res.data
      else this.error = res.message
      this.loading = false
    },
    onRowClick(row) {
      if (!this.canDrill) {
        toast.info(this.drillReason || '当前角色不可查看学生明细')
        return
      }
      this.drill.row = row
      this.drill.visible = true
      this.drill.pagination.page = 1
      this.loadDrill()
    },
    onDrillPage(page) {
      this.drill.pagination.page = page
      this.loadDrill()
    },
    async loadDrill() {
      if (!this.drill.row) return
      this.drill.loading = true
      this.drill.error = ''
      const params = {
        metricKey: 'ALL',
        page: this.drill.pagination.page,
        pageSize: this.drill.pagination.pageSize
      }
      const orgKey = LEVEL_ORG_PARAM[this.level]
      if (orgKey) params[orgKey] = this.drill.row.id
      const res = await dataCenterApi.getDrilldownStudents(params)
      if (res.code === 0) {
        this.drill.rows = res.data.list
        this.drill.pagination.total = res.data.total
      } else {
        this.drill.error = res.message
      }
      this.drill.loading = false
    },
    onToolbar(key) {
      if (key === 'exportRanking') {
        this.exportPurpose = 'INTERNAL_ANALYSIS'
        this.exportVisible = true
      }
    },
    async onExportConfirm() {
      this.exporting = true
      const res = await dataCenterApi.exportData({ scope: 'RANKING', purpose: this.exportPurpose })
      this.exporting = false
      if (res.code === 0) {
        this.exportVisible = false
        toast.success('导出任务 ' + res.data.taskId + ' 已登记并写入审计日志（演示态，暂未生成实际文件）')
      } else {
        toast.error(res.message)
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.dcr-rank {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: var(--radius-full);
  background: var(--gray-100);
  color: var(--gray-600);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
  font-variant-numeric: var(--font-numeric);
}
.dcr-rank.is-top {
  background: var(--primary-600);
  color: var(--text-inverse);
  box-shadow: var(--shadow-capsule);
}
.dcr-bar {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.dcr-bar__track {
  flex: 1;
  height: 10px;
  background: var(--gray-100);
  border-radius: var(--radius-full);
  overflow: hidden;
}
.dcr-bar__fill {
  height: 100%;
  border-radius: var(--radius-full);
  background: linear-gradient(90deg, var(--primary-500), var(--primary-600));
}
.dcr-bar__value {
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  font-variant-numeric: var(--font-numeric);
  min-width: 44px;
  text-align: right;
}
.dcr-num {
  font-variant-numeric: var(--font-numeric);
}
.dcr-delta {
  font-size: var(--font-size-xs);
  font-variant-numeric: var(--font-numeric);
}
.dcr-delta.is-good { color: var(--trend-good); }
.dcr-delta.is-bad { color: var(--trend-bad); }
.dcr-delta.is-neutral { color: var(--trend-neutral); }
</style>
