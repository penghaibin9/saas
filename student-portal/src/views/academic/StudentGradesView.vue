<template>
  <div data-academic-page class="sp-page academic-prototype grades-page">
    <AcademicPrototypeHeader title="我的成绩" group="成绩与考试" description="只显示正式发布的成绩，不把缺分当零分。" :loading="loading" @refresh="load" />
    <StateBlock v-if="loading" type="loading" text="正在读取已发布成绩…" />
    <div v-else-if="error" class="card pad"><StateBlock type="error" :text="error" /><button class="btn" @click="load">重新加载</button></div>
    <div v-else class="stack">
      <section class="card pad"><div class="row between wrap">
        <div class="metrics-inline">
          <div class="metric"><small>已获得学分</small><strong>{{ transcript.earnedCredits ?? '待确认' }}</strong><small>正式有效成绩</small></div>
          <div class="metric"><small>平均绩点</small><strong>{{ transcript.gpa ?? '待确认' }}</strong><small>学校版本化策略</small></div>
          <div class="metric"><small>需补救课程</small><strong>{{ transcript.failCount ?? '待确认' }}</strong><small>查看补考重修</small></div>
        </div>
        <button class="btn" :disabled="printing || !rows.length" @click="printQueryCopy">{{ printing ? '生成中…' : '生成本人查询件' }}</button>
      </div></section>
      <div class="toolbar" aria-label="成绩筛选" data-workspace-filter>
        <select v-model="termFilter" aria-label="成绩学期"><option value="">全部已发布学期</option><option v-for="term in termOptions" :key="term" :value="term">{{ term }}</option></select>
        <select v-model="typeFilter" aria-label="课程类型"><option value="">全部课程类型</option><option v-for="type in typeOptions" :key="type" :value="type">{{ type }}</option></select>
        <span class="grow"></span><RouterLink class="btn link" to="/academic/makeup">补考重修</RouterLink>
      </div>
      <section class="card table-scroll">
        <table class="table">
          <thead><tr><th>课程 / 稳定代码</th><th>修读学期</th><th>学分</th><th>正式结果</th><th>状态</th><th>下一步</th></tr></thead>
          <tbody><tr v-for="grade in filteredRows" :key="gradeKey(grade)">
            <td><strong>{{ grade.courseName || '—' }}</strong><small>{{ grade.courseCode || '代码未提供' }} · 已发布课程版本</small></td>
            <td>{{ termOf(grade) }}</td><td>{{ grade.credit ?? '—' }}</td><td><b>{{ scoreText(grade) }}</b><small>{{ sourceLabel(grade) }}</small></td>
            <td><span class="tag" :class="{ red: resultTone(grade) === 'danger', green: resultTone(grade) === 'success', gray: resultTone(grade) === 'default' }">{{ resultText(grade) }}</span></td>
            <td><RouterLink v-if="safeGradeId(grade)" class="btn link small" :to="{ path: '/academic/recheck', query: { gradeId: safeGradeId(grade) } }">申请复查</RouterLink><small v-else>复查对象暂未提供</small></td>
          </tr></tbody>
        </table>
        <StateBlock v-if="!filteredRows.length" type="empty" :text="rows.length ? '没有符合筛选条件的已发布成绩，请调整筛选。' : transcript.note || '暂无已发布成绩'" />
      </section>
      <div class="notice"><AcademicPrototypeIcon name="circle-info" /><div>当前列表只展示正式发布结果。成绩更正经审核后形成新版本，不覆盖旧记录。<small>免修、缓考、缺考不按 0 分展示。个人成绩查询件带操作留痕和水印，不等同于学校盖章的正式证明。</small></div></div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import StateBlock from '../../components/StateBlock.vue'
import AcademicPrototypeHeader from '../../components/academic/AcademicPrototypeHeader.vue'
import AcademicPrototypeIcon from '../../components/academic/AcademicPrototypeIcon.vue'
import { createStudentAcademicCommandGuard, exactPositiveDecimalId, readStudentAcademicSnapshot, studentAcademicIdentity } from '../../components/academic/studentAcademicCommandGuard'
import { academicErrorKind, academicErrorMessage } from '../../components/academic/studentAcademicUi'
import { portalApi } from '../../services/portalApi'
import { createInAppPrintFrame } from '../../services/printInApp'
import { systemPrompt } from '../../services/systemDialog'
import { useSessionStore } from '../../stores/session'
import { useUiStore } from '../../stores/ui'

const ui = useUiStore()
const session = useSessionStore()
const guard = createStudentAcademicCommandGuard(() => studentAcademicIdentity(session))
const loading = ref(true)
const error = ref('')
const printing = ref(false)
const transcript = ref({ items: [] })
const termFilter = ref('')
const typeFilter = ref('')
const search = ref('')

const rows = computed(() => Array.isArray(transcript.value.items) ? transcript.value.items : [])
const termOf = (grade) => grade.term || grade.termCode || '未分学期'
const typeOf = (grade) => grade.courseTypeLabel || grade.courseType || '未提供类型'
const termOptions = computed(() => [...new Set(rows.value.map(termOf))].sort().reverse())
const typeOptions = computed(() => [...new Set(rows.value.map(typeOf))])
const filteredRows = computed(() => rows.value.filter((grade) =>
  (!termFilter.value || termOf(grade) === termFilter.value) &&
  (!typeFilter.value || typeOf(grade) === typeFilter.value) &&
  (!search.value || [grade.courseName, grade.courseCode].join(' ').toLowerCase().includes(search.value.toLowerCase()))))

