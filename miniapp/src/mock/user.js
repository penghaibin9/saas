/** 当前登录用户 mock（学生 / 教师） */
import { teacherIdentities } from '@/config/roles.config'

export const mockStudentUser = {
  id: 'stu_2023100001',
  name: '张一鸣',
  avatar: '',
  studentNo: '2023100001',
  gender: '男',
  college: '软件学院',
  major: '软件工程',
  className: '软件工程 2401 班',
  grade: '2023 级',
  // 当前阶段（对应 08A：ENROLLED 在校）
  stage: 'ENROLLED',
  stageText: '在校',
  counselor: { name: '周敏', phone: '13800000001' },
  phone: '13612345678',
  idCard: '4301231999xxxx1234'
}

export const mockTeacherUser = {
  id: 'tea_zhang',
  name: '张明远',
  avatar: '',
  workNo: 'T20190087',
  college: '信息工程学院',
  title: '副教授',
  phone: '13900000002',
  // 该老师同时拥有多个教师身份（08B 3.2 当前工作上下文）
  identities: teacherIdentities
}

export default { mockStudentUser, mockTeacherUser }
