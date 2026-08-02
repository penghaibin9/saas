<template>
  <ModulePageShell title="商业授权与消费对账" subtitle="合同、套餐、授权、学校启用、双层配额与真实消费统一核对" role-name="平台商业/负责人" data-scope-name="全平台只读对账">
    <div class="commercial-page">
      <section class="hero"><div><h3>{{ conclusion }}</h3><p>实际消费以 FileObject 与仍处于 HELD 的配额预留为准；降配不会静默删除学校文件。</p></div><button @click="load">重新对账</button></section>
      <section class="panel"><table><thead><tr><th>学校</th><th>套餐</th><th>商业上限</th><th>学校配额</th><th>实际消费</th><th>结论</th></tr></thead>
        <tbody><tr v-for="item in items" :key="item.tenantId"><td>{{ item.tenantName }}</td><td>{{ item.packageCode }}</td><td>{{ gib(item.commercialStorageLimitBytes) }}</td><td>{{ gib(item.schoolGovernanceQuotaBytes) }}</td><td>{{ gib(item.actualConsumptionBytes) }}</td><td><strong :class="item.healthy ? 'ok' : 'bad'">{{ item.healthy ? '一致' : (item.violations || []).map(v => v.code).join(' / ') }}</strong></td></tr><tr v-if="!items.length"><td colspan="6">暂无学校对账数据</td></tr></tbody></table></section>
      <div v-if="error" class="error">{{ error }}</div>
    </div>
  </ModulePageShell>
</template>
<script>
import { ModulePageShell } from '@/components/business'
import { platformControlApi } from '@/modules/platform/api/platformControl.api'
const GIB = 1024 ** 3
export default { name:'PlatformCommercialControlView', components:{ModulePageShell}, data:()=>({items:[],error:''}), computed:{ conclusion(){ const bad=this.items.filter(x=>!x.healthy).length; return bad ? `发现 ${bad} 所学校存在授权或配额不一致` : '商业授权、学校配额与实际消费当前一致' } }, created(){this.load()}, methods:{gib(v){return v==null?'未配置':`${(Number(v)/GIB).toFixed(2)} GiB`}, async load(){const res=await platformControlApi.listReconciliations(); if(res.code!==0){this.error=res.message;return} this.items=res.data.items||[]}} }
</script>
<style scoped>
.commercial-page{display:grid;gap:16px}.hero,.panel{background:#fff;border:1px solid #e5e6eb;border-radius:12px;padding:18px}.hero{display:flex;justify-content:space-between;gap:16px}.hero h3{margin:0 0 6px}.hero p{margin:0;color:#646a73}table{width:100%;border-collapse:collapse}th,td{padding:10px;border-bottom:1px solid #e5e6eb;text-align:left}.ok{color:#067647}.bad,.error{color:#b42318}.error{padding:12px;background:#fff2f0}
</style>
