<template>
  <div class="aa-grid-wrap">
    <table class="aa-grid">
      <thead>
        <tr>
          <th class="aa-grid__slot-col">节次</th>
          <th v-for="d in WEEKDAYS" :key="d.v">{{ d.label }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="slot in slots" :key="slot.slotNo">
          <th class="aa-grid__slot-col">
            <div>第 {{ slot.slotNo }} 节</div>
            <div v-if="slot.startTime" class="aa-grid__time">{{ slot.startTime }}<template v-if="slot.endTime">-{{ slot.endTime }}</template></div>
          </th>
          <td
            v-for="d in WEEKDAYS"
            :key="d.v"
            class="aa-grid__cell"
            :class="{ 'is-editable': editable, 'is-conflict': isConflict(d.v, slot.slotNo) }"
            @click="onCellClick(d.v, slot.slotNo, $event)"
          >
            <div
              v-for="it in itemsAt(d.v, slot.slotNo)"
              :key="(it.itemId || (it.courseName + it.weekday + it.slotNo)) + (it.source || '')"
              class="aa-grid__item"
              :class="{ 'is-enrolled': it.source === 'ENROLLED' }"
              @click.stop="$emit('item-click', it)"
            >
              <div class="aa-grid__course">
                {{ it.courseName }}
                <span v-if="it.source === 'ENROLLED'" class="aa-grid__tag">选修</span>
              </div>
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
            <span v-if="editable && !itemsAt(d.v, slot.slotNo).length" class="aa-grid__add">＋</span>
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
    conflict: { type: Object, default: null }
  },
  emits: ['cell-click', 'item-click'],
  data() {
    return { WEEKDAYS }
  },
  methods: {
    itemsAt(weekday, slotNo) {
      return this.items.filter((it) => Number(it.weekday) === weekday && Number(it.slotNo) === slotNo)
    },
    isConflict(weekday, slotNo) {
      return this.conflict && Number(this.conflict.weekday) === weekday && Number(this.conflict.slotNo) === slotNo
    },
    onCellClick(weekday, slotNo, e) {
      if (!this.editable) return
      // 点击到课表项内部由 item-click 处理，这里只处理空白格
      if (e.target.closest('.aa-grid__item')) return
      this.$emit('cell-click', { weekday, slotNo })
    }
  }
}
</script>

<style scoped>
.aa-grid-wrap { overflow-x: auto; }
.aa-grid { width: 100%; border-collapse: collapse; min-width: 760px; }
.aa-grid th, .aa-grid td { border: 1px solid var(--border-200, #e5e6eb); vertical-align: top; }
.aa-grid thead th { background: var(--fill-100, #f2f3f5); padding: 8px; font-size: 13px; font-weight: 500; color: var(--text-700, #4e5969); text-align: center; }
.aa-grid__slot-col { width: 88px; text-align: center; padding: 8px; font-size: 12px; color: var(--text-500, #646a73); background: var(--fill-50, #f7f8fa); }
.aa-grid__time { font-size: 11px; color: var(--text-400, #8a9099); margin-top: 2px; }
.aa-grid__cell { height: 68px; padding: 4px; position: relative; }
.aa-grid__cell.is-editable { cursor: pointer; }
.aa-grid__cell.is-editable:hover { background: var(--fill-50, #f7f8fa); }
.aa-grid__cell.is-conflict { outline: 2px solid var(--danger-500, #ef4444); outline-offset: -2px; background: var(--danger-50, #fef2f2); }
.aa-grid__item { background: var(--primary-50, #eff6ff); border-left: 3px solid var(--primary-400, #60a5fa); border-radius: 4px; padding: 4px 6px; margin-bottom: 4px; cursor: pointer; }
.aa-grid__item.is-enrolled { background: var(--success-50, #ecfdf5); border-left-color: var(--success-400, #34d399); }
.aa-grid__course { font-size: 12px; font-weight: 500; color: var(--text-900, #1f2329); }
.aa-grid__tag { display: inline-block; font-size: 10px; font-weight: 500; color: var(--success-600, #059669); background: var(--success-100, #d1fae5); border-radius: 3px; padding: 0 4px; margin-left: 4px; vertical-align: middle; }
.aa-grid__meta { font-size: 11px; color: var(--text-600, #566073); display: flex; gap: 6px; }
.aa-grid__weeks { font-size: 11px; color: var(--text-400, #8a9099); }
.aa-grid__parity { color: var(--warning-600, #d97706); margin-left: 2px; }
.aa-grid__cls { color: var(--text-500, #646a73); }
.aa-grid__add { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); color: var(--border-300, #d0d3d9); font-size: 18px; }
.aa-grid__cell.is-editable:hover .aa-grid__add { color: var(--primary-400, #60a5fa); }
.aa-grid__empty { text-align: center; color: var(--text-400, #8a9099); padding: 24px; font-size: 13px; }
</style>
