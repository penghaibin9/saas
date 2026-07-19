<template>
  <div class="sp-page">
    <StateBlock v-if="loading" type="loading" text="正在加载工作台…" />
    <template v-else>
      <!-- 阶段横幅 -->
      <section class="hero">
        <div class="hero__glow" />
        <div class="hero__row">
          <div style="min-width:0;flex:1">
            <div class="hero__hi">{{ greeting }}，{{ studentName }}</div>
            <div class="hero__chips">
              <span v-for="c in identity" :key="c.label" class="chip"><span style="color:#A9B0BD">{{ c.label }}</span>{{ c.value }}</span>
            </div>
            <div v-if="topAlert" class="hero__alert">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#D92D20" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" style="flex:none"><path d="M12 9v4M12 17h.01M10.3 3.9 2 18a2 2 0 0 0 1.7 3h16.6a2 2 0 0 0 1.7-3L14 3.9a2 2 0 0 0-3.4 0z" /></svg>
              <div style="font-size:13.5px;color:#7A2016;line-height:1.5"><b style="color:#B42318">下一步 · </b>{{ topAlert.title }}</div>
            </div>
          </div>
          <div style="display:flex;flex-direction:column;gap:10px;flex:none;align-items:flex-end">
            <div style="font-size:12.5px;color:var(--t3)">当前阶段</div>
            <div class="hero__stage"><span class="dot" />{{ stageLabel }}</div>
            <button v-if="ctaModule" class="hero__cta" @click="goModule(ctaModule)">{{ ctaText }} →</button>
          </div>
        </div>
      </section>

      <!-- 4 指标卡 -->
      <div class="metrics">
        <div v-for="m in metrics" :key="m.title" class="metric">
          <div class="metric__t">{{ m.title }}</div>
          <div style="margin-top:9px;display:flex;align-items:baseline;gap:3px">
            <span class="metric__v" :style="{ color: m.color }">{{ m.value }}</span>
            <span style="font-size:14px;color:var(--t3);font-weight:500">{{ m.unit }}</span>
          </div>
          <div style="margin-top:6px;font-size:12px;color:var(--t4)">{{ m.sub }}</div>
        </div>
      </div>

      <!-- 待办中心 + 右列 -->
      <div class="cols">
        <section class="card">
          <div class="card__head">
            <div style="display:flex;align-items:center;gap:9px"><span class="card__title">待办中心</span><span class="cnt">{{ todos.length }}</span></div>
            <span class="sp-muted">等我提交 / 确认 / 整改的事项</span>
          </div>
          <StateBlock v-if="!todos.length" type="empty" text="暂无待办，一切就绪" />
          <div v-else style="display:flex;flex-direction:column;gap:10px">
            <button v-for="t in todos" :key="t.id" class="todo" @click="goModule(t.module)">
              <span class="todo__tag" :style="modTagStyle(t.module)">{{ modName(t.module) }}</span>
              <div style="flex:1;min-width:0">
                <div class="todo__title">{{ t.title }}</div>
                <div style="margin-top:3px;font-size:12px;color:var(--t4)">{{ t.dueAt ? ('截止 ' + fmt(t.dueAt)) : '待办事项' }}</div>
              </div>
              <span class="todo__go">去处理<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 6 6 6-6 6" /></svg></span>
            </button>
          </div>
        </section>

        <div style="display:flex;flex-direction:column;gap:18px">
          <section class="card">
            <div class="card__head"><span class="card__title">消息速览</span><a style="font-size:12.5px;color:var(--pri);cursor:pointer" @click="goMsg">全部</a></div>
            <StateBlock v-if="!msgs.length" type="empty" text="暂无新消息" />
            <button v-for="m in msgs" :key="m.id" class="msg" @click="goModule(m.link || m.module)">
              <span class="msg__dot" :style="{ background: m.read ? '#C9CED6' : 'var(--pri)' }" />
              <div style="flex:1;min-width:0">
                <div class="msg__title" :style="{ fontWeight: m.read ? 400 : 600 }">{{ m.title }}</div>
                <div style="margin-top:3px;font-size:12px;color:var(--t4)">{{ modName(m.module) }} · {{ fmt(m.time) }}</div>
              </div>
            </button>
          </section>

          <section class="card">
            <div class="card__title" style="margin-bottom:6px">各环节状态</div>
            <StateBlock v-if="!domains.length" type="empty" text="暂无环节信息" />
            <div v-for="d in domains" :key="d.key" class="sched">
              <span class="sched__dot" :style="{ background: d.hasData ? 'var(--pri)' : '#C9CED6' }" />
              <div style="flex:1;min-width:0"><div style="font-size:13.5px;color:var(--t1)">{{ d.label }}</div></div>
              <StatusTag :text="d.hasData ? statusLabel(d.status) : '未开始'" :tone="d.hasData ? 'primary' : 'default'" />
            </div>
          </section>
        </div>
      </div>

      <!-- 快捷入口 6 宫格 -->
      <section class="card" style="margin-top:18px">
        <div class="card__title" style="margin-bottom:14px">快捷入口</div>
        <div class="quick">
          <button v-for="q in quick" :key="q.key" class="quick__i" @click="goModule(q.key)">
            <span class="quick__ic"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path :d="q.d1" /><path :d="q.d2" /></svg></span>
            <span style="font-size:12.5px;color:var(--t2)">{{ q.label }}</span>
          </button>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useSessionStore } from '../../stores/session'
