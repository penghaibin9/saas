<template>
  <SystemWorkspaceFrame title="数据字典" subtitle="维护本校业务页面使用的名称和可选项。" :ctx="ctx">
    <template #actions>
      <button type="button" class="sw-btn" :disabled="loading || saving" @click="load">刷新</button>
      <button type="button" class="sw-btn sw-btn--primary" :disabled="!canWriteSelected || loading || saving || !selected" @click="save">
        {{ saving ? '保存中…' : '保存当前字典' }}
      </button>
    </template>

    <div v-if="message" class="sw-alert sw-alert--success" role="status">{{ message }}</div>
    <div v-if="!canWrite" class="sw-alert">当前身份可以查看数据字典，修改需要“系统配置管理”权限。</div>
    <div v-if="loading" class="sw-card sw-state" role="status">正在读取本校数据字典…</div>
    <div v-else-if="error" class="sw-alert sw-alert--error" role="alert">
      {{ error }}<button type="button" class="sw-btn" @click="load">重新读取</button>
    </div>
    <div v-else class="dict-workbench sw-card">
      <aside class="dict-nav" aria-label="字典分类">
        <div class="dict-count"><b>{{ dictionaries.length }}</b> 类字典</div>
        <label class="dict-search">
          <span class="sr-only">搜索字典</span>
          <input v-model.trim="keyword" class="sw-input" placeholder="搜索字典" />
        </label>
        <div class="dict-nav-list">
          <button
            v-for="dictionary in filteredDictionaries"
            :key="dictionary.code"
            type="button"
            class="sw-choice"
            :aria-current="dictionary.code === selectedCode"
            @click="select(dictionary.code)"
          >
            <b>{{ dictionary.label }}</b>
            <small>{{ dictionary.items.length }} 项 · {{ sourceLabel(dictionary) }}</small>
          </button>
          <p v-if="!filteredDictionaries.length" class="dict-empty">没有匹配的字典</p>
        </div>
      </aside>

      <section v-if="selected" class="dict-content">
        <header class="dict-head">
          <div>
            <div class="sw-row">
              <h2>{{ selected.label }}</h2>
              <span class="sw-tag" :class="selected.source === 'SCHOOL' ? 'sw-tag--blue' : ''">
                {{ sourceLabel(selected) }}
              </span>
            </div>
            <p class="sw-muted">{{ selected.description }}</p>
            <p class="dict-usage">
              {{ selected.consumers?.length ? `已用于：${consumerLabels(selected.consumers)}` : '尚未接入业务页面，当前配置仅作预留' }}
            </p>
          </div>
          <button v-if="selected.editable" type="button" class="sw-btn" :disabled="!canWriteSelected || saving" @click="addItem">新增字典项</button>
        </header>

        <div class="sw-table-wrap">
          <table class="sw-table dict-table">
            <thead>
              <tr><th>编码</th><th>显示名称</th><th>状态</th><th>操作</th></tr>
            </thead>
            <tbody>
              <tr v-for="(item, index) in selected.items" :key="item._key">
                <td>
                  <input v-model.trim="item.code" class="sw-input dict-code" :readonly="!item._new || !selected.editable" :disabled="!canWriteSelected || saving" maxlength="64" />
                </td>
                <td>
                  <input v-model.trim="item.label" class="sw-input" :disabled="!canWriteSelected || saving" maxlength="80" placeholder="请输入显示名称" />
                </td>
                <td>
                  <label class="dict-enabled">
                    <input v-model="item.enabled" class="sw-check" type="checkbox" :disabled="!canWriteSelected || saving" />
                    {{ item.enabled ? '启用' : '停用' }}
                  </label>
                </td>
                <td>
                  <button v-if="selected.editable && item._new" type="button" class="sw-link" :disabled="saving" @click="removeItem(index)">移除</button>
                  <span v-else-if="selected.editable" class="sw-muted">停用后不再作为可选项</span>
                  <span v-else class="sw-muted">平台统一</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="dict-footer">
          <span class="sw-muted">{{ selected.editable ? '已有编码保持不变；需要下线时关闭“启用”。' : '该类口径由平台统一维护，学校端只读。' }}</span>
          <button v-if="selected.editable" type="button" class="sw-btn sw-btn--primary" :disabled="!canWriteSelected || saving" @click="save">
            {{ saving ? '保存中…' : '保存' }}
          </button>
        </div>
      </section>
    </div>
  </SystemWorkspaceFrame>
</template>

<script>
import SystemWorkspaceFrame from '@/modules/system/components/workspace/SystemWorkspaceFrame.vue'
import { systemApi } from '@/modules/system/api/system.api'
import { matchPermission } from '@/config/navPlan'

let rowKey = 0
const decorateItems = (items = []) => items.map((item) => ({ ...item, _key: `dict-${++rowKey}`, _new: false }))

