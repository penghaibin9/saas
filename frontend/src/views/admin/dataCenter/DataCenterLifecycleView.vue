<template>
  <ModulePageShell
    title="学生生命周期总览"
    :subtitle="lifecycle ? '全校实时聚合 · 数据截至 ' + asOfLabel : '迎新报到 → 就业去向 全流程漏斗'"
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
      v-else-if="!lifecycle || !lifecycle.funnel || !lifecycle.funnel.stages.length"
      title="当前全校口径暂无生命周期数据"
      description="本页只展示服务端可证明的全校实时聚合，不使用浏览器估算或演示数据补齐。"
    />

    <div v-else class="mp-stack">
      <section class="mp-card dclc-contract">
        <div class="mp-card__body dclc-contract__body">
          <div>
            <div class="dclc-contract__label">数据范围</div>
            <div class="dclc-contract__value">{{ scopeLabel }}</div>
          </div>
          <div>
            <div class="dclc-contract__label">统计口径</div>
            <div class="dclc-contract__value">{{ caliberLabel }}</div>
          </div>
          <div>
            <div class="dclc-contract__label">数据来源</div>
            <div class="dclc-contract__value">{{ sourceNames || '服务端真实聚合' }}</div>
          </div>
          <div>
            <div class="dclc-contract__label">质量提示</div>
            <div class="dclc-contract__value">{{ qualityFlags.length ? qualityFlags.length + ' 项' : '无阻断项' }}</div>
          </div>
        </div>
      </section>

      <div class="mp-grid-2">
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
                <span class="dclc-stage__count">{{ s.count }} 人 · 占全校 {{ s.rate }}%</span>
              </div>
              <div class="dclc-stage__track">
                <div class="dclc-stage__bar" :style="{ width: barWidth(s) }" />
              </div>
              <div class="dclc-stage__side">
                <span class="dclc-stage__abnormal">异常/待跟进 {{ s.abnormal }} 人</span>
                <span class="mp-note">{{ s.note }}</span>
              </div>
            </div>
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
            <p class="dclc-boundary">
              阶段重点学生名单尚未形成跨域统一服务端口径。本页不返回“全校学生”冒充命中名单；明细处置请进入对应业务模块。
            </p>
          </div>
        </section>
      </div>

      <section v-if="qualityFlags.length" class="mp-card">
        <div class="mp-card__head"><span class="mp-card__title">数据质量提示</span></div>
        <div class="mp-card__body mp-stack">
          <div v-for="flag in qualityFlags" :key="flag.code" class="dclc-quality">
            <StatusTag :type="flag.severity === 'ERROR' ? 'danger' : 'info'" :label="flag.code" />
            <span>{{ flag.message }}</span>
          </div>
        </div>
      </section>
    </div>

    <AppDrawer v-model:visible="guideVisible" title="生命周期数据口径">
      <div class="mp-stack">
        <div class="mp-kv"><span class="mp-kv__k">数据截至</span><span class="mp-kv__v">{{ asOfLabel }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">统计口径</span><span class="mp-kv__v">{{ caliberLabel }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">数据范围</span><span class="mp-kv__v">{{ scopeLabel }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">来源</span><span class="mp-kv__v">{{ sourceNames || '服务端真实聚合' }}</span></div>
        <p class="mp-note">
          当前 A4 只开放后端已实现的全校实时口径。学院、专业、班级、年级、时间范围筛选以及阶段命中名单未服务端化前不展示，防止浏览器估算被误认为正式事实。
        </p>
        <div v-for="flag in qualityFlags" :key="'drawer-' + flag.code" class="dclc-quality">
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
  StatusTag,
  LoadingState,
  ErrorState,
  EmptyState
} from '@/components/business'
import { AppGlobalState } from '@/components/common'
import { AppDrawer } from '@/components/ui'
import { dataCenterApi } from '@/modules/dataCenter/api/dataCenter.api'

export default {
  name: 'DataCenterLifecycleView',
  components: {
    ModulePageShell,
    ModuleToolbar,
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
      lifecycle: null,
      activeStageKey: 'ORIENTATION',
      guideVisible: false
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
    toolbarActions() {
      return [{ key: 'metricGuide', label: '数据口径与质量', variant: 'ghost' }]
    },
    activeStage() {
      if (!this.lifecycle || !this.lifecycle.funnel) return null
      const stages = this.lifecycle.funnel.stages || []
      return stages.find((s) => s.key === this.activeStageKey) || stages[0] || null
    },
    activeStats() {
      if (!this.lifecycle || !this.activeStage) return null
      return (this.lifecycle.stageStats || {})[this.activeStage.key] || null
    },
    meta() {
      return (this.lifecycle && this.lifecycle.meta) || {}
    },
    qualityFlags() {
      return Array.isArray(this.meta.qualityFlags) ? this.meta.qualityFlags : []
    },
    sourceNames() {
      const rows = Array.isArray(this.meta.source) ? this.meta.source : []
      return rows.map((x) => x.module).filter(Boolean).join('、')
    },
    scopeLabel() {
      return (this.meta.scope && this.meta.scope.scopeName) || this.lifecycle.scopeLabel || this.ctx.dataScope.scopeName || '—'
    },
    caliberLabel() {
      return this.meta.caliberLabel || '服务端在册口径'
    },
    asOfLabel() {
      return this.meta.asOf || (this.lifecycle && this.lifecycle.funnel && this.lifecycle.funnel.updatedAt) || '—'
    }
  },
  created() {
    if (this.viewAllowed) this.load()
  },
  methods: {
    barWidth(stage) {
      if (!this.lifecycle || !this.lifecycle.funnel || !this.lifecycle.funnel.totalCount) return '0%'
      const pct = (stage.count / this.lifecycle.funnel.totalCount) * 100
      return Math.max(4, Math.min(100, Math.round(pct * 10) / 10)) + '%'
    },
    onToolbar(key) {
      if (key === 'metricGuide') this.guideVisible = true
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await dataCenterApi.getLifecycle()
      if (res.code === 0) {
        this.lifecycle = res.data
      } else {
        this.lifecycle = null
        this.error = res.message
      }
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.dclc-contract__body {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-4);
}
.dclc-contract__label {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.dclc-contract__value {
  margin-top: var(--space-1);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  overflow-wrap: anywhere;
}
.dclc-stage {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  cursor: pointer;
  transition: border-color var(--motion-fast) var(--ease-standard), background var(--motion-fast) var(--ease-standard);
}
.dclc-stage:hover { background: var(--bg-hover); }
.dclc-stage.is-active {
  border-color: var(--primary-500);
  background: var(--primary-25);
}
.dclc-stage__meta,
.dclc-stage__side {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}
.dclc-stage__meta { margin-bottom: var(--space-2); }
.dclc-stage__side { margin-top: var(--space-2); align-items: flex-start; }
.dclc-stage__label {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
}
.dclc-stage__count,
.dclc-stage__abnormal {
  font-size: var(--font-size-xs);
  font-variant-numeric: var(--font-numeric);
}
.dclc-stage__count { color: var(--text-secondary); }
.dclc-stage__abnormal { color: var(--danger-600); white-space: nowrap; }
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
.dclc-boundary {
  margin: var(--space-4) 0 0;
  padding: var(--space-3);
  border: 1px solid var(--info-100);
  border-radius: var(--radius-md);
  background: var(--info-50);
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
  line-height: var(--line-height-base);
}
.dclc-quality {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
@media (max-width: 960px) {
  .dclc-contract__body { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
