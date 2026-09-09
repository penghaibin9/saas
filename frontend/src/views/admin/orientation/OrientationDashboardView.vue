<template>
  <ModulePageShell flat title="迎新工作台" :subtitle="subtitle" :role-name="roleName" :data-scope-name="dataScopeName" watermark-purpose="迎新看板查阅">
    <div class="batch-toolbar"><label for="orientation-workspace-batch">迎新批次</label><select id="orientation-workspace-batch" v-model="selectedBatch" @change="changeBatch"><option value="">当前批次</option><option v-for="b in batches" :key="b.id" :value="String(b.id)">{{ b.batchName }} · {{ b.statusLabel }}</option></select><button type="button" @click="load">刷新</button></div>
    <LoadingState v-if="loading" text="正在加载迎新看板…" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <template v-else-if="board">
      <div class="flat-note"><strong>{{ board.batchName }}</strong><span>{{ board.batchPeriod }}</span></div>
      <BusinessMetrics :items="board.kpis" />
      <section class="orientation-tasks">
        <h2>待办事项</h2>
        <button v-for="t in board.todos" :key="t.id" type="button" @click="goLink(t.label.includes('绿色通道') ? '/admin/orientation/green-channels' : t.link)"><span>{{ t.label }}</span><strong>{{ t.value }}</strong><span class="mp-link">{{ Number(t.value) > 0 ? '处理' : '查看' }}</span></button>
        <p v-if="!board.todos?.length" class="flat-note">暂无待办</p>
      </section>

      <div class="ori-grid">
        <div class="ori-col">
          <section class="ori-section">
            <div class="ori-section__head">
              <h3 class="ori-section__title">报到环节完成漏斗</h3>
              <button type="button" class="ori-section__more" @click="go('/admin/orientation/progress')">查看报到进度 →</button>
            </div>
            <p v-if="!board.stepFunnel?.length" class="flat-note">暂无报到环节数据</p>
            <div v-for="s in board.stepFunnel" :key="s.key" class="ori-rate">
              <div class="ori-rate__head">
                <span>{{ s.label }}</span>
                <span class="ori-rate__value">{{ s.done }}/{{ totalStudents }}</span>
              </div>
              <div class="ori-rate__track"><div class="ori-rate__bar" :style="{ width: funnelWidth(s) }" /></div>
            </div>
          </section>

          <section class="ori-section" style="margin-top: var(--space-4)">
            <div class="ori-section__head">
              <h3 class="ori-section__title">学院预报到完成率</h3>
              <button type="button" class="ori-section__more" @click="go('/admin/orientation/students')">查看新生列表 →</button>
            </div>
            <p v-if="!board.collegeRates?.length" class="flat-note">暂无学院报到数据</p>
            <div v-for="c in board.collegeRates" :key="c.name" class="ori-rate">
              <div class="ori-rate__head">
                <span>{{ c.name }}</span>
                <span class="ori-rate__value">{{ c.prepared }}/{{ c.total }} · {{ c.rate }}%</span>
              </div>
              <div class="ori-rate__track"><div class="ori-rate__bar" :style="{ width: c.rate + '%' }" /></div>
            </div>
          </section>
        </div>

        <div class="ori-col">


          <section class="ori-section" style="margin-top: var(--space-4)">
            <h3 class="ori-section__title">风险提醒</h3>
            <button type="button" v-for="r in board.riskAlerts" :key="r.id" class="ori-alert" @click="goLink(r.link)">
              <RiskTag :level="r.level" />
              <span class="ori-alert__title">{{ r.title }}</span>
              <span>查看</span>
            </button>
            <p v-if="!board.riskAlerts?.length" class="flat-note">暂无风险提醒</p>
          </section>
        </div>
      </div>
    </template>
  </ModulePageShell>
</template>

<script>
import BusinessMetrics from '@/components/workspace/BusinessMetrics.vue'
/** 页面 1：/admin/orientation 数字迎新首页 / 管理看板（数据全部来自迎新正式 API）。 */
import { ModulePageShell, LoadingState, ErrorState, RiskTag } from '@/components/business'
import { getOrientationContext, getOrientationDashboard, getOrientationBatches } from '@/modules/orientation/api/orientation.api'

const LINKS = {
  students: '/admin/orientation/students',
  progress: '/admin/orientation/progress',
  payment: '/admin/orientation/payment',
  materials: '/admin/orientation/materials',
  dorm: '/admin/orientation/dorm',
  exceptions: '/admin/orientation/exceptions'
}

