require('dotenv').config();
const fs = require('fs');
const path = require('path');
const mysql = require('mysql2/promise');

/**
 * 数据库初始化脚本
 * 用法：node scripts/init-db.js
 */
async function initDatabase() {
  try {
    // 连接到 MySQL（不指定数据库）
    const connection = await mysql.createConnection({
      host: process.env.DB_HOST || 'localhost',
      user: process.env.DB_USER || 'root',
      password: process.env.DB_PASSWORD || '',
      charset: 'utf8mb4'
    });

    console.log('✅ 连接到 MySQL 成功');

    // 读取 SQL 脚本
    const sqlFilePath = path.join(__dirname, 'init-db.sql');
    const sql = fs.readFileSync(sqlFilePath, 'utf8');

    // 分割 SQL 语句（简单的按 ; 分割）
    const statements = sql
      .split(';')
      .map(stmt => stmt.trim())
      .filter(stmt => stmt && !stmt.startsWith('--'));

    // 执行每条语句
    for (const statement of statements) {
      try {
        await connection.query(statement);
        const preview = statement.substring(0, 50).replace(/\n/g, ' ');
        console.log(`✓ ${preview}${statement.length > 50 ? '...' : ''}`);
      } catch (err) {
        console.error(`✗ 执行失败: ${statement.substring(0, 50)}...`);
        console.error(`  错误: ${err.message}`);
        // 某些错误可以忽略（如表已存在），继续执行
        if (!err.message.includes('already exists')) {
          throw err;
        }
      }
    }

    await connection.end();
    console.log('\n✅ 数据库初始化完成！');
    console.log('   默认账户：admin / 123456');
    console.log('   请登录后修改密码！');

    process.exit(0);
  } catch (err) {
    console.error('\n❌ 数据库初始化失败：');
    console.error(err.message);
    console.error('\n请检查以下内容：');
    console.error('1. .env 文件中的数据库配置是否正确');
    console.error('2. MySQL 服务是否正在运行');
    console.error('3. 数据库用户是否有创建数据库的权限');
    process.exit(1);
  }
}

initDatabase();
