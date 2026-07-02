<template>
  <AppBadge :type="badge">{{ label }}</AppBadge>
</template>

<script>
/** StudentStatusTag — 统一学生状态标签 */
import { AppBadge } from '@/components/ui'
import { formatStudentStatus } from '../helpers/student-format.helper'
import { getStudentStatusBadge } from '../helpers/student-status.helper'

export default {
  name: 'StudentStatusTag',
  components: { AppBadge },
  props: { status: { type: String, required: true } },
  computed: {
    label() {
      return formatStudentStatus(this.status)
    },
    badge() {
      return getStudentStatusBadge(this.status)
    }
  }
}
</script>
