<template>
  <AppCard class="stu-panel">
    <AppSectionHeader title="学籍信息" compact>
      <template #extra>
        <AppBadge :type="academicBadge">{{ academicText }}</AppBadge>
      </template>
    </AppSectionHeader>
    <dl class="stu-kv">
      <dt>学院</dt><dd>{{ student.collegeName }}</dd>
      <dt>专业</dt><dd>{{ student.majorName }}</dd>
      <dt>班级</dt><dd>{{ student.className }}</dd>
      <dt>年级</dt><dd>{{ student.grade }} 级</dd>
      <dt>学历层次</dt><dd>{{ eduText }}</dd>
      <dt>学生类型</dt><dd>{{ typeText }}</dd>
      <dt>入学日期</dt><dd>{{ student.enrollmentDate }}</dd>
      <dt>预计毕业</dt><dd>{{ student.expectedGraduationDate }}</dd>
      <dt>学制</dt><dd>{{ student.studyDuration }} 年</dd>
      <dt>本学期注册</dt><dd>{{ regText }}</dd>
    </dl>
  </AppCard>
</template>

<script>
/** StudentAcademicPanel — 学籍/注册/归属 */
import { AppCard, AppBadge, AppSectionHeader } from '@/components/ui'
import {
  formatAcademicStatus,
  formatEducationLevel,
  formatStudentType,
  formatRegistrationStatus
} from '../helpers/student-format.helper'
import { getAcademicBadge } from '../helpers/student-status.helper'

export default {
  name: 'StudentAcademicPanel',
  components: { AppCard, AppBadge, AppSectionHeader },
  props: { student: { type: Object, required: true } },
  computed: {
    academicText() {
      return formatAcademicStatus(this.student.academicStatus)
    },
    academicBadge() {
      return getAcademicBadge(this.student.academicStatus)
    },
    eduText() {
      return formatEducationLevel(this.student.educationLevel)
    },
    typeText() {
      return formatStudentType(this.student.studentType)
    },
    regText() {
      return formatRegistrationStatus(this.student.registrationStatus)
    }
  }
}
</script>

<style scoped>
@import './student-panel.css';
</style>
