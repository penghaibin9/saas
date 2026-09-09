
/* Original procedural campus renderer. No CDN, tracking, maps or student data.
   The model is a brand illustration, NOT a digital twin. destroy() releases all listeners. */
import { CAMPUS_MODULES } from './content.js'

'use strict';
const TAU=Math.PI*2, clamp=(n,a,b)=>Math.max(a,Math.min(b,n));
const modules=CAMPUS_MODULES;
const cameras={
 overview:{yaw:.67,pitch:.66,distance:870,target:[0,8,0]},
 affairs:{yaw:.45,pitch:.62,distance:535,target:[-119,14,79]},
 academic:{yaw:.8,pitch:.59,distance:563,target:[-83,36,-107]},
 internship:{yaw:.55,pitch:.61,distance:575,target:[149,19,-55]},
 graduation:{yaw:.92,pitch:.66,distance:546,target:[96,10,122]}
};
function hexMix(hex,a,b=255){const c=hex.replace('#','');return '#'+[0,2,4].map(i=>Math.round(parseInt(c.slice(i,i+2),16)*a+b*(1-a)).toString(16).padStart(2,'0')).join('');}
function buildWorld(){
 const faces=[];
 function face(p,color,normal=[0,1,0],opts={}){faces.push({p,color,normal,...opts});}
 function plane(x,z,w,d,color,y=.18,opts={}){face([[x-w/2,y,z-d/2],[x+w/2,y,z-d/2],[x+w/2,y,z+d/2],[x-w/2,y,z+d/2]],color,[0,1,0],opts);}
 function box(x,z,w,d,h,color='#e8f0f6',y=0,opts={}){
  const a=x-w/2,b=x+w/2,c=z-d/2,e=z+d/2,t=y+h;
  face([[a,t,c],[b,t,c],[b,t,e],[a,t,e]],hexMix(color,.76),[0,1,0],opts);
  face([[a,y,e],[b,y,e],[b,t,e],[a,t,e]],hexMix(color,.91,176),[0,0,1],opts);
  face([[b,y,c],[b,y,e],[b,t,e],[b,t,c]],hexMix(color,.89,126),[1,0,0],opts);
  face([[a,y,c],[b,y,c],[b,t,c],[a,t,c]],hexMix(color,.86,168),[0,0,-1],opts);
  face([[a,y,c],[a,y,e],[a,t,e],[a,t,c]],hexMix(color,.90,199),[-1,0,0],opts);
 }
 function cylinder(x,z,r,h,color,y=0,n=20,opts={}){
  const top=[];for(let i=0;i<n;i++){const a=i/n*TAU,b=(i+1)/n*TAU;let p=[x+Math.cos(a)*r,y+h,z+Math.sin(a)*r],q=[x+Math.cos(b)*r,y+h,z+Math.sin(b)*r];top.push(p);const nx=Math.cos((a+b)/2),nz=Math.sin((a+b)/2);const strength=.86+nx*.045-nz*.055;face([[p[0],y,p[2]],[q[0],y,q[2]],q,p],hexMix(color,strength,135),[nx,0,nz],opts);}
  face(top,hexMix(color,.85),[0,1,0],opts);
 }
 function circle(x,z,r,color,y=.2,n=36){const p=[];for(let i=0;i<n;i++)p.push([x+Math.cos(i/n*TAU)*r,y,z+Math.sin(i/n*TAU)*r]);face(p,color);}
 function lineGround(points,width,color,y=.3){for(let i=1;i<points.length;i++){const p=points[i-1],q=points[i],len=Math.hypot(q[0]-p[0],q[1]-p[1]),nx=(q[1]-p[1])/len*width/2,nz=-(q[0]-p[0])/len*width/2;face([[p[0]+nx,y,p[1]+nz],[q[0]+nx,y,q[1]+nz],[q[0]-nx,y,q[1]-nz],[p[0]-nx,y,p[1]-nz]],color);}}
 function shadow(x,z,w,d,h){face([[x-w/2,.13,z-d/2],[x+w/2,.13,z-d/2],[x+w/2+h*.54,.13,z+d/2+h*.27],[x-w/2+h*.54,.13,z+d/2+h*.27]],'rgba(9,35,44,.20)',[0,1,0]);}
 function building(x,z,w,d,h,module,color='#edf2f5'){
  const palette={affairs:['#d6e7dd','#307d61'],academic:['#d8e5ef','#285f8e'],internship:['#ddd8e8','#69538a'],graduation:['#eee0c7','#aa783b']};const [wall,roof]=palette[module]||['#e9dfc8','#6d766b'];color=wall;const opts={module};shadow(x,z,w,d,h);box(x,z,w+5,d+5,3,'#d8e3ed',0,opts);box(x,z,w,d,h,color,3,opts);box(x,z,w+2,d+2,1.6,roof,h+3,opts);
  // Window bands remain geometry rather than a raster texture.
  const rows=Math.max(1,Math.floor((h-8)/10));
  for(let r=0;r<rows;r++){
   let y=8+r*10;let gap=7;
   for(let i=-w/2+5;i<w/2-3;i+=gap){let ww=Math.min(4.1,w/2-i-1);face([[x+i,y,z+d/2+.08],[x+i+ww,y,z+d/2+.08],[x+i+ww,y+5,z+d/2+.08],[x+i,y+5,z+d/2+.08]],r%2?'#5185a4':'#87b9d0',[0,0,1],opts);}
   for(let i=-d/2+5;i<d/2-3;i+=gap){let dd=Math.min(4.1,d/2-i-1);face([[x+w/2+.08,y,z+i],[x+w/2+.08,y,z+i+dd],[x+w/2+.08,y+5,z+i+dd],[x+w/2+.08,y+5,z+i]],'#406c8a',[1,0,0],opts);}
   face([[x-w/2-.08,y,z-d/2+4],[x-w/2-.08,y,z+d/2-4],[x-w/2-.08,y+4,z+d/2-4],[x-w/2-.08,y+4,z-d/2+4]],'#c0d9e4',[-1,0,0],opts);
  }
  box(x-7,z-5,w*.43,d*.35,3,'#cadbe5',h+4.6,opts);
  // Dark glass skylight, with mullions.
  plane(x-7,z-5,w*.40,d*.32,'#779db4',h+7.7,opts);
  for(let k=-1;k<=1;k++)plane(x-7+k*w*.1,z-5,.8,d*.32,'#e8f0f5',h+7.8,opts);
 }
 function tree(x,z,s=1){
  circle(x+3,z+2,6.5*s,'rgba(71,112,103,.13)',.36,10);box(x,z,1.35*s,1.35*s,6*s,'#796346',.4);const y=7*s;
  // A faceted, soft low-poly crown.
  const n=7,ring0=[],ring1=[];for(let i=0;i<n;i++){let a=i/n*TAU;ring0.push([x+Math.cos(a)*5.6*s,y,z+Math.sin(a)*5.6*s]);ring1.push([x+Math.cos(a)*4.0*s,y+6*s,z+Math.sin(a)*4.0*s]);}
  for(let i=0;i<n;i++){let j=(i+1)%n,a=(i+.5)/n*TAU;face([ring0[i],ring0[j],ring1[j],ring1[i]],i%2?'#3f8053':'#2d714c',[Math.cos(a),.28,Math.sin(a)]);face([ring1[i],ring1[j],[x,y+9*s,z]],i%2?'#61994d':'#4c8b55',[Math.cos(a)*.45,.8,Math.sin(a)*.45]);}
 }
 // Floating plinth, paving, planted districts and avenues.
 box(0,0,622,478,11,'#597166',-11);plane(0,0,615,470,'#a9cda8',.02);
 [[-137,62,147,152],[-96,-116,152,148],[148,-73,166,159],[104,130,148,116]].forEach(([x,z,w,d])=>{plane(x,z,w+8,d+8,'#e1eceb',.08);plane(x,z,w,d,'#e9f1ef',.10);});
 plane(15,0,34,461,'#fbfcfd');plane(0,-4,603,27,'#fcfdfe');plane(-264,0,18,434,'#fafcfe');plane(0,-208,538,13,'#fafcfe');plane(0,202,541,15,'#fafcfe');plane(278,0,15,425,'#fafcfe');
 plane(15,0,.8,461,'#dce8f6',.24);plane(0,-4,603,.8,'#dce8f6',.24);
 // Sports field in the back-left district.
 plane(-214,-120,84,142,'#d9e8e3');plane(-214,-120,76,132,'#ddbbb2',.23);plane(-214,-120,59,111,'#a5cbb9',.25);
 for(let i=0;i<7;i++)plane(-214,-169+i*16,59,8,'#aed0bf',.28);
 lineGround([[-239,-171],[-189,-171],[-189,-70],[-239,-70],[-239,-171]],.8,'#f2faf7',.3);lineGround([[-239,-120],[-189,-120]],.7,'#f2faf7',.3);
 for(let z of [-169,-71]){box(-214,z,15,1,5,'#eaf7f4',.4);}
 // Teaching courtyard; connected academic towers.
 building(-111,-114,44,91,67,'academic');building(-56,-111,42,92,53,'academic');
 box(-83,-148,34,13,9,'#dceaf2',36,{module:'academic'});box(-83,-148,35,15,1.5,'#f6fcff',45,{module:'academic'});
 plane(-83,-90,14,52,'#d2e5eb',.3);
 for(let z=-111;z<-58;z+=13)tree(-85,z,.55);
 // Student affairs: administration & student services around a garden.
 building(-151,53,87,31,36,'affairs');building(-181,101,28,65,30,'affairs');building(-118,101,26,65,33,'affairs');
 plane(-149,100,28,32,'#c6dfd5',.25);circle(-149,100,9,'#aed2c0',.35);tree(-149,100,1.05);
 for(let i=0;i<5;i++)box(-148+i*2,132,25-i*2,4,1,'#d7e4e9',i*.5);
 // Library, low horizontal block behind the main plaza.
 building(-55,159,69,35,24,'affairs');for(let i=-2;i<=2;i++)box(-55+i*12,159,1,34,5,'#f2f8fb',28);
 // Internship / enterprise cooperation: workshop, skylights & office tower.
 building(140,-72,101,69,25,'internship');building(213,-123,30,47,66,'internship');building(222,-48,27,71,31,'internship');
 for(let j=0;j<4;j++){box(102+j*24,-73,15,49,4,'#d8e9f1',30,{module:'internship'});plane(102+j*24,-73,12,44,'#8bb9d3',34.1,{module:'internship'});}
 plane(133,-125,102,16,'#f9fbfc');for(let i=0;i<8;i++)plane(91+i*12,-125,.8,13,'#ccd8e3',.3);
 // Graduation: stepped auditorium and exhibition building.
 building(85,130,92,61,21,'graduation');building(159,121,33,70,42,'graduation');
 for(let i=0;i<7;i++)box(48+i*12,130,11,62,4+Math.sin(i/6*Math.PI)*11,'#e4edf5',26,{module:'graduation'});
 box(82,166,110,5,2,'#d8e3eb',.4);box(82,171,118,5,1,'#e1e9ef',.4);
 // Fountain / common student identity plaza.
 circle(16,20,40,'#e0eaf0');circle(16,20,35,'#d9dac1',.25);circle(16,20,26,'#3c9bb5',.4);circle(16,20,21,'#2484a4',.5);cylinder(16,20,10,4,'#f7fbff',.5,32);box(16,20,7,7,24,'#b6d7ef',4.5);box(16,20,10,10,2,'#e1f2ff',29);
 // Pond & green sitting garden on the front-right.
 plane(223,137,52,90,'#659a63');circle(223,123,20,'#248da8',.28);circle(229,139,21,'#248da8',.29);
 for(let z=105;z<=165;z+=20)tree(256,z,.85);
 // North entrance & low walls.
 box(13,215,84,5,6,'#f4f8fc',25);box(-26,215,5,6,26,'#ecf2f7');box(52,215,5,6,26,'#ecf2f7');plane(13,217,52,21,'#dde9f2',.3);
 // Boulevard tree rhythm, no synthetic location markers.
 for(let x=-243;x<=260;x+=25){if(x<-42||x>62)tree(x,194,.84);tree(x,-195,.80);}
 for(let z=-166;z<=176;z+=28){tree(-247,z,.8);tree(263,z,.84);}
 [-52,-24,64,102,143,172].forEach(z=>tree(-12,z,.68));
 for(let x of [-220,-198,-85,-60,54,81,110,169,196,223]){tree(x,24,.70);}
 // Small outdoor seating and a few neutral vehicles establish scale.
 for(let x=-220;x<-50;x+=37)box(x,181,10,3,3,'#b7c7bd',.4);
 for(let i=0;i<7;i++){box(273,-132+i*20,5,10,3,i%3===0?'#8fb4d9':'#d0dce4',.4);box(273,-132+i*20,4.3,5,1.6,'#bfd6e3',3.4);}
 return faces;
}
const WORLD=buildWorld();
class CampusScene{
 constructor(canvas,{dark=false,hotspots=null,enabled=true}={}){
  this.canvas=canvas;this.ctx=canvas.getContext('2d',{alpha:true});this.dark=dark;this.hotspots=hotspots;this.scene='overview';this.wire=0;this.wireGoal=0;this.motion=false;this.enabled=enabled;this.inView=true;this.dead=false;this.reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;this.frame=0;this.last=0;this.lastMove=0;this.phase=0;this.cam={...cameras.overview,target:[...cameras.overview.target]};this.goal={...this.cam,target:[...this.cam.target]};this.width=1;this.height=1;this.dirty=true;
  if(!this.ctx){canvas.parentElement.classList.add('canvas-failed');return;}
  canvas.parentElement.classList.add('canvas-ready');
  this.onVisibility=()=>{this.request()};document.addEventListener('visibilitychange',this.onVisibility);
  this.media=matchMedia('(prefers-reduced-motion: reduce)');this.onMedia=e=>{this.reduced=e.matches;this.request()};this.media.addEventListener('change',this.onMedia);
  this.resize=new ResizeObserver(()=>this.resizeCanvas());this.resize.observe(canvas);
  this.intersection=new IntersectionObserver(entries=>{this.inView=entries[0].isIntersecting;this.request()},{rootMargin:'100px'});this.intersection.observe(canvas);
  this.onDown=e=>{if(e.pointerType==='touch')return;this.drag={x:e.clientX,y:e.clientY};canvas.setPointerCapture(e.pointerId);canvas.classList.add('dragging')};
  this.onMove=e=>{if(!this.drag)return;this.goal.yaw+=(this.drag.x-e.clientX)*.005;this.goal.pitch=clamp(this.goal.pitch+(e.clientY-this.drag.y)*.003,.34,.95);this.drag={x:e.clientX,y:e.clientY};this.request()};
  this.onUp=()=>{this.drag=null;canvas.classList.remove('dragging')};
  canvas.addEventListener('pointerdown',this.onDown);canvas.addEventListener('pointermove',this.onMove);canvas.addEventListener('pointerup',this.onUp);canvas.addEventListener('pointercancel',this.onUp);canvas.addEventListener('lostpointercapture',this.onUp);
  if(hotspots){hotspots.textContent='';for(const m of modules){const b=document.createElement('button');b.className='hotspot';b.type='button';b.dataset.hotspot=m.key;b.setAttribute('aria-label',`查看${m.name}校园场景`);const dot=document.createElement('i');const text=document.createElement('span');text.textContent=m.name;b.append(dot,text);b.addEventListener('click',()=>{canvas.dispatchEvent(new CustomEvent('campusselect',{detail:m.key,bubbles:true}))});hotspots.appendChild(b);}}
  this.resizeCanvas();
 }
 resizeCanvas(){const rect=this.canvas.getBoundingClientRect();if(rect.width<1||rect.height<1)return;this.width=rect.width;this.height=rect.height;this.dpr=Math.min(window.devicePixelRatio||1,1.6);this.canvas.width=Math.round(this.width*this.dpr);this.canvas.height=Math.round(this.height*this.dpr);this.request();}
 setScene(key){if(!cameras[key])return;this.scene=key;this.goal={...cameras[key],target:[...cameras[key].target]};this.request();}
 resetCamera(){this.setScene('overview');}
 setWireframe(on){this.wireGoal=on?1:0;this.request();}
 setMotion(on){this.motion=Boolean(on);this.request();}
 setEnabled(on){this.enabled=Boolean(on);this.request();}
 request(){this.dirty=true;if(!this.frame&&!this.dead&&this.ctx&&this.enabled&&this.inView&&!document.hidden)this.frame=requestAnimationFrame(t=>this.draw(t));}
 project(p){const d=[p[0]-this.eye[0],p[1]-this.eye[1],p[2]-this.eye[2]];let z=d[0]*this.fw[0]+d[1]*this.fw[1]+d[2]*this.fw[2];if(z<15)return null;const x=d[0]*this.right[0]+d[2]*this.right[2],y=d[0]*this.up[0]+d[1]*this.up[1]+d[2]*this.up[2];return [this.width*.5+x*this.focal/z,this.height*.53-y*this.focal/z,z];}
 polygon(ps,fill,stroke=null,width=.5){const c=this.ctx;c.beginPath();for(let i=0;i<ps.length;i++){if(i)c.lineTo(ps[i][0],ps[i][1]);else c.moveTo(ps[i][0],ps[i][1]);}c.closePath();if(fill){c.fillStyle=fill;c.fill();}if(stroke){c.strokeStyle=stroke;c.lineWidth=width;c.stroke();}}
 draw(t){
  this.frame=0;if(this.dead||!this.enabled||!this.inView||document.hidden)return;
  if(t-this.last<32){this.frame=requestAnimationFrame(n=>this.draw(n));return;}
  const dt=Math.min(70,t-this.last||32);this.last=t;
  const smoothing=this.reduced?1:Math.min(.20,dt/190);let moving=0;
  for(const k of ['yaw','pitch','distance']){const delta=this.goal[k]-this.cam[k];moving+=Math.abs(delta);this.cam[k]+=delta*smoothing;}
  for(let i=0;i<3;i++){const delta=this.goal.target[i]-this.cam.target[i];moving+=Math.abs(delta);this.cam.target[i]+=delta*smoothing;}
  const wd=this.wireGoal-this.wire;moving+=Math.abs(wd);this.wire+=wd*smoothing;
  if(this.motion&&!this.reduced)this.phase+=dt/1000;
  const {yaw,pitch,distance,target}=this.cam,cy=Math.cos(yaw),sy=Math.sin(yaw),cp=Math.cos(pitch),sp=Math.sin(pitch);
  this.eye=[target[0]+distance*cp*sy,target[1]+distance*sp,target[2]+distance*cp*cy];this.fw=[-cp*sy,-sp,-cp*cy];this.right=[cy,0,-sy];this.up=[-sp*sy,cp,-sp*cy];this.focal=this.height*1.23;
  const c=this.ctx;c.setTransform(this.dpr,0,0,this.dpr,0,0);c.clearRect(0,0,this.width,this.height);
  // Non-geographic ground grid.
  c.lineWidth=.65;c.strokeStyle=this.dark?'rgba(112,157,212,.13)':'rgba(108,143,186,.115)';
  for(let i=-650;i<=650;i+=50){for(const pair of [[[i,-13,-650],[i,-13,650]],[[-650,-13,i],[650,-13,i]]]){const p=this.project(pair[0]),q=this.project(pair[1]);if(p&&q){c.beginPath();c.moveTo(p[0],p[1]);c.lineTo(q[0],q[1]);c.stroke();}}}
  const projected=[];
  for(const f of WORLD){
   const p0=f.p[0],n=f.normal,to=[this.eye[0]-p0[0],this.eye[1]-p0[1],this.eye[2]-p0[2]];
   if(to[0]*n[0]+to[1]*n[1]+to[2]*n[2]<0)continue;
   const ps=f.p.map(p=>this.project(p));if(ps.some(p=>!p))continue;projected.push({f,ps,layer:f.p.every(p=>p[1]<=.6)?0:1,z:ps.reduce((a,p)=>a+p[2],0)/ps.length});
  }
  projected.sort((a,b)=>a.layer-b.layer||b.z-a.z);
  for(const {f,ps} of projected){
   const focused=this.scene==='overview'||!f.module||f.module===this.scene;
   c.globalAlpha=this.wire>.01?1-this.wire*.88:1;
   this.polygon(ps,f.color,focused?'rgba(96,123,148,.16)':'rgba(122,145,166,.10)',.45);
   if(this.wire>.01){c.globalAlpha=this.wire*.8;this.polygon(ps,null,this.dark?'#7fc1e5':'#458ac5',.65);}
  }
  c.globalAlpha=1;
  // Abstract connections: these are visual storytelling paths, not live location tracks.
  const start=[16,2.2,20];
  for(let i=0;i<modules.length;i++){
   const m=modules[i],pos=m.world;const path=[start,[16,2.5,pos[2]],[pos[0],3,pos[2]]];const active=this.scene===m.key;
   c.strokeStyle=active?(this.dark?'#76c8ff':'#2474d8'):(this.dark?'rgba(118,177,224,.30)':'rgba(97,150,203,.36)');c.lineWidth=active?2.5:1.25;c.setLineDash(active?[]:[4,4]);c.beginPath();path.forEach((p,j)=>{const v=this.project(p);if(v){if(j)c.lineTo(v[0],v[1]);else c.moveTo(v[0],v[1]);}});c.stroke();c.setLineDash([]);
   if(active||this.scene==='overview'){
    const tm=(this.phase*.19+i*.23)%1;const seg=tm<.5?0:1,f=(tm%0.5)*2;const p=path[seg].map((v,k)=>v+(path[seg+1][k]-v)*f),screen=this.project(p);if(screen){c.beginPath();c.arc(screen[0],screen[1],active?3.6:2.5,0,TAU);c.fillStyle=this.dark?'#b4e6ff':'#3d87de';c.fill();}
   }
  }
  const center=this.project([16,2.8,20]);if(center){c.fillStyle=this.dark?'#c5e6ff':'#326ca5';c.font=`600 ${this.width<500?9:10}px system-ui,sans-serif`;c.textAlign='center';c.fillText('YUEKE',center[0],center[1]+24);}
  if(this.hotspots){for(const m of modules){const b=this.hotspots.querySelector(`[data-hotspot="${m.key}"]`);const p=this.project(m.world);if(!p||p[0]<-15||p[0]>this.width+15||p[1]<-25||p[1]>this.height-20){b.style.visibility='hidden';continue;}b.style.visibility='visible';b.style.left=clamp(p[0],55,this.width-55)+'px';b.style.top=clamp(p[1],38,this.height-35)+'px';b.classList.toggle('active',m.key===this.scene);b.setAttribute('aria-pressed',String(m.key===this.scene));}}
  this.dirty=false;
  if(moving>.02||this.motion&&!this.reduced)this.frame=requestAnimationFrame(n=>this.draw(n));
 }
 destroy(){this.dead=true;if(this.frame)cancelAnimationFrame(this.frame);this.resize?.disconnect();this.intersection?.disconnect();this.media?.removeEventListener('change',this.onMedia);document.removeEventListener('visibilitychange',this.onVisibility);for(const [e,f] of [['pointerdown',this.onDown],['pointermove',this.onMove],['pointerup',this.onUp],['pointercancel',this.onUp],['lostpointercapture',this.onUp]])this.canvas.removeEventListener(e,f);}
}
export { CampusScene };

