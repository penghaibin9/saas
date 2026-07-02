const test = require('node:test');
const assert = require('node:assert/strict');
const { benchmarkModel, gdTopicModel, notificationModel, systemConfigModel } = require('../models');
const benchmarkController = require('../controllers/benchmarkController');

function responseCapture() {
  return {
    statusCode: 200,
    body: null,
    status(code) { this.statusCode = code; return this; },
    json(body) { this.body = body; return body; }
  };
}

function requestFor(user, id = 9) {
  return { user, params: { id: String(id) }, query: {}, body: { status: 1 } };
}

test('学生不能按 ID 查看其他学生的任务书', async () => {
  const original = benchmarkModel.getTaskBook;
  try {
    benchmarkModel.getTaskBook = async () => ({ id: 9, student_id: 200, teacher_id: 30, student_college_id: 2 });
    const res = responseCapture();
    await benchmarkController.getTaskBook(requestFor({ id: 100, role: 4, collegeId: 2 }), res);
    assert.equal(res.statusCode, 403);
  } finally { benchmarkModel.getTaskBook = original; }
});

test('非指导教师不能查看或审核其他教师学生的鉴定表', async () => {
  const originalGet = benchmarkModel.getAppraisal;
  const originalReview = benchmarkModel.reviewAppraisal;
  let reviewed = false;
  try {
    benchmarkModel.getAppraisal = async () => ({ id: 9, student_id: 200, assignment_teacher_id: 31, student_college_id: 2 });
    benchmarkModel.reviewAppraisal = async () => { reviewed = true; };
    const user = { id: 30, role: 3, collegeId: 2 };

    const viewRes = responseCapture();
    await benchmarkController.getAppraisal(requestFor(user), viewRes);
    assert.equal(viewRes.statusCode, 403);

    const reviewRes = responseCapture();
    await benchmarkController.reviewAppraisal(requestFor(user), reviewRes);
    assert.equal(reviewRes.statusCode, 403);
    assert.equal(reviewed, false);
  } finally {
    benchmarkModel.getAppraisal = originalGet;
    benchmarkModel.reviewAppraisal = originalReview;
  }
});

test('二级学院管理员仅能访问本院材料', async () => {
  const original = benchmarkModel.getTaskBook;
  try {
    benchmarkModel.getTaskBook = async () => ({ id: 9, student_id: 200, teacher_id: 30, student_college_id: 7 });
    const denied = responseCapture();
    await benchmarkController.getTaskBook(requestFor({ id: 2, role: 2, collegeId: 6 }), denied);
    assert.equal(denied.statusCode, 403);

    const allowed = responseCapture();
    await benchmarkController.getTaskBook(requestFor({ id: 2, role: 2, collegeId: 7 }), allowed);
    assert.equal(allowed.statusCode, 200);
  } finally { benchmarkModel.getTaskBook = original; }
});

test('教师不能为其他指导教师的学生覆盖任务书', async () => {
  const originalTopics = gdTopicModel.findAll;
  const originalUpsert = benchmarkModel.upsertTaskBook;
  let upserted = false;
  try {
    gdTopicModel.findAll = async () => ({ list: [{ id: 5, student_id: 200, teacher_id: 31 }] });
    benchmarkModel.upsertTaskBook = async () => { upserted = true; return 9; };
    const req = {
      user: { id: 30, role: 3, collegeId: 2 },
      body: { student_id: 200, title: '越权任务书', content: 'x', file_url: 'javascript:alert(1)' }
    };
    const res = responseCapture();
    await benchmarkController.upsertTaskBook(req, res);
    assert.equal(res.statusCode, 403);
    assert.equal(upserted, false);
  } finally {
    gdTopicModel.findAll = originalTopics;
    benchmarkModel.upsertTaskBook = originalUpsert;
  }
});

test('教师可为本人指导学生保存任务书且忽略客户端 file_url', async () => {
  const originalTopics = gdTopicModel.findAll;
  const originalUpsert = benchmarkModel.upsertTaskBook;
  const originalNotifyCreate = notificationModel.create;
  const originalGetConfig = systemConfigModel.getAll;
  let saved = null;
  try {
    gdTopicModel.findAll = async () => ({ list: [{ id: 5, student_id: 200, teacher_id: 30 }] });
    benchmarkModel.upsertTaskBook = async (row) => { saved = row; return 9; };
    notificationModel.create = async () => 1;
    systemConfigModel.getAll = async () => ({ notify_wx_enabled: '0', notify_sms_enabled: '0', notify_email_enabled: '0' });
    const req = {
      user: { id: 30, role: 3, collegeId: 2 },
      body: { student_id: 200, title: '正常任务书', content: 'x', file_url: 'javascript:alert(1)' }
    };
    const res = responseCapture();
    await benchmarkController.upsertTaskBook(req, res);
    assert.equal(res.statusCode, 201);
    assert.equal(saved.teacher_id, 30);
    assert.equal(saved.file_url, undefined);
  } finally {
    gdTopicModel.findAll = originalTopics;
    benchmarkModel.upsertTaskBook = originalUpsert;
    notificationModel.create = originalNotifyCreate;
    systemConfigModel.getAll = originalGetConfig;
  }
});

test('教师查看免实习申请时强制带本人指导范围', async () => {
  const original = benchmarkModel.listSimple;
  let capturedFilter = null;
  try {
    benchmarkModel.listSimple = async (table, filter) => {
      assert.equal(table, 'alternative');
      capturedFilter = filter;
      return { list: [], total: 0 };
    };
    const res = responseCapture();
    await benchmarkController.listAlternatives({ user: { id: 30, role: 3, collegeId: 2 }, query: {} }, res);
    assert.equal(res.statusCode, 200);
    assert.equal(capturedFilter.teacherId, 30);
  } finally { benchmarkModel.listSimple = original; }
});

test('二级学院管理员不能跨学院审核免实习申请', async () => {
  const originalGet = benchmarkModel.getAlternative;
  const originalReview = benchmarkModel.reviewAlternative;
  let reviewed = false;
  try {
    benchmarkModel.getAlternative = async () => ({ id: 8, student_id: 200, student_college_id: 7 });
    benchmarkModel.reviewAlternative = async () => { reviewed = true; };
    const res = responseCapture();
    await benchmarkController.reviewAlternative({
      user: { id: 2, role: 2, collegeId: 6 }, params: { id: '8' }, body: { status: 1 }
    }, res);
    assert.equal(res.statusCode, 403);
    assert.equal(reviewed, false);
  } finally {
    benchmarkModel.getAlternative = originalGet;
    benchmarkModel.reviewAlternative = originalReview;
  }
});
