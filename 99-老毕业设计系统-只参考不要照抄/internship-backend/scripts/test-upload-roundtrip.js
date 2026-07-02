/** 附件上传→鉴权下载→内容校验→删除草稿的闭环测试。 */
const BASE = (process.env.API_BASE || 'http://localhost:3000/api').replace(/\/$/, '');
const USER = process.env.TEST_STUDENT_USER || 'demo_stu1';
const PASS = process.env.TEST_STUDENT_PASS || 'demo1234';

async function json(url, options) {
  const res = await fetch(url, options);
  const body = await res.json().catch(() => ({}));
  if (!res.ok || body.success === false) throw new Error(`${res.status} ${body.message || url}`);
  return body.data;
}

async function main() {
  const login = await json(BASE + '/users/login', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: USER, password: PASS })
  });
  const token = login.token;
  const marker = `upload-roundtrip-${Date.now()}`;
  const form = new FormData();
  form.append('type', 'weekly');
  form.append('title', marker);
  form.append('content', '自动化附件闭环测试，完成后自动清理。');
  form.append('file', new Blob([marker], { type: 'application/pdf' }), 'roundtrip.pdf');
  const created = await json(BASE + '/intern-logs', {
    method: 'POST', headers: { Authorization: 'Bearer ' + token }, body: form
  });
  try {
    if (!created.file_url) throw new Error('接口未返回附件地址');
    const origin = BASE.replace(/\/api$/, '');
    const downloaded = await fetch(origin + created.file_url, { headers: { Authorization: 'Bearer ' + token } });
    if (!downloaded.ok) throw new Error(`附件下载失败：${downloaded.status}`);
    const content = await downloaded.text();
    if (content !== marker) throw new Error('下载内容与上传内容不一致');
    console.log('✅ 上传、鉴权下载和内容校验通过');
  } finally {
    await fetch(BASE + '/intern-logs/' + created.id, { method: 'DELETE', headers: { Authorization: 'Bearer ' + token } });
  }
}

main().catch((e) => { console.error('❌', e.message); process.exit(1); });