function gradeKey(grade) {
  return grade.gradeId || [grade.term, grade.courseCode, grade.courseName, grade.score].join('-')
}
function safeGradeId(grade) { return exactPositiveDecimalId(grade?.gradeId) }

function resultText(grade) {
  return ({ PASSED: '已通过', FAIL: '未通过', FAILED: '未通过', EXEMPT: '免修', EXEMPTED: '免修', DEFERRED: '缓考', ABSENT: '缺考' })[String(grade.passStatus || '').toUpperCase()] || grade.passStatusLabel || '结果待确认'
}
function scoreText(grade) {
  if (['EXEMPT', 'EXEMPTED', 'DEFERRED', 'ABSENT'].includes(String(grade.passStatus || '').toUpperCase())) return resultText(grade)
  return grade.score == null || grade.score === '' ? '—' : grade.score
}
function resultTone(grade) { return grade.passStatus === 'PASSED' ? 'success' : ['FAIL', 'FAILED'].includes(grade.passStatus) ? 'danger' : 'default' }

function sourceLabel(grade) {
  const map = { PUBLISH: '正常发布', MAKEUP: '补考', RETAKE: '重修', CLEARANCE: '清考', CHANGE: '成绩更正', RECHECK: '复查更正', RECOGNITION: '成绩认定' }
  return map[String(grade.source || '').toUpperCase()] || grade.sourceLabel || '正式成绩'
}


async function load() {
  loading.value = true
  error.value = ''
  const read = await readStudentAcademicSnapshot(guard, () => portalApi.academicTranscript(), 'academic-grades')
  if (read.stale) return false
  if (!read.ok) {
    if (academicErrorKind(read.error) === 'forbidden') clearSensitive(read.error)
    else { error.value = academicErrorMessage(read.error, '成绩读取失败，请稍后重试'); loading.value = false }
    return false
  }
  transcript.value = read.value || { items: [] }
  loading.value = false
  return true
}

function clearSensitive(e) {
  guard.invalidate()
  transcript.value = { items: [] }
  termFilter.value = ''
  typeFilter.value = ''
  search.value = ''
  printing.value = false
  loading.value = false
  error.value = academicErrorMessage(e)
}

function appendText(parent, tag, text) {
  const el = parent.ownerDocument.createElement(tag)
  el.textContent = String(text ?? '')
  parent.appendChild(el)
  return el
}

async function printQueryCopy() {
  if (printing.value || loading.value || error.value || !rows.value.length) return
  const reason = await systemPrompt({ title:'填写成绩单开具事由', message:'本次事由将写入审计记录。', defaultValue:'个人成绩查询', minLength:5, confirmText:'确认开具' })
  if (reason == null) return
  if (reason.trim().length < 5) {
    ui.notify('开具事由不少于5个字')
    return
  }
  const command = guard.beginCommand({ reason: reason.trim() })
  const win = createInAppPrintFrame('个人成绩查询件')
  appendText(win.document.body, 'p', '正在生成个人成绩查询件，请稍候…')
  printing.value = true
  try {
    const audit = await portalApi.academicTranscriptPrint({ reason: command.reason })
    if (!guard.isCurrentCommand(command)) { if (!win.closed) win.close(); return }
    const documentData = audit?.document
    if (!Array.isArray(documentData?.items)) throw new Error('学校未返回本次正式成绩查询件，不能使用页面旧数据打印')
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
    const meta = appendText(doc.body, 'div', `开具事由：${command.reason} · 留痕时间：${audit?.loggedAt || '—'}`)
    meta.className = 'meta'
    const table = doc.createElement('table')
    const head = doc.createElement('tr')
    ;['学期', '课程', '课程代码', '学分', '成绩', '结果', '来源'].forEach((x) => appendText(head, 'th', x))
    table.appendChild(head)
    for (const grade of documentData.items) {
      const tr = doc.createElement('tr')
      ;[grade.term || grade.termCode || '—', grade.courseName || '—', grade.courseCode || '—', grade.credit ?? '—', scoreText(grade), resultText(grade), sourceLabel(grade)]
        .forEach((x) => appendText(tr, 'td', x))
      table.appendChild(tr)
    }
    doc.body.appendChild(table)
    const foot = appendText(doc.body, 'div', `已获学分：${documentData.earnedCredits ?? '待确认'} · GPA：${documentData.gpa ?? '—'} · 未通过：${documentData.failCount ?? '待确认'}门`)
    foot.className = 'foot'
    win.focus()
    win.print()
    ui.notify('成绩查询件开具留痕已记录')
  } catch (e) {
    if (!guard.isCurrentCommand(command)) { if (!win.closed) win.close(); return }
    if (!win.closed) win.close()
    if (academicErrorKind(e) === 'forbidden') clearSensitive(e)
    ui.notify(academicErrorMessage(e, '生成失败'))
  } finally {
    if (guard.isCurrentCommand(command)) printing.value = false
  }
}

onMounted(load)
onBeforeUnmount(() => guard.dispose())
</script>

<style src="../../components/academic/studentAcademicPrototype.css"></style>
<style scoped>
.table-scroll { overflow-x: auto; }
.table { min-width: 760px; }
</style>
