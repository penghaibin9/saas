<template>
  <view class="teacher-shell common-services">
    <view class="ts-heading"><view class="ts-title"><view class="ts-marker" /><text>常用服务</text></view>
      <view class="common-heading-actions"><button v-if="!editing" class="ts-link ts-plain" :disabled="!storageKey || !!readError" @click="startEdit">编辑</button><button class="ts-link ts-plain" @click="goHall">服务大厅<MobileShellIcon name="chevron-right" :size="16" /></button></view>
    </view>
    <view v-if="readError" class="ts-error"><text>{{ readError }}</text><button class="ts-link ts-plain" @click="load">重试</button></view>
    <template v-else-if="editing">
      <text class="ts-muted">已选 {{ selected.length }}/{{ limit }} · 用上移、下移调整顺序</text>
      <view v-if="!selected.length" class="ts-empty">还未选择服务，可从下方添加。</view>
      <view v-for="(item,index) in selected" :key="item.key" class="common-selected">
        <text class="common-selected-name">{{ index + 1 }}. {{ item.label }}</text>
        <button class="ts-link ts-plain" :class="{ 'common-move-disabled': index === 0 }" :disabled="index === 0" :aria-label="'上移' + item.label" @click="move(item.key,-1)">上移</button>
        <button class="ts-link ts-plain" :class="{ 'common-move-disabled': index === selected.length-1 }" :disabled="index === selected.length-1" :aria-label="'下移' + item.label" @click="move(item.key,1)">下移</button>
        <button class="ts-link ts-plain common-remove" :aria-label="'移除' + item.label" @click="remove(item.key)">移除</button>
      </view>
      <view v-for="group in groups" :key="group.label" class="common-group">
        <text class="common-group-title">{{ group.label }}</text>
        <view class="common-options"><button v-for="item in group.items" :key="item.key" class="common-option ts-plain" :class="{ 'is-selected': draftKeys.includes(item.key) }" :aria-pressed="draftKeys.includes(item.key)" @click="toggle(item.key)">
          <MobileShellIcon :name="visual(item.label).icon" :tone="visual(item.label).tone" :size="22" /><text class="common-option-name">{{ item.label }}</text><text class="common-option-state">{{ draftKeys.includes(item.key) ? '已选' : '添加' }}</text>
        </button></view>
      </view>
      <text v-if="!services.length" class="ts-empty">当前身份暂无可添加的服务。</text>
      <text class="ts-muted common-note">仅保存在当前设备，按账号和工作身份分别设置。</text>
      <text v-if="editError" class="common-error" role="alert">{{ editError }}</text>
      <view class="common-edit-actions"><button class="ts-link ts-plain common-restore" @click="restoreDefaults">恢复默认</button><button class="ts-link ts-plain" @click="cancelEdit">取消</button><button class="ts-action" @click="save">保存</button></view>
    </template>
    <template v-else>
      <view class="common-grid"><button v-for="item in visibleServices" :key="item.key" class="common-service ts-plain" @click="$emit('open',item)"><MobileShellIcon :name="visual(item.label).icon" :tone="visual(item.label).tone" :size="26" round /><text>{{ item.label }}</text></button></view>
      <view v-if="!visibleServices.length" class="ts-empty">尚未设置常用服务，点击“编辑”添加。</view>
    </template>
  </view>
