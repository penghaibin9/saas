<template>
  <div>
    <div class="sp-panel">
      <div class="sp-panel__head">{{ meta.title }}</div>

      <div class="sp-actions">
        <button v-if="feat('upload')" class="sp-btn sp-btn--ghost" @click="ui.notify('材料上传已开通（后续版本接入）')">上传材料</button>
        <button v-if="feat('export')" class="sp-btn sp-btn--ghost" @click="ui.notify('导出已开通（后续版本接入）')">导出</button>
        <button v-if="feat('proofDownload')" class="sp-btn sp-btn--ghost" @click="ui.notify('证明下载已开通（后续版本接入）')">证明下载</button>
        <button v-if="feat('materialCenter')" class="sp-btn sp-btn--ghost" @click="ui.notify('材料中心已开通（后续版本接入）')">材料中心</button>
      </div>

      <StateBlock v-if="loading" type="loading" text="加载中…" />
      <StateBlock v-else-if="error" type="error" :text="error" />
      <DataPanel v-else :title="meta.title" :columns="meta.columns" :rows="rows" />
      <div class="sp-muted" style="margin-top:8px;">大表格 / 长表单等重任务将在此模块深化（P2）。</div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { usePortalConfigStore } from '../../stores/portalConfig'
import { useUiStore } from '../../stores/ui'
import { portalApi } from '../../services/portalApi'
import { moduleByPath } from '../../platform/moduleRegistry'
import { metaFor } from '../../mock/portalTemplateFixture'
import DataPanel from '../../components/DataPanel.vue'
import StateBlock from '../../components/StateBlock.vue'

const route = useRoute()
const cfg = usePortalConfigStore()
const ui = useUiStore()

const loading = ref(true)
const error = ref('')
const rows = ref([])

const meta = computed(() => metaFor(route.params.module))
function feat(k) { return cfg.isFeatureEnabled(k) }

function fmt(v) {
  if (v == null) return ''
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}
function toRows(data) {
  const list = Array.isArray(data) ? data : (data?.items || data?.list || data?.rows || [])
  if (Array.isArray(list) && list.length) {
    return list.map((o) => (o && typeof o === 'object'
      ? Object.values(o).slice(0, meta.value.columns.length).map(fmt)
      : [fmt(o)]))
  }
  return []
}

async function fetchData() {
  loading.value = true
  error.value = ''
  rows.value = []
  const mod = moduleByPath(route.params.module)
  try {
    let data
    if (!mod || mod.domain == null) {
      if (route.params.module === 'messages') data = await portalApi.messages()
      else if (route.params.module === 'profile') data = await portalApi.profile()
      else data = await portalApi.overview()
    } else {
      data = await portalApi.domainMy(mod.domain)
    }
    rows.value = toRows(data)
  } catch (e) {
    error.value = e?.message || '数据加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(fetchData)
watch(() => route.params.module, fetchData)
</script>
