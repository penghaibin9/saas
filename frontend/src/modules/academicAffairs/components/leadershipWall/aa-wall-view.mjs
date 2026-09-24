import {emptyView,safeAsset,record} from './aa-wall-data.mjs';
import {icon} from './aa-wall-icons.mjs';
import {metricDescription,stateLabel,previewMessage,wallStatus,sourceTimeLabel,SOURCE_LABELS} from './aa-wall-presentation.mjs';
export const escapeHtml = v => String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const E=escapeHtml;
const fmt=(x,d=0)=>typeof x==='number'&&Number.isFinite(x)?x.toLocaleString('en-US',{maximumFractionDigits:d,minimumFractionDigits:d}):'—';
const COLORS=['#23d9e8','#efc27a','#3a99f3','#87a9cd','#7f8dde','#e38170','#418698'];
const STATUS_LABEL={IN_PROGRESS:'进行中',NOT_STARTED:'未开始',ENDED:'已结束',UNKNOWN:'未确定'};
const noData=(heading='暂未形成统计',note='没有可信数字时保留空态，不回填样例。')=>`<div class="empty-panel"><b>${E(heading)}</b>${E(note)}</div>`;
export function donut(segments,label,value,small=false){
 const valid=Array.isArray(segments)&&segments.length>0&&segments.every(s=>typeof s.value==='number'&&s.value>=0&&Number.isFinite(s.value));
 const total=valid?segments.reduce((a,s)=>a+s.value,0):0; const circumference=2*Math.PI*56;let offset=0;
 const rings=total>0?segments.filter(s=>s.value>0).map((s,i)=>{const length=s.value/total*circumference;const dash=Math.max(0,length-1.8);const out=`<circle cx="70" cy="70" r="56" fill="none" stroke="${s.color||COLORS[i%COLORS.length]}" stroke-width="13" stroke-dasharray="${dash.toFixed(3)} ${(circumference-dash).toFixed(3)}" stroke-dashoffset="${(-offset).toFixed(3)}"/>`;offset+=length;return out}).join(''):'';
 return `<div class="donut ${small?'sm':''}"><svg viewBox="0 0 140 140" aria-hidden="true"><circle cx="70" cy="70" r="56" fill="none" stroke="#113851" stroke-width="13"/><circle cx="70" cy="70" r="43" fill="none" stroke="#12344f" stroke-width="1"/>${rings}</svg><div class="donut-center"><strong>${E(value)}</strong><span>${E(label)}</span></div></div>`;
}
function legend(rows,unit=''){return `<div class="legend">${rows.map((x,i)=>`<div class="legend-row"><i style="--dot:${x.color||COLORS[i%COLORS.length]}"></i><span class="name">${E(x.label)}</span><b>${fmt(x.value)}<small>${E(unit)}</small></b></div>`).join('')}</div>`;}
function track(value,denominator=100){const good=typeof value==='number'&&typeof denominator==='number'&&denominator>0&&value>=0&&value<=denominator;return `<div class="progress-track"><div class="progress-fill" style="width:${good?(value/denominator*100).toFixed(3):0}%"></div></div>`;}
function trendChart(series){
 if(!series.length)return noData('趋势暂不可用','不把接口失败填为连续零值。');
 const s=['gradeSubmit','scheduleChange','warning'].map(k=>series.find(x=>x.key===k)).filter(Boolean);
 if(!s.length||!s[0].points.length)return noData('暂无业务趋势');
 const width=650,height=139,l=31,r=12,t=10,b=25;const keys=s[0].points.map(x=>x.date);const n=keys.length;
 if(!s.every(x=>x.points.length===n&&x.points.every((p,i)=>p.date===keys[i])))return noData('趋势日期不一致','未进行插值补齐');
 const max=Math.max(1,...s.flatMap(x=>x.points.map(p=>p.value)));const scale=Math.ceil(max/10)*10;const w=width-l-r,h=height-t-b;
 let svg=`<svg class="trend-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="真实近14天教务业务发生量，不是预测或到课率">`;
 for(let i=0;i<=3;i++){const y=t+h*i/3;svg+=`<line class="grid" x1="${l}" x2="${width-r}" y1="${y}" y2="${y}"/><text x="${l-6}" y="${y+4}" text-anchor="end">${Math.round(scale*(1-i/3))}</text>`;}
 const xs=i=>l+(i+.5)*w/n;const ys=v=>t+h-v/scale*h;
 s.slice(0,2).forEach((ss,j)=>ss.points.forEach((p,i)=>{const bw=w/n*.25;svg+=`<rect x="${xs(i)+(j-.9)*bw}" y="${ys(p.value)}" width="${bw-1}" height="${t+h-ys(p.value)}" rx="1" fill="${j===0?'#328ff3':'#42d5e8'}" opacity=".9"/>`;}));
 if(s[2]){svg+=`<polyline points="${s[2].points.map((p,i)=>`${xs(i)},${ys(p.value)}`).join(' ')}" fill="none" stroke="#efc27a" stroke-width="2"/>`;s[2].points.forEach((p,i)=>{svg+=`<circle cx="${xs(i)}" cy="${ys(p.value)}" r="2.2" fill="#ffd486"/>`;});}
 keys.forEach((dt,i)=>{if(i%2===0||i===n-1)svg+=`<text x="${xs(i)}" y="${height-5}" text-anchor="middle">${E(dt.slice(5))}</text>`;});return svg+'</svg>';
}
export function validateBrandPatch(patch){
 if(!record(patch))throw new Error('配置必须为对象');
 const allowed=['schemaVersion','title','schoolName','subtitle','mottoLeft','mottoRight','mapMotto','footerLeft','footerRight','logoVisible','primary','blue','gold','danger','panelTitles','metricLabels','showStaffNames','timezone','refreshSeconds','imageFit'];
 for(const k of Object.keys(patch))if(!allowed.includes(k))throw new Error(`不允许的配置字段: ${k}`);
 for(const k of ['primary','blue','gold','danger'])if(k in patch&&!/^#[0-9a-f]{6}$/i.test(patch[k]))throw new Error('主题颜色须为六位HEX');
 for(const k of ['title','schoolName','subtitle','mottoLeft','mottoRight','footerLeft','footerRight'])if(k in patch&&(typeof patch[k]!=='string'||patch[k].length>140))throw new Error('标题/文案长度须小于140字');
 for(const k of ['panelTitles','metricLabels'])if(k in patch&&(!record(patch[k])||Object.values(patch[k]).some(v=>typeof v!=='string'||v.length>80)))throw new Error('标签配置无效');
 for(const k of ['logoVisible','showStaffNames'])if(k in patch&&typeof patch[k]!=='boolean')throw new Error('开关须为布尔值');
 if('mapMotto' in patch&&(!Array.isArray(patch.mapMotto)||patch.mapMotto.length>3||patch.mapMotto.some(x=>typeof x!=='string'||x.length>80)))throw new Error('地图题词最多3行');
 if('refreshSeconds' in patch&&(!Number.isInteger(patch.refreshSeconds)||patch.refreshSeconds<30||patch.refreshSeconds>600))throw new Error('刷新间隔须为30–600秒');
 if('imageFit' in patch&&!['contain','cover'].includes(patch.imageFit))throw new Error('imageFit无效');
 if('timezone' in patch){try{new Intl.DateTimeFormat('zh-CN',{timeZone:patch.timezone}).format()}catch{throw new Error('时区无效')}}
 if('schemaVersion' in patch&&patch.schemaVersion!==1)throw new Error('不支持的配置版本');
 return patch;
}

/** All data, text, labels and charts stay in DOM/SVG. Only the scenery is raster. */
export function mountAcademicWall(host,{css,brand,campus,assets={},onNavigate=()=>{},onRefresh=()=>{},onExit=()=>{},sampleSpatial=null,allowEditor=false,previewStates=null,onPreviewState=()=>{},assetFiles={}}={}){
 if(!host)throw new Error('Missing host');
 let b=structuredClone(validateBrandPatch(brand||{})),layout=structuredClone(campus||{markers:[]}),urls={...assets};
 let queuedView=null,vm=emptyView(),mapMode='3d',selected=layout.markers?.[0]?.id||'',dead=false,toastTimer,focusBefore=null,dialogContent='';
 const root=host.shadowRoot||host.attachShadow({mode:'open'});
 root.innerHTML=`<style>${css||''}</style><div class="viewport"><div class="board"></div></div><div class="modal-slot"></div><div class="toast-slot"></div>`;
 const board=root.querySelector('.board');const modal=root.querySelector('.modal-slot');
 const title=k=>b.panelTitles?.[k]||k;
 const m=id=>vm.metrics[id]||{value:null,state:'MISSING',label:id,unit:''};
 const v=id=>m(id).value;
 const ml=id=>b.metricLabels?.[id]||m(id).label;
 const label=id=>fmt(v(id),m(id).unit==='%'?1:0);
 const head=(key,route,extra='')=>`<header class="panel-head"><h2>${E(title(key))}</h2>${extra}${route?`<button class="more" data-action="nav" data-target="${E(route)}">更多 ›</button>`:''}</header>`;
 function metric(id,cls=''){return `<span class="metric-open ${cls}" data-action="metric" data-id="${id}" role="button" tabindex="0" aria-label="${E(ml(id))}，${E(label(id))}，查看口径">${label(id)}</span>`;}
 const previewEmpty=kind=>noData(...previewMessage(kind,vm.metadata,vm.metrics));
 const sn=txt=>`<div class="micro-note">${E(txt)}</div>`;
 function render(){
  if(dead)return;
  const kpis=[['todayTotal','book','今日有效排课 · 课次口径'],['teacherCount','person','今日排课 · 按教师去重'],['classCount','users','今日排课 · 按班级去重'],['occupiedRooms','room','今日占用 · 非实时空间'],['gradeSubmittedRate','check','累计任务 · 点击查看口径'],['pendingChanges','swap','待审批申请 · 累计口径'],['warningCount','alert','待处置记录 · 条数口径']];
  const teaching=['inProgress','notStarted','ended','unknownSlots'].map(k=>vm.teachingSegments.find(x=>x.key===k)).filter(Boolean);
  const prog=v('inProgress')!==null&&v('todayTotal')>0?(v('inProgress')/v('todayTotal')*100):null;
  const submitted=v('gradeSubmitted'),gt=v('gradeTotal');
  const gradeRing=typeof submitted==='number'&&typeof gt==='number'&&submitted<=gt?[{value:submitted,color:'#25dce4'},{value:gt-submitted,color:'#388ced'}]:[];
  const gradeBreak=vm.gradeSegments.length?[
     {label:'已提交/审核/发布',value:v('gradeSubmitted'),color:'#27d5e8'},
     {label:'录入中',value:v('gradeInputting'),color:'#368ef3'},
     {label:'未开始',value:v('gradeNotStarted'),color:'#eac078'},
     {label:'已退回',value:v('gradeReturned'),color:'#ef8174'},
     {label:'已归档',value:v('gradeArchived'),color:'#7f8dde'},
     ...vm.gradeSegments.filter(x=>!['SUBMITTED','ACADEMIC_REVIEW','PUBLISHED','INPUTTING','NOT_STARTED','RETURNED','ARCHIVED'].includes(x.key))
   ]:[];
  const roTotal=v('roomTotal'),oc=v('occupiedRooms');
  const roomsRing=typeof roTotal==='number'&&typeof oc==='number'&&roTotal>=oc?[{value:oc,color:'#29d8ed'},{value:roTotal-oc,color:'#3b8ddd'}]:[];
  const activeSlots=new Set(vm.courses.filter(c=>c.runStatus==='IN_PROGRESS').map(c=>c.slotNo).filter(Boolean));
  const slotNos=vm.courses.length?Array.from({length:Math.max(12,Math.min(16,Math.max(...vm.courses.map(x=>x.slotNo||0))))},(_,i)=>i+1):[];
  const sample=vm.metadata.isSample===true;
  const spatial=sample&&sampleSpatial;
  const marker=layout.markers.find(x=>x.id===selected)||layout.markers[0];
  const markerTitle=marker?.name||'教学楼';
  let sideResource=spatial?`<div class="floor-list">${spatial.floors.map(f=>`<div class="floor-row"><span>${E(f.label)}</span><span>${f.used}/${f.total}</span>${track(f.used,f.total)}<b>${Math.round(f.used/f.total*100)}%</b></div>`).join('')}</div><div class="floor-legend">${['空闲','教学使用','预约','维护'].map((x,i)=>`<span><i class="dot" style="--dot:${COLORS[i]}"></i>${x}</span>`).join('')}</div>`:
    (vm.resources.length?`<div class="room-list">${vm.resources.slice(0,6).map(r=>`<div class="room-row"><span>${E(r.classroom)}</span><b>${fmt(r.useCount)} 次使用</b></div>`).join('')}</div>${sn('展示部分使用记录，更多请进入教室资源。')}`:previewEmpty('resources'));
  const tokens={primary:'--cyan',blue:'--blue',gold:'--gold',danger:'--red'};
  for(const [k,p]of Object.entries(tokens))if(/^#[0-9a-f]{6}$/i.test(b[k]||''))host.style.setProperty(p,b[k]);
  board.classList.toggle('has-critical',vm.metadata.notes.length>0||vm.metadata.termMismatch||['RESTRICTED','UNAVAILABLE','PARTIAL'].includes(vm.state));
  board.innerHTML=`
  <header class="header">
   <div class="brand-area">${b.logoVisible&&safeAsset(urls.logo,{blob:true})?`<img class="brand-logo" src="${E(urls.logo)}" alt="学校标志"/>`:''}<div><div class="motto">${E(b.mottoLeft)}</div><span class="brand-name">${E(vm.metadata.schoolName||b.schoolName)}</span></div></div>
   <div class="header-center"><h1>${E(b.title)}</h1><p>${E(b.subtitle)}</p></div>
   <div class="header-right"><div class="header-tools">${previewStates?`<select class="preview-state" aria-label="预览数据状态">${previewStates.map(x=>`<option value="${E(x.id)}">${E(x.label)}</option>`).join('')}</select>`:''}<button class="tool" data-action="refresh" title="刷新真实统计" aria-label="刷新统计">${icon('refresh')}</button>${allowEditor?`<button class="tool" data-action="edit" title="修改文字与素材" aria-label="修改文字与素材">${icon('settings')}</button>`:''}<button class="tool" data-action="fullscreen" title="全屏" aria-label="全屏">${icon('fullscreen')}</button><button class="tool" data-action="exit" title="返回工作台" aria-label="返回工作台">${icon('back')}</button></div><div class="clock"><small class="motto-right">${E(b.mottoRight)}</small><small data-date></small><strong data-clock></strong></div></div>
  </header>
  <section class="kpis" aria-label="核心指标">${kpis.map(([id,ic,note],i)=>`<button class="kpi" data-action="metric" data-id="${id}" data-state="${m(id).state}" style="--kc:${i===6?'#ff8a7c':i===4?'#efc787':'#43dcef'}"><span class="kpi-ring">${icon(ic)}</span><span><span class="label">${E(ml(id))}</span><br/><span class="number">${label(id)}<small class="unit">${E(m(id).unit)}</small></span><span class="sub" style="display:block">${E(m(id).state==='OK'?note:m(id).note)}</span></span></button>`).join('')}</section>
  <main class="body-grid">
   <div class="left-column">
    <section class="panel">${head('teaching','teaching')}<div class="panel-body"><div class="status-caption"><span>${E(vm.metadata.dateLabel||'今日统计日期未返回')}</span>${vm.metadata.weekNo!==null?`<b>第${vm.metadata.weekNo}教学周</b>`:''}</div><div class="timeline" aria-label="从服务器课程预览标记进行中的节次">${slotNos.map(x=>`<span class="slot ${activeSlots.has(x)?'active':''}"><i></i>${x}</span>`).join('')}</div><div class="donut-row">${donut(teaching,'按课表进行中',prog===null?'—':fmt(prog,1)+'%')}${legend(teaching,'课次')}</div><div class="caption-line"><span>按课表时间判定 · 不代表考勤</span><span>调课关联 ${label('adjustedToday')} 课位</span></div></div></section>
    <section class="panel">${head('grade','grade')}<div class="panel-body"><div class="donut-row">${donut(gradeBreak,'累计成绩任务',label('gradeTotal'),true)}${legend([{label:'已提交/审核/发布',value:submitted,color:'#27d5e8'},{label:'录入中',value:v('gradeInputting'),color:'#368ef3'},{label:'未开始',value:v('gradeNotStarted'),color:'#eac078'},{label:'已退回',value:v('gradeReturned'),color:'#ef8174'}],'项')}</div><div class="caption-line"><span>已归档 ${label('gradeArchived')} 项单独计数</span><button class="back-link" data-action="metric" data-id="gradeSubmitted">统计口径 ›</button></div></div></section>
    <section class="panel">${head('resource','resource')}<div class="panel-body"><div class="donut-row">${donut(roomsRing,'今日占用比例',v('roomRate')===null?'—':label('roomRate')+'%',true)}${legend([{label:'今日占用（间）',value:oc,color:'#23d6e6'},{label:'可用教室（间）',value:roTotal,color:'#418ee6'},{label:'待核对文本（项）',value:v('unmatchedRooms'),color:'#e4b974'}])}</div><div class="caption-line"><span>按今日排课与已批准预约统计</span></div></div></section>
    <section class="panel">${head('exams','exams')}<div class="panel-body" style="padding:3px 11px">${vm.exams.length?`<table class="exam-table"><thead><tr><th>日期</th><th>考试课程</th><th>批次状态</th></tr></thead><tbody>${vm.exams.slice(0,4).map(x=>`<tr><td>${E(x.date.slice(5))}</td><td class="name">${E(x.courseName)}</td><td>${x.status==='PUBLISHED'?'已发布':x.status==='ARRANGED'?'已安排':'未确定'}</td></tr>`).join('')}</tbody></table><div class="mini-source">未来${vm.metadata.examWindow??'—'}天共${label('examUpcoming')}项 · 服务器明细最多10项</div>`:previewEmpty('exams')}</div></section>
   </div>
   <section class="panel map-panel">${head('map',null,`<div class="map-tabs"><button class="map-tab ${mapMode==='3d'?'active':''}" data-action="map" data-mode="3d">教学楼</button><button class="map-tab ${mapMode==='plan'?'active':''}" data-action="map" data-mode="plan">平面示意</button><button class="map-tab" data-action="nav" data-target="resource">教室资源 ›</button><span class="tag">${sample?'设计样例':'当前授权范围'}</span></div>`)}
    <div class="map-content"><div class="map-scene ${mapMode==='plan'?'plan':''}"><img class="campus-image" src="${E(safeAsset(mapMode==='plan'?urls.plan:urls.campus,{blob:true}))}" style="object-fit:${b.imageFit==='contain'?'contain':'cover'}" alt="可替换的校园空间示意底图，不代表真实学校数字孪生"/><div class="map-footnote">${sample?'校园与楼层数据均为设计样例':'校园空间示意'}</div>
     ${layout.markers.map(x=>`<button class="marker ${selected===x.id?'selected':''}" data-action="marker" data-id="${E(x.id)}" style="left:${Math.max(5,Math.min(95,Number(x.x)||50))}%;top:${Math.max(7,Math.min(87,Number(x.y)||50))}%"><strong>${E(x.name)}</strong>${spatial?`<span class="marker-stat">使用率参考 <b>${fmt(spatial.usage[x.id])}%</b></span>`:'<span class="marker-live">校园示意标注</span>'}</button>`).join('')}
     ${layout.libraryLabel?`<span class="library-label" style="left:${Math.max(0,Math.min(100,Number(layout.libraryLabel.x)||70))}%;top:${Math.max(0,Math.min(100,Number(layout.libraryLabel.y)||45))}%">${E(layout.libraryLabel.text)}</span>`:''}
     <div class="map-motto">${(Array.isArray(b.mapMotto)?b.mapMotto:[]).map(E).join('<br/>')}</div></div>
     <aside class="map-side"><section class="inset-panel"><header class="inset-head">${E(spatial?markerTitle:'今日占用教室')}<small>${spatial?'楼层使用 · 样例':'今日排课与已批准预约'}</small></header>${sideResource}</section>
      <section class="inset-panel"><header class="inset-head">${E(title('courses'))}<small>前${vm.courses.length} / ${vm.metadata.courseCount===null?'—':fmt(vm.metadata.courseCount)}课次</small></header>${vm.courses.length?`<div style="padding:1px 5px"><table class="course-table"><thead><tr><th>教室</th><th>课程名称</th><th>课表状态</th><th>节次</th></tr></thead><tbody>${vm.courses.slice(0,7).map(x=>`<tr><td title="${E(x.classroom)}">${E(x.classroom)}</td><td title="${E(x.courseName)}">${E(x.courseName)}</td><td><span class="badge ${x.runStatus==='IN_PROGRESS'?'running':x.runStatus==='NOT_STARTED'?'wait':'end'}">${STATUS_LABEL[x.runStatus]||'未确定'}</span></td><td>${fmt(x.slotNo)}</td></tr>`).join('')}</tbody></table></div><div class="source-line">按课表时间显示；完整安排请查看课表。</div>`:previewEmpty('courses')}</section>
     </aside></div>
   </section>
   <div class="right-column">
    <section class="panel">${head('progress','grade')}<div class="panel-body"><div class="donut-row">${donut(gradeRing,'累计成绩提交率',v('gradeSubmittedRate')===null?'—':label('gradeSubmittedRate')+'%',true)}${legend([{label:'全部任务',value:gt},{label:'已提交/审核/发布',value:submitted},{label:'已发布',value:v('gradePublished')},{label:'已归档',value:v('gradeArchived')}],'项')}</div></div></section>
    <section class="panel">${head('quality','quality')}<div class="panel-body"><div class="quality-mini"><button class="quality-card" data-action="metric" data-id="taskRate">${icon('check')}<span><label>${E(ml('taskRate'))}</label><strong>${label('taskRate')}<small> %</small></strong><small>累计任务确认情况</small></span></button><button class="quality-card" data-action="metric" data-id="programRate">${icon('shield')}<span><label>${E(ml('programRate'))}</label><strong>${label('programRate')}<small> %</small></strong><small>累计培养方案</small></span></button></div>
     <div class="quality-bars">${['qualityGradeRate','failRate','programRate'].map(id=>`<div class="quality-row" data-action="metric" data-id="${id}" role="button" tabindex="0"><span>${E(ml(id))}</span>${track(v(id))}<b>${label(id)}%</b></div>`).join('')}</div><div class="caption-line" style="margin-top:9px"><span>启用课程 ${label('enabledCourses')} 门</span><span>按累计业务记录统计</span></div></div></section>
    <section class="panel">${head('warning','warning')}<div class="panel-body"><div class="warning-grid"><div class="warning-block">${icon('shield')}<span><span>待处置记录</span><b>${metric('warningCount')}<small style="font-size:12px"> 条</small></b></span></div><div class="warning-extra"><strong>只展示汇总，不公开学生名单</strong>待处置与全部在办口径不同<br/>进入预警工作区查看办理详情</div></div></div></section>
   </div>
   <div class="bottom-row"><section class="panel">${head('trends',null,'<div class="chart-legend"><span><i class="dot" style="--dot:#328ff3"></i>成绩提交</span><span><i class="dot" style="--dot:#42d5e8"></i>调停课申请</span><span><i class="dot" style="--dot:#efc27a"></i>新增预警</span></div>')}${trendChart(vm.trends)}</section>
    <section class="panel">${head('issues','readiness')}<div style="padding:2px 11px">${vm.issues.length?`<table class="issue-table"><thead><tr><th>序号</th><th>规则关注事项</th><th>责任角色</th><th>截止说明</th><th>数量</th></tr></thead><tbody>${vm.issues.slice(0,5).map((x,i)=>`<tr><td><span class="rank ${i>1?'blue':''}">${i+1}</span></td><td><button class="issue-title" data-action="issue" data-index="${i}" title="${E(x.title)}">${E(x.title)}</button></td><td title="${E(x.ownerRole)}">${E(x.ownerRole)}</td><td title="${E(x.deadline)}">${E(x.deadline)}</td><td>${fmt(x.count)}</td></tr>`).join('')}</tbody></table>`:noData(vm.metadata.sources.readiness.state==='OK'?'当前阶段无待关注规则':'运行检查暂不可用','规则数量与学生、事故、任务去重总数不同')}</div></section>
   </div>
  </main>
  <footer class="footer"><span>${E(b.footerLeft)}</span><div class="footer-middle"><span class="state-pill ${sample?'':vm.state==='READY'?'live':'bad'}">${sample?('设计样例 · '+(vm.state==='READY'?'非生产数据':vm.state==='PARTIAL'?'部分不可用':vm.state==='RESTRICTED'?'范围受限':vm.state==='LOADING'?'加载状态':'暂无口径')):E(wallStatus(vm))}</span><button class="back-link" data-action="sources">指标与数据口径</button><span class="footer-note">${E(vm.metadata.termLabel)} · ${E(vm.metadata.sourceTime?('数据截至 '+sourceTimeLabel(vm.metadata.sourceTime,b.timezone)):'无有效统计时间')}</span></div><span>${E(b.footerRight)}</span></footer>
  <div class="diagnostic-banner">${E(vm.metadata.notes.join(' · ')||'当前授权范围不支持全校汇总；不显示假零')}</div>`;
  if(previewStates&&host.dataset.previewState)root.querySelector('.preview-state').value=host.dataset.previewState;syncFullscreen();tick();resize();
 }
 function resize(){if(dead)return;const rect=host.getBoundingClientRect();const width=rect.width||window.innerWidth,height=rect.height||window.innerHeight;const scale=Math.min(width/1920,height/1080);board.style.transform=`translate(${(width-1920*scale)/2}px, ${(height-1080*scale)/2}px) scale(${scale})`;}
 function tick(){if(dead)return;const date=vm.metadata.isSample?new Date('2026-09-06T08:28:35Z'):new Date();let zone=b.timezone||'Asia/Shanghai';try{new Intl.DateTimeFormat('zh-CN',{timeZone:zone}).format(date);}catch{zone='Asia/Shanghai';}const time=new Intl.DateTimeFormat('zh-CN',{timeZone:zone,hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}).format(date);const dt=new Intl.DateTimeFormat('zh-CN',{timeZone:zone,year:'numeric',month:'2-digit',day:'2-digit',weekday:'short'}).format(date);const clock=root.querySelector('[data-clock]'),ds=root.querySelector('[data-date]');if(clock)clock.textContent=time;if(ds)ds.textContent=dt+(vm.metadata.isSample?' · 样例时刻':' · 本地时钟');}
 function notify(text){clearTimeout(toastTimer);root.querySelector('.toast-slot').innerHTML=`<div role="status" class="toast">${E(text)}</div>`;toastTimer=setTimeout(()=>{if(!dead)root.querySelector('.toast-slot').innerHTML='';},4500);}
 function closeDialog(){board.inert=false;modal.innerHTML='';dialogContent='';if(queuedView){vm=queuedView;queuedView=null;render();}if(focusBefore?.isConnected)focusBefore.focus();}
 function dialog(title,body){focusBefore=root.activeElement;dialogContent=title;modal.innerHTML=`<div class="dialog-shade"><section class="dialog" role="dialog" aria-modal="true" aria-label="${E(title)}"><header><h2>${E(title)}</h2><button data-action="close" aria-label="关闭弹窗">${icon('close')}</button></header><div class="dialog-body">${body}</div></section></div>`;const actions=modal.querySelector('.dialog-actions');if(actions)modal.querySelector('.dialog').append(actions);board.inert=true;modal.querySelector('button')?.focus();}
 function metricDialog(id){const s=m(id);dialog(ml(id),`<dl><dt>当前结果</dt><dd><b>${label(id)} ${E(s.unit)}</b> · ${E(stateLabel(s.state))}</dd><dt>统计说明</dt><dd>${E(metricDescription(s))}</dd>${s.state!=='OK'?`<dt>当前情况</dt><dd>${E(s.note)}</dd>`:''}</dl><details class="technical-details"><summary>技术信息（供管理员排查）</summary><dl><dt>数据来源</dt><dd>${E(SOURCE_LABELS[s.endpoint]||s.endpoint)}</dd><dt>统计字段</dt><dd><code>${E(s.path)}</code></dd></dl></details><div class="dialog-actions"><button class="action-btn primary" data-action="nav" data-target="${E(s.route||'readiness')}">进入对应工作区</button><button class="action-btn" data-action="close">返回大屏</button></div>`);}
 function sourcesDialog(){dialog('数据更新与统计说明',`<p><b>${E(wallStatus(vm))}</b>。大屏自动刷新，也可以点击右上角手动刷新。</p><table class="atlas-table"><thead><tr><th>统计内容</th><th>读取状态</th><th>说明</th></tr></thead><tbody>${Object.entries(vm.metadata.sources).map(([k,s])=>`<tr><td>${E(SOURCE_LABELS[k]||k)}</td><td>${E(stateLabel(s.state))}</td><td>${E(s.note||(s.state==='OK'?'读取正常；暂无业务记录时显示空态':'请稍后刷新，或联系管理员核对'))}</td></tr>`).join('')}</tbody></table>${vm.metadata.notes.length?`<h3>当前提醒</h3><ul>${vm.metadata.notes.map(n=>`<li>${E(n)}</li>`).join('')}</ul>`:''}<p>“—”表示暂不具备计算条件，0 表示实际统计结果为零。录入并完成相应业务后，数据会自动更新。</p><p>校园图片为空间示意，楼层实时使用率尚未接入。课程、教室和考试仅展示部分明细，点击对应区域“更多”可查看完整业务记录。</p><div class="dialog-actions"><button class="action-btn" data-action="close">返回大屏</button></div>`);}
 function editor(){
  dialog('品牌、文字与空间标牌编辑',`<p>仅修改本地视觉配置，不改后台业务数据。所有修改均可导出给 Codex；正式校园应换成学校授权图片。</p><div class="edit-grid">${[['title','大屏标题'],['schoolName','学校名称（预览）'],['mottoLeft','左侧题词'],['mottoRight','右侧题词'],['subtitle','副标题'],['footerRight','页脚右侧'],['footerLeft','页脚左侧']].map(([key,txt])=>`<label>${txt}<input data-brand="${key}" value="${E(b[key]||'')}" maxlength="120"/></label>`).join('')}<label>校园底图（PNG/JPG/WebP）<input type="file" data-upload="campus" accept="image/png,image/jpeg,image/webp"/></label><label>学校Logo（PNG/JPG/WebP）<input type="file" data-upload="logo" accept="image/png,image/jpeg,image/webp"/></label>${Object.keys(b.panelTitles||{}).map(key=>`<label>区域标题 · ${key}<input data-panel="${key}" value="${E(b.panelTitles[key])}" maxlength="80"/></label>`).join('')}<label class="full">顶部七项指标显示名（单位/定义仍由数据合同决定）</label>${['todayTotal','teacherCount','classCount','occupiedRooms','gradeSubmittedRate','pendingChanges','warningCount'].map(id=>`<label>${E(id)}<input data-metric-label="${id}" value="${E(ml(id))}" maxlength="50"/></label>`).join('')}</div><h3>楼宇名称与位置（%）</h3><label>图书馆标牌 <input data-library-name value="${E(layout.libraryLabel?.text||'')}" maxlength="30"/></label><div class="micro-note">原底图文字已清除；X、Y为示意图内位置，不是地理坐标。</div>${layout.markers.map((x,i)=>`<div class="edit-markers"><input data-marker-name="${i}" value="${E(x.name)}" maxlength="30" aria-label="楼宇名称"/><input type="number" min="5" max="95" data-marker-x="${i}" value="${x.x}" aria-label="横坐标"/><input type="number" min="7" max="87" data-marker-y="${i}" value="${x.y}" aria-label="纵坐标"/></div>`).join('')}<div class="dialog-actions"><button class="action-btn primary" data-action="apply-edit">应用预览</button><button class="action-btn" data-action="export-config">导出配置与上传素材ZIP</button><button class="action-btn" data-action="close">关闭</button></div>`);
 }
 function collectEdits(){
  modal.querySelectorAll('[data-brand]').forEach(x=>b[x.dataset.brand]=x.value);
  modal.querySelectorAll('[data-panel]').forEach(x=>(b.panelTitles??={})[x.dataset.panel]=x.value);
  modal.querySelectorAll('[data-metric-label]').forEach(x=>(b.metricLabels??={})[x.dataset.metricLabel]=x.value);
  for(let i=0;i<layout.markers.length;i++){
   const n=modal.querySelector(`[data-marker-name="${i}"]`);if(!n)continue;
   layout.markers[i].name=n.value;layout.markers[i].x=Math.max(5,Math.min(95,Number(modal.querySelector(`[data-marker-x="${i}"]`).value)||50));layout.markers[i].y=Math.max(7,Math.min(87,Number(modal.querySelector(`[data-marker-y="${i}"]`).value)||50));
  }
  if(layout.libraryLabel&&modal.querySelector('[data-library-name]'))layout.libraryLabel.text=modal.querySelector('[data-library-name]').value;
   validateBrandPatch(b);if(vm.metadata.isSample)vm.metadata.schoolName=b.schoolName;
 }
 const uploads={};
 async function readUpload(file,key){
  if(!['image/png','image/jpeg','image/webp'].includes(file.type)||file.size>8*1024*1024){notify('请选择8MB以内PNG/JPG/WebP图片');return;}
  const bitmap=await createImageBitmap(file);if(dead){bitmap.close();return;}if(bitmap.width*bitmap.height>24000000){bitmap.close();notify('图片像素过大，请先缩小');return;}
  const cv=document.createElement('canvas');cv.width=bitmap.width;cv.height=bitmap.height;cv.getContext('2d').drawImage(bitmap,0,0);bitmap.close();
  const url=cv.toDataURL('image/webp',.94);if(url.length>12*1024*1024){notify('转换后素材过大，请缩小图片');return;}uploads[key]={file:`${key}-custom.webp`,url};urls[key]=url;if(key==='logo')b.logoVisible=true;
  notify('素材已载入，点击应用预览或导出配置。');
 }
 function download(name,bytes,mime){const u=URL.createObjectURL(new Blob([bytes],{type:mime}));const a=document.createElement('a');a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),5000);}
 // Minimal uncompressed ZIP writer; no remote dependency and no metrics in the export.
 function zipStore(files){const enc=new TextEncoder(),parts=[],central=[];let offset=0;const crc=b=>{let c=-1;for(const x of b){c^=x;for(let i=0;i<8;i++)c=(c>>>1)^(0xedb88320&-(c&1));}return (c^-1)>>>0;};
  for(const f of files){const name=enc.encode(f.name),data=typeof f.data==='string'?enc.encode(f.data):f.data,c=crc(data);const local=new Uint8Array(30+name.length),v=new DataView(local.buffer);v.setUint32(0,0x04034b50,true);v.setUint16(4,20,true);v.setUint16(6,0x800,true);v.setUint32(14,c,true);v.setUint32(18,data.length,true);v.setUint32(22,data.length,true);v.setUint16(26,name.length,true);local.set(name,30);parts.push(local,data);
   const cd=new Uint8Array(46+name.length),d=new DataView(cd.buffer);d.setUint32(0,0x02014b50,true);d.setUint16(4,20,true);d.setUint16(6,20,true);d.setUint16(8,0x800,true);d.setUint32(16,c,true);d.setUint32(20,data.length,true);d.setUint32(24,data.length,true);d.setUint16(28,name.length,true);d.setUint32(42,offset,true);cd.set(name,46);central.push(cd);offset+=local.length+data.length;}
  const cl=central.reduce((a,x)=>a+x.length,0),end=new Uint8Array(22),ev=new DataView(end.buffer);ev.setUint32(0,0x06054b50,true);ev.setUint16(8,files.length,true);ev.setUint16(10,files.length,true);ev.setUint32(12,cl,true);ev.setUint32(16,offset,true);return new Blob([...parts,...central,end],{type:'application/zip'});
 }
 function exportConfig(){collectEdits();const map={campus:'campus-clean.webp',plan:'campus-plan.svg',logo:'logo.svg',...assetFiles};const files=[{name:'config/brand.json',data:JSON.stringify(b,null,2)},{name:'config/campus.json',data:JSON.stringify(layout,null,2)}];for(const [k,u]of Object.entries(uploads)){map[k]=u.file;files.push({name:'src/assets/'+u.file,data:Uint8Array.from(atob(u.url.split(',')[1]),c=>c.charCodeAt(0))});}files.push({name:'config/assets.json',data:JSON.stringify(map,null,2)});download('教务大屏-品牌与素材替换.zip',zipStore(files),'application/zip');notify('只导出视觉配置和上传素材，不包含业务数据。');}
 function syncFullscreen(){const button=root.querySelector('[data-action="fullscreen"]');if(!button)return;const active=document.fullscreenElement===host;button.title=active?'退出全屏':'全屏';button.setAttribute('aria-label',button.title);button.setAttribute('aria-pressed',String(active));}
 async function toggleFullscreen(){try{if(document.fullscreenElement)await document.exitFullscreen();else if(host.requestFullscreen)await host.requestFullscreen();else notify('当前浏览器不支持全屏，请在桌面浏览器中打开。');}catch{notify('暂时无法切换全屏，请重试。');}finally{if(!dead)syncFullscreen();}}
 function eventClick(ev){if(ev.target.classList.contains('dialog-shade')){closeDialog();return;}const el=ev.target.closest('[data-action]');if(!el)return;const a=el.dataset.action;
  if(a==='metric')metricDialog(el.dataset.id);
  else if(a==='nav'){closeDialog();onNavigate(el.dataset.target);}
  else if(a==='map'){mapMode=el.dataset.mode;render();}
  else if(a==='marker'){selected=el.dataset.id;render();if(!vm.metadata.isSample)notify('此处为校园示意。请通过“教室资源”查看实际教室及使用记录。');}
  else if(a==='issue'){const it=vm.issues[Number(el.dataset.index)];if(it?.target)onNavigate(it.target);else notify('该事项没有有效下钻入口');}
  else if(a==='refresh')onRefresh();
  else if(a==='exit')onExit();
  else if(a==='fullscreen')void toggleFullscreen();
  else if(a==='close')closeDialog();
  else if(a==='sources')sourcesDialog();
  else if(a==='edit')editor();
  else if(a==='apply-edit'){try{collectEdits();closeDialog();render();notify('已更新本地视觉，业务数据口径未改变。');}catch(e){notify(e.message);}}
  else if(a==='export-config'){try{exportConfig();}catch(e){notify(e.message);}}
 }
 function keydown(ev){
  if(ev.key==='Escape'){if(dialogContent){ev.preventDefault();closeDialog();}return;}
  if((ev.key==='Enter'||ev.key===' ')&&ev.target.matches('[role="button"][data-action]')){ev.preventDefault();ev.target.click();}
  if(ev.key==='Tab'&&dialogContent){const items=[...modal.querySelectorAll('button,input,select,summary,[tabindex="0"]')].filter(x=>!x.disabled);if(!items.length)return;const active=root.activeElement;if(ev.shiftKey&&active===items[0]){ev.preventDefault();items.at(-1).focus();}else if(!ev.shiftKey&&active===items.at(-1)){ev.preventDefault();items[0].focus();}}
 }
 const uploadHandler=ev=>{if(ev.target.classList.contains('preview-state')){onPreviewState(ev.target.value);return;}const key=ev.target.dataset.upload;if(key&&ev.target.files?.[0])readUpload(ev.target.files[0],key).catch(()=>notify('图片无法读取'));};
 root.addEventListener('click',eventClick);root.addEventListener('keydown',keydown);root.addEventListener('change',uploadHandler);
 document.addEventListener('fullscreenchange',syncFullscreen);
 const observer=new ResizeObserver(resize);observer.observe(host);const timer=setInterval(tick,1000);render();
 return {update(view){if(dialogContent){queuedView=view;return;}vm=view||emptyView();render();},reset(state='LOADING'){queuedView=null;vm=emptyView(state);closeDialog();render();},notify,closeDialog,
  setBrand(next){b={...b,...validateBrandPatch(next)};if(vm.metadata.isSample)vm.metadata.schoolName=b.schoolName;render();},
  getConfig(){return {brand:structuredClone(b),campus:structuredClone(layout)};},
  destroy(){dead=true;document.removeEventListener('fullscreenchange',syncFullscreen);clearInterval(timer);clearTimeout(toastTimer);observer.disconnect();root.removeEventListener('click',eventClick);root.removeEventListener('keydown',keydown);root.removeEventListener('change',uploadHandler);root.innerHTML='';},
  getView(){return vm;},setSpatial(value){sampleSpatial=value;render();},resize
 };
}
