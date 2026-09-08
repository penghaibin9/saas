<template>
  <dialog ref="dialog" class="shortcut-editor" aria-labelledby="shortcut-editor-title" @close="dragged = ''">
    <header class="editor-head"><div><p>常用入口，按你的习惯排列</p><h2 id="shortcut-editor-title">编辑快捷栏</h2></div><button type="button" class="icon-button" aria-label="关闭快捷栏编辑" @click="dialog.close()"><Close /></button></header>
    <div class="editor-body">
      <section class="editor-selection">
        <header><h3>我的快捷入口</h3><small>{{ draft.shortcuts.length }} / 8</small></header>
        <p class="editor-hint">拖动调整顺序，点击入口修改样式。</p>
        <ol class="selection-list">
          <li v-for="(page, index) in selectedPages" :key="page.id" :class="{ selected: selectedId === page.id, dragging: dragged === page.id }" draggable="true" @dragstart="startDrag($event, page.id)" @dragend="dragged = ''" @dragover.prevent @drop.prevent="dropOn(page.id)">
            <Rank class="drag-handle" aria-hidden="true" />
            <button type="button" class="selection-item" :aria-pressed="selectedId === page.id" @click="select(page.id)"><span class="color-icon" :style="iconStyle(page)"><component :is="SHORTCUT_ICONS[look(page).icon]" /></span><span class="selection-copy"><strong>{{ look(page).label || page.title }}</strong><small>{{ page.title }}</small></span></button>
            <span class="order-controls"><button type="button" :disabled="index === 0" :aria-label="'上移' + page.title" @click="move(index, -1)"><ArrowUp /></button><button type="button" :disabled="index === selectedPages.length - 1" :aria-label="'下移' + page.title" @click="move(index, 1)"><ArrowDown /></button></span>
            <button type="button" class="icon-button remove" :aria-label="'移除' + page.title" @click="remove(page.id)"><Close /></button>
          </li>
        </ol>
        <p v-if="!selectedPages.length" class="editor-hint">从右侧添加常用入口</p>
      </section>
      <section class="editor-right">
        <div class="editor-tabs" role="group" aria-label="快捷栏设置"><button type="button" :aria-pressed="tab === 'add'" @click="tab = 'add'">添加入口</button><button type="button" :aria-pressed="tab === 'style'" :disabled="!selectedPage" @click="tab = 'style'">外观设置</button></div>
        <div v-if="tab === 'add'" class="editor-add">
          <input v-model="query" type="search" placeholder="搜索页面或业务模块" aria-label="搜索可添加入口" />
          <div class="available-list"><label v-for="page in availablePages" :key="page.id"><input type="checkbox" :checked="draft.shortcuts.includes(page.id)" :disabled="draft.shortcuts.length >= 8 && !draft.shortcuts.includes(page.id)" @change="toggle(page.id, $event.target.checked)" /><span>{{ page.title }}<small>{{ page.trail }}</small></span></label><p v-if="!availablePages.length" class="editor-hint">没有匹配的入口</p></div>
        </div>
        <div v-else-if="selectedPage" class="editor-style">
          <div class="style-preview"><span class="color-icon" :style="iconStyle(selectedPage)"><component :is="SHORTCUT_ICONS[look(selectedPage).icon]" /></span><strong>{{ look(selectedPage).label || selectedPage.title }}</strong></div>
          <label class="style-field"><span>显示名称 <small>最多 16 个字</small></span><input :value="draft.appearance[selectedId]?.label || ''" :placeholder="selectedPage.title" maxlength="16" @input="setStyle('label', $event.target.value)" /></label>
          <p class="editor-hint">对应页面：{{ selectedPage.trail }} / {{ selectedPage.title }}</p>
          <h3>图标</h3><div class="icon-options"><button v-for="(icon, key) in SHORTCUT_ICONS" :key="key" type="button" :aria-label="SHORTCUT_ICON_LABELS[key] + '图标'" :title="SHORTCUT_ICON_LABELS[key]" :aria-pressed="look(selectedPage).icon === key" @click="setStyle('icon', key)"><component :is="icon" /></button></div>
          <h3>颜色</h3><div class="color-options"><button v-for="(tone, key) in WORKSPACE_TONES" :key="key" type="button" :style="{ '--swatch': tone.value }" :aria-label="tone.label" :title="tone.label" :aria-pressed="look(selectedPage).color === key" @click="setStyle('color', key)"><Check v-if="look(selectedPage).color === key" /></button></div>
        </div>
      </section>
    </div>
    <footer class="editor-footer"><button type="button" class="reset-button" @click="resetDraft">恢复默认</button><span>保存后生效</span><button type="button" @click="dialog.close()">取消</button><button type="button" class="save-button" @click="save">保存快捷栏</button></footer>
  </dialog>
