<template>
  <div data-academic-page class="sp-page academic-prototype major-page">
    <AcademicPrototypeHeader :title="editingBatch ? '分流志愿填报' : '专业分流'" group="培养与毕业" :object="!!editingBatch" description="按顺序填报本人志愿，学校分配结果另行确认。" :loading="loading || submitting" @refresh="load" />
    <StateBlock v-if="loading" type="loading" text="正在读取分流批次与本人志愿…" />
    <div v-else-if="error" class="card pad"><StateBlock type="error" :text="error" /><button class="btn" @click="load">重新加载</button></div>
    <div v-else class="stack">
      <AcademicBusinessReceipt :receipt="receipt" :tone="receiptTone" />
      <AcademicPrototypeSteps :labels="editingBatch ? ['选择本人对象', '填写申请', '学校受理', '查看结果'] : ['学校开批次', '本人填志愿', '学校分配', '确认结果']" />
      <section v-if="editingBatch" class="card"><header class="card-head"><h2>{{ editingBatch.batchName }} · 本人志愿</h2></header><form class="card-body" @submit.prevent="submit(editingBatch)">
        <div class="form-grid"><label v-for="rank in maxChoices(editingBatch)" :key="rank" class="field"><span :class="{ req: rank === 1 }">第 {{ rank }} 志愿</span><select :value="choicesFor(editingBatch)[rank - 1] || ''" @change="setChoice(editingBatch, rank, $event.target.value)"><option value="">请选择方向</option><option v-for="option in editingBatch.options || []" :key="optionKey(option)" :value="optionKey(option)" :disabled="choiceRank(editingBatch, option) > 0 && choiceRank(editingBatch, option) !== rank">{{ option.majorName || option.optionName || option.name }}</option></select></label></div>
        <div class="notice amber form-notice"><AcademicPrototypeIcon name="circle-info" /><span>志愿不能重复。提交顺序保留，学校分配结果与本人志愿分别显示。</span></div>
        <footer class="form-foot"><button class="btn" type="button" @click="editingBatchId = ''">返回分流批次</button><button class="btn primary" :disabled="submitting || !choicesFor(editingBatch).some(Boolean)">{{ submitting ? '提交中…' : '提交本人志愿' }}</button></footer>
      </form></section>
      <template v-else>
        <StateBlock v-if="!openBatches.length && !myVolunteers.length" type="empty" text="暂无本人可办理的分流批次或志愿记录" />
        <section v-for="batch in openBatches" :key="batch.batchId" class="card"><header class="card-head"><h2>{{ batch.batchName || '专业方向分流' }}</h2></header><div class="card-body">
          <div class="row between"><h2>{{ batch.grade || '本人' }} · 方向分流</h2><span class="tag amber">{{ myVolunteers.some(record => String(record.batchId) === String(batch.batchId)) ? '已提交志愿' : '志愿待提交' }}</span></div>
          <dl class="definition"><dt>可选方向</dt><dd>{{ (batch.options || []).map(option => option.majorName || option.optionName || option.name).join(' / ') || '学校尚未提供' }}</dd><dt>当前责任</dt><dd>本人填报志愿</dd><dt>后续处理</dt><dd>学校按已发布规则分配，不保证第一志愿录取</dd></dl><footer class="form-foot"><button class="btn primary" :disabled="!batch.options?.length" @click="editingBatchId = String(batch.batchId)">编辑志愿顺序</button></footer>
        </div></section>
        <section v-if="myVolunteers.length" class="card"><header class="card-head"><h2>本人志愿与正式结果</h2></header><div class="card-body"><div v-for="record in myVolunteers" :key="record.volunteerId || record.batchId" class="taskline"><div class="grow"><strong>{{ record.batchName || '本人分流志愿' }}</strong><small>{{ volunteerText(record) }}</small><small>分配结果：{{ allocationText(record) }}</small></div><span class="tag">{{ volunteerStatus(record) }}</span></div></div></section>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import AcademicBusinessReceipt from '../../components/academic/AcademicBusinessReceipt.vue'
import { academicErrorKind, academicErrorMessage, academicReceipt, markStudentAcademicFormClean } from '../../components/academic/studentAcademicUi'
import StateBlock from '../../components/StateBlock.vue'
import AcademicPrototypeHeader from '../../components/academic/AcademicPrototypeHeader.vue'
import AcademicPrototypeIcon from '../../components/academic/AcademicPrototypeIcon.vue'
import AcademicPrototypeSteps from '../../components/academic/AcademicPrototypeSteps.vue'
import { createStudentAcademicCommandGuard, readStudentAcademicSnapshot, studentAcademicIdentity, studentAcademicWriteErrorKind } from '../../components/academic/studentAcademicCommandGuard'

import { portalApi } from '../../services/portalApi'
import { systemConfirm } from '../../services/systemDialog'
import { useSessionStore } from '../../stores/session'

