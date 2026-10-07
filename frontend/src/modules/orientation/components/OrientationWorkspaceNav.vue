<template>
  <div v-if="workspace" class="orientation-nav">
    <div class="orientation-nav__context">
      <strong>{{ workspace.label }}</strong>
      <span v-if="loading">正在读取批次…</span>
      <span v-else-if="error" role="alert">{{ error }}</span>
      <span v-else>{{ scoped ? (batchName || '未限定批次') : $route.path.endsWith('/checkin') ? '按报到凭证核对所属批次' : '学校统一设置与管理' }}</span>
      <router-link v-if="scoped" :to="batchHome">切换批次</router-link>
    </div>
    <nav v-if="workspace.pages.length > 1" aria-label="迎新工作区功能">
      <router-link v-for="page in workspace.pages" :key="page.path" :to="destination(page.path)"
        :aria-current="active(page.path) ? 'page' : undefined" :class="{ selected: active(page.path) }">{{ page.label }}</router-link>
    </nav>
  </div>
</template>

<script>
import { orientationWorkspace } from '../workspaces'
import { orientationDestination, ORIENTATION_BATCH_PAGES } from '../routeContext'
import { getOrientationBatch } from '../api/orientation.api'
export default {
  data: () => ({ batchName: '', error: '', loading: false, serial: 0 }),
  computed: {
    workspace() { return orientationWorkspace(this.$route.path) },
    scoped() { return ORIENTATION_BATCH_PAGES.has(this.$route.path) || this.$route.path.startsWith('/admin/orientation/students/') },
    batchHome() { return { path: '/admin/orientation', query: this.$route.query.batchId ? { batchId: this.$route.query.batchId } : {} } }
  },
  watch: { '$route.query.batchId': { immediate: true, handler: 'loadBatch' } },
  beforeUnmount() { ++this.serial },
  methods: {
    active(path) { return this.$route.path === path || (path.endsWith('/students') && this.$route.path.startsWith(path + '/')) },
    destination(path) { return orientationDestination(path, this.$route) },
    async loadBatch(id) {
      const serial = ++this.serial
      this.batchName = ''; this.error = ''; this.loading = !!id
      if (!id) return
      try {
        const result = await getOrientationBatch(String(id))
        if (serial !== this.serial) return
        if (result.code !== 0) throw new Error(result.message || '批次读取失败')
        this.batchName = result.data.batchName
      } catch (e) { if (serial === this.serial) this.error = e.message || '批次读取失败' }
      finally { if (serial === this.serial) this.loading = false }
    }
  }
}
</script>

<style scoped>
.orientation-nav{margin:0 24px;padding:12px 0 0;border-bottom:1px solid var(--border-light);color:var(--text-primary)}
.orientation-nav__context{display:flex;align-items:center;gap:14px;flex-wrap:wrap;font-size:13px;padding-bottom:10px}
.orientation-nav__context span{color:var(--text-secondary)}
nav{display:flex;gap:6px;flex-wrap:wrap}a{color:var(--pri);text-decoration:none}nav a{padding:10px 14px;border-bottom:3px solid transparent;color:var(--text-secondary)}
nav a.selected{border-color:var(--pri);color:var(--pri);font-weight:600}a:focus-visible{outline:2px solid var(--pri);outline-offset:2px}
@media(max-width:700px){.orientation-nav{margin:0 12px}nav a{padding:10px}}
</style>
