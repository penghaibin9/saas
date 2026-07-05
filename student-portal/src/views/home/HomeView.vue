<template>
  <div>
    <div class="sp-panel">
      <div class="sp-panel__head">欢迎，{{ user?.realName || '同学' }}</div>
      <StateBlock v-if="loading" type="loading" text="加载中…" />
      <div v-else class="sp-muted">
        这里是学生 PC 服务门户首页。重任务（材料上传、证明下载、长表单、大表格）请进入左侧对应模块办理；
        日常提醒与快速操作可在小程序完成，两端同一账号、同一数据。
      </div>
    </div>

    <div class="sp-panel">
      <div class="sp-panel__head">我的模块</div>
      <StateBlock v-if="!cards.length" type="empty" text="暂无已开通模块，请联系学校管理员" />
      <div v-else class="sp-grid">
        <ModuleCard v-for="m in cards" :key="m.key" :title="m.title" :icon="m.icon" :to="m.to" />
      </div>
    </div>

    <TodoPanel :items="todos" />

    <div v-if="canUpload" class="sp-panel">
      <div class="sp-panel__head">材料上传（大文件）</div>
      <FileDropzone :disabled="!canUpload" @pick="onPick" />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { usePortalConfigStore } from '../../stores/portalConfig'
import { useSessionStore } from '../../stores/session'
import { useUiStore } from '../../stores/ui'
import { portalApi } from '../../services/portalApi'
import { buildMenu } from '../../platform/menuRegistry'
import ModuleCard from '../../components/ModuleCard.vue'
import TodoPanel from '../../components/TodoPanel.vue'
import FileDropzone from '../../components/FileDropzone.vue'
import StateBlock from '../../components/StateBlock.vue'

const cfg = usePortalConfigStore()
const session = useSessionStore()
const ui = useUiStore()

const user = computed(() => session.user)
const loading = ref(true)
const todos = ref([])

const cards = computed(() => buildMenu(cfg.config).filter((m) => m.key !== 'dashboard'))
const canUpload = computed(() => cfg.isFeatureEnabled('upload'))

function onPick() {
  ui.notify('已选择文件（大文件上传将于后续版本接入真实存储）')
}

onMounted(async () => {
  try {
    const [, td] = await Promise.allSettled([portalApi.overview(), portalApi.todos()])
    if (td && td.status === 'fulfilled') {
      const v = td.value
      todos.value = Array.isArray(v) ? v : (v?.items || v?.todos || [])
    }
  } catch (e) {
    void e
  } finally {
    loading.value = false
  }
})
</script>