const session = useSessionStore()
const guard = createStudentAcademicCommandGuard(() => studentAcademicIdentity(session), 'major-split')
const loading = ref(true)
const submitting = ref(false)
const error = ref('')
const data = ref({})
const picks = ref({})
const receipt = ref(null)
const receiptTone = ref('success')
const editingBatchId = ref('')
const uncertainBatchIds = ref([])
const editingBatch = computed(() => openBatches.value.find(batch => String(batch.batchId) === editingBatchId.value))
function setChoice(batch, rank, value) { const key = String(batch.batchId); const choices = [...choicesFor(batch)]; choices[rank - 1] = value; picks.value = { ...picks.value, [key]: choices } }

const openBatches = computed(() => Array.isArray(data.value.openBatches) ? data.value.openBatches : [])
const myVolunteers = computed(() => Array.isArray(data.value.myVolunteers) ? data.value.myVolunteers : [])

function optionKey(option) {
  return String(option?.majorId || option?.optionId || option?.id || '')
}

function maxChoices(batch) {
  return Math.max(1, Number(batch?.maxChoices || 1))
}

function choicesFor(batch) {
  return picks.value[String(batch.batchId)] || []
}

function choiceRank(batch, option) {
  return choicesFor(batch).indexOf(optionKey(option)) + 1
}


function normalizeExistingChoice(choice) {
  if (choice && typeof choice === 'object') return String(choice.optionId || choice.majorId || choice.id || '')
  return String(choice || '')
}

function majorName(record, choice) {
  if (choice && typeof choice === 'object' && (choice.majorName || choice.optionName)) return choice.majorName || choice.optionName
  const id = normalizeExistingChoice(choice)
  const batch = openBatches.value.find(item => String(item.batchId) === String(record.batchId))
  const option = batch?.options?.find(item => optionKey(item) === id)
  return option?.majorName || option?.optionName || '专业名称待学校提供'
}
function allocationText(record) {
  if (record.assignedMajorName || record.resultMajorName) return record.assignedMajorName || record.resultMajorName
  if (record.resultMajorId) return majorName(record, record.resultMajorId)
  return record.status === 'UNALLOCATED' ? '尚未分配，等待学校调剂' : '尚未提供正式分配结果'
}
function volunteerStatus(record) {
  return record.statusLabel || ({ SUBMITTED: '志愿已提交', ALLOCATED: '已分配待确认', UNALLOCATED: '待调剂', CONFIRMED: '分流已正式生效' })[record.status] || '状态待核对'
}
function persistentCommandCleared(reference) {
  const pending = guard.pendingCommands()
  return Boolean(reference?.commandKey) && reference.identity === studentAcademicIdentity(session) && !pending.persistenceError && !pending.some((item) => item.commandKey === reference.commandKey)
}
function reconcilePersistentCommands() {
  const pending = guard.pendingCommands().filter((item) => item.action === 'SUBMIT_MAJOR_SPLIT')
  uncertainBatchIds.value = pending.map((item) => item.objectId)
  for (const reference of pending) {
    const formal = reference.ackId ? myVolunteers.value.find((item) => String(item.volunteerId || '') === reference.ackId && String(item.batchId || '') === reference.objectId) : null
    if (formal && guard.completePersistentCommand(reference)) {
      receiptTone.value = 'success'
      receipt.value = academicReceipt({ title: '原专业分流志愿已通过正式记录确认', object: formal.batchName || '原专业分流批次', status: volunteerStatus(formal), operatedAt: formal.submittedAt || formal.createdAt, next: '志愿提交不代表录取，请等待学校正式分流结果。' })
    } else {
      receiptTone.value = 'waiting'
      receipt.value = academicReceipt({ title: '原专业分流志愿结果待确认', object: '原专业分流批次', status: reference.ackId ? formal ? '正式记录已读到，但本地待确认引用未能安全清理' : '尚未读取到原回执对应的本人志愿' : '原提交未取得服务端回执编号', next: '本页只会刷新本人正式志愿，不会自动再次提交。' })
    }
  }
  uncertainBatchIds.value = guard.pendingCommands().filter((item) => item.action === 'SUBMIT_MAJOR_SPLIT').map((item) => item.objectId)
}

async function load() {
  loading.value = true
  error.value = ''
  const read = await readStudentAcademicSnapshot(guard, () => portalApi.academicMajorSplit())
  if (read.stale) return false
  if (!read.ok) {
    if (academicErrorKind(read.error) === 'forbidden') { clearSensitive(read.error); return false }
    error.value = academicErrorMessage(read.error, '专业分流数据加载失败，请稍后重试')
    loading.value = false
    return false
  }
  data.value = read.value || {}
  reconcilePersistentCommands()
  const next = {}
  for (const batch of openBatches.value) {
    const existing = myVolunteers.value.find((item) => String(item.batchId || '') === String(batch.batchId || ''))
    const id = String(batch.batchId)
    next[id] = Object.prototype.hasOwnProperty.call(picks.value, id) ? [...picks.value[id]] : (existing?.choices || []).map(normalizeExistingChoice).filter(Boolean)
  }
  picks.value = next
  loading.value = false
  return true
}

