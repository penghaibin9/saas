<template>
  <div ref="viewport" class="runtime-viewport" :class="{ 'is-fullscreen': fullscreen }">
    <main class="runtime-wall" :style="canvasStyle" :class="`scene-${scene}`" aria-label="学工中心运行大屏">
      <header class="rw-header">
        <div class="rw-brand">
          <span class="rw-mark">YK</span>
          <div><b>{{ snapshot.brand }}</b><small>服务学生 · 赋能成长</small></div>
        </div>
        <div class="rw-title"><h1>学工中心运行总览</h1><p>学生工作 · 实时态势 · 决策支撑</p></div>
        <div class="rw-head-right">
          <div class="rw-time"><span>{{ dateLabel }}</span><b>{{ clock }}</b><small>{{ snapshot.scope }}</small></div>
          <button :disabled="loading" @click="$emit('refresh')">{{ loading ? '更新中' : '刷新' }}</button>
          <button :aria-pressed="autoRefresh" @click="$emit('toggle-auto')">自动 {{ autoRefresh ? '开' : '关' }}</button>
          <button @click="showContracts = true">口径</button>
          <button @click="toggleFullscreen">{{ fullscreen ? '退出' : '全屏' }}</button>
        </div>
      </header>

      <section class="rw-kpis" aria-label="核心运行指标">
        <button v-for="item in topMetrics" :key="item.id" class="rw-kpi" :class="[item.tone, metricState(item.id)]" @click="openMetric(item.id)">
          <span class="rw-kpi-icon"><component :is="item.icon" /></span>
          <span class="rw-kpi-copy"><em>{{ item.label }}</em><strong>{{ value(item.id) }}<small>{{ metric(item.id)?.status === 'OK' ? metric(item.id)?.unit : '' }}</small></strong><i>{{ statusLine(item.id) }}</i></span>
        </button>
      </section>

      <section class="rw-body">
        <aside class="rw-stack rw-left">
          <article class="rw-panel rw-alerts">
            <PanelTitle :icon="WarningFilled" title="重点事项预警" subtitle="当前待处置" />
            <button v-for="row in alertRows" :key="row.id" :class="metricState(row.id)" @click="openMetric(row.id)"><span><i :class="row.tone" />{{ row.label }}</span><strong>{{ value(row.id) }}</strong><small>{{ metric(row.id)?.status === 'OK' ? metric(row.id)?.unit : statusText(metric(row.id)?.status) }}</small></button>
          </article>

          <article class="rw-panel rw-leave-chart">
            <PanelTitle :icon="Calendar" title="请假类型分布" :subtitle="snapshot.breakdownStatus === 'OK' ? '当前统计范围' : statusText(snapshot.breakdownStatus)" />
            <div v-if="snapshot.breakdownStatus === 'OK' && snapshot.breakdown.length" class="rw-bars">
              <div v-for="row in snapshot.breakdown.slice(0, 6)" :key="row.label"><span>{{ row.label }}</span><i><b :style="{ width: breakdownWidth(row.value) }" /></i><strong>{{ row.value }}</strong></div>
            </div>
            <p v-else class="rw-unavailable">暂无可用的请假类型数据</p>
            <div class="rw-chart-summary"><button @click="openMetric('leavePending')"><b>{{ value('leavePending') }}</b><span>待审批</span></button><button @click="openMetric('leaveWaitCancel')"><b>{{ value('leaveWaitCancel') }}</b><span>待销假</span></button><button @click="openMetric('leaveOverdue')"><b>{{ value('leaveOverdue') }}</b><span>逾期未销</span></button></div>
          </article>

          <article class="rw-panel rw-privacy-panel">
            <PanelTitle :icon="Lock" title="心理关注" subtitle="专项授权" />
            <div class="rw-privacy-content"><span class="rw-heart"><Lock /></span><div><b>敏感信息保护中</b><p>大屏不展示心理学生人数、个人身份和具体事由。</p></div></div>
          </article>

          <article class="rw-panel rw-event-panel">
            <PanelTitle :icon="TrendCharts" title="风险处置构成" subtitle="记录口径" />
            <div class="rw-event-grid"><button v-for="row in eventRows" :key="row.id" @click="openMetric(row.id)"><span>{{ row.label }}</span><strong>{{ value(row.id) }}</strong><small>{{ metric(row.id)?.status === 'OK' ? metric(row.id)?.unit : statusText(metric(row.id)?.status) }}</small></button></div>
          </article>
        </aside>

        <section class="rw-center">
          <article class="rw-panel rw-campus">
            <header class="rw-map-head"><PanelTitle :icon="DataAnalysis" title="学工态势总览" subtitle="校园示意 · 非实际地理分布" /><nav aria-label="大屏场景"><button v-for="item in scenes" :key="item.key" :class="{ active: scene === item.key }" @click="scene = item.key">{{ item.label }}</button></nav></header>
            <div class="rw-campus-map" :style="{ backgroundImage: `linear-gradient(180deg, #03152a22, #03152a70), url(${campusImage})` }">
              <button v-for="item in mapMarkers" :key="item.id" class="rw-marker" :class="item.position" @click="openMetric(item.id)"><span class="rw-marker-icon"><component :is="item.icon" /></span><span><small>{{ item.label }}</small><strong>{{ value(item.id) }}<em>{{ metric(item.id)?.status === 'OK' ? metric(item.id)?.unit : '' }}</em></strong></span></button>
              <div class="rw-map-slogan"><b>以学生为本</b><span>用数据赋能 · 让成长看得见</span></div>
            </div>
          </article>

          <div class="rw-center-bottom">
            <article class="rw-panel rw-business">
              <PanelTitle :icon="OfficeBuilding" title="学工业务分布" subtitle="不同业务分别计数" />
              <div class="rw-business-bars"><button v-for="row in businessRows" :key="row.id" @click="openMetric(row.id)"><span>{{ row.label }}</span><i><b :style="{ width: businessWidth(row.id) }" /></i><strong>{{ value(row.id) }}</strong></button></div>
            </article>
            <article class="rw-panel rw-closure">
              <PanelTitle :icon="CircleCheckFilled" title="风险闭环态势" subtitle="当前存量" />
              <div class="rw-closure-body"><button class="rw-ring" :style="ringStyle" @click="openMetric('riskRate')"><span><strong>{{ value('riskRate', 1) }}</strong><small>{{ metric('riskRate')?.status === 'OK' ? '%' : '' }}</small><em>关闭占比</em></span></button><dl><div><dt>记录总量</dt><dd>{{ value('riskTotal') }}</dd></div><div><dt>已关闭</dt><dd>{{ value('riskClosed') }}</dd></div><div><dt>未关闭</dt><dd>{{ value('riskOpen') }}</dd></div></dl></div>
            </article>
          </div>
        </section>

        <aside class="rw-stack rw-right">
          <article class="rw-panel rw-dorm-panel">
            <PanelTitle :icon="House" title="住宿管理态势" subtitle="床位台账" />
            <div class="rw-icon-metrics"><button v-for="row in dormRows" :key="row.id" @click="openMetric(row.id)"><span :class="row.tone"><component :is="row.icon" /></span><em>{{ row.label }}</em><strong>{{ value(row.id, row.id === 'occupancy' ? 1 : 0) }}<small>{{ metric(row.id)?.status === 'OK' ? metric(row.id)?.unit : '' }}</small></strong></button></div>
          </article>

          <article class="rw-panel rw-aid-panel">
            <PanelTitle :icon="Coin" title="资助与奖惩" subtitle="当前业务存量" />
            <div class="rw-icon-metrics"><button v-for="row in aidRows" :key="row.id" @click="openMetric(row.id)"><span :class="row.tone"><component :is="row.icon" /></span><em>{{ row.label }}</em><strong>{{ value(row.id) }}<small>{{ metric(row.id)?.status === 'OK' ? metric(row.id)?.unit : '' }}</small></strong></button></div>
          </article>

          <article class="rw-panel rw-work-panel">
            <PanelTitle :icon="UserFilled" title="辅导员协同办理" subtitle="业务记录" />
            <div class="rw-icon-metrics"><button v-for="row in workRows" :key="row.id" @click="openMetric(row.id)"><span :class="row.tone"><component :is="row.icon" /></span><em>{{ row.label }}</em><strong>{{ value(row.id) }}<small>{{ metric(row.id)?.status === 'OK' ? metric(row.id)?.unit : '' }}</small></strong></button></div>
          </article>

          <article class="rw-panel rw-priority">
            <PanelTitle :icon="BellFilled" title="当前重点关注事项" subtitle="按数量排序" />
            <ol><li v-for="(row, index) in priorityRows" :key="row.id"><button @click="openMetric(row.id)"><i>{{ index + 1 }}</i><span><b>{{ row.label }}</b><small>{{ row.note }}</small></span><strong>{{ value(row.id) }}</strong><em>{{ priorityTag(row.id) }}</em></button></li></ol>
          </article>
        </aside>
      </section>

      <footer class="rw-footer"><span>学生成长 · 学校发展 · 社会进步</span><span><i />数据更新 {{ updatedLabel }} · 真实聚合接口</span><span>F 全屏 · Esc 退出</span></footer>
    </main>

    <div v-if="detail" class="rw-modal" role="dialog" aria-modal="true" aria-labelledby="runtime-metric-title" @click.self="detail = null"><article><button class="rw-close" aria-label="关闭" @click="detail = null">×</button><span>指标口径</span><h2 id="runtime-metric-title">{{ detail.label }}</h2><strong>{{ value(detail.id, detail.unit === '%' ? 1 : 0) }} {{ detail.status === 'OK' ? detail.unit : '' }}</strong><p>{{ detail.note }}</p><dl><div><dt>当前状态</dt><dd>{{ statusText(detail.status) }}</dd></div><div><dt>数据范围</dt><dd>{{ snapshot.scope }}</dd></div></dl><button v-if="canDrill(detail.id)" class="rw-primary" @click="go(detail)">进入业务台账</button></article></div>
    <div v-if="showContracts" class="rw-modal" role="dialog" aria-modal="true" aria-labelledby="runtime-contract-title" @click.self="showContracts = false"><article class="rw-contract"><button class="rw-close" aria-label="关闭" @click="showContracts = false">×</button><span>数据说明</span><h2 id="runtime-contract-title">学工大屏指标口径</h2><p>所有数字来自当前登录身份、当前学校与当前数据范围下的聚合接口。接口失败、字段缺失、无权限与真实零值分别展示。</p><div><b>人数</b><span>学生主档、未结风险学生等按学生口径统计。</span><b>记录数</b><span>风险、请假、认定、奖助等按业务记录统计。</span><b>住宿</b><span>统计床位台账状态，不代表学生实时在寝。</span><b>隐私</b><span>心理业务不在大屏展示个人和敏感内容。</span></div></article></div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import PanelTitle from './WallPanelTitle.vue'
