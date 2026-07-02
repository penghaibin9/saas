require('dotenv').config();
const mysql = require('mysql2/promise');
(async () => {
  try {
    const conn = await mysql.createConnection({
      host: process.env.DB_HOST || 'localhost',
      user: process.env.DB_USER || 'root',
      password: process.env.DB_PASSWORD || '',
      database: process.env.DB_NAME || 'internship_management'
    });
    const [cols] = await conn.query('SHOW COLUMNS FROM t_class');
    console.table(cols);
    await conn.end();
  } catch (err) {
    console.error(err.message);
    process.exit(1);
  }
})();