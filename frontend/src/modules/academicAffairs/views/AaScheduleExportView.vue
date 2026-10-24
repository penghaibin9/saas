<template>
  <ModulePageShell
    class="aa-schedule-workspace"
    title="课表导出"
    subtitle="按班级、教师或教室导出带水印的已发布课表。"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="$router.push('/admin/academic-affairs/schedule')">课表批次</AppButton>
    </template>

    <div class="mp-stack">
      <AaScheduleStageRail :active-index="4" />
      <AaScheduleObjectBar
        :name="identifier ? selectedName || scopeLabel : '请选择导出范围'"
        :identity="`${termId ? '所选学期' : '默认学期'} · ${weekRangeLabel}`"
        source="仅导出已发布的课表。"
        :status="identifier ? '待填写导出条件' : '待选择'"
        :owner="ctx.currentRole.roleName || '教务排课岗'"
        next-owner="使用人按填写的用途使用"
      />

      <AppInlineAlert
        v-if="receipt"
        :type="receipt.type"
        :title="receipt.title"
        :description="receipt.description"
      />

      <div class="aa-export-layout">
        <AppSectionCard compact title="导出条件">
          <div class="aa-form">
          <label class="aa-form__item">
            导出范围
            <AppSelect v-model="scope" :options="scopeOptions" placeholder="" @change="identifier = ''; selectedName = ''" />
          </label>

          <label v-if="scope === 'CLASS'" class="aa-form__item aa-form__item--grow">
            班级
            <AppClassPicker v-model="identifier" placeholder="搜索班级名称" @change="onSelectionChange" />
          </label>
          <label v-else-if="scope === 'TEACHER'" class="aa-form__item">
            教师
            <AppTeacherPicker v-model="identifier" :query="teacherKeyQuery" placeholder="搜索教师姓名/工号" @change="onSelectionChange" />
          </label>
          <label v-else class="aa-form__item aa-form__item--grow">
            教室
            <AppClassroomPicker v-model="identifier" placeholder="搜索楼栋/教室编号" @change="onSelectionChange" />
          </label>

          <label class="aa-form__item">
            学期（可选）
            <AppTermEntityPicker v-model="termId" placeholder="默认学期" />
          </label>
          <label class="aa-form__item">
            起始周（可选）
            <input v-model.number="weekStart" type="number" min="1" max="30" class="aa-input aa-input--sm" />
          </label>
          <label class="aa-form__item">
            结束周（可选）
            <input v-model.number="weekEnd" type="number" min="1" max="30" class="aa-input aa-input--sm" />
          </label>

          <label class="aa-form__item aa-form__item--full">
            导出用途（必填，至少5字）
            <input v-model.trim="purpose" class="aa-input" placeholder="如：教务处存档 / 班级课表打印分发" maxlength="200" />
          </label>

          <AppButton variant="primary" :disabled="!canExport" :loading="exporting" @click="doExport">
            导出表格
          </AppButton>
          </div>
        </AppSectionCard>

        <aside class="aa-export-guide" aria-label="课表文件使用说明">
          <h3>文件使用说明</h3>
          <dl>
            <div><dt>内容范围</dt><dd>包含所选范围的全部课程，不限于列表当前页。</dd></div>
            <div><dt>文件水印</dt><dd>首行注明导出人、时间和用途。</dd></div>
            <div><dt>使用要求</dt><dd>导出操作会留存记录，请按填写的用途使用，勿随意外发。</dd></div>
          </dl>
        </aside>
      </div>
    </div>
  </ModulePageShell>
</template>

<script>
/**
 * 课表导出（/admin/academic-affairs/schedule/export）：13B 课表管理 Tier1 R2。
 * POST /academic-affairs/schedule/export（scope=CLASS/TEACHER/ROOM + identifier + 可选周次范围 + 用途），
 * 后端 xlsx 二进制流下载（水印+AffairsAuditTrail 审计），对齐 quality/reports/export 同款 requestBlob 约定。
 */
import { ModulePageShell } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSectionCard, AppClassPicker, AppTeacherPicker, AppClassroomPicker, AppTermEntityPicker, AppSelect, AppInlineAlert } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import AaScheduleObjectBar from '@/modules/academicAffairs/components/AaScheduleObjectBar.vue'
import AaScheduleStageRail from '@/modules/academicAffairs/components/AaScheduleStageRail.vue'

