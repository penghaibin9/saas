<template>
  <section aria-label="角色变更影响">
    <el-alert type="warning" :closable="false" :title="`任职成员 ${impact.memberCount} 人，责任关系 ${impact.scopeCount} 条；请假待审批 ${impact.pendingApprovalCount} 条、等待前级 ${impact.waitingApprovalCount} 条。`"/>
    <p>其中已需交接的请假节点 {{ impact.blockedApprovalCount }} 条；成员当前待办共 {{ impact.memberTodoCount }} 条。{{ impact.note }}</p>
    <el-table v-if="impact.items.length" :data="impact.items">
      <el-table-column prop="objectId" label="请假单编号"/>
      <el-table-column prop="assigneeName" label="原承办人"/>
      <el-table-column prop="stage" label="审批级次"/>
      <el-table-column prop="statusLabel" label="当前进度"/>
    </el-table>
  </section>
</template>
<script setup>
import { ElAlert, ElTable, ElTableColumn } from 'element-plus'
defineProps({impact:{type:Object,required:true}})
</script>
