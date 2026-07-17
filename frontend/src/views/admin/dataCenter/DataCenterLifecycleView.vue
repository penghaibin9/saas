<template>
  <ModulePageShell
    title="学生生命周期总览"
    :subtitle="lifecycle ? '统计范围：' + lifecycle.scopeLabel + ' · ' + lifecycle.funnel.cohortLabel : '迎新报到 → 就业去向 全流程漏斗'"
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
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState
        v-else-if="!lifecycle || !lifecycle.funnel.stages.length"
        title="当前筛选条件下暂无生命周期数据"
        description="可调整学院 / 年级 / 时间范围后重新查询"
      />
      <div v-else class="mp-grid-2">
        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">生命周期漏斗（{{ lifecycle.funnel.totalCount }} 人）</span>
            <span class="mp-note">更新于 {{ lifecycle.funnel.updatedAt }}</span>
          </div>
          <div class="mp-card__body mp-stack">
            <div
              v-for="s in lifecycle.funnel.stages"
              :key="s.key"
              class="dclc-stage"
              :class="{ 'is-active': activeStageKey === s.key }"
              @click="activeStageKey = s.key"
            >
              <div class="dclc-stage__meta">
                <span class="dclc-stage__label">{{ s.label }}</span>
                <span class="dclc-stage__count">{{ s.count }} 人 · 完成率 {{ s.rate }}%</span>
              </div>
              <div class="dclc-stage__track">
                <div class="dclc-stage__bar" :style="{ width: barWidth(s) }" />
              </div>
              <div class="dclc-stage__side">
                <span class="dclc-stage__abnormal">异常 {{ s.abnormal }} 人</span>
                <button class="mp-link" :class="{ 'is-disabled': !canDrill }" :title="drillReason" @click.stop="openDrill(s)">
                  学生清单
                </button>
              </div>
            </div>
            <p class="mp-note">
              漏斗人数为进入并完成对应阶段的学生数，逐阶段递减；异常数指该阶段规则命中且未闭环的学生。
            </p>
          </div>
        </section>

        <section v-if="activeStage" class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">{{ activeStats ? activeStats.title : activeStage.label }}</span>
            <StatusTag type="processing" :label="activeStage.label" dot />
          </div>
          <div class="mp-card__body">
            <p v-if="activeStats" class="mp-note" style="margin: 0 0 var(--space-2)">{{ activeStats.scopeNote }}</p>
            <div v-for="it in activeStats ? activeStats.items : []" :key="it.label" class="mp-kv">
              <span class="mp-kv__k">{{ it.label }}</span>
              <span class="mp-kv__v">{{ it.value }}</span>
            </div>
            <p class="mp-note" style="margin-top: var(--space-3)">{{ activeStage.note }}</p>
            <button
              class="mp-link"
              :class="{ 'is-disabled': !canDrill }"
              :title="drillReason"
              style="margin-top: var(--space-2)"
              @click="openDrill(activeStage)"
            >
              查看该阶段重点关注学生 →
            </button>
          </div>
        </section>
      </div>
    </div>

    <AppDrawer v-model:visible="drill.visible" :title="drill.stage ? drill.stage.label + ' · 重点关注学生' : '重点关注学生'">
      <div class="mp-stack">
        <p class="mp-note">清单仅包含需重点关注的学生样本；学号、手机号默认脱敏，查询行为已留痕。</p>
        <ErrorState v-if="drill.error" :description="drill.error" @retry="loadDrill" />
        <LoadingState v-else-if="drill.loading" text="正在加载学生清单…" />
        <EmptyState
          v-else-if="!drill.rows.length"
          title="该阶段暂无重点关注学生"
          description="当前筛选范围内没有命中该阶段规则的学生"
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
          <template #cell-org="{ row }">
            <div class="mp-cell-main">{{ row.className }}</div>
            <div class="mp-cell-sub">{{ row.collegeName }}</div>
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
      title="导出生命周期统计"
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
 * 学生生命周期总览（/admin/data-center/lifecycle）。
 * 漏斗为纯 CSS 横向条（宽度按人数占比），阶段点击联动右侧统计；
 * 每阶段可下钻学生清单（AppDrawer + 脱敏 DataTable），导出需确认用途并留痕。
 */
