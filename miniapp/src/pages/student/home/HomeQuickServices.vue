<template>
  <view class="quick">
    <view class="quick__heading">
      <text class="quick__title">常用服务</text>
      <view class="quick__links"><button class="quick__link" :disabled="saving" @click="openEditor">编辑</button><button class="quick__link" @click="allServices">全部服务 ›</button></view>
    </view>
    <view v-if="error" class="quick__error"><text>{{ error }}</text><button v-if="!editing" class="quick__link" @click="load">重试</button></view>
    <text v-if="loading" class="quick__muted">正在读取常用服务…</text>
    <view v-else-if="!editing && loaded" class="quick__grid">
      <button v-for="item in displayed" :key="item.key" class="quick__item" @click="openService(item)"><MobileShellIcon :name="visual(item.label).icon" :tone="visual(item.label).tone" :size="27" round /><text>{{ item.label }}</text></button>
      <button v-if="!displayed.length" class="quick__empty" @click="openEditor">还没有常用服务，点此添加</button>
    </view>
    <view v-if="editing" class="quick__editor">
      <text class="quick__muted">已选 {{ draft.length }}/8 项 · 按下方顺序显示</text>
      <view v-for="(key, index) in draft" :key="key" class="quick__selected">
        <text class="quick__selected-name">{{ index + 1 }}. {{ nameOf(key) }}</text>
        <button class="quick__small" :disabled="saving || index === 0" @click="move(index, -1)" :aria-label="'上移' + nameOf(key)">上移</button>
        <button class="quick__small" :disabled="saving || index === draft.length - 1" @click="move(index, 1)" :aria-label="'下移' + nameOf(key)">下移</button>
        <button class="quick__small quick__remove" :disabled="saving" @click="toggle(key)">移除</button>
      </view>
      <view class="quick__tabs"><button v-for="cat in categories" :key="cat.key" :class="['quick__tab', { active: category === cat.key }]" :disabled="saving" @click="category = cat.key">{{ cat.label }}</button></view>
      <scroll-view scroll-y class="quick__options">
        <view class="quick__choices"><button v-for="item in candidates" :key="keyOf(item)" :class="['quick__choice', { selected: draft.includes(keyOf(item)) }]" :disabled="saving" @click="toggle(keyOf(item))"><MobileShellIcon :name="visual(item.name).icon" :tone="visual(item.name).tone" :size="19" /><text class="quick__choice-name">{{ item.name }}</text><text class="quick__check">{{ draft.includes(keyOf(item)) ? '已选' : '+' }}</text></button></view>
        <text v-if="!candidates.length" class="quick__muted">{{ categoryReason || '该模块暂无可选服务' }}</text>
      </scroll-view>
      <text class="quick__muted">仅调整首页入口，具体办理资格以学校规定为准。</text>
      <view class="quick__footer"><button class="quick__small" :disabled="saving" @click="restore">恢复推荐</button><button class="quick__small" :disabled="saving" @click="cancel">取消</button><button class="quick__save" :disabled="saving || loading" @click="save">{{ saving ? '保存中…' : '保存' }}</button></view>
    </view>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { realRequest, normalizeError } from '@/services/request'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { canNavigate, runAction } from '@/services/actionRouter'
import { serviceVisual } from '@/services/studentShellPresentation.mjs'
import { go, toast } from '@/utils/nav'
import { HOME_SHORTCUT_KEY, MAX_HOME_SHORTCUTS, shortcutKey, decodeShortcuts, encodeShortcuts, resolveShortcuts } from '@/services/homeShortcutPreferences.mjs'

