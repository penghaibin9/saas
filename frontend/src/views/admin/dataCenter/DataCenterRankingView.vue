<template>
  <ModulePageShell
    title="排行分析"
    :subtitle="ranking ? ranking.scopeName + ' · 数据截至 ' + asOfLabel : '学院 / 专业 / 班级真实组织聚合'"
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
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <EmptyState
      v-else-if="!ranking || !ranking.rows || !ranking.rows.length"
      title="当前组织维度暂无排行数据"
      description="本页只展示 StudentProfile 服务端真实聚合，不使用浏览器补数。"
    />

    <div v-else class="mp-stack">
      <section class="mp-card">
        <div class="mp-card__body dcr-levels">
          <span class="mp-note">排行维度：</span>
          <button
            v-for="item in ctx.filterOptions.rankLevels"
            :key="item.value"
            type="button"
            class="dcr-levels__btn"
            :class="{ 'is-active': level === item.value }"
            @click="setLevel(item.value)"
          >
            {{ item.label }}
          </button>
        </div>
      </section>

      <section class="mp-card dcr-contract">
        <div class="mp-card__body dcr-contract__body">
          <div>
            <div class="dcr-contract__label">数据范围</div>
            <div class="dcr-contract__value">{{ scopeLabel }}</div>
          </div>
          <div>
            <div class="dcr-contract__label">统计口径</div>
            <div class="dcr-contract__value">{{ caliberLabel }}</div>
          </div>
          <div>
            <div class="dcr-contract__label">数据来源</div>
            <div class="dcr-contract__value">{{ sourceNames || 'StudentProfile' }}</div>
          </div>
          <div>
            <div class="dcr-contract__label">质量提示</div>
            <div class="dcr-contract__value">{{ qualityFlags.length ? qualityFlags.length + ' 项' : '无阻断项' }}</div>
          </div>
        </div>
      </section>

      <section class="mp-card">
        <div class="mp-card__head">
          <span class="mp-card__title">{{ ranking.scopeName }}</span>
          <span class="mp-note">覆盖 {{ ranking.totalCount }} 名学生</span>
        </div>
        <div class="mp-card__body">
          <DataTable :columns="columns" :rows="ranking.rows" row-key="id">
            <template #cell-rank="{ row }">
              <span class="dcr-rank" :class="{ 'is-top': row.rank <= 3 }">{{ row.rank }}</span>
            </template>
            <template #cell-name="{ row }">
              <button class="mp-link" :title="canDrill ? '查看该组织学生清单' : drillReason" @click="onRowClick(row)">
                {{ row.name }}
              </button>
              <div class="mp-cell-sub">{{ row.studentCount }} 人</div>
            </template>
            <template #cell-completion="{ row }">
              <div class="dcr-bar">
                <div class="dcr-bar__track"><div class="dcr-bar__fill" :style="{ width: row.completionRate + '%' }" /></div>
                <span class="dcr-bar__value">{{ row.completionRate }}%</span>
              </div>
            </template>
            <template #cell-employmentRate="{ row }"><span class="dcr-num">{{ row.employmentRate }}%</span></template>
            <template #cell-risk="{ row }"><span class="dcr-num">{{ row.riskCount }} 人</span></template>
            <template #cell-delta="{ row }"><span class="dcr-delta" :class="'is-' + (row.deltaQuality || 'neutral')">{{ row.delta }}</span></template>
          </DataTable>
        </div>
      </section>

      <section class="mp-card">
        <div class="mp-card__head"><span class="mp-card__title">口径说明</span></div>
        <div class="mp-card__body mp-stack">
          <p class="mp-note">{{ ranking.note }}</p>
          <div v-for="flag in qualityFlags" :key="flag.code" class="dcr-quality">
            <StatusTag :type="flag.severity === 'ERROR' ? 'danger' : 'info'" :label="flag.code" />
            <span>{{ flag.message }}</span>
          </div>
        </div>
      </section>
    </div>

    <AppDrawer v-model:visible="drill.visible" :title="drill.row ? drill.row.name + ' · 学生清单' : '学生清单'">
      <div class="mp-stack">
        <p class="mp-note">本清单由服务端按当前组织 ID 查询，学号已在服务端脱敏；不使用浏览器名单过滤冒充结果。</p>
        <ErrorState v-if="drill.error" :description="drill.error" @retry="loadDrill" />
        <LoadingState v-else-if="drill.loading" text="正在加载组织学生清单…" />
        <EmptyState v-else-if="!drill.rows.length" title="该组织暂无学生" description="当前权威主档中没有符合条件的学生。" />
        <DataTable
          v-else
          :columns="drillColumns"
          :rows="drill.rows"
          row-key="studentNo"
          :pagination="drill.pagination"
          @page-change="onDrillPage"
        >
          <template #cell-student="{ row }">
            <div class="mp-cell-main">{{ row.name }}</div>
            <div class="mp-cell-sub">{{ row.studentNo }}</div>
          </template>
          <template #cell-stage="{ row }">
            <div class="mp-cell-main">{{ row.stage || '—' }}</div>
            <div class="mp-cell-sub">{{ row.collegeName || '—' }}</div>
          </template>
          <template #cell-status="{ row }">{{ row.studentStatus || '—' }}</template>
        </DataTable>
      </div>
    </AppDrawer>

    <AppDrawer v-model:visible="guideVisible" title="排行数据口径">
      <div class="mp-stack">
        <div class="mp-kv"><span class="mp-kv__k">数据截至</span><span class="mp-kv__v">{{ asOfLabel }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">数据范围</span><span class="mp-kv__v">{{ scopeLabel }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">来源</span><span class="mp-kv__v">{{ sourceNames || 'StudentProfile' }}</span></div>
        <p class="mp-note">{{ ranking ? ranking.note : '' }}</p>
        <div v-for="flag in qualityFlags" :key="'guide-' + flag.code" class="dcr-quality">
          <StatusTag :type="flag.severity === 'ERROR' ? 'danger' : 'info'" :label="flag.code" />
          <span>{{ flag.message }}</span>
        </div>
      </div>
    </AppDrawer>
  </ModulePageShell>
</template>

<script>
import {
  ModulePageShell,
  ModuleToolbar,
  DataTable,
  StatusTag,
  LoadingState,
  ErrorState,
  EmptyState
} from '@/components/business'
import { AppGlobalState } from '@/components/common'
import { AppDrawer } from '@/components/ui'
import { dataCenterApi } from '@/modules/dataCenter/api/dataCenter.api'

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
        { key: 'employmentRate', title: '去向代理率', width: '110px' },
        { key: 'risk', title: '异常学籍', width: '110px' },
        { key: 'delta', title: '较上期', width: '90px' }
      ],
      drill: {
        visible: false,
        row: null,
        loading: false,
        error: '',
        rows: [],
        pagination: { page: 1, pageSize: 10, total: 0 }
      },
      drillColumns: [
        { key: 'student', title: '学生' },
        { key: 'stage', title: '阶段 / 学院' },
        { key: 'status', title: '学籍状态' }
      ],
      guideVisible: false
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
      return pa && !pa.allowed ? pa.reason : '当前角色不可查看组织学生明细'
    },
    toolbarActions() {
      return [{ key: 'metricGuide', label: '数据口径与质量', variant: 'ghost' }]
    },
    meta() {
      return (this.ranking && this.ranking.meta) || {}
    },
    qualityFlags() {
      return Array.isArray(this.meta.qualityFlags) ? this.meta.qualityFlags : []
    },
    sourceNames() {
      const rows = Array.isArray(this.meta.source) ? this.meta.source : []
      return rows.map((x) => x.module).filter(Boolean).join('、')
    },
    scopeLabel() {
      return (this.meta.scope && this.meta.scope.scopeName) || this.ctx.dataScope.scopeName || '—'
    },
    caliberLabel() {
      return this.meta.caliberLabel || '在册组织主档代理口径'
    },
    asOfLabel() {
      return this.meta.asOf || '—'
    }
  },
  created() {
    if (this.viewAllowed) this.load()
  },
  methods: {
    setLevel(value) {
      if (value === this.level) return
      this.level = value
      this.load()
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await dataCenterApi.getRankings({ level: this.level })
      if (res.code === 0) {
        this.ranking = res.data
      } else {
        this.ranking = null
        this.error = res.message
      }
      this.loading = false
    },
    onRowClick(row) {
      if (!this.canDrill) return
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
        this.drill.rows = res.data.list || []
        this.drill.pagination.total = res.data.total || 0
      } else {
        this.drill.rows = []
        this.drill.error = res.message
      }
      this.drill.loading = false
    },
    onToolbar(key) {
      if (key === 'metricGuide') this.guideVisible = true
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.dcr-levels {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.dcr-levels__btn {
  border: 1px solid var(--border-base);
  border-radius: var(--radius-full);
  background: var(--bg-card);
  color: var(--text-secondary);
  padding: var(--space-1) var(--space-4);
  cursor: pointer;
}
.dcr-levels__btn.is-active {
  background: var(--primary-600);
  border-color: var(--primary-600);
  color: var(--text-inverse);
}
.dcr-contract__body {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-4);
}
.dcr-contract__label { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.dcr-contract__value {
  margin-top: var(--space-1);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  overflow-wrap: anywhere;
}
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
}
.dcr-rank.is-top { background: var(--primary-600); color: var(--text-inverse); }
.dcr-bar { display: flex; align-items: center; gap: var(--space-2); }
.dcr-bar__track {
  flex: 1;
  height: 10px;
  background: var(--gray-100);
  border-radius: var(--radius-full);
  overflow: hidden;
}
.dcr-bar__fill { height: 100%; background: var(--primary-600); border-radius: var(--radius-full); }
.dcr-bar__value,
.dcr-num,
.dcr-delta { font-size: var(--font-size-xs); font-variant-numeric: var(--font-numeric); }
.dcr-delta.is-good { color: var(--trend-good); }
.dcr-delta.is-bad { color: var(--trend-bad); }
.dcr-delta.is-neutral { color: var(--trend-neutral); }
.dcr-quality {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
}
@media (max-width: 960px) {
  .dcr-contract__body { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