</template>
<script>
import { teacherVisual } from '@/services/teacherServiceCatalog.mjs'
import { COMMON_SERVICE_LIMIT, allowedCommonServiceKeys, defaultCommonServiceKeys, readCommonServiceKeys, saveCommonServiceKeys } from '@/services/teacherCommonServices.mjs'
import { go, toast } from '@/utils/nav'
export default {
  props: { services: { type: Array, default: () => [] }, storageKey: { type: String, default: '' }, role: String },
  emits: ['open'],
  data: () => ({ storedKeys: null, draftKeys: [], editing: false, readError: '', editError: '', limit: COMMON_SERVICE_LIMIT, editScope: '' }),
  watch: { storageKey: { immediate: true, handler() { this.cancelEdit(); this.load() } } },
  computed: {
    visibleServices() {
      const keys = allowedCommonServiceKeys(this.storedKeys === null ? defaultCommonServiceKeys(this.services,this.role) : this.storedKeys, this.services)
      return keys.map(key => this.services.find(item => item.key === key))
    },
    selected() { return allowedCommonServiceKeys(this.draftKeys,this.services).map(key => this.services.find(item => item.key === key)) },
    groups() {
      const groups = []
      for (const item of this.services) {
        let group = groups.find(group => group.label === item.group)
        if (!group) { group = { label: item.group, items: [] }; groups.push(group) }
        group.items.push(item)
      }
      return groups
    }
  },
  methods: {
    visual: teacherVisual,
    goHall() { go('/pages/teacher/services/index') },
    load() {
      this.storedKeys = null; this.readError = ''
      if (!this.storageKey) return
      try { this.storedKeys = readCommonServiceKeys(uni, this.storageKey) }
      catch (_) { this.readError = '常用服务设置读取失败，请重试。' }
    },
    startEdit() {
      if (!this.storageKey || this.readError) return
      this.editScope = this.storageKey; this.draftKeys = this.visibleServices.map(item => item.key); this.editError = ''; this.editing = true
    },
    cancelEdit() { this.editing = false; this.draftKeys = []; this.editError = ''; this.editScope = '' },
    remove(key) { this.draftKeys = this.draftKeys.filter(item => item !== key); this.editError = '' },
    toggle(key) {
      if (this.draftKeys.includes(key)) return this.remove(key)
      this.draftKeys = allowedCommonServiceKeys(this.draftKeys,this.services)
      if (this.draftKeys.length >= this.limit) { this.editError = `最多显示${this.limit}个常用服务，请先移除一项。`; return }
      if (this.services.some(item => item.key === key && item.path && !item.disabledReason)) this.draftKeys.push(key)
      this.editError = ''
    },
    move(key, direction) {
      const keys = allowedCommonServiceKeys(this.draftKeys,this.services), index = keys.indexOf(key), target = index + direction
      if (index < 0 || target < 0 || target >= keys.length) return
      ;[keys[index], keys[target]] = [keys[target], keys[index]]
      this.draftKeys = keys
    },
    restoreDefaults() { this.draftKeys = defaultCommonServiceKeys(this.services,this.role); this.editError = '' },
    save() {
      if (!this.editing || !this.storageKey || this.editScope !== this.storageKey) return this.cancelEdit()
      const keys = allowedCommonServiceKeys(this.draftKeys,this.services)
      try { saveCommonServiceKeys(uni,this.storageKey,keys) }
      catch (_) { this.editError = '保存失败，请检查设备存储空间后重试。'; return }
      this.storedKeys = keys; this.cancelEdit(); toast('常用服务已保存')
    }
  }
}
</script>
<style scoped lang="scss">
$teacher-shell-component: true;
@import '@/styles/teacher-shell.scss';
.common-services { min-height: 0; padding: 0; background: transparent; }
.common-heading-actions { display: flex; gap: 10px; }
.common-grid { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: 20px 12px; padding: 8px 0 20px; }
.common-service { display: flex; flex-direction: column; align-items: center; gap: 12px; font-size: 14px; line-height: 1.5; color: #142440; text-align: center !important; }
.common-selected { display: flex; align-items: center; gap: 4px; padding: 6px 0; border-bottom: 1px solid #edf0f5; }
.common-selected-name { flex: 1; min-width: 0; font-size: 14px; overflow-wrap: anywhere; }
.common-selected .ts-link { min-width: 40px; font-size: 13px; }
.common-selected .common-move-disabled { color: #a0a9b7; }
.common-remove { color: #d54c4c !important; }
.common-group { margin-top: 18px; }
.common-group-title { display: block; font-size: 15px; font-weight: 600; margin-bottom: 8px; }
.common-options { display: flex; flex-direction: column; gap: 8px; }
.common-option { display: flex; align-items: center; gap: 10px; min-height: 48px; width: 100%; padding: 8px 12px !important; border: 1px solid #e5eaf2 !important; border-radius: 10px; box-sizing: border-box; }
.common-option.is-selected { background: #eef5ff !important; border-color: #9cc1ff !important; }
.common-option-name { flex: 1; min-width: 0; font-size: 14px; color: #142440; }
.common-option-state { color: #1671f8; font-size: 13px; }
.common-note { margin-top: 18px; }
.common-error { display: block; color: #bd3434; font-size: 13px; line-height: 1.7; margin-top: 8px; }
.common-edit-actions { display: flex; align-items: center; justify-content: flex-end; gap: 16px; padding: 12px 0; }
.common-edit-actions .ts-action { min-height: 44px; }
.common-edit-actions .common-restore { margin-right: auto; }
</style>