export default {
  props: { defaults: { type: Array, default: () => [] } },
  data() { return { keys: null, directory: [], categories: [], category: 'studentAffairs', draft: [], editing: false, loading: false, saving: false, error: '', loaded: false, generation: -1, sequence: 0, disposed: false } },
  computed: {
    displayed() { return resolveShortcuts(this.keys, this.directory, this.defaults).filter(item => canNavigate(item.action, 'student')) },
    candidates() { return this.directory.filter(item => item.cat === this.category) },
    categoryReason() { return this.categories.find(cat => cat.key === this.category)?.reason || '' }
  },
  mounted() { this.load() },
  beforeUnmount() { this.disposed = true; this.sequence++ },
  methods: {
    visual: serviceVisual, keyOf: shortcutKey,
    allServices() { go('/pages/student/campus-service/index') },
    current(sequence, generation) { return !this.disposed && sequence === this.sequence && generation === currentSessionGeneration() },
    nameOf(key) { return this.directory.find(item => shortcutKey(item) === key)?.name || '已停用服务' },
    acceptDirectory(directory) {
      if (!Array.isArray(directory?.items) || !Array.isArray(directory?.categories)) throw new Error('服务目录读取不完整，请重试')
      const centers = directory.categories.map(cat => ({ ...cat, name: cat.label, cat: cat.key }))
      this.directory = [...directory.items, ...centers].filter(item => canNavigate(item.action, 'student'))
      this.categories = directory.categories
    },
    finish(sequence, generation, flag) {
      if (this.disposed || sequence !== this.sequence) return
      this[flag] = false
      if (generation !== currentSessionGeneration()) {
        this.loaded = false; this.keys = null; this.directory = []; this.draft = []; this.editing = false
        this.error = '登录状态已变化，请重新加载常用服务'
      }
    },
    openService(item) { if (this.generation !== currentSessionGeneration()) return this.load(); return runAction(item.action, { side: 'student' }) },
    async load() {
      if (this.loading || this.saving) return
      const sequence = ++this.sequence, generation = currentSessionGeneration()
      this.generation = generation; this.loading = true; this.error = ''; this.loaded = false; this.keys = null; this.directory = []; this.editing = false
      try {
        const [directory, prefs] = await Promise.all([studentApi.getServices(), realRequest('/me/preferences', { data: { keys: HOME_SHORTCUT_KEY } })])
        if (!this.current(sequence, generation)) return
        if (!Array.isArray(directory?.items) || !Array.isArray(directory?.categories) || !prefs?.items) throw new Error('常用服务读取不完整，请重试')
        this.acceptDirectory(directory)
        try { this.keys = decodeShortcuts(prefs.items[HOME_SHORTCUT_KEY]) }
        catch { this.keys = []; this.error = '原常用服务配置无法读取，请点编辑重新选择并保存' }
        this.loaded = true
      } catch (e) { if (this.current(sequence, generation)) this.error = normalizeError(e).text || '常用服务加载失败，请重试' }
      finally { this.finish(sequence, generation, 'loading') }
    },
    async openEditor() {
      if (this.saving || this.loading) return
      if (!this.loaded || this.generation !== currentSessionGeneration()) await this.load()
      if (!this.loaded || this.generation !== currentSessionGeneration() || this.disposed) return
      this.draft = this.displayed.map(item => shortcutKey(item)).filter(key => this.directory.some(item => shortcutKey(item) === key))
      this.error = ''; this.editing = true
    },
    toggle(key) {
      if (this.saving) return
      if (this.draft.includes(key)) this.draft = this.draft.filter(item => item !== key)
      else if (this.draft.length >= MAX_HOME_SHORTCUTS) toast('最多选择8项常用服务')
      else if (this.directory.some(item => shortcutKey(item) === key)) this.draft = [...this.draft, key]
    },
    move(index, delta) {
      if (this.saving || index + delta < 0 || index + delta >= this.draft.length) return
      const next = [...this.draft]; [next[index], next[index + delta]] = [next[index + delta], next[index]]; this.draft = next
    },
    restore() { if (!this.saving) this.draft = this.defaults.map(shortcutKey).filter(key => this.directory.some(item => shortcutKey(item) === key)).slice(0, MAX_HOME_SHORTCUTS) },
    cancel() { if (!this.saving) { this.editing = false; this.error = ''; this.draft = [] } },
    async save() {
      if (this.saving || !this.editing || !this.loaded) return
      if (this.generation !== currentSessionGeneration()) return this.load()
      const sequence = this.sequence, generation = this.generation, keys = [...this.draft]
      this.saving = true; this.error = ''
      try {
        const value = encodeShortcuts(keys)
        const directory = await studentApi.getServices()
        if (!this.current(sequence, generation)) return
        this.acceptDirectory(directory)
        if (keys.some(key => !this.directory.some(item => shortcutKey(item) === key))) throw new Error('部分服务已停用，请移除后重新保存')
        const result = await realRequest('/me/preferences', { method: 'POST', data: { key: HOME_SHORTCUT_KEY, value } })
        if (!this.current(sequence, generation)) return
        if (result?.key !== HOME_SHORTCUT_KEY || result?.value !== value) throw new Error('保存结果不完整，请重试')
        const prefs = await realRequest('/me/preferences', { data: { keys: HOME_SHORTCUT_KEY } })
        if (!this.current(sequence, generation)) return
        if (prefs?.items?.[HOME_SHORTCUT_KEY] !== value) throw new Error('保存结果尚未确认，请重试')
        this.keys = decodeShortcuts(value); this.editing = false; toast('常用服务已保存')
      } catch (e) { if (this.current(sequence, generation)) this.error = normalizeError(e).text || '保存失败，已保留选择，请重试' }
      finally { this.finish(sequence, generation, 'saving') }
    }
  }
}
</script>

