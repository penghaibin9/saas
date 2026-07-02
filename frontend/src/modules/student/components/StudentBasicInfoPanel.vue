<template>
  <AppCard class="stu-panel">
    <AppSectionHeader title="基础信息" compact />
    <dl class="stu-kv">
      <dt>姓名</dt><dd>{{ student.name }}</dd>
      <dt>学号</dt><dd>{{ student.studentNo }}</dd>
      <dt>性别</dt><dd>{{ genderText }}</dd>
      <dt>出生日期</dt><dd>{{ student.birthday || '—' }}</dd>
      <dt>民族</dt><dd>{{ student.nationality || '—' }}</dd>
      <dt>政治面貌</dt><dd>{{ student.politicalStatus || '—' }}</dd>
      <dt>身份证号</dt><dd>{{ masked.idCard || '未登记' }}</dd>
      <dt>家庭住址</dt><dd>{{ masked.homeAddress || '未登记' }}</dd>
      <dt>在校住址</dt><dd>{{ student.currentAddress || '—' }}</dd>
      <dt>生源渠道</dt><dd>{{ student.sourceChannel || '—' }}</dd>
    </dl>
  </AppCard>
</template>

<script>
/** StudentBasicInfoPanel — 基础信息（身份证/住址经 security 脱敏展示） */
import { AppCard, AppSectionHeader } from '@/components/ui'
import { formatGender } from '../helpers/student-format.helper'
import { maskStudentForDisplay } from '../helpers/student-security.helper'

export default {
  name: 'StudentBasicInfoPanel',
  components: { AppCard, AppSectionHeader },
  props: { student: { type: Object, required: true } },
  computed: {
    genderText() {
      return formatGender(this.student.gender)
    },
    masked() {
      return maskStudentForDisplay(this.student)
    }
  }
}
</script>

<style scoped>
@import './student-panel.css';
</style>
