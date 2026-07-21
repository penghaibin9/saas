<template>
  <ModulePageShell
    title="课表导出"
    subtitle="按班级/教师/教室导出当前已发布课表 xlsx（水印+审计留痕）"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="$router.push('/admin/academic-affairs/schedule')">课表批次</AppButton>
    </template>

    <div class="mp-stack">
      <AppSectionCard title="导出条件">
        <div class="aa-form">
          <label class="aa-form__item">
            导出范围
            <AppSelect v-model="scope" :options="scopeOptions" placeholder="" @change="identifier = ''" />
          </label>

          <label v-if="scope === 'CLASS'" class="aa-form__item aa-form__item--grow">
            班级
            <AppClassPicker v-model="identifier" :remote-search="searchClasses" placeholder="搜索班级名称" />
          </label>
          <label v-else-if="scope === 'TEACHER'" class="aa-form__item">
            教师工号
            <input v-model.trim="identifier" class="aa-input" placeholder="输入教师工号" />
          </label>
          <label v-else class="aa-form__item aa-form__item--grow">
            教室
            <AppRemoteSelect v-model="identifier" :remote-search="searchRooms" placeholder="搜索楼栋/教室编号" />
          </label>

          <label class="aa-form__item">
            学期（可选）
            <AppSelect v-model="termId" :options="termOptions" placeholder="" />
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
            导出用途（必填，≥5字，写审计）
            <input v-model.trim="purpose" class="aa-input" placeholder="如：教务处存档 / 班级课表打印分发" maxlength="200" />
          </label>

          <AppButton variant="primary" :disabled="!canExport" :loading="exporting" @click="doExport">
            导出 Excel
          </AppButton>
        </div>
        <p class="mp-note">导出文件首行含导出人/时间/用途水印；单次导出写入操作审计，请勿随意外发。</p>
      </AppSectionCard>
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
import { AppSectionCard, AppClassPicker, AppRemoteSelect, AppSelect } from '@/components/common'
import { academicAffairsApi, academicAffairsOrgApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

export default {
  name: 'AaScheduleExportView',
  components: { ModulePageShell, AppButton, AppSectionCard, AppClassPicker, AppRemoteSelect, AppSelect },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      scope: 'CLASS', identifier: '', termId: '', weekStart: null, weekEnd: null, purpose: '',
      terms: [], exporting: false
    }
  },
  computed: {
    canExport() { return !!this.identifier && this.purpose.trim().length >= 5 },
    scopeOptions() {
      return [
        { value: 'CLASS', label: '班级课表' },
        { value: 'TEACHER', label: '教师课表' },
        { value: 'ROOM', label: '教室课表' }
      ]
    },
    termOptions() {
      return [
        { value: '', label: '当前已发布批次' },
        ...this.terms.map((t) => ({ value: t.termId, label: `${t.yearCode} 第 ${t.termNo} 学期` }))
      ]
    }
  },
  created() { this.loadTerms() },
  methods: {
    async searchClasses(keyword) {
      const res = await academicAffairsOrgApi.listClasses({ keyword, pageSize: 20 })
      if (res.code !== 0) return []
      return (res.data.list || []).map((c) => ({ label: c.className, value: c.id }))
    },
    async searchRooms(keyword) {
      const res = await academicAffairsApi.getClassroomOptions(keyword)
      if (res.code !== 0) return []
      return (res.data || []).map((c) => ({ label: c.label || `${c.buildingName || ''}${c.roomCode || ''}`, value: c.classroomId }))
    },
    async loadTerms() {
      const res = await academicAffairsApi.getTerms({ page: 1, pageSize: 100 })
      if (res.code === 0) this.terms = res.data.list
    },
    async doExport() {
      if (!this.canExport) { toast.error('请选择导出对象并填写用途（≥5字）'); return }
      this.exporting = true
      const res = await academicAffairsApi.exportScheduleXlsx({
        scope: this.scope, identifier: this.identifier,
        termId: this.termId || undefined, weekStart: this.weekStart || undefined, weekEnd: this.weekEnd || undefined,
        purpose: this.purpose.trim()
      })
      this.exporting = false
      if (res.code === 0) {
        const url = URL.createObjectURL(res.data)
        const a = document.createElement('a')
        a.href = url
        a.download = `schedule_${this.scope.toLowerCase()}_export.xlsx`
        a.click()
        URL.revokeObjectURL(url)
        toast.success('导出成功，已写入审计')
      } else {
        toast.error(res.message || '导出失败')
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-form { display: flex; flex-wrap: wrap; gap: 14px; align-items: flex-end; }
.aa-form__item { display: inline-flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); min-width: 180px; }
.aa-form__item--grow { flex: 1; min-width: 240px; }
.aa-form__item--full { flex-basis: 100%; }
.aa-input, .aa-select { height: 34px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; box-sizing: border-box; }
.aa-input--sm { width: 100px; }
</style>
