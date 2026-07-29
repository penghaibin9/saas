<template>
  <div class="sp-page grades-page">
    <section class="grades-hero">
      <div>
        <div class="grades-hero__eyebrow">教务学业 · 我的成绩</div>
        <h1>已发布成绩与学分</h1>
        <p>这里只展示教务处已经正式发布的成绩；复查、更正和补考结果以最新有效记录为准。</p>
      </div>
      <div class="grades-hero__actions">
        <button class="sp-btn sp-btn--ghost" @click="goSchedule">我的课表</button>
        <button class="sp-btn" :disabled="printing || loading || !rows.length" @click="printQueryCopy">
          {{ printing ? '生成中…' : '打印个人成绩查询件' }}
        </button>
      </div>
    </section>

    <section v-if="!loading && !error" class="grades-summary">
      <article class="summary-card"><span>已获学分</span><b>{{ transcript.earnedCredits ?? 0 }}</b></article>
      <article class="summary-card"><span>平均绩点</span><b>{{ transcript.gpa ?? '—' }}</b></article>
      <article class="summary-card" :class="{ 'is-risk': Number(transcript.failCount || 0) > 0 }"><span>当前未通过</span><b>{{ transcript.failCount ?? 0 }} 门</b></article>
      <article class="summary-card"><span>已发布课程</span><b>{{ rows.length }} 门</b></article>
    </section>

    <StateBlock v-if="loading" type="loading" text="正在读取已发布成绩…" />
    <section v-else-if="error" class="grades-error sp-card">
      <StateBlock type="error" :text="error" />
      <button class="sp-btn sp-btn--ghost" @click="load">重新加载</button>
    </section>
    <StateBlock v-else-if="!rows.length" type="empty" :text="transcript.note || '暂无已发布成绩'" />

    <template v-else>
      <section v-for="term in terms" :key="term.term" class="term-card sp-card">
        <header class="term-card__head">
          <div><strong>{{ term.term || '未分学期' }}</strong><span>{{ term.rows.length }} 门课程</span></div>
          <span>通过学分 {{ term.credits }}</span>
        </header>
        <div class="table-wrap">
          <table class="sp-table">
            <thead><tr><th>课程</th><th>课程代码</th><th>学分</th><th>成绩</th><th>结果</th><th>成绩来源</th></tr></thead>
            <tbody>
              <tr v-for="grade in term.rows" :key="gradeKey(grade)">
                <td class="course-name">{{ grade.courseName || '—' }}</td>
                <td>{{ grade.courseCode || '—' }}</td>
                <td>{{ grade.credit ?? '—' }}</td>
                <td class="score" :class="scoreClass(grade)">{{ grade.score ?? '—' }}</td>
                <td><StatusTag :text="grade.passStatus === 'PASSED' ? '已通过' : '未通过'" :tone="grade.passStatus === 'PASSED' ? 'success' : 'danger'" /></td>
                <td>{{ sourceLabel(grade) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>

    <section class="grades-note sp-card">
      <strong>文件说明</strong>
      <span>本页生成的是带操作留痕和水印的“个人成绩查询件”，不等同于学校盖章的正式证明。正式证明、电子签章和二维码验真应由学校另行开具。</span>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import { portalApi } from '../../services/portalApi'
import { useUiStore } from '../../stores/ui'

const router = useRouter()
const ui = useUiStore()
const loading = ref(true)
const error = ref('')
const printing = ref(false)
const transcript = ref({ items: [] })

const rows = computed(() => Array.isArray(transcript.value.items) ? transcript.value.items : [])
const terms = computed(() => {
  const map = new Map()
  for (const grade of rows.value) {
    const key = grade.term || grade.termCode || '未分学期'
    if (!map.has(key)) map.set(key, { term: key, rows: [], credits: 0 })
    const item = map.get(key)
    item.rows.push(grade)
    if (grade.passStatus === 'PASSED') item.credits += Number(grade.credit || 0)
  }
  return [...map.values()].sort((a, b) => String(b.term).localeCompare(String(a.term)))
})

function gradeKey(grade) {
  return grade.gradeId || [grade.term, grade.courseCode, grade.courseName, grade.score].join('-')
}

function scoreClass(grade) {
  return grade.passStatus === 'PASSED' ? 'is-pass' : 'is-fail'
}

function sourceLabel(grade) {
  const map = { PUBLISH: '正常发布', MAKEUP: '补考', RETAKE: '重修', CLEARANCE: '清考', CHANGE: '成绩更正', RECOGNITION: '成绩认定' }
  return map[String(grade.source || '').toUpperCase()] || grade.sourceLabel || '正式成绩'
}

function goSchedule() {
  router.push('/academic/schedule')
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    transcript.value = await portalApi.academicTranscript() || { items: [] }
  } catch (e) {
    error.value = e?.message || '成绩读取失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

function appendText(parent, tag, text) {
  const el = parent.ownerDocument.createElement(tag)
  el.textContent = String(text ?? '')
  parent.appendChild(el)
  return el
}

async function printQueryCopy() {
  if (printing.value || !rows.value.length) return
  const reason = window.prompt('请输入开具事由（不少于5个字，将记录审计）', '个人成绩查询')
  if (reason == null) return
  if (reason.trim().length < 5) {
    ui.notify('开具事由不少于5个字')
    return
  }
  const win = window.open('', '_blank')
  if (!win) {
    ui.notify('浏览器阻止了打印窗口，请允许弹出窗口后重试')
    return
  }
  win.opener = null
  appendText(win.document.body, 'p', '正在生成个人成绩查询件，请稍候…')
  printing.value = true
  try {
    const audit = await portalApi.academicTranscriptPrint({ reason: reason.trim() })
    const doc = win.document
    doc.head.textContent = ''
    doc.body.textContent = ''
    doc.title = '个人成绩查询件'
    const style = doc.createElement('style')
    style.textContent = 'body{font-family:Segoe UI,Microsoft YaHei,sans-serif;padding:26px;color:#111}h1{text-align:center;font-size:21px;margin:0 0 6px}.notice{text-align:center;color:#8a5a00;font-size:12px;margin-bottom:18px}.meta{color:#666;font-size:12px;margin-bottom:14px}table{width:100%;border-collapse:collapse;font-size:12.5px}th,td{border:1px solid #ddd;padding:7px;text-align:left}th{background:#f5f7fa}.wm{position:fixed;inset:30% 8%;font-size:36px;color:rgba(0,0,0,.06);transform:rotate(-24deg);pointer-events:none;text-align:center}.foot{margin-top:14px;color:#777;font-size:11px}'
    doc.head.appendChild(style)
    const wm = appendText(doc.body, 'div', audit?.watermark || '')
    wm.className = 'wm'
    appendText(doc.body, 'h1', '个人成绩查询件')
    const notice = appendText(doc.body, 'div', '本文件不等同于学校盖章的正式证明')
    notice.className = 'notice'
    const meta = appendText(doc.body, 'div', `开具事由：${reason.trim()} · 留痕时间：${audit?.loggedAt || '—'}`)
    meta.className = 'meta'
    const table = doc.createElement('table')
    const head = doc.createElement('tr')
    ;['学期', '课程', '课程代码', '学分', '成绩', '结果', '来源'].forEach((x) => appendText(head, 'th', x))
    table.appendChild(head)
    for (const grade of rows.value) {
      const tr = doc.createElement('tr')
      ;[grade.term || grade.termCode || '—', grade.courseName || '—', grade.courseCode || '—', grade.credit ?? '—', grade.score ?? '—', grade.passStatus === 'PASSED' ? '通过' : '未通过', sourceLabel(grade)]
        .forEach((x) => appendText(tr, 'td', x))
      table.appendChild(tr)
    }
    doc.body.appendChild(table)
    const foot = appendText(doc.body, 'div', `已获学分：${transcript.value.earnedCredits ?? 0} · GPA：${transcript.value.gpa ?? '—'} · 未通过：${transcript.value.failCount ?? 0}门`)
    foot.className = 'foot'
    win.focus()
    win.print()
    ui.notify('成绩查询件开具留痕已记录')
  } catch (e) {
    if (!win.closed) win.close()
    ui.notify(e?.message || '生成失败')
  } finally {
    printing.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.grades-page { max-width: 1280px; margin: 0 auto; }
.grades-hero { display: flex; justify-content: space-between; gap: 24px; padding: 24px 26px; margin-bottom: 16px; border: 1px solid var(--line); border-radius: 16px; background: linear-gradient(135deg, #fff, var(--pri-50)); }
.grades-hero__eyebrow { color: var(--pri); font-size: 12px; font-weight: 600; letter-spacing: .08em; }
.grades-hero h1 { margin: 8px 0 6px; color: var(--t1); font-size: 24px; }
.grades-hero p { margin: 0; color: var(--t3); font-size: 13px; }
.grades-hero__actions { display: flex; align-items: flex-start; gap: 10px; flex-wrap: wrap; }
.grades-summary { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px; }
.summary-card { padding: 16px 18px; border: 1px solid var(--line); border-radius: 13px; background: #fff; }
.summary-card span { display: block; color: var(--t3); font-size: 12px; }
.summary-card b { display: block; margin-top: 7px; color: var(--pri); font-size: 22px; }
.summary-card.is-risk b { color: var(--danger-fg); }
.grades-error { display: flex; flex-direction: column; align-items: center; gap: 12px; }
.term-card { padding: 0; overflow: hidden; margin-bottom: 14px; }
.term-card__head { display: flex; justify-content: space-between; align-items: center; padding: 14px 18px; border-bottom: 1px solid var(--line2); }
.term-card__head div { display: flex; align-items: center; gap: 10px; }
.term-card__head strong { color: var(--t1); font-size: 14px; }
.term-card__head span { color: var(--t3); font-size: 12px; }
.table-wrap { overflow-x: auto; }
.course-name { color: var(--t1); font-weight: 500; }
.score { font-weight: 700; }
.score.is-pass { color: var(--ok-fg); }
.score.is-fail { color: var(--danger-fg); }
.grades-note { display: flex; gap: 12px; color: var(--t3); font-size: 12.5px; }
.grades-note strong { color: var(--t1); white-space: nowrap; }
@media (max-width: 980px) { .grades-summary { grid-template-columns: repeat(2, 1fr); } }
</style>
