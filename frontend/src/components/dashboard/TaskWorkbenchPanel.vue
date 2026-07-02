<template>
  <div class="task-workbench-panel">
    <div v-if="groups.urgent.length" class="dash-todo-group">
      <h4 class="dash-todo-group__title is-urgent">
        今日必须处理 <span>{{ groups.urgent.length }} 项</span>
      </h4>
      <div class="dash-card-list">
        <TaskCard
          v-for="t in groups.urgent"
          :key="t.taskId"
          :task="t"
          @handle="$emit('handle-task', t.taskId)"
        />
      </div>
    </div>
    <div v-if="groups.weekFocus.length" class="dash-todo-group">
      <h4 class="dash-todo-group__title is-week">
        本周重点跟进 <span>{{ groups.weekFocus.length }} 项</span>
      </h4>
      <div class="dash-card-list">
        <TaskCard
          v-for="t in groups.weekFocus"
          :key="t.taskId"
          :task="t"
          @handle="$emit('handle-task', t.taskId)"
        />
      </div>
    </div>
    <div v-if="groups.deferred.length" class="dash-todo-group">
      <h4 class="dash-todo-group__title">
        可延后处理 <span>{{ groups.deferred.length }} 项</span>
      </h4>
      <div class="dash-card-list">
        <TaskCard
          v-for="t in groups.deferred"
          :key="t.taskId"
          :task="t"
          @handle="$emit('handle-task', t.taskId)"
        />
      </div>
    </div>
  </div>
</template>

<script>
import TaskCard from './TaskCard.vue'

export default {
  name: 'TaskWorkbenchPanel',
  components: { TaskCard },
  props: {
    groups: {
      type: Object,
      default: () => ({ urgent: [], weekFocus: [], deferred: [] })
    }
  },
  emits: ['handle-task']
}
</script>