export default {
  name: 'OrientationDashboardView',
  components: { BusinessMetrics, ModulePageShell, LoadingState, ErrorState, RiskTag },
  data() {
    return { loading: true, error: '', board: null, ctx: null, batches: [], batchesLoaded: false, selectedBatch: '', requestSerial: 0 }
  },
  computed: {
    roleName() {
      return this.ctx?.currentRole?.roleName || ''
    },
    dataScopeName() {
      return this.ctx?.dataScope?.name || ''
    },
    subtitle() {
      return this.ctx ? `${this.ctx.tenantBrandConfig.schoolName} · ${this.ctx.tenantBrandConfig.platformDisplayName}` : ''
    },
    heroChips() {
      if (!this.ctx) return []
      return [`角色：${this.roleName}`, `数据范围：${this.dataScopeName}`]
    },
    totalStudents() {
      const kpi = this.board?.kpis?.find((k) => k.key === 'total')
      return kpi ? Number(kpi.value) : 0
    }
  },
  created() {
    this.selectedBatch = String(this.$route.query.batchId || '')
    this.load()
  },
  watch: { '$route.query.batchId'(value) { const next = String(value || ''); if (next !== this.selectedBatch) { this.selectedBatch = next; this.load() } } },
  methods: {
    changeBatch() {
      this.$router.replace({ query: { ...this.$route.query, batchId: this.selectedBatch || undefined } })
      this.load()
    },
    go(path) {
      this.$router.push(['/admin/orientation/students', '/admin/orientation/materials', '/admin/orientation/green-channels', '/admin/orientation/exceptions'].includes(path) && this.board?.batchId ? { path, query: { batchId: this.board.batchId } } : path)
    },
    goLink(link) {
      if (link && String(link).startsWith('/')) {
        this.go(link)
        return
      }
      if (LINKS[link]) this.go(LINKS[link])
    },
    funnelWidth(s) {
      if (!this.totalStudents) return '0%'
      return `${Math.round((s.done / this.totalStudents) * 100)}%`
    },
    async load() {
      const serial = ++this.requestSerial
      this.loading = true
      this.error = ''
      try {
        if (!this.batchesLoaded) {
          const batches = []
          for (let page = 1; ; page++) {
            const result = await getOrientationBatches({ page, pageSize: 200 })
            if (result.code !== 0) throw new Error(result.message || '批次读取失败')
            const rows = result.data.list || []
            batches.push(...rows)
            if (!rows.length || batches.length >= result.data.total) break
          }
          if (serial !== this.requestSerial) return
          this.batches = batches
          this.batchesLoaded = true
        }
        const [ctxRes, boardRes] = await Promise.all([getOrientationContext(), getOrientationDashboard({ batchId: this.selectedBatch || undefined })])
        if (serial !== this.requestSerial) return
        if (ctxRes.code === 0) this.ctx = ctxRes.data
        if (boardRes.code === 0) this.board = boardRes.data
        else this.error = boardRes.message
      } catch (e) {
        if (serial === this.requestSerial) this.error = e.message || '加载失败'
      } finally {
        if (serial === this.requestSerial) this.loading = false
      }
    }
  }
}
</script>

<style scoped>
.batch-toolbar{display:flex;align-items:center;gap:12px;margin-bottom:16px;flex-wrap:wrap}.batch-toolbar select{max-width:100%;min-height:36px;padding:6px 10px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--t1)}.batch-toolbar button{color:var(--pri);background:transparent;border:0;cursor:pointer}
@import './orientation-page.css';
.orientation-tasks{border-bottom:1px solid var(--line);padding:0 0 12px}.orientation-tasks h2{font-size:15px;margin:4px 0 8px}.orientation-tasks button{display:flex;align-items:center;gap:18px;width:100%;padding:12px 0;border:0;border-top:1px solid var(--line);background:transparent;color:var(--t1);text-align:left;cursor:pointer}.orientation-tasks button>span:first-child{flex:1}.orientation-tasks button:hover{background:var(--pri-50)}.orientation-tasks strong{font-variant-numeric:tabular-nums;font-size:18px}.ori-grid{grid-template-columns:minmax(0,1.4fr) minmax(240px,1fr);gap:28px}.ori-section{padding:10px 0!important}.ori-alert{width:100%;background:transparent;color:var(--t1);border:0;border-bottom:1px solid var(--line);text-align:left}.ori-rate__bar{background:var(--pri)}.ori-rate__track{background:var(--line);height:4px}.ori-section__title{font-size:15px}@media(max-width:900px){.ori-grid{grid-template-columns:1fr}}

</style>