export default {
  name: 'AaScheduleExportView',
  components: { ModulePageShell, AppButton, AppSectionCard, AppClassPicker, AppTeacherPicker, AppClassroomPicker, AppTermEntityPicker, AppSelect, AppInlineAlert, AaScheduleObjectBar, AaScheduleStageRail },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      scope: 'CLASS', identifier: '', selectedName: '', teacherKeyQuery: { valueField: 'loginName' }, termId: '', weekStart: null, weekEnd: null, purpose: '',
      exporting: false, receipt: null
    }
  },
  computed: {
    canExport() {
      const rangeValid = !this.weekStart || !this.weekEnd || Number(this.weekStart) <= Number(this.weekEnd)
      return !!this.identifier && this.purpose.trim().length >= 5 && rangeValid
    },
    scopeLabel() { return this.scopeOptions.find((item) => item.value === this.scope)?.label || '课表' },
    weekRangeLabel() {
      if (this.weekStart && this.weekEnd) return `第 ${this.weekStart}-${this.weekEnd} 周`
      if (this.weekStart) return `第 ${this.weekStart} 周起`
      if (this.weekEnd) return `截至第 ${this.weekEnd} 周`
      return '全部教学周'
    },
    scopeOptions() {
      return [
        { value: 'CLASS', label: '班级课表' },
        { value: 'TEACHER', label: '教师课表' },
        { value: 'ROOM', label: '教室课表' }
      ]
    }
  },
  methods: {
    onSelectionChange(_value, items) { this.selectedName = items?.[0]?.label || '' },
    async doExport() {
      if (!this.canExport) {
        const message = this.weekStart && this.weekEnd && Number(this.weekStart) > Number(this.weekEnd)
          ? '起始周不能晚于结束周'
          : '请选择班级、教师或教室，并填写至少5字的用途'
        this.receipt = { type: 'warning', title: '请完善导出条件', description: message }
        return
      }
      this.exporting = true
      this.receipt = null
      try {
        const res = await academicAffairsApi.exportScheduleXlsx({
          scope: this.scope, identifier: this.identifier,
          termId: this.termId || undefined, weekStart: this.weekStart || undefined, weekEnd: this.weekEnd || undefined,
          purpose: this.purpose.trim()
        })
        if (res.code === 0) {
          const url = URL.createObjectURL(res.data)
          const a = document.createElement('a')
          a.href = url
          a.download = `schedule_${this.scope.toLowerCase()}_export.xlsx`
          a.click()
          URL.revokeObjectURL(url)
          this.receipt = {
            type: 'success',
            title: '课表文件已生成',
            description: `${this.selectedName || this.scopeLabel} · ${this.weekRangeLabel}`
          }
        } else {
          const message = res.message || '未能获取课表文件，请稍后重试'
          this.receipt = { type: 'danger', title: '未能获取课表文件', description: message }
        }
      } catch (error) {
        const message = error?.message || '网络连接中断，未收到文件，请稍后重试'
        this.receipt = { type: 'danger', title: '未能获取课表文件', description: message }
      } finally { this.exporting = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
@import '../styles/schedule-workspace.css';
.aa-form { display: flex; flex-wrap: wrap; gap: 14px; align-items: flex-end; }
.aa-form__item { display: inline-flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); min-width: 180px; }
.aa-form__item--grow { flex: 1; min-width: 240px; }
.aa-form__item--full { flex-basis: 100%; }
.aa-input, .aa-select { height: 34px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; box-sizing: border-box; }
.aa-input--sm { width: 100px; }
.aa-export-layout { display: grid; grid-template-columns: minmax(0, 1fr) 280px; gap: 16px; align-items: start; }
.aa-export-guide { padding: 18px; border: 1px solid var(--border-200, #dbe3ed); border-radius: 10px; background: var(--bg-white, #fff); }
.aa-export-guide h3 { margin: 0 0 14px; color: var(--text-900, #193252); font-size: 16px; }
.aa-export-guide dl { display: grid; gap: 16px; margin: 0; }
.aa-export-guide dt { color: var(--text-700, #435875); font-size: 13px; font-weight: 600; }
.aa-export-guide dd { margin: 5px 0 0; color: var(--text-500, #68788c); font-size: 12px; line-height: 1.65; }
@media (max-width: 980px) { .aa-export-layout { grid-template-columns: 1fr; } }
</style>
