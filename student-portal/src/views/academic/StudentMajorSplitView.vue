<template>
  <div class="sp-page major-split-page">
    <section class="sp-card major-hero">
      <div>
        <span class="major-eyebrow">教务学业 · 专业分流</span>
        <h1>专业分流志愿</h1>
        <p>按学校开放批次填写本人志愿。志愿提交不等于录取，最终仍由服务器校验并以学校正式发布结果为准。</p>
      </div>
      <button class="sp-btn sp-btn--ghost" type="button" :disabled="loading" @click="load">
        {{ loading ? '加载中…' : '刷新' }}
      </button>
    </section>

    <StateBlock v-if="loading" type="loading" text="正在读取本人专业分流批次…" />
    <section v-else-if="error" class="sp-card">
      <StateBlock type="error" :text="error" />
      <button class="sp-btn sp-btn--ghost" type="button" @click="load">重新加载</button>
    </section>

    <template v-else>
      <section v-if="openBatches.length" class="batch-list">
        <article v-for="batch in openBatches" :key="batch.batchId" class="sp-card batch-card">
          <header class="batch-head">
            <div>
              <strong>{{ batch.batchName || '专业分流批次' }}</strong>
              <span>{{ batch.grade ? `${batch.grade}级 · ` : '' }}最多 {{ maxChoices(batch) }} 个志愿</span>
            </div>
            <span class="server-badge">服务器权威</span>
          </header>

          <div class="option-list">
            <button
              v-for="option in batch.options || []"
              :key="optionKey(option)"
              class="option-row"
              :class="{ 'is-picked': choiceRank(batch, option) > 0 }"
              type="button"
              :disabled="submitting"
              @click="toggleChoice(batch, option)"
            >
              <span>
                <b>{{ option.majorName || option.optionName || `专业 ${optionKey(option)}` }}</b>
                <small v-if="option.remain != null || option.capacity != null">
                  余 {{ option.remain ?? '—' }}/{{ option.capacity ?? '—' }}
                </small>
              </span>
              <em>{{ choiceRank(batch, option) ? `第${choiceRank(batch, option)}志愿` : '选择' }}</em>
            </button>
          </div>

          <footer class="batch-actions">
            <span>当前已选 {{ choicesFor(batch).length }} 项</span>
            <button class="sp-btn sp-btn--primary" type="button" :disabled="submitting || !choicesFor(batch).length" @click="submit(batch)">
              {{ submitting ? '提交中…' : '提交志愿' }}
            </button>
          </footer>
        </article>
      </section>
      <StateBlock v-else type="empty" :text="data.note || '暂无开放中的专业分流批次'" />

      <section v-if="myVolunteers.length" class="sp-card result-card">
        <header class="result-head">
          <div><strong>我的志愿与学校结果</strong><span>客户端不自行计算录取结论</span></div>
        </header>
        <article v-for="record in myVolunteers" :key="record.volunteerId || record.id" class="result-row">
          <div>
            <b>{{ record.batchName || '专业分流志愿' }}</b>
            <span>志愿：{{ volunteerText(record) }}</span>
            <strong v-if="record.resultMajorName || record.resultMajorId" class="official-result">
              学校结果：{{ record.resultMajorName || `专业 ${record.resultMajorId}` }}
            </strong>
          </div>
          <StatusTag :text="record.status || '已提交'" :tone="record.resultMajorId ? 'success' : 'info'" />
        </article>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import { portalApi } from '../../services/portalApi'

const loading = ref(true)
const submitting = ref(false)
const error = ref('')
const data = ref({})
const picks = ref({})

const openBatches = computed(() => Array.isArray(data.value.openBatches) ? data.value.openBatches : [])
const myVolunteers = computed(() => Array.isArray(data.value.myVolunteers) ? data.value.myVolunteers : [])

function optionKey(option) {
  return String(option?.optionId || option?.majorId || option?.id || '')
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

function toggleChoice(batch, option) {
  const key = String(batch.batchId)
  const optionId = optionKey(option)
  if (!optionId) return
  const choices = [...choicesFor(batch)]
  const current = choices.indexOf(optionId)
  if (current >= 0) {
    choices.splice(current, 1)
  } else if (choices.length < maxChoices(batch)) {
    choices.push(optionId)
  }
  picks.value = { ...picks.value, [key]: choices }
}

function normalizeExistingChoice(choice) {
  if (choice && typeof choice === 'object') return String(choice.optionId || choice.majorId || choice.id || '')
  return String(choice || '')
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await portalApi.academicMajorSplit()
    const next = {}
    for (const batch of openBatches.value) {
      const existing = myVolunteers.value.find((item) => String(item.batchId || '') === String(batch.batchId || ''))
      next[String(batch.batchId)] = (existing?.choices || []).map(normalizeExistingChoice).filter(Boolean)
    }
    picks.value = next
  } catch (e) {
    error.value = e?.message || '专业分流数据加载失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

async function submit(batch) {
  const choices = choicesFor(batch)
  if (!choices.length || submitting.value) return
  if (new Set(choices).size === choices.length) {
    submitting.value = true
    try {
      await portalApi.academicMajorSplitSubmit({
        batchId: String(batch.batchId),
        choices: choices.map((optionId, index) => ({ optionId, priority: index + 1 }))
      })
      await load()
    } catch (e) {
      error.value = e?.message || '志愿提交失败，请核对批次状态后重试'
    } finally {
      submitting.value = false
    }
  }
}

function volunteerText(record) {
  const choices = Array.isArray(record?.choices) ? record.choices : []
  if (!choices.length) return '—'
  return choices.map((choice) => {
    if (choice && typeof choice === 'object') return choice.majorName || choice.optionName || choice.optionId || choice.majorId || '—'
    return String(choice)
  }).join(' / ')
}

onMounted(load)
</script>

<style scoped>
.major-split-page { display: grid; gap: 16px; }
.major-hero { display: flex; align-items: flex-end; justify-content: space-between; gap: 20px; }
.major-hero h1 { margin: 6px 0; font-size: 24px; }
.major-hero p { margin: 0; max-width: 760px; color: #64748b; }
.major-eyebrow { color: #2563eb; font-size: 12px; font-weight: 700; }
.batch-list { display: grid; gap: 16px; }
.batch-card { display: grid; gap: 14px; }
.batch-head, .batch-actions, .result-head, .result-row { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.batch-head div, .result-head div, .result-row > div { display: grid; gap: 4px; }
.batch-head span, .result-head span, .result-row span { color: #64748b; font-size: 13px; }
.server-badge { border-radius: 999px; padding: 4px 9px; background: #eff6ff; color: #1d4ed8 !important; font-size: 12px !important; }
.option-list { display: grid; gap: 8px; }
.option-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; width: 100%; padding: 12px 14px; border: 1px solid #e2e8f0; border-radius: 10px; background: #fff; text-align: left; cursor: pointer; }
.option-row.is-picked { border-color: #2563eb; background: #eff6ff; }
.option-row span { display: grid; gap: 3px; }
.option-row small { color: #64748b; }
.option-row em { color: #2563eb; font-style: normal; font-size: 13px; }
.batch-actions > span { color: #64748b; font-size: 13px; }
.result-card { display: grid; gap: 10px; }
.result-row { padding: 12px 0; border-top: 1px solid #eef2f7; }
.official-result { color: #166534; font-size: 13px; }
@media (max-width: 720px) { .major-hero, .batch-head, .batch-actions, .result-row { align-items: stretch; flex-direction: column; } }
</style>