import { portalApi } from '../../services/portalApi'
import { MODULES, moduleByKey } from '../../platform/moduleRegistry'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'

const router = useRouter()
const session = useSessionStore()
const loading = ref(true)
const home = ref({})
const audit = ref({})
const msgs = ref([])

const studentName = computed(() => home.value.student?.name || session.user?.realName || '同学')
const stageLabel = computed(() => home.value.stage?.label || '在校')
const todos = computed(() => home.value.todos || [])
const alerts = computed(() => home.value.alerts || [])
const domains = computed(() => home.value.domains || [])
const topAlert = computed(() => alerts.value[0] || null)

const greeting = computed(() => {
  const h = new Date().getHours()
  return h < 11 ? '上午好' : h < 13 ? '中午好' : h < 18 ? '下午好' : '晚上好'
})

const identity = computed(() => {
  const s = home.value.student || {}
  return [
    { label: '学号', value: s.studentNo || '—' },
    { label: '年级', value: s.grade || '—' },
    { label: '班级', value: s.className || '—' }
  ].filter((c) => c.value !== '—')
})

const metrics = computed(() => {
  const c = audit.value.credits || {}
  return [
    { title: '已修学分', value: c.obtainedCredits ?? 0, unit: '', sub: `培养要求 ${c.requiredCredits ?? '—'}`, color: 'var(--t1)' },
    { title: '平均绩点 GPA', value: c.gpa ?? '—', unit: '', sub: '截至最新学期', color: 'var(--t1)' },
    { title: '待办事项', value: todos.value.length, unit: '项', sub: '待我处理', color: todos.value.length ? 'var(--pri)' : 'var(--t1)' },
    { title: '预警提醒', value: alerts.value.length, unit: '项', sub: '需跟进', color: alerts.value.length ? 'var(--danger-fg)' : 'var(--ok-fg)' }
  ]
})

const ctaModule = computed(() => topAlert.value?.domain || (todos.value[0]?.module) || null)
const ctaText = computed(() => (topAlert.value ? '去处理预警' : todos.value.length ? '去处理待办' : ''))
const quick = computed(() => MODULES.filter((m) => m.key !== 'dashboard').slice(0, 6))

const STATUS_LABELS = { CHECKED_IN: '已报到', ONBOARD: '进行中', DONE: '已完成', NORMAL: '正常', SIGNED: '已签约', WARNING: '预警', PENDING: '待处理', PROCESSING: '进行中', APPROVED: '已通过', VERIFIED: '已核验' }
function statusLabel(s) { return STATUS_LABELS[s] || s || '进行中' }
function modName(key) { return moduleByKey(key)?.title || '系统' }
function modTagStyle(key) {
  const map = { academic: ['#F0ECFF', '#6D53E0'], internship: ['#E9F7EF', '#0C8A3E'], employment: ['#FFF4E5', '#B25E00'], campusService: ['#FDEEF3', '#C2416B'] }
  const [bg, color] = map[key] || ['var(--pri-50)', 'var(--pri)']
  return { background: bg, color }
}
function fmt(t) { return t ? String(t).replace('T', ' ').slice(5, 16) : '' }
function goModule(key) {
  const mod = MODULES.find((m) => m.key === key || m.path === key)
  router.push('/' + (mod ? mod.path : (key || 'home')))
}
function goMsg() { router.push('/messages') }

async function load() {
  loading.value = true
  try {
    const [h, a, m] = await Promise.all([
      portalApi.homeOverview().catch(() => ({})),
      portalApi.academicGraduationAudit().catch(() => ({})),
      portalApi.messagesInbox(1, 4).catch(() => ({}))
    ])
    home.value = h || {}
    audit.value = a || {}
    msgs.value = (m && m.list) ? m.list.slice(0, 4) : []
  } finally {
    loading.value = false
  }
}
onMounted(load)
</script>

