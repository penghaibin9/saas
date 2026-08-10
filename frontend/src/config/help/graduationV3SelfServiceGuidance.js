/** V3-03：增强既有 4 张毕设 clean 卡的下一步与人工升级边界。 */
export const GRADUATION_V3_SELF_SERVICE_GUIDANCE = Object.freeze({
  'gd-v2-topic-selection': {
    nextSteps: [
      '题目正式匹配后先确认稳定导师关系，再下达任务书；不要把“匹配到题目”直接等同于可提交开题。',
      '进入指导阶段后需要换题时走题目变更申请，批准后重新核对后续任务书/材料是否仍适用。'
    ],
    contactAdminWhen: [
      '学生正式 topic_id 与题目容量/selected 事实不一致。',
      '学生和题目均满足批次/资格/审核/容量规则，但服务端持续判为越权或跨批次。',
      '历史换题直接改过主档、缺少变更链，导致后续材料无法确认真实题目版本。'
    ]
  },
  'gd-v2-proposal': {
    nextSteps: [
      '开题 APPROVED 后进入持续指导和中期检查；书面开题通过不代表所有学校现场开题要求自动完成。',
      '中期前继续按已确认任务书推进指导记录，不通过重复提交开题制造“新状态”。'
    ],
    contactAdminWhen: [
      '开题业务版本与材料中心 PROPOSAL_REPORT 当前文件版本不一致。',
      '学生已确认任务书且选题/资格正常，仍无法提交本人开题。',
      '驳回重交后旧版本被覆盖或审计无法区分各版本。'
    ]
  },
  'gd-v2-defense': {
    nextSteps: [
      '答辩组正式发布后，评委按稳定席位完成当前轮次评分，答辩秘书按授权确认；必要二辩必须显式创建后续轮次。',
      '评分 CONFIRMED 后再进入综合成绩核算，不能用未确认评分直接形成正式成绩。'
    ],
    contactAdminWhen: [
      '秘书/评委已经绑定稳定 mentorId/expertId，但系统仍把本人席位判为越权。',
      '已发布答辩组被编辑后 published 未撤回，或重新发布后学生名单/席位仍是旧版本。',
      '同一学生当前轮次出现无法解释的重复 CONFIRMED 评分来源。'
    ]
  },
  'gd-v2-grade': {
    nextSteps: [
      'PUBLISHED 成绩如果无人申诉且来源稳定，进入毕业设计归档；归档要求的不是页面显示“有成绩”，而是正式 PUBLISHED 事实。',
      '已发布成绩发生合法纠错应走撤回/重新核算/复核/发布或已存在的申诉链，不直接覆盖分数。'
    ],
    contactAdminWhen: [
      '权威定稿、COMPLETED 评阅、CONFIRMED 答辩都存在，但成绩核算仍报告来源缺失。',
      'sourceSnapshotHash 与当前权威来源无故不一致，且确认没有合法上游变更。',
      '成绩已 PUBLISHED 但归档完整性仍读取不到正式成绩事实。'
    ]
  }
})
