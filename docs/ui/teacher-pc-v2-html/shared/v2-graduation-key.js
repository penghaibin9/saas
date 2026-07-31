(function(){'use strict';

const P=window.V2_PAGE||{};
const I='../shared/icons.svg#';

const WORKSPACES=[
  {key:'workbench',label:'我的工作台',file:'overview.html',route:'/admin/graduation',permission:'graduationDesign.dashboard.view'},
  {key:'batch',label:'批次与实施',file:'batch-implementation.html',route:'/admin/graduation/batches?panel=list',permission:'graduationDesign.batch.view'},
  {key:'topic',label:'题目与选题',file:'topic.html',route:'/admin/graduation/topic-lib',permission:'graduationDesign.topic.lib'},
  {key:'process',label:'过程指导',file:'process.html',route:'/admin/graduation/process?panel=taskbook',permission:'graduationDesign.guidance.view'},
  {key:'proposalFinal',label:'开题与成果',file:'proposal-final.html',route:'/admin/graduation/proposals',permission:'graduationDesign.proposal.view'},
  {key:'defense',label:'答辩与成绩',file:'defense.html',route:'/admin/graduation/defense',permission:'graduationDesign.defense.view'},
  {key:'riskArchive',label:'风险与归档',file:'risk-archive.html',route:'/admin/graduation/risk-archive?panel=risk',permission:'graduationDesign.riskArchive.manage'},
  {key:'templates',label:'模板与设置',file:'templates.html',route:'/admin/graduation/templates',permission:'graduationDesign.template.manage'}
];

const META={
  workbench:{
    title:'我的工作台',
    desc:'按当前角色、批次与数据范围聚合本人待办、关键进度、风险和同口径下钻。',
    role:'毕设管理员 / 学院 / 指导教师 / 评阅教师',
    scope:'当前授权批次与本人职责范围',
    boundary:'工作台只聚合生产事实，不复制各工作区主数据；每个数字必须保留批次、范围、口径和下钻目标。'
  },
  batch:{
    title:'批次与实施',
    desc:'管理批次、阶段时间轴、规则、学生资格、导师名单、学生分配与冲突检测。',
    role:'毕设管理员 / 学院管理员',
    scope:'授权批次、学院、专业与学生',
    boundary:'批次规则与时间轴必须版本化；资格、导师准入、学生分配和冲突处理是独立事实，不能用前端临时选择覆盖正式关系。'
  },
  topic:{
    title:'题目与选题',
    desc:'贯通题目库、待审核题目、选题轮次、学生志愿、匹配结果、容量冲突和题目调整。',
    role:'毕设管理员 / 学院 / 指导教师',
    scope:'授权批次、专业、导师和学生',
    boundary:'题目申报、审核、发布、学生志愿、匹配、确认和最终结果相互分离；容量、专业、导师上限和重复分配冲突必须阻断。'
  },
  process:{
    title:'过程指导',
    desc:'统一承载规范流程、任务书、指导记录、指导计划、导师评价和中期检查。',
    role:'指导教师 / 学院管理员',
    scope:'本人指导学生或授权学院范围',
    boundary:'任务书、计划、指导记录、评价和中期检查均追加版本与证据；任何延期或整改都不得静默改写原截止时间和原结论。'
  },
  proposalFinal:{
    title:'开题与成果',
    desc:'处理开题批阅、成果提交与批阅、查重记录、教师评阅和成果互查整改。',
    role:'指导教师 / 评阅教师 / 学院管理员',
    scope:'本人任务或授权学生范围',
    boundary:'开题、初稿、定稿、查重证据、教师评阅和互查整改是不同事实；查重结果不能自动生成学术结论，退回重交不能覆盖旧版本。'
  },
  defense:{
    title:'答辩与成绩',
    desc:'贯通答辩安排、延期答辩、评委评分、秘书确认、成绩台账、优秀成果与更正申诉。',
    role:'答辩管理员 / 评委 / 答辩秘书 / 学院',
    scope:'授权批次、答辩组与评分任务',
    boundary:'答辩发布前重检人员、回避、时间、场地和容量；评分提交、秘书确认、成绩汇总、发布、优秀认定与更正申诉保持分离。'
  },
  riskArchive:{
    title:'风险与归档',
    desc:'集中处理问题预警、毕设材料归档和同口径统计。',
    role:'毕设管理员 / 学院 / 归档审计人员',
    scope:'授权批次与已办结学生范围',
    boundary:'风险必须保留来源、责任人与处置时限；归档只收最终版本和完整审计，缺材料时输出缺失清单而不是伪完整档案。'
  },
  templates:{
    title:'模板与设置',
    desc:'维护材料模板、任务书模板、开题模板和全部模板版本。',
    role:'毕设模板管理员',
    scope:'学校或租户级模板管理范围',
    boundary:'模板版本只影响明确绑定的新任务或新批次；已发布批次和历史材料必须继续引用原模板版本，不得被后续编辑追溯改写。'
  }
};

const svg=(name)=>`<svg aria-hidden="true"><use href="${I}${name}"></use></svg>`;
const badge=(text,cls='')=>`<span class="v2-badge ${cls}">${text}</span>`;
const action=(text,href,cls='')=>`<a class="v2-btn ${cls}" href="${href}">${text}</a>`;
const button=(text,cls='',attrs='')=>`<button type="button" class="v2-btn ${cls}" ${attrs}>${text}</button>`;
const table=(heads,rows,width=980)=>`<div class="v2-table-wrap"><table class="v2-table" style="min-width:${width}px"><thead><tr>${heads.map(x=>`<th>${x}</th>`).join('')}</tr></thead><tbody>${rows.map(row=>`<tr>${row.map((x,i)=>`<td${i===row.length-1?' class="actions"':''}>${x}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
const pager=`<div class="v2-pager"><span class="v2-note">共 — 条 · 服务端分页</span><button type="button" class="v2-page-no active">1</button><button type="button" class="v2-page-no">2</button><button type="button" class="v2-page-no">›</button></div>`;
const kpis=(items)=>`<div class="v2-gr-kpis v2-section">${items.map(([label,value,note,cls=''])=>`<article class="v2-gr-kpi ${cls}"><small>${label}</small><strong>${value}</strong><span>${note}</span></article>`).join('')}</div>`;
const progress=(items,current=2)=>`<div class="v2-gr-progress">${items.map((label,i)=>`<div class="${i<current?'done':i===current?'current':''}"><span>${i+1}</span><b>${label}</b></div>`).join('')}</div>`;
const filter=(extra='')=>`<section class="v2-card v2-filter v2-section"><div class="v2-field"><label>毕业设计批次</label><select class="v2-select"><option>当前授权批次</option></select></div><div class="v2-field"><label>学院 / 专业 / 状态</label><select class="v2-select"><option>全部可见范围</option></select></div><div class="v2-field grow"><label>关键词</label><input class="v2-input" placeholder="学生 / 导师 / 题目 / 材料"/></div>${button('查询','primary')}${button('重置')}${extra}</section>`;

const stateButtons=`<div class="v2-state-tools"><button type="button" data-state-button="ready" class="active">默认</button><button type="button" data-state-button="loading">加载</button><button type="button" data-state-button="empty">空</button><button type="button" data-state-button="error">错误</button><button type="button" data-state-button="unauthorized">403/只读</button><button type="button" data-state-button="long">长数据</button></div>`;
const states=(name)=>`<section class="v2-state" data-prototype-state="loading"><div class="v2-state-card"><span class="v2-spinner"></span><h3>正在加载${name}</h3><p>等待真实批次、权限、数据范围和业务数据。</p></div></section><section class="v2-state" data-prototype-state="empty"><div class="v2-state-card">${svg('i-inbox')}<h3>当前范围暂无记录</h3><p>区分未建批次、无权限、无数据范围和真实空数据。</p></div></section><section class="v2-state" data-prototype-state="error"><div class="v2-state-card">${svg('i-alert')}<h3>${name}加载失败</h3><p>保留当前批次和筛选条件，不把接口失败显示成 0。</p>${button('重新加载','primary')}</div></section><section class="v2-state" data-prototype-state="unauthorized"><div class="v2-state-card">${svg('i-lock')}<h3>无权限、无数据范围或当前阶段只读</h3><p>菜单、按钮、批次状态与后端权限必须同口径；不回退到全校数据。</p></div></section><section class="v2-state" data-prototype-state="long"><div class="v2-state-card"><h3>大批次与长数据状态</h3><p>学生、题目、材料、答辩和成绩均使用服务端分页；宽表只在容器内滚动。</p></div></section>`;

function workbench(){
  return kpis([
    ['本人待办','—','按角色与任务池'],
    ['批次学生','—','当前授权范围'],
    ['待评阅开题','—','本人任务','warning'],
    ['待评阅成果','—','本人任务','warning'],
    ['答辩评分待办','—','本人答辩组','danger'],
    ['过程风险','—','逾期 / 缺项','danger'],
    ['待归档学生','—','已办结未归档'],
    ['统计更新时间','—','后端返回新鲜度']
  ])+`<section class="v2-card v2-panel v2-section"><div class="v2-table-toolbar"><div><h2>当前批次主链</h2><p class="v2-note">所有卡片继承同一批次和数据范围。</p></div>${action('查看批次','/admin/graduation/batches?panel=list')}</div>${progress(['批次实施','题目选题','过程指导','开题成果','答辩成绩','风险归档'],2)}</section><div class="v2-gr-layout v2-section"><section class="v2-card v2-panel"><h2>今日任务</h2><div class="v2-gr-checks"><article class="v2-gr-check block"><span>!</span><div><b>开题待评阅</b><small>只统计分配给本人的有效任务</small></div>${action('进入队列','/admin/graduation/proposals?tab=PENDING_REVIEW','primary')}</article><article class="v2-gr-check"><span>✓</span><div><b>成果待评阅</b><small>初稿、定稿和教师评阅分开</small></div>${action('进入队列','/admin/graduation/finals?tab=PENDING_REVIEW')}</article><article class="v2-gr-check block"><span>!</span><div><b>答辩评分待提交</b><small>评委回避校验通过后才能评分</small></div>${action('去评分','/admin/graduation/defense-scoring')}</article><article class="v2-gr-check"><span>✓</span><div><b>统计与审计</b><small>同口径报表与操作日志</small></div>${action('查看统计','/admin/graduation/stats-report')}</article></div></section><aside class="v2-card v2-panel"><h2>数据可信说明</h2><div class="v2-stats-definition"><article><b>不是第二套业务台账</b><small>工作台只聚合，不复制开题、成果、评分或归档记录。</small></article><article><b>下钻保持同一范围</b><small>批次、学院、专业、角色和时间条件必须传递。</small></article><article><b>失败不等于零</b><small>接口错误、无范围和真实零值使用不同状态。</small></article></div></aside></div>`;
}

function batch(){
  return kpis([
    ['有效批次','—','当前学年'],
    ['阶段配置','—','规则版本'],
    ['批次学生','—','名单范围'],
    ['资格待认定','—','学生任务','warning'],
    ['导师待准入','—','导师名单','warning'],
    ['分配冲突','—','上限 / 重复','danger']
  ])+`<section class="v2-card v2-panel v2-section"><h2>批次实施链</h2>${progress(['创建批次','阶段时间轴','规则配置','学生名单','资格认定','导师名单','学生分配','冲突收口'],3)}</section>${filter(action('批次列表','/admin/graduation/batches?panel=list')+action('阶段配置','/admin/graduation/batches?panel=stages')+action('规则配置','/admin/graduation/batches?panel=rules'))}<section class="v2-card v2-table-card v2-section">${table(['批次 / 学年','阶段版本','学生范围','资格完成','导师完成','分配完成','冲突','操作'],[['2026届毕业设计','v3','软件技术等 3 专业','— / —','— / —','— / —',badge('待扫描','warning'),action('查看批次','/admin/graduation/batches?panel=list')],['2025届毕业设计','v5','已归档范围','— / —','— / —','— / —',badge('只读','success'),action('查看历史','/admin/graduation/batches?panel=list')]])}${pager}</section><div class="v2-gr-layout v2-section"><section class="v2-card v2-panel"><h2>实施任务</h2><div class="v2-gr-checks"><article class="v2-gr-check"><span>1</span><div><b>学生资格认定</b><small>资格结论、依据与操作人留痕</small></div>${action('进入名单','/admin/graduation/students?panel=eligibility')}</article><article class="v2-gr-check"><span>2</span><div><b>导师名单与准入</b><small>导师资格、专业范围和指导上限</small></div>${action('导师名单','/admin/graduation/mentors?panel=list')}</article><article class="v2-gr-check block"><span>!</span><div><b>学生分配冲突</b><small>重复分配、导师超限和范围冲突</small></div>${action('冲突检测','/admin/graduation/mentors/conflicts','primary')}</article></div></section><aside class="v2-card v2-panel"><h2>批次纪律</h2><p class="v2-note">阶段时间轴和规则修改形成新版本；已启动或已归档批次不得被后续设置静默追溯改写。</p></aside></div>`;
}

function topic(){
  return kpis([
    ['题目库','—','当前批次'],
    ['待审核题目','—','学院审核','warning'],
    ['已发布题目','—','可选范围'],
    ['未选题学生','—','需跟进','danger'],
    ['匹配待确认','—','轮次结果'],
    ['容量冲突','—','阻断最终结果','danger']
  ])+`<section class="v2-card v2-panel v2-section"><h2>题目与选题状态链</h2>${progress(['题目申报','题目审核','题目发布','学生志愿','匹配计算','结果确认','冲突复核','题目调整'],3)}</section>${filter(action('题目列表','/admin/graduation/topic-lib?panel=list')+action('待审核题目','/admin/graduation/topic-lib?panel=pending')+action('选题轮次','/admin/graduation/topic-rounds?panel=rounds'))}<section class="v2-card v2-table-card v2-section">${table(['题目','申报导师','适用专业','容量','审核 / 发布','学生志愿','匹配结果','操作'],[['题目 A','导师 A','软件技术','3',badge('已发布','success'),'—',badge('待匹配','warning'),action('题目详情','/admin/graduation/topic-lib?panel=list')],['题目 B','导师 B','大数据技术','2',badge('待审核','warning'),'—','未开放',action('审核队列','/admin/graduation/topic-lib?panel=pending')],['题目 C','导师 C','跨专业候选','1',badge('已发布','success'),'—',badge('容量冲突','danger'),action('冲突复核','/admin/graduation/topic-rounds?panel=conflicts','primary')]])}${pager}</section><div class="v2-gr-rule v2-section">学生志愿和匹配结果不是最终分配。确认前必须重新检查题目容量、导师指导上限、专业范围、重复分配和题目调整中的并发版本。</div>`;
}

function processWorkspace(){
  return kpis([
    ['任务书待确认','—','当前阶段','warning'],
    ['指导计划','—','本人学生'],
    ['本周指导记录','—','真实提交'],
    ['中期待检查','—','需处理','warning'],
    ['逾期里程碑','—','风险学生','danger'],
    ['整改未闭环','—','责任与时限','danger']
  ])+`<section class="v2-card v2-panel v2-section"><h2>过程指导工作区</h2>${progress(['规范流程','任务书','指导计划','指导记录','里程碑证据','中期检查','问题整改','阶段完成'],3)}</section>${filter(action('任务书','/admin/graduation/process?panel=taskbook')+action('指导记录','/admin/graduation/process?panel=guidance')+action('中期检查','/admin/graduation/process?panel=midterm'))}<section class="v2-card v2-table-card v2-section">${table(['学生','任务书版本','指导计划','最近指导','中期检查','问题 / 整改','状态','操作'],[['学生 A','v2','已确认','2026-07-30',badge('待检查','warning'),'无',badge('进行中'),action('指导记录','/admin/graduation/process?panel=guidance')],['学生 B','v1','待确认','2026-07-22','未开始',badge('里程碑逾期','danger'),badge('需跟进','danger'),action('查看计划','/admin/graduation/process?panel=plan','primary')],['学生 C','v3','已确认','2026-07-29',badge('整改中','warning'),'问题单 #—',badge('整改中','warning'),action('中期检查','/admin/graduation/process?panel=midterm')]])}${pager}</section><div class="v2-gr-rule v2-section">任务书、指导计划、指导记录、导师评价和中期检查均追加历史。延期审批只能生成新的有效截止时间，不能覆盖原截止和原证据。</div>`;
}

function proposalFinal(){
  return kpis([
    ['开题待评阅','—','本人任务','warning'],
    ['开题退回待重交','—','旧版本保留','danger'],
    ['成果待批阅','—','初稿 / 定稿','warning'],
    ['查重记录待核','—','证据'],
    ['教师评阅待完成','—','分配任务','warning'],
    ['互查整改未闭环','—','整改版本','danger']
  ])+`<section class="v2-card v2-panel v2-section"><h2>开题与成果材料链</h2>${progress(['开题提交','开题批阅','退回重交','初稿提交','定稿提交','查重证据','教师评阅','互查整改'],2)}</section>${filter(action('开题批阅','/admin/graduation/proposals')+action('成果批阅','/admin/graduation/finals')+action('查重台账','/admin/graduation/plagiarism-ledger'))}<section class="v2-card v2-table-card v2-section">${table(['学生','开题版本 / 状态','成果版本 / 状态','查重证据','教师评阅','互查整改','完整性','操作'],[['学生 A','v2 / '+badge('待评阅','warning'),'初稿 v1 / 待定稿','报告 #—','未分配','无',badge('待补齐','warning'),action('开题批阅','/admin/graduation/proposals')],['学生 B','v3 / '+badge('已通过','success'),'定稿 v2 / '+badge('待批阅','warning'),'18% / 报告 #—','待评阅','无',badge('材料完整','success'),action('成果批阅','/admin/graduation/finals','primary')],['学生 C','v2 / '+badge('已通过','success'),'定稿 v3 / 已评阅','复核完成','已完成',badge('整改中','warning'),badge('未闭环','danger'),action('互查整改','/admin/graduation/more?panel=peer')]])}${pager}</section><div class="v2-gr-rule v2-section">开题通过不代表成果通过；初稿、定稿、查重报告、教师评阅和互查整改各自保留版本。查重比例只是证据，不自动生成学术合格或不合格结论。</div>`;
}

function defense(){
  return kpis([
    ['答辩组','—','当前批次'],
    ['待分配学生','—','容量校验','warning'],
    ['回避冲突','—','发布阻断','danger'],
    ['我的评分待办','—','评委任务','warning'],
    ['秘书待确认','—','评分确认','warning'],
    ['成绩缺项','—','阻断台账','danger'],
    ['优秀成果待认定','—','独立流程'],
    ['更正申诉待处理','—','发布后流程','danger']
  ])+`<section class="v2-card v2-panel v2-section"><h2>答辩与成绩状态链</h2>${progress(['答辩安排','学生分配','回避预检','计划发布','评委评分','秘书确认','成绩台账','更正申诉'],2)}</section>${filter(action('答辩安排','/admin/graduation/defense')+action('我的评分','/admin/graduation/defense-scoring')+action('成绩台账','/admin/graduation/grade-ledger'))}<div class="v2-gr-layout v2-section"><section class="v2-card v2-panel"><h2>发布前核验</h2><div class="v2-gr-checks"><article class="v2-gr-check"><span>✓</span><div><b>答辩组和容量</b><small>成员、角色与学生上限完整</small></div>${badge('通过','success')}</article><article class="v2-gr-check block"><span>!</span><div><b>评委回避</b><small>指导关系或利益冲突待处理</small></div>${badge('阻断','danger')}</article><article class="v2-gr-check block"><span>!</span><div><b>时间与场地</b><small>发布时重新读取最新冲突事实</small></div>${badge('阻断','danger')}</article><article class="v2-gr-check"><span>✓</span><div><b>成绩规则</b><small>评分项、确认节点与缺项处理已冻结</small></div>${badge('已配置','success')}</article></div></section><aside class="v2-card v2-panel"><h2>成绩边界</h2><p class="v2-note">评委评分提交后仍需秘书确认；成绩台账、优秀成果认定和发布后更正申诉分别受独立权限与状态机控制。</p></aside></div><section class="v2-card v2-table-card v2-section">${table(['学生','答辩组','评委评分','秘书确认','综合成绩','台账状态','异常','操作'],[['学生 A','第一组','已提交','待确认','—',badge('阻断','warning'),'无',action('秘书确认','/admin/graduation/defense-confirmation')],['学生 B','第二组','缺 1 项','不可确认','—',badge('缺项','danger'),'评分缺失',action('评分任务','/admin/graduation/defense-scoring','primary')],['学生 C','第三组','已提交','已确认','—',badge('待发布','warning'),'无',action('成绩台账','/admin/graduation/grade-ledger')]])}${pager}</section>`;
}

function riskArchive(){
  return kpis([
    ['过程预警','—','来源去重','danger'],
    ['逾期未闭环','—','责任与时限','danger'],
    ['待归档学生','—','已办结'],
    ['材料完整','—','可生成档案'],
    ['缺失材料','—','阻断完整包','danger'],
    ['统计更新时间','—','同口径聚合']
  ])+`${filter(action('问题预警','/admin/graduation/risk-archive?panel=risk')+action('材料归档','/admin/graduation/risk-archive?panel=archive')+action('毕设统计','/admin/graduation/stats-report'))}<div class="v2-gr-layout v2-section"><section class="v2-card v2-panel"><h2>风险处置</h2><div class="v2-gr-checks"><article class="v2-gr-check block"><span>!</span><div><b>里程碑逾期</b><small>来源、学生、责任人、截止和升级记录</small></div>${action('进入预警','/admin/graduation/risk-archive?panel=risk','primary')}</article><article class="v2-gr-check block"><span>!</span><div><b>答辩冲突未闭环</b><small>不能只在前端标记“已知晓”</small></div>${badge('阻断','danger')}</article><article class="v2-gr-check"><span>✓</span><div><b>风险关闭</b><small>证据、结论与关闭人完整</small></div>${badge('可归档','success')}</article></div></section><aside class="v2-card v2-panel"><h2>归档完整性</h2><div class="v2-gr-checks"><article class="v2-gr-check"><span>✓</span><div><b>最终题目与开题</b><small>引用最终有效版本</small></div>${badge('完整','success')}</article><article class="v2-gr-check block"><span>!</span><div><b>教师评阅缺失</b><small>生成缺失清单，不生成假完整包</small></div>${badge('阻断','danger')}</article><article class="v2-gr-check"><span>✓</span><div><b>下载保护</b><small>用途、水印、权限、范围与审计</small></div>${badge('必需')}</article></div></aside></div><section class="v2-card v2-table-card v2-section">${table(['学生','风险状态','材料完整度','最终版本','归档状态','缺失项','下载','操作'],[['学生 A',badge('已关闭','success'),'完整','已锁定',badge('可归档','success'),'无','填写用途',action('归档工作区','/admin/graduation/risk-archive?panel=archive')],['学生 B',badge('处理中','warning'),'缺 2 项','未锁定',badge('阻断','danger'),'评阅 / 答辩记录','不可下载',action('查看缺失','/admin/graduation/risk-archive?panel=archive','primary')]])}${pager}</section>`;
}

function templates(){
  return kpis([
    ['材料模板','—','有效版本'],
    ['任务书模板','—','有效版本'],
    ['开题模板','—','有效版本'],
    ['草稿版本','—','未发布'],
    ['已绑定批次','—','只读引用'],
    ['待停用模板','—','影响分析','warning']
  ])+`${filter(action('材料模板','/admin/graduation/templates?type=MATERIAL')+action('任务书模板','/admin/graduation/templates?type=TASKBOOK')+action('开题模板','/admin/graduation/templates?type=PROPOSAL'))}<section class="v2-card v2-table-card v2-section">${table(['模板','类型','当前版本','状态','已绑定批次','更新时间','影响边界','操作'],[['毕业设计材料清单','材料模板','v4',badge('已发布','success'),'2','2026-07-20','新绑定任务使用 v4',action('查看模板','/admin/graduation/templates?type=MATERIAL')],['任务书标准模板','任务书模板','v3',badge('草稿','warning'),'1','2026-07-28','历史任务继续引用 v2',action('编辑草稿','/admin/graduation/templates?type=TASKBOOK')],['开题报告模板','开题模板','v5',badge('已发布','success'),'3','2026-07-18','停用前需影响分析',action('查看模板','/admin/graduation/templates?type=PROPOSAL')]])}${pager}</section><div class="v2-gr-layout v2-section"><section class="v2-card v2-panel"><h2>版本纪律</h2><div class="v2-gr-checks"><article class="v2-gr-check"><span>1</span><div><b>草稿编辑</b><small>只影响当前草稿版本</small></div>${badge('可编辑')}</article><article class="v2-gr-check"><span>2</span><div><b>发布新版本</b><small>新任务或明确迁移后使用</small></div>${badge('需确认','warning')}</article><article class="v2-gr-check"><span>3</span><div><b>历史引用锁定</b><small>已提交材料继续关联原版本</small></div>${badge('只读','success')}</article></div></section><aside class="v2-card v2-panel"><h2>禁止行为</h2><p class="v2-note">不得因为管理员更新模板，就追溯替换已发布批次、已下发任务书、已提交开题或已归档材料中的历史模板版本。</p></aside></div>`;
}

const RENDERERS={workbench,batch,topic,process:processWorkspace,proposalFinal,defense,riskArchive,templates};
const key=WORKSPACES.some(x=>x.key===P.active)?P.active:'workbench';
const current=WORKSPACES.find(x=>x.key===key);
const meta=META[key];
const ready=RENDERERS[key]();

const top=`<header class="v2-topbar"><div class="v2-brand"><span class="v2-brand-mark">跃</span><div><strong>校园综合管理平台</strong><small>Teacher PC V2 原型库</small></div></div><nav class="v2-centers"><a>工作台</a><a>学工中心</a><a>教务中心</a><a class="active">毕业设计中心</a><a>岗位实习中心</a><a>系统管理</a></nav><div class="v2-top-actions">${svg('i-search')}${svg('i-bell')}<span class="v2-avatar">毕</span></div></header>`;
const side=`<aside class="v2-sidebar"><div class="v2-side-head"><b>毕业设计中心</b><button type="button" data-v2-sidebar-toggle aria-expanded="true">‹</button></div><div class="v2-side-search">${svg('i-search')}<input data-v2-side-search placeholder="搜索工作区"/></div><nav class="v2-side-nav">${WORKSPACES.map(ws=>`<a class="${ws.key===key?'active':''}" data-v2-module-label="${ws.label}" href="${ws.file}">${svg(ws.key===key?'i-grid':'i-folder')}<span>${ws.label}</span>${ws.key===key?'<i></i>':''}</a>`).join('')}</nav><div class="v2-side-search-empty" hidden>未找到工作区</div></aside>`;
const tabs=`<nav class="v2-gr-tabs" aria-label="毕业设计工作区">${WORKSPACES.map(ws=>`<a class="v2-gr-tab ${ws.key===key?'active':''}" href="${ws.file}">${ws.label}</a>`).join('')}</nav>`;

document.body.dataset.theme='academy';
document.body.innerHTML=`<div class="v2-app">${top}<div class="v2-layout">${side}<main class="v2-content"><div class="v2-page"><div class="v2-breadcrumb">毕业设计中心 / ${meta.title}</div><div class="v2-main-grid"><div><section class="v2-page-head"><div class="v2-page-title"><span class="v2-page-title-icon">${svg(key==='defense'?'i-calendar':key==='riskArchive'?'i-archive':key==='templates'?'i-settings':'i-grid')}</span><div><h1>${meta.title}</h1><p>${meta.desc}</p></div></div><div class="v2-head-actions"><span class="v2-soft-chip">生产工作区：${current.key}</span><span class="v2-soft-chip">角色：${meta.role}</span><span class="v2-soft-chip">范围：${meta.scope}</span><span class="v2-soft-chip">权限：${P.permission||current.permission}</span></div></section>${tabs}<section class="v2-state active" data-prototype-state="ready">${ready}</section>${states(meta.title)}</div><aside class="v2-context"><section class="v2-card v2-context-card"><h2>原型状态</h2>${stateButtons}</section><section class="v2-card v2-context-card"><h2>生产入口</h2><p class="v2-note"><code>${current.route}</code></p>${action('打开生产路由',current.route,'primary')}</section><section class="v2-card v2-context-card"><h2>本页边界</h2><p class="v2-note">${meta.boundary}</p></section><section class="v2-card v2-context-card"><h2>统一纪律</h2><ul class="v2-plain-list"><li>批次上下文贯穿全部工作区。</li><li>学生与教师身份来自统一主档。</li><li>材料、规则、计划与成绩保留版本。</li><li>冲突与缺项不能由前端静默绕过。</li><li>下载受权限、范围、用途、水印和审计约束。</li></ul></section><section class="v2-card v2-context-card"><h2>数据说明</h2><p class="v2-note">数值均为中性占位；真实字段、状态、权限和 API 以生产代码为准。</p></section></aside></div></div></main></div></div>`;

const sidebar=document.querySelector('.v2-sidebar');
const nav=sidebar.querySelector('.v2-side-nav');
const search=sidebar.querySelector('[data-v2-side-search]');
const empty=sidebar.querySelector('.v2-side-search-empty');

search.addEventListener('input',()=>{
  const query=search.value.trim().toLowerCase();
  let visible=0;
  nav.querySelectorAll('a').forEach(link=>{
    const hit=!query||link.dataset.v2ModuleLabel.toLowerCase().includes(query);
    link.hidden=!hit;
    if(hit) visible+=1;
  });
  empty.hidden=visible>0;
});

sidebar.querySelector('[data-v2-sidebar-toggle]').addEventListener('click',(event)=>{
  const collapsed=!sidebar.classList.contains('is-collapsed');
  sidebar.classList.toggle('is-collapsed',collapsed);
  document.querySelector('.v2-layout').classList.toggle('is-sidebar-collapsed',collapsed);
  event.currentTarget.setAttribute('aria-expanded',String(!collapsed));
  event.currentTarget.textContent=collapsed?'›':'‹';
});

document.addEventListener('click',(event)=>{
  const trigger=event.target.closest('[data-state-button]');
  if(!trigger) return;
  document.querySelectorAll('[data-prototype-state]').forEach(section=>{
    section.classList.toggle('active',section.dataset.prototypeState===trigger.dataset.stateButton);
  });
  document.querySelectorAll('[data-state-button]').forEach(buttonEl=>{
    buttonEl.classList.toggle('active',buttonEl===trigger);
  });
});

})();