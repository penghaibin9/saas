import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileTemplate } from '@vue/compiler-sfc'
import { isDefiniteWriteRejection } from '../src/modules/academicAffairs/components/parallel-b/unconfirmedWrite.js'
import { page, deferred } from './academic-pc-parallel-b-harness.mjs'

const response = (list, total = list.length) => ({ code: 0, data: { list, total } })
const exam = { examId: '9007199254740999', examName: '虚构等级考试', status: 'CLOSED', passLine: 0 }
function mount(api = {}) {
  const { state } = page('AaLevelExamView', {
    academicAffairsLevelExamApi: api, isDefiniteWriteRejection,
    matchPermission: (patterns, code) => patterns.includes(code)
  }, {ctx:{currentRole:{roleName:'测试岗'},dataScope:{scope:'TENANT_ALL'},permissionPatterns:[]}})
  state.ctx.permissionPatterns = ['academicAffairs.levelExam.manage']
  return state
}

test('等级考试模板可编译，阶段与报名录分流程一致', () => {
  const source = readFileSync(new URL('../src/modules/academicAffairs/views/AaLevelExamView.vue', import.meta.url), 'utf8')
  const { descriptor, errors } = parse(source)
  assert.deepEqual(errors, [])
  assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: 'AaLevelExamView.vue', id: 'level-flow' }).errors, [])
  const vm = mount()
  assert.match(vm.stageSteps.join('、'), /学生报名与缴费确认/)
  assert.doesNotMatch(vm.stageSteps.join('、'), /圈课|编排/)
})

test('超过200人的报名可以按页读取，不丢失后续学生', async () => {
  const calls = []
  const vm = mount({ listRegs: async (id, params) => { calls.push({ id, ...params }); return response([{ regId: '201' }], 201) } })
  await vm.select(exam)
  await vm.changeRegPage(11)
  assert.equal(calls[1].page, 11)
  assert.equal(calls[1].pageSize, 20)
  assert.equal(vm.regPagination.total, 201)
  assert.equal(vm.regs[0].regId, '201')
})

test('考试列表翻页清掉旧详情及旧录分窗口', async () => {
  const calls = []
  const vm = mount({ listExams: async params => { calls.push(params); return response([{ ...exam, examId: '2' }], 21) } })
  vm.current = exam; vm.regs = [{ regId: '1' }]; vm.scoreVisible = true
  await vm.changePage(2)
  assert.equal(calls[0].page, 2)
  assert.equal(vm.current, null)
  assert.equal(vm.scoreVisible, false)
  assert.equal(vm.regs.length, 0)
})

test('名单读取失败不留旧学生，也不冒充空名单成功', async () => {
  const vm = mount({ listRegs: async () => { throw new Error('名单读取失败') } })
  vm.regs = [{ regId: 'old' }]
  await vm.select(exam)
  assert.equal(vm.regs.length, 0)
  assert.match(vm.detailError, /失败/)
  assert.equal(vm.detailLoading, false)
})

test('合格线为0仍按分数制，允许真实0分', async () => {
  const writes = []
  const vm = mount({ enterResult: async (id, body) => { writes.push({ id, body }); return { code: 0 } }, listRegs: async () => response([{ regId: '1', status: 'SCORED' }]) })
  vm.current = exam; vm.openScore({ regId: '1', studentName: '虚构学生' })
  await vm.submitScore()
  assert.equal(writes.length, 0)
  vm.scoreForm.score = 0
  await vm.submitScore()
  assert.equal(writes[0].body.score, 0)
  assert.equal(vm.saving, false)
})

test('录分网络异常保留填写内容并解除保存中状态', async () => {
  const vm = mount({ enterResult: async () => { throw new Error('网络中断') } })
  vm.current = exam; vm.openScore({ regId: '1' }); vm.scoreForm.score = 88
  await vm.submitScore()
  assert.equal(vm.scoreForm.score, 88)
  assert.equal(vm.scoreVisible, true)
  assert.equal(vm.saving, false)
  assert.match(vm.scoreError, /网络中断/)
})

test('没有权限或换考试后不能提交旧录分对象', async () => {
  let writes = 0
  const vm = mount({ enterResult: async () => { writes++; return { code: 0 } } })
  vm.current = exam; vm.openScore({ regId: '1' }); vm.scoreForm.score = 88
  vm.current = { ...exam, examId: '2' }; await vm.submitScore()
  assert.equal(writes, 0)
  vm.current = exam; vm.ctx.permissionPatterns = []; await vm.submitScore()
  assert.equal(writes, 0)
})