import { BellFilled, Calendar, CircleCheckFilled, Coin, DataAnalysis, House, Lock, Medal, OfficeBuilding, Tools, TrendCharts, UserFilled, WarningFilled } from '@element-plus/icons-vue'
import campusImage from '@/modules/studentAffairs/assets/campus-operations-night.png'
import { canCode } from '@/modules/studentAffairs/composables/permission'
import { formatWallMetric } from '@/modules/studentAffairs/composables/studentAffairsWallProjection'
import { WALL_ROUTES, WALL_STATUS_TEXT } from '@/modules/studentAffairs/config/studentAffairsWall.contract'

const props = defineProps({ snapshot: { type: Object, required: true }, ctx: { type: Object, default: null }, loading: Boolean, autoRefresh: Boolean })
const emit = defineEmits(['refresh', 'toggle-auto', 'drill'])
const viewport = ref(null), scale = ref(1), fullscreen = ref(false), scene = ref('all'), detailId = ref(null), showContracts = ref(false), clock = ref('')
const detail = computed({ get: () => metric(detailId.value) || null, set: item => { detailId.value = item?.id || null } })
let observer, clockTimer
const scenes = [{ key: 'all', label: '今日态势' }, { key: 'risk', label: '风险处置' }, { key: 'dorm', label: '住宿资源' }]
const topMetrics = [
  { id: 'students', label: '学生主档', tone: 'blue', icon: UserFilled }, { id: 'classes', label: '班级总数', tone: 'cyan', icon: OfficeBuilding },
  { id: 'riskStudents', label: '未结风险学生', tone: 'amber', icon: WarningFilled }, { id: 'pendingLeave', label: '待审请假', tone: 'blue', icon: Calendar },
  { id: 'overdueLeave', label: '逾期未销假', tone: 'red', icon: BellFilled }, { id: 'occupied', label: '已入住床位', tone: 'green', icon: House },
  { id: 'aidApproved', label: '已认定申请', tone: 'purple', icon: Medal }, { id: 'fundingGranted', label: '已获资助申请', tone: 'gold', icon: Coin }
]
const alertRows = [{ id: 'riskOpen', label: '未关闭风险记录', tone: 'red' }, { id: 'riskLate', label: '风险处置超时', tone: 'amber' }, { id: 'riskUnassigned', label: '未分派责任人', tone: 'blue' }, { id: 'overdueLeave', label: '逾期未销假', tone: 'purple' }, { id: 'pendingDiscipline', label: '处分审理在办', tone: 'gold' }]
const eventRows = [{ id: 'riskTotal', label: '风险记录' }, { id: 'riskOpen', label: '未关闭' }, { id: 'riskClosed', label: '已关闭' }, { id: 'riskHigh', label: '高危/危急' }]
const mapMarkers = [{ id: 'riskOpen', label: '风险处置', position: 'm1', icon: WarningFilled }, { id: 'pendingAid', label: '困难认定', position: 'm2', icon: UserFilled }, { id: 'pendingFunding', label: '奖助评审', position: 'm3', icon: Coin }, { id: 'pendingLeave', label: '请假审批', position: 'm4', icon: Calendar }, { id: 'familyPending', label: '家校待回', position: 'm5', icon: BellFilled }, { id: 'occupied', label: '宿舍入住', position: 'm6', icon: House }]
const businessRows = [{ id: 'activities', label: '学生活动' }, { id: 'talks', label: '谈心谈话' }, { id: 'family', label: '家校联系' }, { id: 'pendingDiscipline', label: '处分审理' }, { id: 'aidTotal', label: '困难认定' }, { id: 'fundingTotal', label: '奖助申请' }]
const dormRows = [{ id: 'occupied', label: '已入住', tone: 'blue', icon: House }, { id: 'vacant', label: '空床位', tone: 'cyan', icon: CircleCheckFilled }, { id: 'locked', label: '锁定床位', tone: 'red', icon: WarningFilled }, { id: 'occupancy', label: '入住率', tone: 'green', icon: DataAnalysis }]
const aidRows = [{ id: 'aidApproved', label: '已认定', tone: 'pink', icon: UserFilled }, { id: 'fundingGranted', label: '已资助', tone: 'gold', icon: Coin }, { id: 'pendingFunding', label: '待评审', tone: 'amber', icon: Medal }, { id: 'pendingDiscipline', label: '处分在办', tone: 'blue', icon: WarningFilled }]
const workRows = [{ id: 'workPending', label: '勤工待审', tone: 'blue', icon: Tools }, { id: 'talkCompleted', label: '已谈话', tone: 'green', icon: CircleCheckFilled }, { id: 'familyPending', label: '家校待回', tone: 'cyan', icon: BellFilled }, { id: 'leavePending', label: '请假待审', tone: 'purple', icon: Calendar }]
const priorityDefinitions = [{ id: 'riskLate', label: '风险处置超时', note: '核查处置进展与责任人' }, { id: 'overdueLeave', label: '逾期未销假', note: '跟进返校与销假确认' }, { id: 'pendingFunding', label: '奖助申请待评审', note: '推进审核与公示' }, { id: 'familyPending', label: '家校联系待回执', note: '跟进家长反馈' }, { id: 'archivePending', label: '档案包待归档', note: '核对业务办结材料' }]
const canvasStyle = computed(() => ({ transform: `translate(-50%, -50%) scale(${scale.value})` }))
const updatedLabel = computed(() => { const raw = props.snapshot.sourceTimes?.cockpit || props.snapshot.sourceTimes?.dashboard; if (!raw) return '尚未取得'; const d = new Date(raw); return Number.isNaN(d.getTime()) ? '时间待确认' : d.toLocaleString('zh-CN', { hour12: false }) })
const dateLabel = computed(() => new Date().toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', weekday: 'short' }))
const priorityRows = computed(() => priorityDefinitions.map(row => ({ ...row, score: metric(row.id)?.status === 'OK' ? metric(row.id).value : -1 })).sort((a, b) => b.score - a.score))
const ringStyle = computed(() => { const m = metric('riskRate'); if (m?.status !== 'OK') return { background: '#123349' }; const n = Math.max(0, Math.min(100, m.value)); return { background: `conic-gradient(#33e4ef ${n}%, #ffbd4a ${n}% 100%)` } })
function metric(id) { return props.snapshot.metrics?.[id] }
function value(id, digits = 0) { return formatWallMetric(metric(id), digits) }
function metricState(id) { return 'state-' + String(metric(id)?.status || 'MISSING').toLowerCase() }
function statusText(status) { return WALL_STATUS_TEXT[status] || '暂不可用' }
function statusLine(id) { const m = metric(id); return m?.status === 'OK' ? m.note : statusText(m?.status) }
function breakdownWidth(n) { const max = Math.max(...props.snapshot.breakdown.map(row => row.value), 1); return `${n / max * 100}%` }
function businessWidth(id) { const values = businessRows.map(row => metric(row.id)).filter(row => row?.status === 'OK').map(row => row.value); const max = Math.max(...values, 1); const current = metric(id); return `${current?.status === 'OK' ? current.value / max * 100 : 0}%` }
function priorityTag(id) { const item = metric(id); if (item?.status !== 'OK') return statusText(item?.status); if (item.value === 0) return '暂无'; if (['riskLate', 'overdueLeave'].includes(id)) return '优先'; if (id === 'pendingFunding') return '审核'; return '跟进' }
function routeKey(id) { return metric(id)?.route }
function canDrill(id) { const route = WALL_ROUTES[routeKey(id)]; return Boolean(route && canCode(props.ctx, route.permission) && metric(id)?.status === 'OK') }
function openMetric(id) { detail.value = metric(id) || null }
function go(item) { if (canDrill(item.id)) emit('drill', item.route) }
function resize() { if (!viewport.value) return; const box = viewport.value.getBoundingClientRect(); scale.value = Math.min(box.width / 1920, box.height / 1080) }
async function toggleFullscreen() { try { if (document.fullscreenElement === viewport.value) await document.exitFullscreen(); else await viewport.value?.requestFullscreen() } catch { /* 浏览器不支持时保持页面画幅 */ } }
function onFullscreen() { fullscreen.value = document.fullscreenElement === viewport.value; resize() }
function onKey(event) { if (event.key === 'Escape') { detail.value = null; showContracts.value = false } else if (event.key.toLowerCase() === 'f' && !event.ctrlKey && !event.metaKey && !event.altKey) toggleFullscreen() }
function tick() { clock.value = new Date().toLocaleTimeString('zh-CN', { hour12: false }) }
onMounted(() => { observer = new ResizeObserver(resize); observer.observe(viewport.value); document.addEventListener('fullscreenchange', onFullscreen); window.addEventListener('keydown', onKey); tick(); clockTimer = window.setInterval(tick, 1000); resize() })
onBeforeUnmount(() => { observer?.disconnect(); document.removeEventListener('fullscreenchange', onFullscreen); window.removeEventListener('keydown', onKey); window.clearInterval(clockTimer) })
</script>

<style scoped>
.runtime-viewport{position:relative;width:100%;height:calc(100dvh - 188px);min-height:360px;overflow:hidden;border:1px solid #0b3f76;background:#010b1c}.runtime-viewport:fullscreen{height:100dvh;border:0}.runtime-wall{--cyan:#38e7ff;--green:#35f0c9;--blue:#59b5ff;--amber:#ffc65c;--red:#ff6f7d;--purple:#b286ff;position:absolute;left:50%;top:50%;box-sizing:border-box;width:1920px;height:1080px;padding:12px 14px 8px;display:grid;grid-template-rows:78px 112px minmax(0,1fr) 22px;gap:9px;color:#d9efff;background:radial-gradient(circle at 50% 43%,#064b8626,transparent 46%),linear-gradient(180deg,#021531,#020b1c);font-family:"Microsoft YaHei","PingFang SC",sans-serif;transform-origin:center;overflow:hidden}.runtime-wall:before{content:"";position:absolute;inset:0;pointer-events:none;background-image:linear-gradient(#51cfff0a 1px,transparent 1px),linear-gradient(90deg,#51cfff0a 1px,transparent 1px);background-size:36px 36px}.rw-header{position:relative;z-index:1;display:grid;grid-template-columns:1fr 1.35fr 1fr;align-items:center;border-bottom:1px solid #0f77bd;background:linear-gradient(90deg,#03214a99,transparent 32%,transparent 68%,#03214a99)}.rw-header:before,.rw-header:after{content:"";position:absolute;bottom:-3px;width:35%;height:3px;background:linear-gradient(90deg,transparent,#21aefa)}.rw-header:before{left:0}.rw-header:after{right:0;transform:scaleX(-1)}.rw-brand{display:flex;align-items:center;gap:14px;padding-left:18px}.rw-mark{display:grid;place-items:center;width:50px;height:50px;border:2px solid #2acfff;border-radius:50%;background:#083a69;color:#c5f5ff;font-weight:800;box-shadow:0 0 18px #31cfff80}.rw-brand b{display:block;font-size:18px;letter-spacing:3px}.rw-brand small{display:block;margin-top:7px;color:#91c8e6;font-size:11px;letter-spacing:3px}.rw-title{text-align:center}.rw-title h1{margin:0;color:white;font-size:40px;letter-spacing:8px;text-shadow:0 0 8px #fff,0 0 22px #159cff}.rw-title p{margin:7px 0 0;color:#9bdfff;font-size:13px;letter-spacing:7px}.rw-head-right{display:flex;align-items:center;justify-content:flex-end;gap:7px;padding-right:16px}.rw-head-right button{height:31px;padding:0 10px;border:1px solid #1970ad;background:#062b55;color:#b8e7ff}.rw-time{display:grid;grid-template-columns:auto auto;gap:4px 12px;margin-right:7px;color:#b7d9ed;font-size:11px}.rw-time b{font-size:17px;color:#fff}.rw-time small{grid-column:1/-1;text-align:right;color:#67b5dd}.rw-kpis{position:relative;z-index:1;display:grid;grid-template-columns:repeat(8,1fr);gap:8px}.rw-kpi{display:grid;grid-template-columns:56px minmax(0,1fr);align-items:center;gap:10px;padding:12px;border:1px solid #168dd1;border-radius:6px;background:linear-gradient(145deg,#063462e6,#031a38e8);color:#d9efff;text-align:left;box-shadow:inset 0 0 18px #087bc52b,0 0 8px #058ff84a}.rw-kpi-icon{display:grid;place-items:center;width:52px;height:52px;border:1px solid currentColor;border-radius:50%;background:#0a3c6b;color:var(--blue);box-shadow:0 0 17px currentColor}.rw-kpi-icon svg{width:29px}.rw-kpi-copy{min-width:0}.rw-kpi em{display:block;overflow:hidden;color:#d7e9f6;font-size:13px;font-style:normal;text-overflow:ellipsis;white-space:nowrap}.rw-kpi strong{display:block;margin-top:4px;color:#dff8ff;font-size:28px;font-variant-numeric:tabular-nums}.rw-kpi strong small{margin-left:5px;font-size:11px;font-weight:400}.rw-kpi i{display:block;overflow:hidden;margin-top:3px;color:#6da8c9;font-size:9px;font-style:normal;text-overflow:ellipsis;white-space:nowrap}.rw-kpi.cyan .rw-kpi-icon{color:var(--cyan)}.rw-kpi.green .rw-kpi-icon{color:var(--green)}.rw-kpi.amber .rw-kpi-icon,.rw-kpi.gold .rw-kpi-icon{color:var(--amber)}.rw-kpi.red .rw-kpi-icon{color:var(--red)}.rw-kpi.purple .rw-kpi-icon{color:var(--purple)}.rw-body{position:relative;z-index:1;display:grid;grid-template-columns:474px minmax(0,1fr) 474px;gap:10px;min-height:0}.rw-stack{display:grid;gap:9px;min-height:0}.rw-left{grid-template-rows:1.18fr 1.28fr .78fr 1fr}.rw-right{grid-template-rows:1fr .88fr .88fr 1.25fr}.rw-center{display:grid;grid-template-rows:minmax(0,1fr) 222px;gap:9px;min-width:0;min-height:0}.rw-panel{position:relative;min-width:0;min-height:0;overflow:hidden;border:1px solid #128bcf;border-radius:5px;background:linear-gradient(145deg,#052e58e8,#021a38eb);box-shadow:inset 0 0 22px #087dd42b,0 0 7px #008de64d}.rw-panel:after{content:"";position:absolute;left:8px;top:-1px;width:90px;height:2px;background:#54e8ff;box-shadow:0 0 12px #54e8ff}.rw-panel-title{height:37px;box-sizing:border-box;display:flex;align-items:center;gap:9px;padding:6px 11px;border-bottom:1px solid #0c5586;background:linear-gradient(90deg,#063b70,#04274e 55%,transparent)}.rw-panel-icon{display:grid;place-items:center;width:22px;height:22px;color:var(--cyan)}.rw-panel-icon svg{width:20px}.rw-panel-title h2{margin:0;font-size:16px;letter-spacing:1px}.rw-panel-title small{display:block;margin-top:1px;color:#5fa3c9;font-size:8px}.rw-alerts>button{display:grid;grid-template-columns:1fr 54px 30px;align-items:center;width:calc(100% - 18px);height:31px;margin:0 9px;border:0;border-bottom:1px solid #0b4e7d;background:transparent;color:#bfe2f4;text-align:left}.rw-alerts>button span{display:flex;align-items:center;gap:9px}.rw-alerts>button span i{width:7px;height:17px;border-radius:2px;background:var(--blue)}.rw-alerts>button span i.red{background:var(--red)}.rw-alerts>button span i.amber{background:var(--amber)}.rw-alerts>button span i.purple{background:var(--purple)}.rw-alerts>button span i.gold{background:#ffad3b}.rw-alerts>button strong{text-align:right;color:#fff;font-size:19px}.rw-alerts>button small{color:#79a9c5;text-align:right}.rw-bars{display:grid;gap:8px;padding:12px 14px 6px}.rw-bars>div{display:grid;grid-template-columns:78px 1fr 34px;align-items:center;gap:8px;color:#8ebdd6;font-size:10px}.rw-bars i,.rw-business-bars i{height:7px;background:#0a426d;overflow:hidden}.rw-bars i b,.rw-business-bars i b{display:block;height:100%;background:linear-gradient(90deg,#258dff,#62f3ff);box-shadow:0 0 8px #49dfff}.rw-bars strong{color:#c8efff;text-align:right}.rw-chart-summary{display:grid;grid-template-columns:repeat(3,1fr);margin:4px 10px 0;border-top:1px solid #0c5685}.rw-chart-summary button{padding:8px;border:0;border-right:1px solid #0c5685;background:transparent;color:#7eb0ca}.rw-chart-summary button:last-child{border:0}.rw-chart-summary b{display:block;color:#56dfff;font-size:19px}.rw-chart-summary span{font-size:9px}.rw-unavailable{padding:22px;color:#74a1bb;text-align:center}.rw-privacy-content{display:flex;align-items:center;gap:18px;height:calc(100% - 38px);padding:0 20px}.rw-heart{display:grid;place-items:center;width:48px;height:48px;border-radius:50%;background:#123c6b;color:#b485ff;box-shadow:0 0 18px #9c73ff55}.rw-heart svg{width:25px}.rw-privacy-content b{font-size:15px}.rw-privacy-content p{margin:5px 0 0;color:#76a4be;font-size:10px;line-height:1.5}.rw-event-grid{display:grid;grid-template-columns:repeat(4,1fr);height:calc(100% - 38px)}.rw-event-grid button{border:0;border-right:1px solid #0d5788;background:transparent;color:#74a5c1}.rw-event-grid button:last-child{border:0}.rw-event-grid span{display:block;font-size:9px}.rw-event-grid strong{display:inline-block;margin-top:7px;color:#d7f3ff;font-size:24px}.rw-event-grid small{margin-left:3px}.rw-map-head{display:flex;align-items:center;justify-content:space-between;height:38px}.rw-map-head>.rw-panel-title{flex:1;border:0}.rw-map-head nav{display:flex;gap:5px;padding-right:9px}.rw-map-head nav button{height:24px;padding:0 10px;border:1px solid #166ea5;background:#062a51;color:#7fb7d4;font-size:9px}.rw-map-head nav button.active{border-color:#42e4ff;background:#07568a;color:#fff;box-shadow:0 0 9px #2fcfff}.rw-campus-map{position:relative;height:calc(100% - 38px);background-position:center;background-size:cover}.rw-campus-map:after{content:"";position:absolute;inset:0;pointer-events:none;background:linear-gradient(90deg,#03162b99,transparent 18%,transparent 82%,#03162b99),linear-gradient(180deg,transparent 76%,#03162bbd)}.rw-map-slogan{position:absolute;z-index:2;left:28px;top:28px;display:grid;gap:6px;padding:12px 15px;border-left:3px solid #62e7ff;background:#021a33a8;color:white}.rw-map-slogan b{font-size:20px;letter-spacing:5px}.rw-map-slogan span{color:#a8def4;letter-spacing:3px}.rw-marker{position:absolute;z-index:3;display:flex;align-items:center;gap:8px;padding:6px 10px;border:1px solid #34d7ff;border-radius:4px;background:#04284ce8;color:#d9f4ff;text-align:left;box-shadow:0 0 14px #28bfff80}.rw-marker-icon{display:grid;place-items:center;width:30px;height:30px;border-radius:50%;background:#0a6092;color:#65ecff}.rw-marker-icon svg{width:18px}.rw-marker small{display:block;color:#9dd8ef;font-size:9px}.rw-marker strong{font-size:18px}.rw-marker em{margin-left:3px;font-size:9px;font-style:normal;font-weight:400}.m1{left:42%;top:11%}.m2{left:13%;top:30%}.m3{right:10%;top:29%}.m4{left:8%;bottom:18%}.m5{left:44%;bottom:8%}.m6{right:12%;bottom:18%}.scene-risk .rw-marker:not(.m1),.scene-risk .rw-dorm-panel,.scene-dorm .rw-marker:not(.m6),.scene-dorm .rw-alerts{opacity:.3}.rw-center-bottom{display:grid;grid-template-columns:1.55fr 1fr;gap:9px;min-height:0}.rw-business-bars{display:grid;gap:7px;padding:10px 15px}.rw-business-bars button{display:grid;grid-template-columns:82px 1fr 42px;align-items:center;gap:9px;border:0;background:transparent;color:#93bad0;text-align:left}.rw-business-bars strong{color:#d1efff;text-align:right}.rw-closure-body{display:flex;align-items:center;justify-content:center;gap:30px;height:calc(100% - 38px)}.rw-ring{display:grid;place-items:center;width:135px;height:135px;padding:10px;border:0;border-radius:50%;color:white}.rw-ring>span{display:grid;place-items:center;align-content:center;width:100%;height:100%;border-radius:50%;background:#052346;box-shadow:inset 0 0 18px #118ac0}.rw-ring strong{font-size:30px}.rw-ring small{font-size:12px}.rw-ring em{margin-top:3px;color:#88bbd5;font-size:9px;font-style:normal}.rw-closure dl{display:grid;gap:10px;margin:0}.rw-closure dl div{display:grid;grid-template-columns:62px 45px;align-items:center}.rw-closure dt{color:#7ca8c0;font-size:10px}.rw-closure dd{margin:0;color:#e1f6ff;text-align:right;font-size:19px}.rw-icon-metrics{display:grid;grid-template-columns:repeat(4,1fr);height:calc(100% - 38px)}.rw-icon-metrics button{display:grid;place-items:center;align-content:center;gap:5px;border:0;border-right:1px solid #0c5685;background:transparent;color:#82adc6}.rw-icon-metrics button:last-child{border:0}.rw-icon-metrics button>span{display:grid;place-items:center;width:38px;height:38px;border-radius:50%;background:#0a3a68;color:var(--blue);box-shadow:0 0 13px currentColor}.rw-icon-metrics button>span svg{width:22px}.rw-icon-metrics button>span.cyan{color:var(--cyan)}.rw-icon-metrics button>span.green{color:var(--green)}.rw-icon-metrics button>span.red{color:var(--red)}.rw-icon-metrics button>span.pink{color:#ff89bc}.rw-icon-metrics button>span.gold,.rw-icon-metrics button>span.amber{color:var(--amber)}.rw-icon-metrics button>span.purple{color:var(--purple)}.rw-icon-metrics em{font-size:10px;font-style:normal}.rw-icon-metrics strong{color:#e6f8ff;font-size:22px}.rw-icon-metrics strong small{margin-left:3px;color:#82adc6;font-size:8px;font-weight:400}.rw-priority ol{margin:0;padding:3px 10px;list-style:none}.rw-priority li button{display:grid;grid-template-columns:24px 1fr 36px 38px;align-items:center;width:100%;height:31px;border:0;border-bottom:1px solid #0b4e7d;background:transparent;color:#c8e7f5;text-align:left}.rw-priority li i{display:grid;place-items:center;width:18px;height:18px;border-radius:3px;background:#1684d4;color:white;font-style:normal}.rw-priority li:first-child i{background:#ed5e5e}.rw-priority li:nth-child(2) i{background:#ee9b38}.rw-priority li span{min-width:0}.rw-priority li span b,.rw-priority li span small{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.rw-priority li span b{font-size:10px}.rw-priority li span small{margin-top:2px;color:#6f9fba;font-size:8px}.rw-priority li strong{text-align:right}.rw-priority li em{margin-left:5px;padding:2px 4px;border-radius:2px;background:#0b60a2;color:#bfeaff;font-size:8px;font-style:normal;text-align:center}.rw-footer{display:flex;align-items:center;justify-content:space-between;padding:0 18px;color:#5e9abc;font-size:9px;letter-spacing:2px}.rw-footer i{display:inline-block;width:6px;height:6px;margin-right:7px;border-radius:50%;background:var(--green);box-shadow:0 0 8px var(--green)}button{font:inherit;cursor:pointer}button:focus-visible{outline:2px solid #74e7ff;outline-offset:-3px}.state-error,.state-missing,.state-restricted,.state-no_scope,.state-invalid{opacity:.58}.rw-modal{position:absolute;inset:0;z-index:20;display:grid;place-items:center;background:#010913df;backdrop-filter:blur(8px)}.rw-modal article{position:relative;width:min(610px,88%);padding:30px;border:1px solid #2b8cb5;background:#082943;color:#d7effc;box-shadow:0 30px 90px #000b}.rw-modal article>span{color:#59cce8;font-size:11px;letter-spacing:2px}.rw-modal h2{margin:8px 0;font-size:25px}.rw-modal article>strong{font-size:34px;color:#72e5ff}.rw-modal p{color:#8db1c6;line-height:1.8}.rw-modal dl{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:20px 0}.rw-modal dl div{padding:12px;background:#0b3552}.rw-modal dt{color:#6f9bb3;font-size:11px}.rw-modal dd{margin:5px 0 0}.rw-close{position:absolute;right:15px;top:11px;border:0;background:transparent;color:#9bc7dc;font-size:26px}.rw-primary{padding:10px 16px;border:1px solid #4dd7f5;background:#0c5374;color:white}.rw-contract div{display:grid;grid-template-columns:90px 1fr;gap:12px;padding-top:12px}.rw-contract div b{color:#64dbf6}.rw-contract div span{color:#92b5c8}@media(prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
</style>
