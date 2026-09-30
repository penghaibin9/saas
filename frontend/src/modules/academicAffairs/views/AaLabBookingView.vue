<template><ResourceBookingWorkspace kind="LAB" :ctx="ctx" /></template>
<script>
import ResourceBookingWorkspace from '../components/parallel-a/ResourceBookingWorkspace.vue'
export default { name: 'AaLabBookingView', components: { ResourceBookingWorkspace }, props: { ctx: { type: Object, required: true } } }
</script>
