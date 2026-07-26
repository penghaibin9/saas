<template>
  <div class="gd-student-list-guard" :class="{ 'is-readonly': !canManageStudents }">
    <AppInlineAlert
      v-if="!canManageStudents"
      type="info"
      title="当前为只读名单视图"
      description="你可以查看本数据范围内的毕设学生、进度和材料状态；建档、导师分配、选题、资格认定、分组、答辩组分配与归档仅对具有学生管理权限的角色开放。"
      class="gd-student-list-guard__notice"
    />
    <GraduationStudentListView :ctx="safeCtx" />
  </div>
</template>

<script>
import { AppInlineAlert } from '@/components/common'
import { matchPermission } from '@/config/navPlan'
import GraduationStudentListView from './GraduationStudentListView.vue'

export default {
  name: 'GraduationStudentListGuardView',
  components: { AppInlineAlert, GraduationStudentListView },
  props: { ctx: { type: Object, required: true } },
  computed: {
    canManageStudents() {
      const patterns = this.ctx?.permissionPatterns
      return Array.isArray(patterns) && matchPermission(patterns, 'graduationDesign.student.manage')
    },
    safeCtx() {
      return {
        ...this.ctx,
        writeEnabled: this.ctx?.writeEnabled !== false && this.canManageStudents
      }
    }
  }
}
</script>

<style scoped>
.gd-student-list-guard__notice { margin-bottom: var(--space-3); }
/* 原列表历史上只按业务状态展示行内写按钮，未逐项消费权限。
 * 包装层在只读角色下保留每行第一个“详情”，隐藏后续写入口；后端仍保留最终权限边界。 */
.gd-student-list-guard.is-readonly :deep(.mp-link + .mp-link) { display: none !important; }
/* 最终毕业资格由教务中心统一重算；隐藏旧的“毕业资格联动”页签，深链由父布局归一到名单。 */
.gd-student-list-guard :deep(.mp-tabs .mp-tab:nth-child(8)) { display: none !important; }
</style>