import {
  ModulePageShell,
  ModuleToolbar,
  AdvancedFilter,
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

const EMPTY_FILTERS = () => ({ collegeId: '', majorId: '', classId: '', grade: '', timeRange: '' })

export default {
  name: 'DataCenterLifecycleView',
  components: {
    ModulePageShell,
    ModuleToolbar,
    AdvancedFilter,
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
      lifecycle: null,
      filters: EMPTY_FILTERS(),
      activeStageKey: 'ORIENTATION',
      drill: {
        visible: false,
        stage: null,
        loading: false,
        error: '',
        rows: [],
        pagination: { page: 1, pageSize: 5, total: 0 }
      },
      drillColumns: [
        { key: 'student', title: '学生' },
        { key: 'org', title: '班级 / 学院' },
        { key: 'status', title: '状态' },
        { key: 'lastEvent', title: '最近动态' }
      ],
      exportVisible: false,
      exportPurpose: 'INTERNAL_ANALYSIS',
      exporting: false
    }
  },
  computed: {
    viewAllowed() {
      const pa = this.ctx.permissionActions.viewLifecycle
      return !!(pa && pa.visible && pa.allowed)
    },
    viewReason() {
      const pa = this.ctx.permissionActions.viewLifecycle
      return (pa && pa.reason) || '当前角色未开通生命周期总览查看权限'
    },
    canDrill() {
      const pa = this.ctx.permissionActions.drilldownStudents
      return !!(pa && pa.visible && pa.allowed)
    },
    drillReason() {
      const pa = this.ctx.permissionActions.drilldownStudents
      return pa && !pa.allowed ? pa.reason : ''
    },
    filterFields() {
      const o = this.ctx.filterOptions
      return [
        { key: 'collegeId', label: '学院', type: 'select', options: o.colleges },
        { key: 'majorId', label: '专业', type: 'select', options: o.majors },
        { key: 'classId', label: '班级', type: 'select', options: o.classes },
        { key: 'grade', label: '年级', type: 'select', options: o.grades },
        { key: 'timeRange', label: '时间范围', type: 'select', options: o.timeRanges }
      ]
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [{ key: 'exportLifecycle', label: '导出统计数据', variant: 'primary' }]
        .filter((a) => pa[a.key] && pa[a.key].visible)
        .map((a) => ({ ...a, disabled: !pa[a.key].allowed, disabledReason: pa[a.key].reason }))
    },
    activeStage() {
      if (!this.lifecycle) return null
      const stages = this.lifecycle.funnel.stages
      return stages.find((s) => s.key === this.activeStageKey) || stages[0] || null
    },
    activeStats() {
      if (!this.lifecycle || !this.activeStage) return null
      return this.lifecycle.stageStats[this.activeStage.key] || null
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
    barWidth(stage) {
      if (!this.lifecycle || !this.lifecycle.funnel.totalCount) return '0%'
      const pct = (stage.count / this.lifecycle.funnel.totalCount) * 100
      return Math.max(4, Math.round(pct * 10) / 10) + '%'
    },
    search() {
      this.load()
    },
    reset() {
      this.filters = EMPTY_FILTERS()
      this.load()
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await dataCenterApi.getLifecycle({ ...this.filters })
      if (res.code === 0) this.lifecycle = res.data
      else this.error = res.message
      this.loading = false
    },
    openDrill(stage) {
      if (!this.canDrill) {
        toast.info(this.drillReason || '当前角色不可查看学生明细')
        return
      }
      this.drill.stage = stage
      this.drill.visible = true
      this.drill.pagination.page = 1
      this.loadDrill()
    },
    onDrillPage(page) {
      this.drill.pagination.page = page
      this.loadDrill()
    },
    async loadDrill() {
      if (!this.drill.stage) return
      this.drill.loading = true
      this.drill.error = ''
      const res = await dataCenterApi.getDrilldownStudents({
        metricKey: this.drill.stage.key,
        collegeId: this.filters.collegeId,
        page: this.drill.pagination.page,
        pageSize: this.drill.pagination.pageSize
      })
      if (res.code === 0) {
        this.drill.rows = res.data.list
        this.drill.pagination.total = res.data.total
      } else {
        this.drill.error = res.message
      }
      this.drill.loading = false
    },
    onToolbar(key) {
      if (key === 'exportLifecycle') {
        this.exportPurpose = 'INTERNAL_ANALYSIS'
        this.exportVisible = true
      }
    },
    async onExportConfirm() {
      this.exporting = true
      const res = await dataCenterApi.exportData({ scope: 'LIFECYCLE', purpose: this.exportPurpose })
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
.dclc-stage {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  cursor: pointer;
  transition: border-color var(--motion-fast) var(--ease-standard), background var(--motion-fast) var(--ease-standard);
}
.dclc-stage:hover {
  background: var(--bg-hover);
}
.dclc-stage.is-active {
  border-color: var(--primary-500);
  background: var(--primary-25);
}
.dclc-stage__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
}
.dclc-stage__label {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
}
.dclc-stage__count {
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  font-variant-numeric: var(--font-numeric);
}
.dclc-stage__track {
  height: 14px;
  background: var(--gray-100);
  border-radius: var(--radius-full);
  overflow: hidden;
}
.dclc-stage__bar {
  height: 100%;
  border-radius: var(--radius-full);
  background: linear-gradient(90deg, var(--primary-500), var(--primary-600));
  transition: width var(--motion-normal) var(--ease-standard);
}
.dclc-stage.is-active .dclc-stage__bar {
  background: linear-gradient(90deg, var(--primary-600), var(--primary-700));
}
.dclc-stage__side {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  margin-top: var(--space-2);
}
.dclc-stage__abnormal {
  font-size: var(--font-size-xs);
  color: var(--danger-600);
  font-variant-numeric: var(--font-numeric);
}
</style>
