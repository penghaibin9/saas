<template>
  <ModulePageShell
    title="排课 · 课表维护"
    subtitle="选择班级载入其课表 → 点空格排课（教师/班级/教室三重冲突自动检测）"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <button class="mp-btn" @click="$router.push('/admin/academic-affairs/schedule')">返回批次</button>
      <button class="mp-btn" @click="showImport = !showImport">批量导入</button>
    </template>

    <div class="mp-stack">
      <div class="aa-filter">
        <label class="aa-filter__item">班级ID<input v-model.trim="classId" class="aa-input aa-input--sm" placeholder="必填" /></label>
        <label class="aa-filter__item">班级名称<input v-model.trim="className" class="aa-input" placeholder="用于新排课项显示" /></label>
        <button class="mp-btn" @click="loadClass">载入课表</button>
      </div>

      <AppInlineAlert v-if="lastConflict" type="error" :message="lastConflict" />

      <AppSectionCard v-if="showImport" title="批量导入课表行">
        <p class="mp-note">每行一条：<code>星期,节次,课程,教师,教室,起始周,结束周,单双周(ALL/ODD/EVEN)</code>。例：<code>1,1,高等数学,张老师,A101,1,18,ALL</code></p>
        <textarea v-model="importText" class="aa-textarea" rows="4" placeholder="1,1,高等数学,张老师,A101,1,18,ALL"></textarea>
        <div class="aa-import-actions">
          <button class="mp-btn mp-btn--primary" :disabled="importing || !classId" @click="doImport">{{ importing ? '导入中…' : '导入到当前班级' }}</button>
        </div>
        <div v-if="importResult" class="aa-import-result">
          成功 {{ importResult.imported }} 条，冲突 {{ (importResult.conflicts || []).length }} 条
          <ul v-if="importResult.conflicts && importResult.conflicts.length">
            <li v-for="c in importResult.conflicts" :key="c.row">第 {{ c.row }} 行：{{ c.detail }}</li>
          </ul>
        </div>
      </AppSectionCard>

      <LoadingState v-if="loading" />
      <AppSectionCard v-else :title="classId ? ('班级 ' + (className || classId) + ' 课表') : '请先载入班级课表'">
        <AaScheduleGrid
          :items="items"
          :slots="slots"
          :editable="!!classId"
          :conflict="conflictCell"
          @cell-click="onCellClick"
          @item-click="onItemClick"
          @item-move="onItemMove"
        />
      </AppSectionCard>
    </div>

    <AppConfirmDialog
      v-model:visible="add.visible"
      :title="`排课 · 周${add.weekday} 第${add.slotNo}节`"
      type="primary"
      confirm-text="确认排课"
      :submitting="add.submitting"
      @confirm="doAdd"
    >
      <div class="aa-assign-form">
        <label>课程名称<input v-model.trim="add.courseName" class="aa-input" placeholder="必填" /></label>
        <label>授课教师<input v-model.trim="add.teacherName" class="aa-input" /></label>
        <label>教师工号<input v-model.trim="add.teacherKey" class="aa-input" placeholder="冲突检测用" /></label>
        <label>教室<input v-model.trim="add.classroom" class="aa-input" /></label>
        <label>起始周<input v-model.number="add.startWeek" type="number" min="1" class="aa-input" /></label>
        <label>结束周<input v-model.number="add.endWeek" type="number" min="1" class="aa-input" /></label>
        <label>单双周
          <AppSelect
            v-model="add.weekParity"
            :options="weekParityOptions"
            placeholder=""
          />
        </label>
      </div>
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
/** 课表维护（/admin/academic-affairs/schedule/:batchId/edit）：AaScheduleGrid 编辑态 + 排课 + 冲突 + 导入。 */
import { ModulePageShell, LoadingState } from '@/components/business'
import { AppSectionCard, AppConfirmDialog, AppInlineAlert, AppSelect } from '@/components/common'
import AaScheduleGrid from '@/modules/academicAffairs/components/AaScheduleGrid.vue'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

