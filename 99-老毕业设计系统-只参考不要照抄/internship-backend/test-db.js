require('dotenv').config();
const pool = require('./config/db');

(async () => {
  try {
    const [db] = await pool.query('SELECT DATABASE() AS db, VERSION() AS version');
    const [tables] = await pool.query('SHOW TABLES');
    const tableKey = tables.length ? Object.keys(tables[0])[0] : null;

    console.log('连接状态: 成功');
    console.log('当前数据库:', db[0].db);
    console.log('MySQL 版本:', db[0].version);
    console.log('表数量:', tables.length);

    if (tables.length) {
      console.log('\n表列表:');
      tables.forEach((row, i) => {
        console.log(`${i + 1}. ${row[tableKey]}`);
      });
    } else {
      console.log('\n数据库已连接，但里面还没有任何表。');
    }
  } catch (err) {
    console.error('连接状态: 失败');
    console.error('错误信息:', err.message);
  } finally {
    process.exit(0);
  }
})();
