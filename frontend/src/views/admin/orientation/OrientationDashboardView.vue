<template>
  <ModulePageShell title="迎新看板" :role-name="roleName" :data-scope-name="dataScopeName" watermark-purpose="迎新看板查阅">
    <template #actions>
      <div class="board-toolbar">
        <label for="orientation-workspace-batch">迎新批次</label>
        <select id="orientation-workspace-batch" v-model="selectedBatch" @change="changeBatch">
          <option value="">系统当前批次</option>
          <option v-for="b in batches" :key="b.id" :value="String(b.id)">{{ b.batchName }} · {{ b.statusLabel }}</option>
        </select>
        <button type="button" class="board-button" :disabled="loading" @click="load">{{ loading ? '刷新中' : '刷新数据' }}</button>
      </div>
    </template>
    <LoadingState v-if="loading" text="正在读取本批次迎新情况…" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <template v-else-if="board">
      <section class="board-overview" aria-label="当前批次与下一步">
        <div>
          <div class="board-eyebrow">当前工作批次 <span v-if="currentBatch">{{ currentBatch.statusLabel }}</span></div>
          <h2>{{ board.batchName }}</h2>
          <p class="board-period">报到时间：{{ board.batchPeriod }}</p>
          <p class="board-next">{{ nextHint }}</p>
          <div class="board-actions">
            <button type="button" class="board-button board-button--primary" @click="openRoster">{{ board.batchId ? (totalStudents ? '查看本批次新生' : '设置本批次新生') : '创建迎新批次' }}</button>
            <button type="button" class="board-button" @click="go('/admin/orientation/flow-config')">查看报到流程配置</button>
          </div>
        </div>
        <nav class="board-journey" aria-label="迎新办理顺序">
          <button v-for="(entry, index) in journey" :key="entry.path" type="button" @click="entry.roster ? openRoster() : go(entry.path)">
            <span class="board-journey__number">{{ index + 1 }}</span>
            <span><strong>{{ entry.label }}</strong><small>{{ entry.hint }}</small></span>
          </button>
        </nav>
      </section>
      <dl class="board-metrics" aria-label="本批次迎新统计">
        <div v-for="item in board.kpis" :key="item.key" class="board-metric">
          <dt>{{ item.label }}</dt><dd>{{ item.value }}</dd>
          <span v-if="item.trend" class="board-metric__note">{{ item.trend }}</span>
        </div>
      </dl>
      <section class="board-section" aria-labelledby="orientation-todo-title">
        <div class="board-section__head"><h2 id="orientation-todo-title">现在需要处理</h2><span>按当前批次与我的数据范围统计</span></div>
        <div class="board-todos">
          <button v-for="t in board.todos" :key="t.id" type="button" :class="{ 'has-pending': Number(t.value) > 0 }" @click="goLink(t.label.includes('绿色通道') ? '/admin/orientation/green-channels' : t.link)">
            <span>{{ t.label }}</span><strong>{{ t.value }}<small> 项</small></strong>
            <span class="board-todos__action">{{ Number(t.value) > 0 ? '进入处理' : '暂无待处理 · 查看记录' }}</span>
          </button>
        </div>
        <p v-if="!board.todos?.length" class="board-empty">当前没有待处理事项。</p>
      </section>
      <div class="board-columns">
        <section class="board-section" aria-labelledby="orientation-progress-title">
          <div class="board-section__head"><h2 id="orientation-progress-title">报到环节进度</h2><button type="button" class="board-link" @click="go('/admin/orientation/progress')">查看办理进度</button></div>
          <p class="board-caption">按本批次实际办理环节统计，已完成含减免及无需办理。</p>
          <div v-for="s in board.stepFunnel" :key="s.key" class="board-progress">
            <div><span>{{ s.label }}</span><strong>{{ s.done }} <small>/ {{ totalStudents }} 人</small></strong></div>
            <progress :aria-label="s.label + '完成进度'" :value="s.done" :max="Math.max(totalStudents, 1)" />
          </div>
          <div v-if="!board.stepFunnel?.length" class="board-empty">
            <strong>{{ totalStudents ? '暂未生成环节进度' : '当前批次还没有新生' }}</strong>
            <p>{{ totalStudents ? '可先查看流程配置和新生办理记录。' : '在本批次设置新生后，这里将展示真实办理情况。' }}</p>
            <button type="button" class="board-link" @click="openRoster">{{ totalStudents ? '查看新生记录' : '去设置新生' }}</button>
          </div>
        </section>
        <section class="board-section" aria-labelledby="orientation-attention-title">
          <div class="board-section__head"><h2 id="orientation-attention-title">重点关注</h2><button type="button" class="board-link" @click="go('/admin/orientation/exceptions')">异常处理</button></div>
          <template v-if="board.riskAlerts?.length">
            <button v-for="r in board.riskAlerts" :key="r.id" type="button" class="board-alert" @click="goLink(r.link)"><RiskTag :level="r.level" /><span>{{ r.title }}</span><span>查看</span></button>
          </template>
          <p v-else class="board-caption">风险明细请到异常学生查看；待处理数量以本页“待处理异常”为准。</p>
          <button type="button" class="board-followup" @click="go('/admin/orientation/no-show')"><strong>未报到学生</strong><span>查看名单，继续跟进报到情况</span></button>
          <button type="button" class="board-followup" @click="go('/admin/orientation/statistics')"><strong>迎新统计</strong><span>查看本批次汇总与分布</span></button>
        </section>
      </div>
      <section v-if="board.collegeRates?.length" class="board-section">
        <div class="board-section__head"><h2>学院预报到完成情况</h2><button type="button" class="board-link" @click="openRoster">查看新生名单</button></div>
        <div v-for="c in board.collegeRates" :key="c.name" class="board-progress">
          <div><span>{{ c.name }}</span><strong>{{ c.prepared }}/{{ c.total }} · {{ c.rate }}%</strong></div>
          <progress :aria-label="c.name + '预报到完成率'" :value="c.rate" max="100" />
        </div>
      </section>
      <p class="board-footer">统计来自服务器最新回读。<span v-if="board.updateTime">更新于 {{ board.updateTime }}</span></p>
    </template>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, LoadingState, ErrorState, RiskTag } from '@/components/business'