export default {
  name: 'SystemDictionariesView',
  components: { SystemWorkspaceFrame },
  props: { ctx: { type: Object, required: true } },
  data() {
    return { dictionaries: [], selectedCode: '', version: 0, keyword: '', loading: true, saving: false, error: '', message: '' }
  },
  computed: {
    canWrite() {
      return Array.isArray(this.ctx.permissionPatterns) && matchPermission(this.ctx.permissionPatterns, 'systemAdmin.config.manage')
    },
    selected() { return this.dictionaries.find((item) => item.code === this.selectedCode) || null },
    canWriteSelected() { return this.canWrite && Boolean(this.selected?.editable) },
    filteredDictionaries() {
      const keyword = this.keyword.toLowerCase()
      if (!keyword) return this.dictionaries
      return this.dictionaries.filter((item) => item.label.toLowerCase().includes(keyword) || item.code.toLowerCase().includes(keyword))
    }
  },
  created() { this.load() },
  methods: {
    sourceLabel(dictionary) {
      if (!dictionary?.editable) return '平台统一'
      return dictionary.source === 'SCHOOL' ? '本校配置' : '平台默认'
    },
    consumerLabels(consumers = []) {
      const labels = { studentCenter: '学工中心' }
      return consumers.map((code) => labels[code] || code).join('、')
    },
    select(code) { this.selectedCode = code; this.message = ''; this.error = '' },
    async load() {
      this.loading = true; this.error = ''; this.message = ''
      const result = await systemApi.getDictionaries()
      this.loading = false
      if (result.code !== 0) { this.error = result.message || '数据字典加载失败'; return }
      this.version = Number(result.data?.version || 0)
      this.dictionaries = (result.data?.dictionaries || []).map((dictionary) => ({
        ...dictionary,
        items: decorateItems(dictionary.items)
      }))
      if (!this.dictionaries.some((item) => item.code === this.selectedCode)) this.selectedCode = this.dictionaries[0]?.code || ''
    },
    addItem() {
      if (!this.canWriteSelected || !this.selected) return
      this.selected.items.push({ code: '', label: '', enabled: true, _new: true, _key: `dict-${++rowKey}` })
    },
    removeItem(index) { if (this.selected?.items[index]?._new) this.selected.items.splice(index, 1) },
    validate() {
      if (!this.selected?.items.length) return '至少保留一个字典项'
      const codes = new Set()
      for (const item of this.selected.items) {
        if (!/^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$/.test(item.code || '')) return '字典编码只能使用字母、数字、点、横线和下划线'
        if (!(item.label || '').trim()) return '显示名称不能为空'
        const code = item.code.toUpperCase()
        if (codes.has(code)) return `字典编码 ${item.code} 重复`
        codes.add(code)
      }
      return ''
    },
    async save() {
      if (!this.canWriteSelected || !this.selected || this.saving) return
      const validationError = this.validate()
      if (validationError) { this.error = validationError; return }
      this.saving = true; this.error = ''; this.message = ''
      const code = this.selected.code
      const result = await systemApi.saveDictionary(code, {
        expectedVersion: this.version,
        items: this.selected.items.map(({ code: itemCode, label, enabled }) => ({ code: itemCode, label, enabled }))
      })
      this.saving = false
      if (result.code !== 0) { this.error = result.message || '字典保存失败'; return }
      this.version = Number(result.data?.version || this.version)
      this.selected.items = decorateItems(result.data?.items || [])
      this.selected.source = 'SCHOOL'
      this.message = `“${this.selected.label}”已保存到本校数据字典。`
    }
  }
}
</script>

<style scoped>
.dict-workbench { display: grid; grid-template-columns: 220px minmax(0, 1fr); min-height: 520px; overflow: hidden; }
.dict-nav { padding: 14px 10px; border-right: 1px solid var(--sw-line); background: var(--sw-bg); }
.dict-search { display: block; padding: 0 4px 10px; }
.dict-count { padding: 0 6px 10px; color: var(--sw-muted); font-size: 12px; }
.dict-count b { color: var(--sw-text); font-size: 18px; margin-right: 3px; }
.dict-nav-list { max-height: 570px; overflow: auto; }
.dict-empty { padding: 24px 12px; color: var(--sw-muted); font-size: 12px; text-align: center; }
.dict-content { min-width: 0; padding: 20px; }
.dict-head, .dict-footer { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.dict-head { margin-bottom: 16px; }
.dict-footer { padding-top: 16px; }
.dict-code { font-family: ui-monospace, Consolas, monospace; }
.dict-enabled { display: inline-flex; align-items: center; gap: 8px; white-space: nowrap; }
.dict-usage { margin: 6px 0 0; color: var(--sw-primary); font-size: 12px; }
.dict-table th:nth-child(1) { width: 28%; }
.dict-table th:nth-child(2) { width: 34%; }
.dict-table th:nth-child(3) { width: 100px; }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
@media (max-width: 760px) {
  .dict-workbench { grid-template-columns: 1fr; }
  .dict-nav { border-right: 0; border-bottom: 1px solid var(--sw-line); }
  .dict-nav-list { display: flex; gap: 6px; overflow-x: auto; }
  .dict-nav-list .sw-choice { min-width: 150px; }
}
</style>
