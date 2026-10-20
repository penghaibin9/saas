/** Lifecycle and routing helpers. No Vue dependency; testable with injected timers. */
import {emptyView} from './aa-wall-data.mjs';
export function routeAllowed(resolved,context,can) {
  if(!resolved||!Array.isArray(resolved.matched)||!resolved.matched.length)return false;
  return resolved.matched.every(row=>{
    const m=row.meta||{};
    if(m.permissionKey&&!can(context,m.permissionKey))return false;
    if(Array.isArray(m.permissionAny)&&m.permissionAny.length&&!m.permissionAny.some(k=>can(context,k)))return false;
    if(Array.isArray(m.permissionAll)&&!m.permissionAll.every(k=>can(context,k)))return false;
    return true;
  });
}
export function refreshInterval(value) {
  const v=Number(value);
  return (Number.isFinite(v)?Math.max(30,Math.min(600,v)):60)*1000;
}
export function createWallRuntime({connector,view,identity,hidden=()=>false,refreshSeconds=60,setTimer=setInterval,clearTimer=clearInterval}) {
  let alive=false,busy=false,queued=false,generation=0,known=identity(),refreshTimer,identityTimer;
  async function refresh() {
    if(!alive||hidden())return;
    if(busy){queued=true;return;}
    busy=true;const run=generation;
    try {
      const data=await connector.load();
      if(alive&&run===generation&&data){view.update(data);known=identity();}
    } catch {
      if(alive&&run===generation)view.update(emptyView('ERROR','统计读取失败，请重试'));
    } finally {
      busy=false;
      if(queued&&alive){queued=false;void refresh();}
    }
  }
  function invalidate(state='LOADING') {
    if(!alive)return;
    generation++;known=identity();connector.invalidate();view.reset(state);void refresh();
  }
  function checkIdentity(){if(alive&&known!==identity())invalidate('RESTRICTED');}
  function visibility(){checkIdentity();if(!hidden())void refresh();}
  function suspend(){if(alive){generation++;connector.invalidate();view.reset('RESTRICTED');}}
  return {
    start(){if(alive)return;alive=true;known=identity();refreshTimer=setTimer(refresh,refreshInterval(refreshSeconds));identityTimer=setTimer(checkIdentity,400);void refresh();},
    refresh,invalidate,visibility,suspend,checkIdentity,
    dispose(){alive=false;queued=false;generation++;clearTimer(refreshTimer);clearTimer(identityTimer);connector.dispose();view.destroy();}
  };
}
