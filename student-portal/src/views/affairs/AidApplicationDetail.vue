<template>
  <dialog ref="dialog" class="aid-detail" aria-labelledby="aid-detail-title" @cancel.prevent="$emit('close')" @click="onBackdrop">
    <header><div><h2 id="aid-detail-title">认定申请详情</h2><p class="sp-muted">申请编号 {{ applyId }}</p></div><button class="sp-btn sp-btn--ghost" @click="$emit('close')">关闭</button></header>
    <div class="aid-detail__body">
      <StateBlock v-if="loading" type="loading" text="正在读取申请…" />
      <div v-else-if="error" role="alert"><p>{{ error }}</p><button class="sp-btn" @click="load">重新加载</button></div>
      <template v-else-if="detail">
        <section class="aid-detail__summary"><div><h3>{{ detail.batchName }}</h3><span class="sp-muted">{{ detail.schoolYear }}</span></div><StatusTag :text="detail.statusLabel" tone="default" /><p role="status">{{ detail.progressHint }}</p><p v-if="detail.returnReason" class="aid-detail__notice">处理意见：{{ detail.returnReason }}</p></section>
        <h3>认定信息</h3>
        <dl><div><dt>申请等级</dt><dd>{{ detail.applyLevelLabel }}</dd></div><div v-if="detail.finalLevel"><dt>{{ detail.status === 'PUBLICITY' ? '拟认定等级' : '认定等级' }}</dt><dd>{{ detail.finalLevelLabel }}</dd></div><div v-if="detail.createdAt"><dt>创建时间</dt><dd>{{ dateTime(detail.createdAt) }}</dd></div><div v-if="detail.publicityEnd"><dt>公示截止</dt><dd>{{ dateTime(detail.publicityEnd) }}</dd></div><div v-if="detail.resultAt"><dt>认定时间</dt><dd>{{ dateTime(detail.resultAt) }}</dd></div></dl>
        <p v-if="detail.status === 'PUBLICITY'" class="aid-detail__notice" role="status">{{ detail.hasPendingObjection ? '异议复核完成后，学校才能确认认定结果。' : detail.publicityHint }}</p>
        <section v-if="detail.adjustment" class="aid-detail__notice" role="status"><h3>等级调整审核中</h3><p>{{ detail.adjustment.fromLabel }} → {{ detail.adjustment.targetLabel }}</p><p>这是申请调整的目标，审核完成前仍以当前认定等级为准。</p></section>
        <section v-if="detail.objectionResults?.length" class="aid-detail__objections">
          <h3>公示异议与复核</h3>
          <article v-for="item in detail.objectionResults" :key="item.objectionId"><strong>{{ item.resultLabel || item.statusLabel }}</strong><time v-if="item.reviewedAt">{{ dateTime(item.reviewedAt) }}</time><p v-if="item.reviewOpinion">{{ item.reviewOpinion }}</p><p v-else>已进入复核，完成后在这里查看结论。</p></article>
        </section>
        <h3>我提交的家庭情况</h3>
        <dl><div><dt>家庭成员</dt><dd>{{ detail.memberCount == null ? '未填写' : detail.memberCount + ' 人' }}</dd></div><div><dt>家庭年收入</dt><dd>{{ amount(detail.annualIncome) }}</dd></div><div><dt>家庭债务</dt><dd>{{ amount(detail.debt) }}</dd></div><div><dt>特殊情况</dt><dd>{{ (detail.specialTags || []).join('、') || '未填写' }}</dd></div></dl>
        <h3>困难情况说明</h3><p class="aid-detail__statement">{{ detail.statement || '未填写' }}</p>
        <section class="aid-detail__materials"><h3>申请材料</h3><p>查看这份申请的补交要求、文件版本与验收结果。</p><button class="sp-btn sp-btn--ghost" @click="openMaterials">材料查看与补交</button></section>
        <section class="aid-detail__history"><h3>办理记录</h3><p v-if="!detail.history?.length">暂无可核验的历史记录。</p><ol v-else><li v-for="item in detail.history" :key="item.id"><strong>{{ item.title }}</strong><time>{{ item.occurredAt ? dateTime(item.occurredAt) : '时间未记录' }}</time><p v-if="item.description">{{ item.description }}</p></li></ol></section>
      </template>
    </div>
    <footer><button class="sp-btn sp-btn--ghost" :disabled="loading" @click="load">刷新进度</button><button v-if="detail?.allowedActions?.includes('EDIT_RETURNED')" class="sp-btn" @click="$emit('edit', detail)">按意见补正并重提</button></footer>
  </dialog>
