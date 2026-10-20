<template><LifecycleSummary :student-id="studentId" mode="student" title="我的成长里程碑" /></template>
<script setup>import LifecycleSummary from './LifecycleSummary.vue';defineProps({studentId:{type:[String,Number],required:true}})</script>
