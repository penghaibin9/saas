const http = require('http');

function request(method, path, body, token) {
  return new Promise((resolve, reject) => {
    const data = body ? JSON.stringify(body) : null;
    const req = http.request(
      {
        hostname: 'localhost',
        port: 3000,
        path,
        method,
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(data ? { 'Content-Length': Buffer.byteLength(data) } : {})
        }
      },
      (res) => {
        let raw = '';
        res.on('data', (chunk) => { raw += chunk; });
        res.on('end', () => {
          resolve({ status: res.statusCode, body: JSON.parse(raw) });
        });
      }
    );
    req.on('error', reject);
    if (data) req.write(data);
    req.end();
  });
}

(async () => {
  console.log('=== /api/test ===');
  console.log(JSON.stringify(await request('GET', '/api/test'), null, 2));

  console.log('\n=== POST /api/users/login ===');
  const login = await request('POST', '/api/users/login', {
    username: 'admin',
    password: '123456'
  });
  console.log(JSON.stringify(login, null, 2));

  const token = login.body?.data?.token;
  if (token) {
    console.log('\n=== GET /api/users/profile ===');
    console.log(JSON.stringify(await request('GET', '/api/users/profile', null, token), null, 2));
  }
})();