<style scoped>
.hero { position: relative; overflow: hidden; background: #fff; border: 1px solid var(--line); border-radius: 16px; box-shadow: 0 1px 2px rgba(16,24,40,.04); padding: 24px 26px; margin-bottom: 18px; }
.hero__glow { position: absolute; right: -40px; top: -40px; width: 220px; height: 220px; border-radius: 50%; background: radial-gradient(circle, rgba(37,99,235,.10), transparent 68%); pointer-events: none; }
.hero__row { position: relative; display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; flex-wrap: wrap; }
.hero__hi { font-size: 22px; font-weight: 600; color: var(--t1); }
.hero__chips { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.chip { display: inline-flex; align-items: center; gap: 5px; height: 26px; padding: 0 10px; background: #F5F7FA; border: 1px solid #EDEFF3; border-radius: 7px; font-size: 12.5px; color: var(--t2); white-space: nowrap; }
.hero__alert { display: flex; align-items: center; gap: 10px; margin-top: 16px; padding: 12px 14px; background: #FEF3F1; border: 1px solid #F7D2CB; border-radius: 11px; max-width: 640px; }
.hero__stage { display: inline-flex; align-items: center; gap: 8px; padding: 9px 14px; background: var(--pri-50); border-radius: 10px; color: var(--pri); font-weight: 600; font-size: 14px; }
.hero__stage .dot, .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--pri); }
.hero__cta { all: unset; cursor: pointer; text-align: center; padding: 10px 16px; border-radius: 10px; background: var(--pri); color: #fff; font-size: 13.5px; font-weight: 600; box-shadow: 0 4px 12px rgba(37,99,235,.24); }
.hero__cta:hover { background: var(--pri-h); }

.metrics { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 18px; }
.metric { background: #fff; border: 1px solid var(--line); border-radius: 14px; box-shadow: 0 1px 2px rgba(16,24,40,.04); padding: 18px 18px 15px; }
.metric__t { font-size: 13px; color: var(--t3); }
.metric__v { font-size: 28px; font-weight: 700; letter-spacing: -.5px; font-variant-numeric: tabular-nums; }

.cols { display: grid; grid-template-columns: 1.55fr 1fr; gap: 18px; align-items: start; }
.card { background: #fff; border: 1px solid var(--line); border-radius: 16px; box-shadow: 0 1px 2px rgba(16,24,40,.04); padding: 20px 22px; }
.card__head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }
.card__title { font-size: 16px; font-weight: 600; color: var(--t1); }
.cnt { min-width: 20px; height: 20px; padding: 0 6px; border-radius: 10px; background: #FEE4E2; color: var(--danger-fg); font-size: 12px; font-weight: 600; display: inline-flex; align-items: center; justify-content: center; }
.todo { all: unset; cursor: pointer; box-sizing: border-box; width: 100%; display: flex; align-items: center; gap: 14px; padding: 13px 15px; border: 1px solid var(--line); border-radius: 12px; background: #fff; box-shadow: inset 3px 0 0 var(--pri); }
.todo:hover { border-color: #C9D8FF; background: #FBFCFE; }
.todo__tag { flex: none; display: inline-flex; align-items: center; height: 22px; padding: 0 9px; border-radius: 6px; font-size: 12px; font-weight: 500; }
.todo__title { font-size: 14px; color: var(--t1); font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.todo__go { flex: none; display: inline-flex; align-items: center; gap: 3px; font-size: 13px; font-weight: 600; color: var(--pri); }
.msg { all: unset; cursor: pointer; box-sizing: border-box; width: 100%; display: flex; align-items: flex-start; gap: 10px; padding: 11px 0; border-bottom: 1px solid #F4F5F7; }
.msg:hover { opacity: .72; }
.msg__dot { margin-top: 6px; width: 7px; height: 7px; border-radius: 50%; flex: none; }
.msg__title { font-size: 13.5px; color: var(--t1); line-height: 1.45; }
.sched { display: flex; align-items: center; gap: 11px; padding: 10px 0; border-bottom: 1px solid #F4F5F7; }
.sched:last-child { border-bottom: 0; }
.sched__dot { width: 8px; height: 8px; border-radius: 50%; flex: none; }
.quick { display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; }
.quick__i { all: unset; cursor: pointer; box-sizing: border-box; display: flex; flex-direction: column; align-items: center; gap: 9px; padding: 15px 8px; border: 1px solid var(--line); border-radius: 12px; background: #fff; }
.quick__i:hover { border-color: #C9D8FF; background: #F6F9FF; }
.quick__ic { width: 38px; height: 38px; border-radius: 11px; background: var(--pri-50); color: var(--pri); display: flex; align-items: center; justify-content: center; }

@media (max-width: 900px) { .metrics { grid-template-columns: repeat(2, 1fr); } .cols { grid-template-columns: 1fr; } .quick { grid-template-columns: repeat(3, 1fr); } }
</style>
