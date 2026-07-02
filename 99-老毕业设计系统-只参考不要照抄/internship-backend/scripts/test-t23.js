const BASE = 'http://localhost:3000/api';
async function api(token, path, method='GET', body){
  const headers={'Content-Type':'application/json'};
  if(token) headers.Authorization='Bearer '+token;
  const res=await fetch(BASE+path,{method,headers,body:body?JSON.stringify(body):undefined});
  let j=null; try{j=await res.json()}catch(_){}
  return {status:res.status,j,ok:res.ok&&j&&j.success};
}
async function login(u,p){const r=await api(null,'/users/login','POST',{username:u,password:p}); if(!r.ok) throw new Error('login '+u+' '+(r.j&&r.j.message)); return {token:r.j.data.token,user:r.j.data.user};}

(async()=>{
  const admin=await login('admin','123456');
  const teacher=await login('demo_teacher','demo1234');
  const student=await login('demo_stu1','demo1234');
  const sid=student.user.id, tid=teacher.user.id;
  console.log('登录OK stu=',sid,'tea=',tid,'\n--- 答辩管理 ---');

  // 答辩组
  let r=await api(admin.token,'/defense/groups','POST',{name:'软件工程答辩一组 '+Date.now(),defense_date:'2026-06-20',location:'实训楼301'});
  const gid=r.ok&&r.j.data.id; console.log('① 建答辩组:',r.ok,'gid='+gid);
  r=await api(admin.token,`/defense/groups/${gid}/committee`,'POST',{teacher_id:tid,role:'chair'}); console.log('② 加评委:',r.ok,r.j&&r.j.message);
  r=await api(admin.token,`/defense/groups/${gid}/members`,'POST',{student_id:sid,seq:1}); console.log('③ 加答辩学生:',r.ok,r.j&&r.j.message);
  r=await api(teacher.token,`/defense/groups/${gid}/students/${sid}/score`,'PUT',{score:88,comment:'结构清晰'}); console.log('④ 评委评分:',r.ok,r.j&&r.j.message);
  // 评委视角双盲
  r=await api(teacher.token,`/defense/groups/${gid}`); console.log('   评委视角 role=',r.ok&&r.j.data.role,' my_score=',r.ok&&r.j.data.members[0]&&r.j.data.members[0].my_score);
  r=await api(admin.token,`/defense/groups/${gid}/finalize`,'POST'); console.log('⑤ 汇总成绩:',r.ok,r.j&&r.j.message);
  r=await api(admin.token,`/defense/groups/${gid}`); const m=r.ok&&r.j.data.members[0]; console.log('   管理员视角 final_score=',m&&m.final_score,' scoresN=',m&&m.scores&&m.scores.length);
  r=await api(admin.token,`/defense/members/${m.id}/recommend`,'PUT',{recommended:1}); console.log('⑥ 推优:',r.ok,r.j&&r.j.message);

  console.log('\n--- 企业导师评价 ---');
  r=await api(admin.token,'/enterprise-evals','POST',{student_id:sid}); const token=r.ok&&r.j.data.token; console.log('⑦ 生成评价链接:',r.ok,'token='+(token?token.slice(0,8)+'…':'-'));
  r=await api(null,'/public/enterprise-eval/'+token); console.log('⑧ 公开读取(免登录):',r.ok, r.ok?('学生='+r.j.data.student_name+' status='+r.j.data.status):r.j&&r.j.message);
  r=await api(null,'/public/enterprise-eval/'+token); // (no-op)
  let pres=await fetch(BASE+'/public/enterprise-eval/'+token,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mentor_name:'张工',mentor_title:'技术主管',score_overall:5,score_attitude:5,score_skill:4,score_discipline:5,comment:'表现优秀'})});
  let pj=await pres.json(); console.log('⑨ 企业导师提交评价:',pj.success,pj.message);
  r=await api(admin.token,'/enterprise-evals'); console.log('   评价列表条数:',r.ok&&r.j.data.total);

  console.log('\n--- 质量报告 ---');
  r=await api(admin.token,'/quality-report'); console.log('⑩ 质量报告:',r.ok, r.ok?JSON.stringify({students:r.j.data.students,checkin:r.j.data.checkin,evalAvg:r.j.data.enterprise_eval.avg_overall,recommended:r.j.data.defense.recommended}):r.j&&r.j.message);

  console.log('\n--- 岗位智能匹配 ---');
  await api(admin.token,'/admin/users/'+sid,'PUT',{skill_tags:'java,web,数据库'});
  // 取一个企业建带标签岗位
  const ent=await api(admin.token,'/enterprises?page_size=1'); const entId=ent.j&&ent.j.data&&ent.j.data.list&&ent.j.data.list[0]&&ent.j.data.list[0].id;
  if(entId){ await api(admin.token,'/positions','POST',{enterprise_id:entId,title:'Java开发实习匹配测试',tags:'java,web,spring',description:'参与数据库与web开发'}); }
  r=await api(student.token,'/positions/recommend'); 
  if(r.ok){ const top=r.j.data.list[0]; console.log('⑪ 推荐岗位:',true,'hasTags='+r.j.data.hasTags,'top='+(top?(top.title+' score='+top.match_score+' tags='+JSON.stringify(top.match_tags)):'-')); }
  else console.log('⑪ 推荐岗位:',false,r.j&&r.j.message);
})().catch(e=>{console.error('FAIL',e.message);process.exit(1)});