import { getOrientationContext, getOrientationDashboard, getOrientationBatches } from '@/modules/orientation/api/orientation.api'

const LINKS = { students: '/admin/orientation/students', progress: '/admin/orientation/progress', payment: '/admin/orientation/payment', materials: '/admin/orientation/materials', dorm: '/admin/orientation/dorm', exceptions: '/admin/orientation/exceptions' }
// Only these destinations consume batchId in their real read API.
const BATCH_PAGES = new Set(['students', 'verify', 'progress', 'materials', 'green-channels', 'exceptions', 'dorm', 'no-show', 'statistics'].map(key => '/admin/orientation/' + key))

export default {
  name: 'OrientationDashboardView',
  components: { ModulePageShell, LoadingState, ErrorState, RiskTag },
  data() {
    return { loading: true, error: '', board: null, ctx: null, batches: [], batchesLoaded: false, selectedBatch: '', requestSerial: 0,
      journey: [
        { label: '准备新生名单', hint: '批次设置与新生导入', path: '/admin/orientation/batches', roster: true },
        { label: '核验新生信息', hint: '核对填报与录取信息', path: '/admin/orientation/verify' },
        { label: '办理现场报到', hint: '报到凭证与现场登记', path: '/admin/orientation/checkin' },
        { label: '跟进办理进度', hint: '查看各环节与阻断原因', path: '/admin/orientation/progress' }
      ] }
  },
  computed: {
    roleName() { return this.ctx?.currentRole?.roleName || '' },
    dataScopeName() { return this.ctx?.dataScope?.name || '' },
    currentBatch() { return this.batches.find(b => String(b.id) === String(this.board?.batchId)) },
    totalStudents() { return Number(this.board?.kpis?.find(k => k.key === 'total')?.value || 0) },
    nextHint() {
      if (!this.board?.batchId) return '先创建迎新批次，再设置本批次的新生名单。'
      if (this.currentBatch?.status === 'CLOSED') return '该批次已结束，可查阅历史名单和办理结果。'
      return this.totalStudents ? '先处理下方待办，再跟进尚未完成报到的学生。' : '下一步：新增或导入本批次新生，再进行信息核验。'
    }
  },
  created() { this.selectedBatch = String(this.$route.query.batchId || ''); this.load() },
  beforeUnmount() { ++this.requestSerial },
  watch: { '$route.query.batchId'(value) { this.selectedBatch = String(value || ''); this.load() } },
  methods: {
    changeBatch() { this.$router.replace({ query: { ...this.$route.query, batchId: this.selectedBatch || undefined } }) },
    openRoster() {
      this.$router.push(this.board?.batchId ? { path: '/admin/orientation/batches', query: { batchId: String(this.board.batchId), panel: 'students' } } : '/admin/orientation/batches')
    },
    go(path) { this.$router.push(BATCH_PAGES.has(path) && this.board?.batchId ? { path, query: { batchId: String(this.board.batchId) } } : path) },
    goLink(link) { if (link && String(link).startsWith('/admin/orientation')) this.go(link); else if (LINKS[link]) this.go(LINKS[link]) },
    async load() {
      const serial = ++this.requestSerial
      this.loading = true; this.error = ''; this.board = null
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
          this.batches = batches; this.batchesLoaded = true
        }
        const [ctxRes, boardRes] = await Promise.all([getOrientationContext(), getOrientationDashboard({ batchId: this.selectedBatch || undefined })])
        if (serial !== this.requestSerial) return
        if (ctxRes.code !== 0) throw new Error(ctxRes.message || '当前身份读取失败')
        this.ctx = ctxRes.data
        if (boardRes.code !== 0 || !boardRes.data) throw new Error(boardRes.message || '看板读取失败')
        this.board = boardRes.data
      } catch (e) { if (serial === this.requestSerial) this.error = e.message || '加载失败' }
      finally { if (serial === this.requestSerial) this.loading = false }
    }
  }
}
</script>

