<template><ResourceBookingWorkspace kind="CLASSROOM" :ctx="ctx" /></template>
<script>
import ResourceBookingWorkspace from '../components/parallel-a/ResourceBookingWorkspace.vue'
export default { name: 'AaClassroomBookingView', components: { ResourceBookingWorkspace }, props: { ctx: { type: Object, required: true } } }
</script>
