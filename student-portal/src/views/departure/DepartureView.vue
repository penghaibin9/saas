<template>
  <div class="sp-page">
    <StateBlock v-if="loading" type="loading" text="正在核对离校清单…" />
    <!-- SP-D03：加载失败必须显式报错，不能显示成"暂无离校事项" -->
    <StateBlock v-else-if="error" type="error" :text="error" />
    <template v-else-if="!data.hasData">
      <StateBlock type="empty" :text="data.note || '暂无离校信息'" />
    </template>
    <template v-else>
      <section class="sp-card" style="margin-bottom:16px">
        <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:20px;flex-wrap:wrap">
          <div>
            <div style="font-size:18px;font-weight:600">毕业离校手续</div>
            <div class="sp-muted" style="margin-top:8px">
              离校清单由各业务环节的真实结论汇总而成，不单独维护一份状态；某一环节有疑问请到该环节页面处理。
            </div>
          </div>
          <span class="statepill" :class="{ warn: data.readiness !== 'READY' }">
            <span class="dot" />{{ data.readiness === 'READY' ? '各环节已办结' : `${data.blockingCount} 项待办结` }}
          </span>
        </div>
      </section>

      <section class="sp-card">
        <div class="sp-panel__head">离校环节</div>
        <div class="items">
          <article v-for="item in data.items" :key="item.key" class="item" :class="toneOf(item.result)">
            <div class="item__head">
              <div>
                <strong>{{ item.title }}</strong>
                <span v-if="!item.blocking" class="sp-muted" style="margin-left:8px;font-size:12px">不阻断离校</span>
              </div>
              <StatusTag :text="resultText(item.result)" :tone="tagTone(item.result)" />
            </div>
            <div class="item__detail">{{ item.detail || '—' }}</div>
            <div class="item__foot">
              <span class="sp-muted">依据：{{ item.source }}<template v-if="item.evidenceVersion"> · v{{ item.evidenceVersion }}</template></span>
              <!-- 没有真实落点时不给按钮，不猜路由 -->
              <button v-if="item.action" class="sp-btn sp-btn--ghost sp-btn--sm" @click="open(item.action)">
                {{ item.action.label }}
              </button>
            </div>
          </article>
        </div>
        <p class="sp-muted" style="margin-top:14px;line-height:1.7">{{ data.policyNote }}</p>
      </section>
    </template>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import { portalApi } from '../../services/portalApi'

const router = useRouter()
const loading = ref(true)
const error = ref('')
const data = ref({ items: [] })

// SP-D03：六种结果各自有明确含义，UNKNOWN（查得到但判不了）与 ERROR（源故障）
// 必须分开表述——把源故障说成"暂无数据"，学生就无法判断是自己没办还是系统坏了。
const RESULT_TEXT = {
  PASS: '已办结',
  FAIL: '未通过',
  NOT_REQUIRED: '无需办理',
  NOT_STARTED: '待你发起',
  MANUAL_PENDING: '待学校处理',
  UNKNOWN: '信息不完整',
  ERROR: '暂时无法读取'
}
const RESULT_TONE = {
  PASS: 'success',
  NOT_REQUIRED: 'default',
  FAIL: 'danger',
  ERROR: 'danger',
  NOT_STARTED: 'warn',
  MANUAL_PENDING: 'warn',
  UNKNOWN: 'warn'
}

function resultText(r) { return RESULT_TEXT[r] || r || '—' }
function tagTone(r) { return RESULT_TONE[r] || 'default' }
function toneOf(r) { return `is-${tagTone(r)}` }

function open(action) {
  if (!action?.path) return
  router.push({ path: action.path, query: action.query || {} })
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await portalApi.departureMy() || { items: [] }
  } catch (e) {
    error.value = e?.message || '离校清单加载失败'
  } finally {
    loading.value = false
  }
}
onMounted(load)
</script>

<style scoped>
.statepill { display: inline-flex; align-items: center; gap: 7px; padding: 8px 13px; background: var(--pri-50); border-radius: 9px; color: var(--pri); font-weight: 600; font-size: 13.5px; }
.statepill.warn { background: var(--warn-bg); color: var(--warn-fg); }
.statepill .dot { width: 8px; height: 8px; border-radius: 50%; background: currentColor; }
.items { display: flex; flex-direction: column; gap: 12px; }
.item { border: 1px solid var(--line); border-radius: 10px; padding: 14px 16px; }
.item.is-danger { border-color: var(--danger, #f56c6c); }
.item.is-warn { border-color: var(--warn-fg, #e6a23c); }
.item__head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.item__detail { margin-top: 8px; font-size: 13px; color: var(--t2); line-height: 1.6; }
.item__foot { margin-top: 10px; display: flex; align-items: center; justify-content: space-between; gap: 12px; font-size: 12px; }
.sp-btn--sm { padding: 5px 12px; font-size: 12.5px; }
</style>
