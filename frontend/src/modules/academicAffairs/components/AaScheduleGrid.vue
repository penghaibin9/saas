<template>
  <div class="aa-grid-wrap" role="region" aria-label="周课表，窄屏可横向滚动" tabindex="0">
    <table class="aa-grid" aria-label="按星期与节次排列的课程">
      <thead>
        <tr>
          <th class="aa-grid__slot-col" scope="col">节次</th>
          <th v-for="d in WEEKDAYS" :key="d.v" scope="col">{{ d.label }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="slot in slots" :key="slot.slotNo">
          <th class="aa-grid__slot-col" scope="row">
            <div>第 {{ slot.slotNo }} 节</div>
            <div v-if="slot.startTime" class="aa-grid__time">{{ slot.startTime }}<template v-if="slot.endTime">-{{ slot.endTime }}</template></div>
          </th>
          <td
            v-for="d in WEEKDAYS"
            :key="d.v"
            class="aa-grid__cell"
            :class="{ 'is-editable': editable, 'is-conflict': isConflict(d.v, slot.slotNo), 'is-drop-target': isDropTarget(d.v, slot.slotNo) }"
            @click="onCellClick(d.v, slot.slotNo, $event)"
            @dragover.prevent="onDragOver(d.v, slot.slotNo)"
            @dragleave="dropTarget = null"
            @drop.prevent="onDrop(d.v, slot.slotNo)"
          >
            <div
              v-for="it in itemsAt(d.v, slot.slotNo)"
              :key="it.itemId || (it.courseName + it.weekday + it.slotNo)"
              class="aa-grid__item"
              :role="interactive || editable ? 'button' : undefined"
              :tabindex="interactive || editable ? 0 : undefined"
              :class="{ 'is-dragging': dragging && dragging.itemId === it.itemId }"
              :draggable="editable && !!it.itemId"
              @dragstart="onDragStart(it, $event)"
              @dragend="dragging = null; dropTarget = null"
              @click.stop="$emit('item-click', it)"
              @keydown.enter.stop.prevent="$emit('item-click', it)"
              @keydown.space.stop.prevent="$emit('item-click', it)"
            >
              <div class="aa-grid__course">{{ it.courseName }}</div>
              <div class="aa-grid__meta">
                <span v-if="it.teacherName">{{ it.teacherName }}</span>
                <span v-if="it.classroom">@{{ it.classroom }}</span>
              </div>
              <div class="aa-grid__weeks">
                {{ it.startWeek }}-{{ it.endWeek }}周
                <span v-if="it.weekParity && it.weekParity !== 'ALL'" class="aa-grid__parity">{{ it.weekParity === 'ODD' ? '单' : '双' }}</span>
                <span v-if="it.className" class="aa-grid__cls">· {{ it.className }}</span>
              </div>
            </div>
            <button v-if="editable && !itemsAt(d.v, slot.slotNo).length" type="button" class="aa-grid__add" :aria-label="`${d.label}第${slot.slotNo}节，安排课程`" @click.stop="$emit('cell-click', { weekday: d.v, slotNo: slot.slotNo })">＋</button>
          </td>
        </tr>
        <tr v-if="!slots.length">
          <td :colspan="8" class="aa-grid__empty">未配置作息节次，请先到「作息节次」添加节次</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script>
/**
 * AaScheduleGrid — 周历课表网格（教务中心自建，不引第三方日历库，手册 D5）。
 * 列=周一至周日，行=作息节次（GET /time-slots）；单元格渲染课表项（课程/教师/教室/周次段/单双周）。
 * 只读 / 编辑两态：editable 时空格显示「＋」可点击（emit cell-click），课表项可点击（emit item-click）。
 * 拖拽调格（对标商业教务图形化排课）：editable 时课表项可拖到任意格，emit item-move
 * {item, weekday, slotNo}；冲突判定由后端同一检测器裁决（409 由调用方 toast），前端不做假校验。
 * 冲突高亮：conflict={weekday,slotNo} 时该格红框。
 */
const WEEKDAYS = [
  { v: 1, label: '周一' }, { v: 2, label: '周二' }, { v: 3, label: '周三' },
  { v: 4, label: '周四' }, { v: 5, label: '周五' }, { v: 6, label: '周六' }, { v: 7, label: '周日' }
]

export default {
  name: 'AaScheduleGrid',
  props: {
    items: { type: Array, default: () => [] },
    slots: { type: Array, default: () => [] },
    editable: { type: Boolean, default: false },
    interactive: { type: Boolean, default: false },
    conflict: { type: Object, default: null }
  },
  emits: ['cell-click', 'item-click', 'item-move'],
  data() {
    return { WEEKDAYS, dragging: null, dropTarget: null }
  },
  methods: {
    itemsAt(weekday, slotNo) {
      return this.items.filter((it) => Number(it.weekday) === weekday && Number(it.slotNo) === slotNo)
    },
    isConflict(weekday, slotNo) {
      return this.conflict && Number(this.conflict.weekday) === weekday && Number(this.conflict.slotNo) === slotNo
    },
    isDropTarget(weekday, slotNo) {
      return this.dragging && this.dropTarget && this.dropTarget.weekday === weekday && this.dropTarget.slotNo === slotNo
    },
    onCellClick(weekday, slotNo, e) {
      if (!this.editable) return
      // 点击到课表项内部由 item-click 处理，这里只处理空白格
      if (e.target.closest('.aa-grid__item')) return
      this.$emit('cell-click', { weekday, slotNo })
    },
    onDragStart(it, e) {
      if (!this.editable || !it.itemId) return
      this.dragging = it
      e.dataTransfer.effectAllowed = 'move'
      e.dataTransfer.setData('text/plain', String(it.itemId))
    },
    onDragOver(weekday, slotNo) {
      if (this.dragging) this.dropTarget = { weekday, slotNo }
    },
    onDrop(weekday, slotNo) {
      const it = this.dragging
      this.dragging = null
      this.dropTarget = null
      if (!it) return
      if (Number(it.weekday) === weekday && Number(it.slotNo) === slotNo) return
      this.$emit('item-move', { item: it, weekday, slotNo })
    }
  }
}
</script>

<style scoped>
.aa-grid-wrap { overflow-x: auto; border-radius: 8px; }
.aa-grid { width: 100%; table-layout: fixed; border-collapse: collapse; min-width: 760px; }
.aa-grid th, .aa-grid td { border: 1px solid var(--border-200, #e5e6eb); vertical-align: top; }
.aa-grid thead th { background: var(--fill-100, #f2f3f5); padding: 8px; font-size: 13px; font-weight: 500; color: var(--text-700, #4e5969); text-align: center; }
.aa-grid__slot-col { position: sticky; left: 0; z-index: 1; width: 88px; text-align: center; padding: 12px 8px; font-size: 12px; color: var(--text-secondary); background: var(--bg-card); }
.aa-grid__time { font-size: 11px; color: var(--text-400, #8a9099); margin-top: 2px; }
.aa-grid__cell { height: 68px; padding: 4px; position: relative; }
.aa-grid__cell.is-editable { cursor: pointer; }
.aa-grid__cell.is-editable:hover { background: var(--fill-50, #f7f8fa); }
.aa-grid__cell.is-conflict { outline: 2px solid var(--danger-500, #ef4444); outline-offset: -2px; background: var(--danger-50, #fef2f2); }
.aa-grid__cell.is-drop-target { outline: 2px dashed var(--primary-400, #60a5fa); outline-offset: -2px; background: var(--primary-50, #eff6ff); }
.aa-grid__item { background: var(--pri-50); border-left: 3px solid var(--pri); border-radius: 6px; padding: 10px 8px; margin-bottom: 4px; overflow-wrap: anywhere; }
.aa-grid__item[role='button'] { cursor: pointer; }
.aa-grid__item[draggable='true'] { cursor: grab; }
.aa-grid__item.is-dragging { opacity: 0.4; }
.aa-grid__course { font-size: 13px; font-weight: 600; line-height: 1.5; color: var(--text-primary); }
.aa-grid__meta { font-size: 12px; color: var(--text-secondary); display: flex; flex-wrap: wrap; gap: 2px 6px; margin-top: 5px; }
.aa-grid__weeks { font-size: 12px; color: var(--text-secondary); margin-top: 6px; line-height: 1.5; }
.aa-grid__parity { color: var(--warning-600, #d97706); margin-left: 2px; }
.aa-grid__cls { color: var(--text-500, #646a73); }
.aa-grid__add { display: block; width: 100%; min-height: 48px; border: 1px dashed var(--border-base); border-radius: 6px; background: transparent; color: var(--text-secondary); font-size: 20px; cursor: pointer; }
.aa-grid-wrap:focus-visible, .aa-grid__item:focus-visible, .aa-grid__add:focus-visible { outline: 2px solid var(--pri); outline-offset: -2px; }
.aa-grid__cell.is-editable:hover .aa-grid__add { color: var(--primary-400, #60a5fa); }
.aa-grid__empty { text-align: center; color: var(--text-400, #8a9099); padding: 24px; font-size: 13px; }
@media print { .aa-grid__slot-col { position: static; } }
</style>
