<template>
  <section v-if="project" class="mp-card" aria-label="实施项目统一摘要">
    <div class="mp-card__body">
      <p>项目：{{ project.projectName }} · {{ project.projectNo || '项目编号未返回' }}</p>
      <p>项目版本：{{ Number.isInteger(project.version) ? project.version : '未返回' }} · 配置覆盖：{{ typeof project.progress === 'number' ? project.progress + '%' : '未返回' }}</p>
      <p class="mp-note">配置覆盖仅表示配置段已加载，不代表安装、检查或验收完成。</p>
      <p v-if="sealed">项目已封板，当前配置只读。后续修改请从已安装记录创建变更项目。</p>
      <p v-else>验收尚未封板，仍需按真实检查结果推进。</p>
      <p v-if="sealed" class="mp-note">封存时检查记录：{{ Array.isArray(project.acceptanceSummary?.checks) ? project.acceptanceSummary.checks.length + ' 项' : '历史摘要未保存明细' }}；当前检查记录：{{ Array.isArray(project.checks) ? project.checks.length + ' 项' : '未取得' }}。两者分别来自封存快照与当前检查表，不互相补写。</p>
    </div>
  </section>
</template>
<script>
export default {
  name: 'ImplementationProjectSummary',
  props: { project: { type: Object, default: null } },
  computed: { sealed() { return this.project?.status === 'ACCEPTED' || !!this.project?.acceptanceDigest } }
}
</script>
