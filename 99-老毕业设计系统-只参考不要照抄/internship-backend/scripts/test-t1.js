const BASE = 'http://localhost:3000/api';
async function api(token, path, method='GET', body){
  const headers={'Content-Type':'application/json'};
  if(token) headers.Authorization='Bearer '+token;
  const res=await fetch(BASE+path,{method,headers,body:body?JSON.stringify(body):undefined});
  let j=null; try{j=await res.json()}catch(_){}
  return {status:res.status,j,ok:res.ok&&j&&j.success};
}
async function login(u,p){const r=await api(null,'/users/login','POST',{username:u,password:p}); if(!r.ok) throw new Error('login '+u+' '+(r.j&&r.j.message)); return {token:r.j.data.token,user:r.j.data.user};}
const addDays=(n)=>new Date(Date.now()+n*86400000).toISOString().slice(0,10);

(async()=>{
  const admin=await login('admin','123456');
  const teacher=await login('demo_teacher','demo1234');
  const student=await login('demo_stu1','demo1234');
  console.log('登录OK  stu=',student.user.id,'tea=',teacher.user.id);

  // 风险预警
  let r=await api(teacher.token,'/risk/warnings');
  console.log('① 教师风险预警:',r.ok, r.ok? JSON.stringify(r.j.data.summary):r.j&&r.j.message);
  r=await api(admin.token,'/risk/warnings');
  console.log('   管理员风险预警:',r.ok, r.ok? 'summary='+JSON.stringify(r.j.data.summary):r.j&&r.j.message);

  // 电子协议全流程
  r=await api(admin.token,'/agreements','POST',{student_id:student.user.id, teacher_id:teacher.user.id, title:'测试实习协议'+Date.now(), content:'实习期间遵守安全规定...', start_date:addDays(1), end_date:addDays(120)});
  console.log('② 发起协议:',r.ok, r.ok?('id='+r.j.data.id):r.j&&r.j.message);
  const aid=r.ok&&r.j.data.id;
  if(aid){
    r=await api(student.token,`/agreements/${aid}/student-sign`,'PUT',{sign_name:'学生本人'});
    console.log('③ 学生签署:',r.ok, r.j&&r.j.message);
    r=await api(teacher.token,`/agreements/${aid}/teacher-sign`,'PUT');
    console.log('④ 教师会签:',r.ok, r.j&&r.j.message);
    r=await api(admin.token,`/agreements/${aid}/activate`,'PUT');
    console.log('⑤ 校方盖章生效:',r.ok, r.j&&r.j.message);
    r=await api(student.token,`/agreements/${aid}`);
    console.log('⑥ 学生查看协议:',r.ok, r.ok?('status='+r.j.data.status+' student_signed='+r.j.data.student_signed+' teacher_signed='+r.j.data.teacher_signed+' school_signed='+r.j.data.school_signed):r.j&&r.j.message);
  }

  // 多部分拍照打卡（构造一张极小 PNG）
  const png=Buffer.from('89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082','hex');
  const fd=new FormData();
  fd.append('latitude','28.21'); fd.append('longitude','112.94'); fd.append('address','拍照打卡测试');
  fd.append('photo', new Blob([png],{type:'image/png'}), 'checkin.png');
  const headers={Authorization:'Bearer '+student.token};
  const cres=await fetch(BASE+'/checkins',{method:'POST',headers,body:fd});
  let cj=null; try{cj=await cres.json()}catch(_){}
  console.log('⑦ 拍照打卡:',cres.status, cj&&cj.message, cj&&cj.data&&cj.data.photo_url?('photo='+cj.data.photo_url):'');
})().catch(e=>{console.error('FAIL',e.message);process.exit(1)});
