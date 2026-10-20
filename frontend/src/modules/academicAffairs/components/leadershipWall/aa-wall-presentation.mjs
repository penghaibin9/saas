import { STATE_LABELS } from './aa-wall-data.mjs';

export const SOURCE_LABELS = {term:'当前学期',reminders:'教学运行与待办',readiness:'开学与教学准备检查',quality:'教学质量统计'};
const EXPLANATIONS = {
  teacherCount:'按今日课表中的教师去重统计，不代表实际到课人数。',
  classCount:'按今日课表中的班级去重统计，不代表上课学生人数。',
  occupiedRooms:'今日课表或已批准预约使用的可用教室数，同一间教室只计一次，不代表此刻实时占用。',
  gradeSubmittedRate:'已提交、教务审核中及已发布的成绩任务数 ÷ 全部成绩任务数 × 100%。按累计任务统计，已归档任务不计入已提交数量。',
  pendingChanges:'已提交、学院审核中及教务审核中的调停课申请总数。',
  warningCount:'当前有效且待处置的学业预警记录数，同一名学生可能有多条记录。',
  adjustedToday:'今日有效课表中与调停课关联的课位数，一份申请可能涉及多个课位。',
  examToday:'今天已安排或已发布的考试课程数。',
  roomTexts:'今日课表中填写的不同教室名称数量，用于核对教室资料。',
  roomTotal:'当前设置为可用的教室数量，不包含停用或尚未录入的教室。',
  roomRate:'今日使用的可用教室数 ÷ 可用教室总数 × 100%。尚未配置教室时暂不计算比例。',
  gradeTotal:'当前学校范围内的累计成绩任务数。',
  gradeSubmitted:'已提交、教务审核中及已发布的成绩任务合计，与成绩提交率使用相同统计范围。',
  gradeArchived:'已经归档的成绩任务单独计数，不加入成绩提交率的已提交数量。',
  examUpcoming:'近期日期范围内已安排或已发布的考试课程总数；大屏展示部分明细，可进入考务工作区查看全部。',
  programRate:'已发布或已启用的培养方案数 ÷ 全部培养方案数 × 100%，按累计方案统计。',
  enabledCourses:'当前已启用的课程数量。',
  qualityWarnings:'尚未关闭的学业预警总数，包括办理中的记录，与待处置预警数量不同。'
};
export const metricDescription = metric => EXPLANATIONS[metric.id] || metric.definition || '该指标暂未提供统计说明。';
export const stateLabel = state => STATE_LABELS[state] || '待确认';
export function previewMessage(kind, metadata, metrics) {
  const state=metadata.previews?.[kind] || 'MISSING';
  if(state==='NO_DATA') {
    if(kind==='courses')return ['今日暂无课程安排','发布覆盖今日的课表后，课程将在这里自动显示。'];
    if(kind==='exams')return ['近期暂无考试安排',`未来${metadata.examWindow??14}天暂无已安排或已发布的考试。`];
    return metrics.roomTotal?.value===0
      ? ['教室资料待配置','在教室资源中维护可用教室后，自动统计今日使用情况。']
      : ['今日暂无教室使用记录','有排课或已批准的预约后，使用情况将在这里显示。'];
  }
  const label={courses:'课程',resources:'教室使用',exams:'考试'}[kind];
  if(state==='LOADING')return [`正在读取${label}`,'请稍候。'];
  if(state==='RESTRICTED')return [`当前范围不可查看${label}`,'请联系学校管理员核对可查看范围。'];
  if(state==='ERROR')return [`${label}读取失败`,'请点击右上角刷新重试，已录入的业务数据不会丢失。'];
  if(state==='INVALID')return [`${label}数据待核对`,'统计数量或学期不一致，请进入对应工作区核对。'];
  return [`${label}明细暂未提供`,'可进入对应工作区查看，稍后刷新重试。'];
}
export function wallStatus(view) {
  if(view.state==='READY')return view.metadata.hasNoData?'统计已更新 · 部分暂无数据':'统计已更新';
  return {RESTRICTED:'当前查看范围受限',LOADING:'正在读取统计',PARTIAL:'部分统计待核对',UNAVAILABLE:'统计暂不可用'}[view.state]||'统计待确认';
}
export function sourceTimeLabel(value, timeZone='Asia/Shanghai') {
  if(!value)return '尚无更新时间';
  const date=new Date(/[zZ]$|[+-]\d{2}:\d{2}$/.test(value)?value:`${value}Z`);
  if(Number.isNaN(date.getTime()))return '更新时间待核对';
  return new Intl.DateTimeFormat('zh-CN',{timeZone,month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(date);
}