test('快速换页时旧名单不能覆盖新考试', async () => {
  const pending = deferred()
  const vm = mount({ listRegs: id => id === exam.examId ? pending.promise : Promise.resolve(response([{ regId: 'new' }])) })
  const old = vm.select(exam)
  await vm.select({ ...exam, examId: '2' })
  pending.resolve(response([{ regId: 'old' }]))
  await old
  assert.equal(vm.regs[0].regId, 'new')
})

test('创建异常保留表单且不锁死保存状态，双击只提交一次', async () => {
  const pending = deferred(); let writes = 0
  const vm = mount({ createExam: () => { writes++; return pending.promise } })
  vm.form.examName = '虚构考试'; vm.createVisible = true
  const first = vm.submitCreate(); await vm.submitCreate()
  pending.reject(new Error('连接中断')); await first
  assert.equal(writes, 1)
  assert.equal(vm.saving, false)
  assert.equal(vm.form.examName, '虚构考试')
  assert.equal(vm.createVisible, true)
})


test('等级考试身份切换清空旧名单、草稿和确认窗口，旧请求不能回灌', async()=>{
 const pending=deferred();const vm=mount({listRegs:()=>pending.promise})
 const read=vm.select(exam);vm.scoreForm.score=88;vm.scoreVisible=true;vm.confirmVisible=true
 vm.ctx={...vm.ctx,currentRole:{roleCode:'OTHER'},permissionPatterns:[]};vm.resetIdentity()
 pending.resolve(response([{regId:'old'}]));await read
 assert.equal(vm.regs.length,0);assert.equal(vm.current,null);assert.equal(vm.scoreForm.score,null)
 assert.equal(vm.scoreVisible,false);assert.equal(vm.confirmVisible,false)
})

test('等级考试旧身份写回执不触发新身份读取或覆盖错误',async()=>{
 const pending=deferred();let reads=0
 const vm=mount({createExam:()=>pending.promise,listExams:async()=>{reads++;return response([])}})
 vm.form.examName='虚构考试';const writing=vm.submitCreate()
 vm.ctx={...vm.ctx,currentRole:{roleCode:'OTHER'},permissionPatterns:[]};vm.resetIdentity();vm.error='新身份错误'
 pending.resolve({code:0,data:{examId:'1'}});await writing
 assert.equal(reads,0);assert.equal(vm.error,'新身份错误');assert.equal(vm.saving,false)
})

test('学院即使持有管理权限也不显示等级考试学校管理操作',()=>{
 const vm=mount();vm.ctx.dataScope.scope='COLLEGE';assert.equal(vm.canManage,false)
})


test('等级考试写入超时后阻止再次提交，核对只发送读取',async()=>{
 let posts=0,reads=0
 const vm=mount({createExam:async()=>{posts++;throw new Error('连接中断')},listExams:async()=>{reads++;return response([])}})
 vm.form.examName='虚构考试';await vm.submitCreate();await vm.submitCreate();await vm.verifyLevelCommand()
 assert.equal(posts,1);assert.equal(reads,1);assert.ok(vm.levelPending);assert.equal(vm.form.examName,'虚构考试')
})

test('等级考试已受理但录分回读失败，保留草稿，核对成功才关闭',async()=>{
 let posts=0,fail=true
 const formal={regId:'1',status:'SCORED',score:88,result:'PASS',certNo:null}
 const vm=mount({enterResult:async()=>{posts++;return {code:0,data:formal}},listRegs:async()=>{if(fail)throw new Error('读取失败');return response([formal])}})
 vm.current=exam;vm.openScore({regId:'1'});vm.scoreForm.score=88
 await vm.submitScore();assert.equal(vm.scoreVisible,true);assert.equal(vm.scoreForm.score,88)
 await vm.submitScore();assert.equal(posts,1)
 fail=false;await vm.verifyLevelCommand();assert.equal(vm.levelPending,null);assert.equal(vm.scoreVisible,false)
})

test('等级考试明确校验拒绝可修改后重试，不永久锁住办理',async()=>{
 let posts=0
 const vm=mount({createExam:async()=>{posts++;return {code:422,message:'名称不正确'}}})
 vm.form.examName='虚构考试';await vm.submitCreate();await vm.submitCreate()
 assert.equal(posts,2);assert.equal(vm.levelPending,null)
})