export default {
  name: 'AaScheduleMaintainView',
  components: { ModulePageShell, LoadingState, AppSectionCard, AppConfirmDialog, AppInlineAlert, AppSelect, AaScheduleGrid },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: false, slots: [], items: [], classId: '', className: '',
      conflictCell: null, lastConflict: '',
      showImport: false, importText: '', importing: false, importResult: null,
      add: { visible: false, submitting: false, weekday: 1, slotNo: 1, courseName: '', teacherName: '', teacherKey: '', classroom: '', startWeek: 1, endWeek: 18, weekParity: 'ALL' }
    }
  },
  computed: {
    batchId() { return this.$route.params.batchId },
    weekParityOptions() {
      return [
        { value: 'ALL', label: '全周' },
        { value: 'ODD', label: '单周' },
        { value: 'EVEN', label: '双周' }
      ]
    }
  },
  created() { this.loadSlots() },
  methods: {
    async loadSlots() {
      const res = await academicAffairsApi.getTimeSlots()
      if (res.code === 0) this.slots = res.data
    },
    async loadClass() {
      if (!this.classId) { toast.error('请先填写班级ID'); return }
      this.loading = true
      const res = await academicAffairsApi.getScheduleClassView(this.batchId, this.classId)
      if (res.code === 0) this.items = (res.data && res.data.items) || []
      else toast.error(res.message || '载入失败')
      this.loading = false
    },
    onCellClick({ weekday, slotNo }) {
      this.conflictCell = null
      this.add = { visible: true, submitting: false, weekday, slotNo, courseName: '', teacherName: '', teacherKey: '', classroom: '', startWeek: 1, endWeek: 18, weekParity: 'ALL' }
    },
    onItemClick(it) {
      toast.info(`${it.courseName} · ${it.teacherName || ''} · ${it.startWeek}-${it.endWeek}周`)
    },
    async onItemMove({ item, weekday, slotNo }) {
      // 拖拽调格：后端同一冲突检测器裁决，409 时提示并回原位（前端不做假校验）
      const res = await academicAffairsApi.moveScheduleItem(item.itemId, weekday, slotNo)
      if (res.code === 0) { toast.success(`已调整到周${weekday}第${slotNo}节`); await this.loadClass() } else toast.error(res.message)
    },
    async doAdd() {
      if (!this.add.courseName) { toast.error('请填写课程名称'); return }
      this.add.submitting = true
      this.lastConflict = ''
      const res = await academicAffairsApi.addScheduleItem(this.batchId, {
        courseName: this.add.courseName,
        classId: this.classId,
        className: this.className || undefined,
        teacherName: this.add.teacherName || undefined,
        teacherKey: this.add.teacherKey || undefined,
        weekday: this.add.weekday, slotNo: this.add.slotNo,
        startWeek: this.add.startWeek, endWeek: this.add.endWeek,
        weekParity: this.add.weekParity, classroom: this.add.classroom || undefined
      })
      this.add.submitting = false
      if (res.code === 0) {
        this.add.visible = false
        toast.success('已排课')
        this.loadClass()
      } else {
        // 冲突：红框 + 提示
        this.conflictCell = { weekday: this.add.weekday, slotNo: this.add.slotNo }
        this.lastConflict = res.message || '排课冲突'
        toast.error(res.message || '排课冲突')
      }
    },
    async doImport() {
      if (!this.classId) { toast.error('请先填写班级ID'); return }
      const lines = this.importText.split('\n').map((l) => l.trim()).filter(Boolean)
      const items = lines.map((l) => {
        const [weekday, slotNo, courseName, teacherName, classroom, startWeek, endWeek, weekParity] = l.split(/[,，]/).map((s) => s.trim())
        return { weekday: Number(weekday), slotNo: Number(slotNo), courseName, teacherName, teacherKey: teacherName, classroom, classId: this.classId, className: this.className, startWeek: Number(startWeek) || 1, endWeek: Number(endWeek) || 18, weekParity: weekParity || 'ALL' }
      })
      if (!items.length) { toast.error('没有可导入的行'); return }
      this.importing = true
      const res = await academicAffairsApi.importSchedule(this.batchId, items)
      this.importing = false
      if (res.code === 0) { this.importResult = res.data; toast.success('导入完成'); this.loadClass() }
      else { toast.error(res.message || '导入失败') }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-filter { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; }
.aa-filter__item { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-input { height: 32px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; box-sizing: border-box; }
.aa-input--sm { width: 120px; }
.aa-textarea { width: 100%; padding: 8px 12px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; font-size: 13px; box-sizing: border-box; font-family: var(--font-mono, monospace); }
.aa-assign-form { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.aa-assign-form label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-import-actions { margin-top: 12px; }
.aa-import-result { margin-top: 12px; font-size: 13px; color: var(--text-700, #4e5969); }
</style>