</template>
<script setup>
import { computed, ref, watch } from 'vue'
import { ArrowUp, ArrowDown, Check, Close, Rank } from '@element-plus/icons-vue'
import { restoreWorkspace, shortcutAppearance, WORKSPACE_TONES } from './teacherWorkspace'
import { SHORTCUT_ICONS, SHORTCUT_ICON_LABELS } from './shortcutIcons'
const props = defineProps({ pages: { type: Array, required: true }, prefs: { type: Object, required: true }, identityKey: { type: String, required: true } })
const emit = defineEmits(['save'])
const dialog = ref(null), draft = ref({ shortcuts: [], appearance: {} }), selectedId = ref(''), tab = ref('add'), query = ref(''), dragged = ref('')
const selectedPages = computed(() => draft.value.shortcuts.map(id => props.pages.find(page => page.id === id)).filter(Boolean))
const selectedPage = computed(() => props.pages.find(page => page.id === selectedId.value))
const availablePages = computed(() => props.pages.filter(page => `${page.title} ${page.trail}`.toLowerCase().includes(query.value.trim().toLowerCase())))
const look = page => shortcutAppearance(page, draft.value.appearance)
const iconStyle = page => ({ background: WORKSPACE_TONES[look(page).color].value })
function open() {
  const restored = restoreWorkspace(props.prefs, props.pages)
  draft.value = { shortcuts: [...restored.shortcuts], appearance: structuredClone(restored.appearance) }
  selectedId.value = draft.value.shortcuts[0] || ''; tab.value = selectedId.value ? 'style' : 'add'; query.value = ''
  dialog.value.showModal()
}
function select(id) { selectedId.value = id; tab.value = 'style' }
function setStyle(key, value) { if (selectedPage.value) draft.value.appearance[selectedId.value] = { ...look(selectedPage.value), [key]: value } }
function remove(id) { draft.value.shortcuts = draft.value.shortcuts.filter(key => key !== id); if (selectedId.value === id) selectedId.value = draft.value.shortcuts[0] || ''; if (!selectedId.value) tab.value = 'add' }
function toggle(id, checked) { if (!checked) return remove(id); if (draft.value.shortcuts.length < 8 && !draft.value.shortcuts.includes(id)) { draft.value.shortcuts.push(id); selectedId.value = id } }
function move(index, direction) { const ids = [...draft.value.shortcuts], next = index + direction; if (next < 0 || next >= ids.length) return; [ids[index], ids[next]] = [ids[next], ids[index]]; draft.value.shortcuts = ids }
function startDrag(event, id) { dragged.value = id; event.dataTransfer.effectAllowed = 'move'; event.dataTransfer.setData('text/plain', id) }
function dropOn(id) { const ids = [...draft.value.shortcuts], from = ids.indexOf(dragged.value), to = ids.indexOf(id); if (from < 0 || to < 0 || from === to) return; ids.splice(to, 0, ids.splice(from, 1)[0]); draft.value.shortcuts = ids; dragged.value = '' }
function resetDraft() { const restored = restoreWorkspace({}, props.pages); draft.value = { shortcuts: restored.shortcuts, appearance: {} }; selectedId.value = draft.value.shortcuts[0] || ''; tab.value = selectedId.value ? 'style' : 'add' }
function save() { const safe = restoreWorkspace({ ...props.prefs, ...draft.value }, props.pages); emit('save', { shortcuts: safe.shortcuts, appearance: safe.appearance }); dialog.value.close() }
watch(() => props.identityKey, () => dialog.value?.close())
defineExpose({ open })
</script>
<style scoped>
.shortcut-editor{width:min(930px,calc(100vw - 32px));height:min(650px,calc(100dvh - 40px));max-height:none;box-sizing:border-box;padding:0;border:1px solid var(--line);border-radius:16px;background:var(--surface);color:var(--t1);box-shadow:0 24px 80px #122e5833;overflow:hidden}.shortcut-editor[open]{display:flex;flex-direction:column}.shortcut-editor::backdrop{background:#172b4648;backdrop-filter:blur(3px)}
.shortcut-editor button{font:inherit;cursor:pointer;color:var(--t3);border:1px solid transparent;background:transparent;border-radius:6px}.shortcut-editor button:disabled{opacity:.4;cursor:default}.shortcut-editor button:focus-visible,.shortcut-editor input:focus-visible{outline:2px solid var(--pri);outline-offset:2px}.shortcut-editor svg{width:20px;height:20px;flex:none}.editor-head{display:flex;justify-content:space-between;align-items:center;padding:20px 24px;border-bottom:1px solid var(--line)}.editor-head p{font-size:12px;color:var(--t3);margin:0 0 8px}.editor-head h2{font-size:22px;margin:0}.icon-button{display:grid;place-items:center;padding:4px}
.editor-body{display:grid;grid-template-columns:340px minmax(0,1fr);flex:1;min-height:0}.editor-selection{background:var(--surface-2);border-right:1px solid var(--line);padding:20px 18px 10px;display:flex;flex-direction:column;min-height:0}.editor-selection header{display:flex;justify-content:space-between;align-items:center}.shortcut-editor h3{font-size:14px;margin:0}.editor-selection small,.editor-hint{color:var(--t3);font-size:12px}.editor-hint{line-height:1.6;margin:9px 0}.selection-list{padding:0 3px 0 0;margin:8px 0 0;list-style:none;overflow:auto;min-height:0;scrollbar-width:thin}.selection-list li{display:flex;align-items:center;gap:6px;padding:8px 6px;background:var(--surface);border:1px solid var(--line);border-radius:8px;margin-bottom:8px;min-height:54px}.selection-list li.selected{border-color:var(--pri)}.selection-list li.dragging{opacity:.45}.drag-handle{width:13px!important;color:var(--t3);cursor:grab}.selection-item{display:flex;align-items:center;gap:9px;flex:1;min-width:0;padding:0;text-align:left}.color-icon{display:grid;place-items:center;width:34px;height:34px;border-radius:10px;color:#fff;flex:none}.color-icon svg{width:21px;height:21px}.selection-copy{display:flex;flex-direction:column;gap:4px;min-width:0}.selection-copy strong{font-size:13px;font-weight:500;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}.selection-copy small{font-size:11px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}.order-controls{display:flex;flex-direction:column}.order-controls button{display:grid;place-items:center;padding:1px}.order-controls svg,.remove svg{width:14px;height:14px}.editor-right{min-width:0;min-height:0;display:flex;flex-direction:column}.editor-tabs{display:flex;gap:24px;margin:0 24px;border-bottom:1px solid var(--line)}.editor-tabs button{padding:17px 0 11px;border-radius:0;border-bottom:2px solid transparent;font-size:14px}.editor-tabs button[aria-pressed=true]{color:var(--pri);border-bottom-color:var(--pri);font-weight:600}.editor-style,.editor-add{padding:18px 24px;overflow:auto;min-height:0}.style-preview{display:flex;align-items:center;gap:16px;background:var(--surface-2);padding:14px;border:1px solid var(--line);border-radius:8px;margin-bottom:18px}.style-preview .color-icon{width:42px;height:42px}.style-preview strong{font-size:18px;font-weight:550;overflow-wrap:anywhere}.style-field{display:block;font-size:13px;color:var(--t3)}.style-field>span{display:flex;justify-content:space-between;margin-bottom:8px}.style-field small{font-size:11px}.style-field input,.editor-add>input{box-sizing:border-box;width:100%;padding:10px 12px;border:1px solid var(--line);border-radius:6px;background:var(--surface);color:var(--t1);font:inherit}.editor-style h3{margin-top:20px;margin-bottom:10px}.icon-options{display:grid;grid-template-columns:repeat(6,1fr);gap:6px}.icon-options button{display:grid;place-items:center;border-color:var(--line);padding:8px;color:var(--t3)}.icon-options button[aria-pressed=true]{border-color:var(--pri);color:var(--pri);background:var(--pri-50)}.color-options{display:flex;gap:13px;flex-wrap:wrap;padding:4px}.color-options button{display:grid;place-items:center;width:30px;height:30px;border-radius:50%;background:var(--swatch);color:#fff;padding:5px}.color-options button[aria-pressed=true]{outline:1px solid var(--swatch);outline-offset:4px}.available-list{display:flex;flex-direction:column;margin-top:12px}.available-list label{display:flex;align-items:center;gap:12px;border-bottom:1px solid var(--line);padding:10px 0;font-size:13px}.available-list label>span{display:flex;flex-direction:column;gap:4px}.available-list small{font-size:11px;color:var(--t3)}.available-list input{accent-color:var(--pri)}.editor-footer{display:flex;align-items:center;gap:12px;border-top:1px solid var(--line);padding:15px 24px}.editor-footer>span{margin-left:auto;font-size:12px;color:var(--t3)}.editor-footer button{padding:10px 16px;border-color:var(--line);font-size:13px}.editor-footer .reset-button{border:0;padding-left:0}.editor-footer .save-button{background:var(--pri);color:var(--pri-on);border-color:var(--pri)}
@media(max-width:700px){.editor-body{grid-template-columns:1fr;overflow:auto}.editor-selection{max-height:210px;min-height:160px;border-right:0;border-bottom:1px solid var(--line)}.editor-right{min-height:400px;overflow:visible}.editor-style,.editor-add{overflow:visible}.editor-head{padding:14px 18px}.editor-footer{padding:12px;gap:8px}.editor-footer>span{display:none}.editor-footer .reset-button{margin-right:auto}.editor-tabs{flex:none}.editor-style{padding:16px}.shortcut-editor{height:calc(100dvh - 24px)}}
</style>
