<template><LifecycleSummary :student-id="studentId" mode="teacher" title="学生跨域里程碑" /></template>
<script setup>import LifecycleSummary from './LifecycleSummary.vue';defineProps({studentId:{type:[String,Number],required:true}})</script>
