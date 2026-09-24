import {ENDPOINTS,buildViewModel,domain,emptyView,identityKey,record,safeText,routeTarget,DESTINATIONS} from './aa-wall-data.mjs';
export {identityKey};
const authError=e=>e?.staleSession||['SESSION_CHANGED','NOT_AUTHENTICATED'].includes(e?.bizCode)||[401,401001].includes(Number(e?.code));
const denied=e=>[403,403001,403002].includes(Number(e?.code))||['NO_PERMISSION','NO_DATA_SCOPE'].includes(e?.bizCode);
/** Inject the repository's request and permission matcher; never send/stash tokens here. */
export function createConnector({request,can,identity=()=>'',onInvalidate=()=>{}}) {
  let epoch=0,disposed=false,latestContext=null,knownIdentity='';
  const invalidate=()=>{epoch++;latestContext=null;onInvalidate();};
  async function load() {
    if(disposed)return null;
    const e=++epoch; let initial=identity();
    latestContext=null;knownIdentity='';
    let ctx;
    try{ctx=await request(ENDPOINTS.context.path);}catch(err){
      if(e!==epoch||disposed)return null;
      return emptyView(authError(err)||denied(err)?'RESTRICTED':'ERROR','身份上下文暂不可用，请重新验证登录');
    }
    if(disposed||e!==epoch||initial&&identity()!==initial)return null;
    initial=identity();
    if(!record(ctx)||ctx.rbacOk===false||!Array.isArray(ctx.permissionPatterns))return emptyView('RESTRICTED','身份权限未确认');
    if(!can(ctx,ENDPOINTS.reminders.permission))return emptyView('RESTRICTED','当前角色未开通教务总览');
    latestContext=ctx;knownIdentity=initial;
    const check=()=>!disposed&&e===epoch&&identity()===initial;
    async function read(key,params) {
      if(!check())return domain('RESTRICTED');
      const spec=ENDPOINTS[key];
      if(spec.permission&&!can(ctx,spec.permission))return domain('RESTRICTED',null,'该统计权限未开通');
      try{
        const data=await request(spec.path,{method:'GET',...(params?{params}:{})});
        if(!check())return domain('RESTRICTED');
        return domain('OK',data);
      }catch(err){
        if(authError(err)){invalidate();return domain('RESTRICTED');}
        return domain(denied(err)?'RESTRICTED':'ERROR',null,denied(err)?'当前角色/范围不可见':'统计接口暂不可用');
      }
    }
    const [term,brand]=await Promise.all([read('term'),read('brand')]);
    if(!check())return null;
    // No free-form term selector: reminders does not accept termId.
    if(term.state!=='OK'||!record(term.data)||!String(term.data.termId||'').match(/^\d+$/)){
      const state=term.state==='RESTRICTED'?'RESTRICTED':term.state==='OK'?'MISSING':'ERROR';
      return buildViewModel({term,reminders:domain(state),readiness:domain(state),quality:domain(state),meta:{note:'当前运行学期尚未确认；不查询跨学期混合总览'}});
    }
    const [reminders,readiness]=await Promise.all([read('reminders'),read('readiness',{termId:String(term.data.termId)})]);
    if(!check())return null;
    // No termId on quality: some audited underlying dimensions do not support it.
    // School aggregate only; no fallback to tenant-wide data for a narrower role.
    const quality=reminders.state==='OK'&&reminders.data?.scopeRestricted===false?await read('quality'):domain('RESTRICTED');
    if(!check())return null;
    return buildViewModel({term,reminders,readiness,quality,meta:{
      schoolName:safeText(brand.data?.schoolName,100),
      scope:safeText(ctx.dataScope?.scopeName||ctx.dataScope?.scopeLabel||ctx.dataScope?.scopeType,100),
      isSample:false
    }});
  }
  async function authorize(target) {
    if(disposed||!latestContext||identity()!==knownIdentity)return null;
    const before=identity(),e=epoch;
    try{
      const c=await request(ENDPOINTS.context.path);
      if(disposed||e!==epoch||identity()!==before||!record(c)||c.rbacOk===false||!Array.isArray(c.permissionPatterns)||!can(c,ENDPOINTS.reminders.permission))return null;
      const value=typeof target==='string'?(DESTINATIONS[target]||target):null;
      const route=value?routeTarget(value):record(target)&&typeof target.path==='string'?routeTarget(target.path):record(target)&&typeof target.name==='string'?routeTarget(target.name):null;
      return route?{route,context:c}:null;
    }catch{return null;}
  }
  return {load,authorize,invalidate,dispose(){disposed=true;invalidate();}};
}
