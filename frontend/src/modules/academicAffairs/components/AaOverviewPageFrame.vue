<template>
  <div class="aa-module02">
    <nav class="m02-breadcrumb" aria-label="当前位置">教务中心 <span>/</span> 教务总览 <span>/</span> {{ title }}</nav>
    <ModulePageShell :title="title" :subtitle="subtitle">
      <template #actions><slot name="actions" /></template>
      <slot />
    </ModulePageShell>
  </div>
</template>

<script>
import { ModulePageShell } from '@/components/business'
export default {
  name: 'AaOverviewPageFrame', components: { ModulePageShell },
  provide: { conciseBusinessHeader: false },
  props: { title: { type: String, required: true }, subtitle: { type: String, default: '' } }
}
</script>

<style>
/* Only the four module-02 bodies. Public navigation and other modules keep their tokens. */
.aa-business-area .aa-module02 { --m02-line:var(--border-base); color:var(--text-primary); font-size:13px; }
.aa-module02 .m02-breadcrumb { display:flex; gap:10px; align-items:center; color:var(--text-secondary); font-size:12px; margin:3px 0 12px; }
.aa-business-area .aa-module02 .mps { gap:16px; }
.aa-business-area .aa-module02 .mps .mps__head { border:0; padding:0; margin:0; align-items:flex-start; }
.aa-business-area .aa-module02 .mps .mps__title { font-size:24px; font-weight:700; line-height:1.4; }
.aa-business-area .aa-module02 .mps .mps__subtitle { display:block; font-size:13px; line-height:1.6; margin:4px 0 0; color:var(--text-secondary); }
.aa-module02 .m02-card { border:1px solid var(--m02-line); border-radius:11px; background:var(--bg-card); overflow:hidden; min-width:0; }
.aa-module02 .m02-card > header { padding:14px 16px; border-bottom:1px solid var(--m02-line); display:flex; align-items:center; justify-content:space-between; gap:12px; }
.aa-module02 h2 { font-size:15px; font-weight:650; margin:0; }
.aa-module02 .m02-metrics { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; }
.aa-module02 .m02-metrics article { padding:14px; border:1px solid var(--m02-line); border-radius:11px; background:var(--bg-card); display:grid; gap:6px; }
.aa-module02 .m02-metrics strong { font-size:26px; line-height:1.2; font-variant-numeric:tabular-nums; }
.aa-module02 .m02-metrics span,.aa-module02 .m02-metrics small { font-size:12px; color:var(--text-secondary); line-height:1.6; }
.aa-module02 .m02-metrics small { font-size:11px; line-height:1.5; }
.aa-module02 .m02-metrics .is-alert { background:var(--aa-warning-bg); border-color:color-mix(in srgb,var(--warning-color,#b76700) 25%,var(--border-base)); }
.aa-module02 .m02-metrics .is-alert strong { color:var(--warning-color,#9a600f); }
.aa-module02 .m02-toolbar { display:flex; align-items:center; gap:8px; padding:12px 16px; flex-wrap:wrap; }
.aa-module02 .m02-toolbar input { height:36px; padding:0 10px; border:1px solid var(--m02-line); border-radius:6px; color:var(--text-primary); background:var(--bg-card); font:inherit; width:220px; max-width:100%; }
.aa-module02 .m02-toolbar small { color:var(--text-secondary); margin-left:auto; font-size:12px; }
.aa-module02 .m02-scroll { overflow:auto; }
.aa-module02 .m02-table { width:100%; border-collapse:collapse; font-size:12px; text-align:left; }
.aa-module02 .m02-table th { padding:12px 14px; background:var(--bg-soft,var(--pri-bg)); color:var(--text-secondary); font-weight:600; white-space:nowrap; }
.aa-module02 .m02-table td { padding:16px 14px; border-top:1px solid var(--m02-line); line-height:1.65; }
.aa-module02 .m02-table strong { color:var(--pri); font-size:13px; }
.aa-module02 .m02-secondary { display:block; font-size:11px; color:var(--text-secondary); margin-top:4px; }
.aa-module02 .m02-link { border:0; background:transparent; color:var(--pri); font:inherit; cursor:pointer; padding:4px 0; }
.aa-module02 .m02-tag { display:inline-block; padding:2px 7px; border-radius:4px; font-size:12px; background:var(--pri-bg); color:var(--pri); }
.aa-module02 .m02-tag.is-alert { color:var(--warning-color,#9a600f); background:var(--aa-warning-bg); }
.aa-module02 .m02-pager { padding:12px 16px; display:flex; align-items:center; justify-content:flex-end; gap:9px; color:var(--text-secondary); font-size:12px; border-top:1px solid var(--m02-line); }
.aa-module02 .m02-pager > span:first-child { margin-right:auto; }
.aa-module02 .m02-note { margin:0; padding:14px 16px; border-radius:9px; font-size:12px; line-height:1.7; background:var(--pri-bg); color:var(--pri); }
@container academic-body (max-width:600px) { .aa-module02 .m02-metrics { grid-template-columns:repeat(2,minmax(0,1fr)); }.aa-module02 .m02-toolbar small { margin-left:0; width:100%; } }
</style>
