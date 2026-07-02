<template>
  <AppTodoCard
    :title="task.title"
    :source-module="task.module || task.sourceModule"
    :student-name="task.studentName"
    :deadline="task.deadline"
    :priority="task.priority"
    :status="statusCode"
    :overdue="task.overdue"
    @handle="$emit('handle')"
  />
</template>

<script>
import { AppTodoCard } from '@/components/common'
import { taskStatusCode } from '@/modules/dashboard/adapter/dashboard.adapter.js'

export default {
  name: 'TaskCard',
  components: { AppTodoCard },
  props: {
    task: { type: Object, required: true }
  },
  emits: ['handle'],
  computed: {
    statusCode() {
      return taskStatusCode(this.task.status)
    }
  }
}
</script>
