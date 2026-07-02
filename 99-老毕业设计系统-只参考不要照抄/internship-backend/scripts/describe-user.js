require('dotenv').config();
const pool = require('../config/db');

(async () => {
  const [rows] = await pool.query('DESCRIBE t_user');
  console.log(JSON.stringify(rows, null, 2));
  const [sample] = await pool.query('SELECT * FROM t_user LIMIT 1');
  console.log('SAMPLE:', JSON.stringify(sample, null, 2));
  process.exit(0);
})();