</template>

<script setup>
import { onMounted, onBeforeUnmount, ref } from 'vue'
import { useRouter } from 'vue-router'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import { affairsFourEndApi } from '../../services/affairsFourEndApi'

const props = defineProps({ applyId: { type: String, required: true } })
const emit = defineEmits(['close', 'edit'])
const router = useRouter()
function openMaterials() { emit('close'); router.push({ name: 'material-supplement', query: { bizType: 'AID', bizId: props.applyId } }) }
const dialog = ref(null), detail = ref(null), loading = ref(true), error = ref('')
let seq = 0
const dateTime = value => new Date(value).toLocaleString('zh-CN', { hour12: false })
const amount = value => value == null || value === '' ? '未填写' : `${Number(value).toLocaleString('zh-CN')} 元`
async function load() {
  const request = ++seq
  loading.value = true; error.value = ''; detail.value = null
  try {
    const data = await affairsFourEndApi.getAidDetail(props.applyId)
    if (request === seq) detail.value = data
  } catch (e) { if (request === seq) error.value = e?.message || '详情加载失败，请重试' }
  finally { if (request === seq) loading.value = false }
}
function onBackdrop(event) {
  if (event.target !== dialog.value) return
  const box = dialog.value.getBoundingClientRect()
  if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) emit('close')
}
onMounted(() => { dialog.value.showModal(); load() })
onBeforeUnmount(() => { seq++; detail.value = null })
</script>

<style scoped>
.aid-detail { width: min(760px, calc(100vw - 32px)); max-height: calc(100dvh - 48px); padding: 0; border: 1px solid var(--line); border-radius: 16px; background: var(--surface); color: var(--t1); box-shadow: 0 24px 64px #0003; }
.aid-detail[open] { display: flex; flex-direction: column; }.aid-detail::backdrop { background: #101a2a80; }
header, footer { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 16px 24px; flex-shrink: 0; }
header { border-bottom: 1px solid var(--line); }footer { border-top: 1px solid var(--line); justify-content: flex-end; }
h2 { font-size: 18px; margin: 0; }h3 { font-size: 15px; margin: 20px 0 12px; }p { margin: 8px 0 0; line-height: 1.7; }
.aid-detail__body { overflow-y: auto; padding: 20px 24px; }.aid-detail__summary { display: flex; align-items: center; flex-wrap: wrap; justify-content: space-between; gap: 8px; padding: 16px; border: 1px solid var(--line); border-radius: 10px; }.aid-detail__summary h3 { margin: 0 0 6px; }.aid-detail__summary p { flex-basis: 100%; }.aid-detail__notice { font-weight: 600; }
dl { display: grid; grid-template-columns: 1fr 1fr; gap: 0 24px; margin: 0; }dl > div { padding: 12px 0; border-bottom: 1px solid var(--line); }dt { color: var(--t3); font-size: 13px; }dd { margin: 6px 0 0; overflow-wrap: anywhere; }.aid-detail__statement { white-space: pre-wrap; overflow-wrap: anywhere; }
@media (max-width: 560px) { dl { grid-template-columns: 1fr; }header, footer, .aid-detail__body { padding: 16px; } }
.aid-detail__objections article { padding: 12px 16px; border-left: 3px solid var(--pri); background: var(--bg); margin-bottom: 8px; border-radius: 4px; }.aid-detail__objections time { display: block; color: var(--t3); margin-top: 4px; font-size: 12px; }
.aid-detail__materials { padding: 0 16px 16px; margin-top: 18px; border: 1px solid var(--line); border-radius: 10px; }.aid-detail__materials button { margin-top: 12px; }.aid-detail__history ol { list-style: none; padding: 0 0 0 18px; margin: 0 0 0 5px; border-left: 1px solid var(--line); }.aid-detail__history li { position: relative; padding: 0 0 20px; }.aid-detail__history li::before { content: ''; position: absolute; left: -23px; top: 5px; width: 9px; height: 9px; border-radius: 50%; background: var(--pri); }.aid-detail__history time { display: block; margin-top: 5px; font-size: 12px; color: var(--t3); }.aid-detail__history p { white-space: pre-wrap; overflow-wrap: anywhere; }
</style>