<style scoped>
.quick { background:#fff; border-radius:18px; padding:18px 16px; margin-bottom:14px; color:#142440 }
.quick__heading,.quick__links,.quick__footer,.quick__selected { display:flex; align-items:center; gap:8px }
.quick__heading { justify-content:space-between; margin-bottom:16px }
.quick__title { font-size:19px; font-weight:700 }
/* Class-only selectors also work inside isolated WeChat components. */
.quick__link,.quick__item,.quick__empty,.quick__small,.quick__tab,.quick__choice,.quick__save { margin:0; line-height:1.5; border:0 }
.quick__link { background:transparent; color:#1671f8; font-size:13px; padding:10px 3px }
.quick__grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:16px 8px }
.quick__item { display:flex; flex-direction:column; align-items:center; gap:9px; background:transparent; padding:0; font-size:13px; color:#142440; min-width:0 }
.quick__muted { display:block; color:#65718a; font-size:12px; line-height:1.7 }
.quick__error { display:flex; align-items:center; justify-content:space-between; background:#fff4ef; color:#a23b23; padding:10px; border-radius:10px; font-size:13px; margin-bottom:12px }
.quick__empty { grid-column:1/-1; background:#eff6ff; color:#1671f8; padding:14px; font-size:14px }
.quick__selected { border-bottom:1px solid #edf0f5; min-height:48px }
.quick__selected-name { flex:1; min-width:0; font-size:13px }
.quick__small { padding:10px 6px; font-size:12px; color:#315681; background:transparent; flex-shrink:0 }
.quick__remove { color:#b54a48 }
.quick__tabs { display:flex; gap:4px; margin:16px 0 12px }
.quick__tab { flex:1; padding:10px 2px; background:#f3f6fa; color:#65718a; font-size:12px; border-radius:8px }
.quick__tab.active { background:#e8f1ff; color:#1163de; font-weight:600 }
.quick__options { height:260px; margin-bottom:12px }
.quick__choices { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px }
.quick__choice { display:flex; align-items:center; gap:5px; min-height:52px; padding:9px 7px; background:#f6f8fb; font-size:12px; text-align:left; color:#263955; border-radius:9px }
.quick__choice.selected { background:#e8f2ff; box-shadow:inset 0 0 0 1px #7eaff8 }
.quick__choice-name { flex:1 }
.quick__check { flex:none; color:#1163de; font-size:11px }
.quick__footer { justify-content:flex-end; border-top:1px solid #edf0f5; padding-top:12px; margin-top:10px }
.quick__save { padding:10px 22px; background:#1671f8; color:#fff; font-size:14px; border-radius:10px }
</style>