async function submit(batch) {
  const choices = choicesFor(batch).filter(Boolean)
  if (choices.length > maxChoices(batch) || choices.some(id => !(batch.options || []).some(option => optionKey(option) === id))) return
  const draftChoices = [...choices]
  if (!choices.length || submitting.value || uncertainBatchIds.value.includes(String(batch.batchId))) return
  if (new Set(choices).size === choices.length) {
    const command = guard.beginCommand({ batchId: String(batch.batchId), batchName: batch.batchName || '专业分流批次', choices: Object.freeze([...choices]) })
    if (!await systemConfirm({ title:'确认专业分流志愿', message:`确认按当前顺序提交“${command.batchName}”志愿？`, confirmText:'确认提交志愿' })) return
    if (!guard.isCurrentCommand(command)) return
    const persistent = guard.preparePersistentCommand({ action: 'SUBMIT_MAJOR_SPLIT', objectId: command.batchId })
    if (!persistent) { receiptTone.value = 'waiting'; receipt.value = academicReceipt({ title: '专业分流志愿未发送', object: command.batchName, status: '浏览器无法保存待确认引用', next: '请检查浏览器本地存储后再提交。' }); return }
    submitting.value = true
    try {
      const result = await portalApi.academicMajorSplitSubmit({
        batchId: command.batchId,
        choices: [...command.choices]
      })
      if (!guard.isCurrentCommand(command)) return
      const acknowledged = guard.rememberPersistentAck(persistent, result?.volunteerId)
      uncertainBatchIds.value = [...new Set([...uncertainBatchIds.value, command.batchId])]
      receiptTone.value = 'waiting'; receipt.value = academicReceipt({ title: '提交结果待正式记录确认', object: command.batchName, status: '正在读取本人正式志愿记录', next: '请保留当前志愿，确认前不要重复提交。' })
      const readOk = await load()
      if (!guard.isCurrentCommand(command) || !readOk) return
      // 同批次、同志愿的历史记录不能代表刚才的 POST；必须回读 POST 返回的 volunteerId。
      const formal = acknowledged?.ackId ? myVolunteers.value.find((item) => String(item.volunteerId) === acknowledged.ackId) : null
      const sameBatch = formal && String(formal.batchId || '') === command.batchId
      const sameChoices = formal && JSON.stringify((formal.choices || []).map(normalizeExistingChoice).filter(Boolean)) === JSON.stringify(command.choices)
      if (sameBatch && sameChoices && persistentCommandCleared(persistent)) {
        receiptTone.value = 'success'; receipt.value = academicReceipt({ title: '专业分流志愿已提交并核对', object: command.batchName, status: formal.status || result?.status || '已提交', operatedAt: formal.submittedAt || formal.createdAt || result?.submittedAt, next: '志愿提交不代表录取，请在本页等待学校正式分流结果。' }); editingBatchId.value = ''
        uncertainBatchIds.value = uncertainBatchIds.value.filter(value => value !== command.batchId)
        markStudentAcademicFormClean()
      } else {
        uncertainBatchIds.value = [...new Set([...uncertainBatchIds.value, command.batchId])]
        receiptTone.value = 'waiting'; receipt.value = academicReceipt({ title: '提交结果待正式记录确认', object: command.batchName, status: '尚未读取到匹配的本人志愿', next: '请保留当前志愿并刷新核对，确认前不要重复提交。' })
      }
    } catch (e) {
    if (!guard.isCurrentCommand(command)) return
    if (studentAcademicWriteErrorKind(e) === 'forbidden') { clearSensitive(e); return }
      const kind = studentAcademicWriteErrorKind(e)
      if (!['network', 'forbidden', 'conflict'].includes(kind)) guard.completePersistentCommand(persistent)
      if (kind === 'network' || kind === 'conflict') uncertainBatchIds.value = [...new Set([...uncertainBatchIds.value, command.batchId])]
      receiptTone.value = 'waiting'; receipt.value = academicReceipt({ title: kind === 'network' ? '提交结果待确认' : kind === 'conflict' ? '批次事实已变化' : '志愿未提交', object: command.batchName, status: kind === 'network' ? '待服务器记录确认' : '未完成', next: academicErrorMessage(e, '请核对批次状态后重试') })

      if (kind === 'network' || kind === 'conflict') { const readOk = await load(); if (guard.isCurrentCommand(command) && readOk) picks.value = { ...picks.value, [command.batchId]: draftChoices } }
    } finally {
      if (guard.isCurrentCommand(command)) submitting.value = false
    }
  }
}

function volunteerText(record) {
  const choices = Array.isArray(record?.choices) ? record.choices : []
  if (!choices.length) return '—'
  return choices.map((choice, index) => `第${index + 1}志愿：${majorName(record, choice)}`).join(' / ')
}

function clearSensitive(e) {
  guard.invalidate()
  data.value = {}; picks.value = {}; editingBatchId.value = ''
  receipt.value = null
  loading.value = false; submitting.value = false
  error.value = academicErrorMessage(e)
}
onMounted(load)
onBeforeUnmount(() => guard.dispose())
</script>

<style src="../../components/academic/studentAcademicPrototype.css"></style>
<style scoped>.definition{margin:14px 0}.form-notice{margin-top:14px}</style>