<style scoped>
.board-toolbar,.board-actions,.board-section__head,.board-progress>div{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.board-toolbar{font-size:14px}.board-toolbar select{min-height:38px;max-width:280px;padding:6px 10px;border:1px solid var(--line,#dce5f3);border-radius:8px;background:var(--bg-card,#fff);color:var(--t1,#17385d)}
.board-button{min-height:38px;padding:8px 14px;border:1px solid var(--line,#dce5f3);border-radius:8px;background:var(--bg-card,#fff);color:var(--pri,#2859b8);cursor:pointer;font:inherit;font-size:14px}.board-button--primary{background:var(--pri,#2859b8);border-color:var(--pri,#2859b8);color:#fff}.board-button:disabled{cursor:wait;opacity:.6}
button:focus-visible,select:focus-visible{outline:3px solid var(--pri,#2859b8);outline-offset:3px}
.board-overview{display:grid;grid-template-columns:minmax(0,1fr) minmax(300px,.9fr);gap:24px;background:var(--bg-card,#fff);border:1px solid var(--line,#dce5f3);border-left:4px solid var(--pri,#2859b8);padding:22px;border-radius:12px}
.board-eyebrow{font-size:13px;color:var(--t2,#536984);display:flex;align-items:center;gap:12px}.board-eyebrow span{color:var(--pri,#2859b8);background:var(--pri-50,#eef4ff);padding:3px 8px;border-radius:5px}.board-overview h2{font-size:24px;line-height:1.35;margin:10px 0;color:var(--t1,#17385d)}.board-period,.board-next{font-size:14px;line-height:1.7;margin:8px 0;color:var(--t2,#536984)}.board-next{color:var(--t1,#17385d);margin-bottom:16px}
.board-journey{display:grid;grid-template-columns:1fr 1fr;gap:10px;align-content:center}.board-journey button{display:flex;gap:10px;align-items:flex-start;text-align:left;padding:12px;border:1px solid var(--line,#dce5f3);border-radius:8px;background:var(--pri-50,#f3f7ff);color:var(--t1,#17385d);cursor:pointer}.board-journey__number{font-size:14px;color:var(--pri,#2859b8);font-weight:700}.board-journey strong{display:block;font-size:14px}.board-journey small{display:block;font-size:12px;color:var(--t2,#536984);margin-top:6px;line-height:1.5}
.board-metrics{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));margin:0;background:var(--bg-card,#fff);border:1px solid var(--line,#dce5f3);border-radius:12px;padding:16px 0}.board-metric{padding:0 18px;border-right:1px solid var(--line,#dce5f3)}.board-metric:last-child{border:0}.board-metric dt{font-size:13px;color:var(--t2,#536984)}.board-metric dd{font-size:28px;line-height:1.3;font-weight:700;color:var(--t1,#17385d);margin:8px 0 4px;font-variant-numeric:tabular-nums}.board-metric__note{font-size:12px;color:var(--t2,#536984)}
.board-section{background:var(--bg-card,#fff);border:1px solid var(--line,#dce5f3);border-radius:12px;padding:20px;min-width:0}.board-section__head{justify-content:space-between;gap:8px;margin-bottom:14px}.board-section h2{font-size:17px;margin:0;color:var(--t1,#17385d)}.board-section__head>span,.board-caption,.board-footer{color:var(--t2,#536984);font-size:13px;line-height:1.7}.board-caption{margin:8px 0 14px}.board-link{padding:6px 0;border:0;background:none;color:var(--pri,#2859b8);font-size:14px;cursor:pointer}
.board-todos{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.board-todos button{display:grid;gap:8px;padding:16px;border:1px solid var(--line,#dce5f3);border-radius:8px;background:var(--bg-card,#fff);text-align:left;color:var(--t1,#17385d);font:inherit;font-size:14px;cursor:pointer}.board-todos strong{font-size:26px;font-variant-numeric:tabular-nums}.board-todos small{font-size:12px;font-weight:400}.board-todos__action{font-size:13px;color:var(--pri,#2859b8)}.board-todos .has-pending{background:var(--pri-50,#f3f7ff);border-color:var(--pri,#2859b8)}
.board-columns{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(280px,1fr);gap:16px}.board-progress{padding:10px 0}.board-progress>div{justify-content:space-between;font-size:14px;margin-bottom:8px}.board-progress strong{font-size:14px;font-variant-numeric:tabular-nums}.board-progress small{font-weight:400;color:var(--t2,#536984)}.board-progress progress{display:block;width:100%;height:8px;accent-color:var(--pri,#2859b8)}.board-empty{text-align:center;padding:24px 12px;color:var(--t2,#536984);font-size:14px;line-height:1.8}.board-empty strong{color:var(--t1,#17385d)}.board-empty p{margin:8px 0}.board-followup{display:flex;flex-direction:column;gap:6px;padding:14px 0;width:100%;border:0;border-top:1px solid var(--line,#dce5f3);background:none;text-align:left;cursor:pointer;color:var(--t1,#17385d)}.board-followup span{font-size:13px;color:var(--t2,#536984)}.board-alert{display:flex;align-items:center;gap:8px;width:100%;border:0;background:none;text-align:left;padding:12px 0;color:var(--t1,#17385d);cursor:pointer}.board-footer{margin:0;text-align:right}
@media(max-width:1100px){.board-overview{grid-template-columns:1fr}.board-metrics{grid-template-columns:repeat(3,1fr);gap:16px 0}.board-metric:nth-child(3){border:0}}
@media(max-width:700px){.board-columns,.board-todos{grid-template-columns:1fr}.board-toolbar{width:100%}.board-toolbar select{min-width:0;max-width:100%;flex:1}.board-overview,.board-section{padding:16px}.board-overview h2{font-size:21px}.board-metric{padding:0 10px}.board-metric dd{font-size:24px}.board-journey{grid-template-columns:1fr}.board-section__head{align-items:flex-start}}
</style>
