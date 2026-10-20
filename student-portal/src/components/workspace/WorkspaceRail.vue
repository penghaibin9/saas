<template>
  <aside class="workspace-rail" :class="[mode, { tertiary }]" :aria-label="label">
    <div class="rail-body">
      <button class="rail-expand" :aria-label="`${mode === 'full' ? '收窄' : '展开'}${label}`" :title="`${mode === 'full' ? '显示两字' : '显示完整名称'}`" @click="$emit('update:mode', mode === 'full' ? 'compact' : 'full')"><WorkspaceIcon :name="mode === 'full' ? 'collapse' : 'expand'" /><strong class="rail-full">{{ title }}</strong></button>
      <nav class="rail-list" :aria-label="label">
        <button v-for="item in items" :key="item.id" :aria-label="item.title" :aria-current="active === item.id ? 'page' : undefined" :title="item.title" :class="{ selected: active === item.id }" @click="$emit('select', item)">
          <WorkspaceIcon v-if="!tertiary" :name="item.id" /><span class="rail-short">{{ item.short }}</span><span class="rail-full">{{ item.title }}</span>
        </button>
      </nav>
    </div>
    <button class="rail-pin" :aria-label="`${mode === 'auto' ? '固定' : '取消固定'}${label}`" :aria-pressed="mode !== 'auto'" :title="mode === 'auto' ? '固定为两字窄栏' : '取消固定，悬停显示全称'" @click="$emit('update:mode', mode === 'auto' ? 'compact' : 'auto')">{{ mode === 'auto' ? '固定' : '已固定' }}</button>
  </aside>
</template>
<script setup>
import WorkspaceIcon from './WorkspaceIcon.vue'
defineProps({ items: { type: Array, default: () => [] }, active: { type: String, default: '' }, mode: { type: String, default: 'compact' }, label: { type: String, required: true }, title: { type: String, default: '' }, tertiary: Boolean })
defineEmits(['update:mode', 'select'])
</script>
<style scoped>
.workspace-rail{width:80px;flex:none;position:relative;border-right:1px solid var(--line);background:var(--surface-2);display:flex;flex-direction:column;z-index:12;min-height:0}
.workspace-rail.tertiary{width:64px;z-index:11}.workspace-rail.full{width:204px}.workspace-rail.tertiary.full{width:192px}
.rail-body{display:flex;flex-direction:column;min-height:0;flex:1;background:var(--surface-2)}
.rail-expand{height:42px;flex:none;border:0;background:transparent;display:flex;align-items:center;gap:12px;padding:0 20px;color:var(--t3);cursor:pointer}
.rail-expand>span{font-size:23px;font-weight:300}.rail-expand strong{font-size:13px;color:var(--t1);white-space:nowrap}
.rail-list{min-height:0;overflow:auto;overflow-x:hidden;padding:4px 6px;flex:1;scrollbar-width:thin;scrollbar-color:var(--line) transparent}
.rail-list button{border:0;background:transparent;width:100%;min-height:42px;margin:2px 0;padding:0 8px;border-radius:6px;display:flex;align-items:center;gap:7px;color:var(--t3);cursor:pointer;text-align:left;white-space:nowrap;font-size:13px}
.rail-list .workspace-icon{width:17px;height:17px}.rail-list button:hover{background:var(--pri-50)}.rail-list button.selected{background:var(--pri-50);box-shadow:inset 2px 0 var(--pri);color:var(--pri);font-weight:650}
.rail-full{display:none}.full .rail-full{display:inline}.full .rail-short{display:none}.tertiary .rail-list button{justify-content:center}.tertiary.full .rail-list button{justify-content:flex-start;padding-left:14px}
.rail-pin{height:44px;flex:none;position:relative;z-index:1;border:0;border-top:1px solid var(--line);background:var(--surface-2);color:var(--pri);font-size:11px;cursor:pointer}
@media(hover:hover){.auto .rail-body:hover,.auto .rail-body:focus-within{position:absolute;inset:0 auto 44px 0;width:204px;box-shadow:12px 0 24px #172b4614;border-right:1px solid var(--line)}.auto .rail-body:hover .rail-full,.auto .rail-body:focus-within .rail-full{display:inline}.auto .rail-body:hover .rail-short,.auto .rail-body:focus-within .rail-short{display:none}.auto.tertiary .rail-body:hover button,.auto.tertiary .rail-body:focus-within button{justify-content:flex-start}}
</style>
