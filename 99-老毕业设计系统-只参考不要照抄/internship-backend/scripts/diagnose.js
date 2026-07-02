#!/usr/bin/env node

/**
 * 项目诊断脚本
 * 用法：npm run diagnose 或 node scripts/diagnose.js
 * 
 * 功能：
 * - 检查 Node.js 版本
 * - 检查所有依赖包
 * - 检查 .env 配置
 * - 测试数据库连接
 * - 检查文件结构
 * - 验证语法
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const ROOT = path.join(__dirname, '..');
let issues = [];
let warnings = [];
let success = [];

// 颜色输出
const colors = {
  reset: '\x1b[0m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  red: '\x1b[31m',
  blue: '\x1b[34m',
  cyan: '\x1b[36m'
};

function log(msg, color = 'reset') {
  console.log(`${colors[color]}${msg}${colors.reset}`);
}

// 1. 检查 Node.js 版本
function checkNodeVersion() {
  try {
    const version = process.version;
    const major = parseInt(version.slice(1).split('.')[0]);
    
    if (major < 14) {
      issues.push(`Node.js 版本过低: ${version} (需要 >= 14.x)`);
    } else {
      success.push(`Node.js 版本: ${version} ✓`);
    }
  } catch (err) {
    issues.push(`检查 Node.js 版本失败: ${err.message}`);
  }
}

// 2. 检查 npm 依赖
function checkDependencies() {
  try {
    const packageJson = require(path.join(ROOT, 'package.json'));
    const nodeModulesPath = path.join(ROOT, 'node_modules');
    
    if (!fs.existsSync(nodeModulesPath)) {
      warnings.push('node_modules 目录不存在，需要运行 npm install');
      return;
    }
    
    const required = [
      'express',
      'mysql2',
      'dotenv',
      'jsonwebtoken',
      'bcryptjs',
      'multer',
      'xlsx',
      'cors',
      'dayjs'
    ];
    
    const installed = fs.readdirSync(nodeModulesPath);
    const missing = required.filter(pkg => !installed.includes(pkg));
    
    if (missing.length > 0) {
      issues.push(`缺少依赖包: ${missing.join(', ')}`);
    } else {
      success.push(`所有依赖包已安装 ✓`);
    }
  } catch (err) {
    issues.push(`检查依赖失败: ${err.message}`);
  }
}

// 3. 检查 .env 文件
function checkEnvFile() {
  const envPath = path.join(ROOT, '.env');
  const examplePath = path.join(ROOT, '.env.example');
  
  if (!fs.existsSync(envPath)) {
    if (fs.existsSync(examplePath)) {
      warnings.push('.env 文件不存在，请复制 .env.example 为 .env');
    } else {
      issues.push('.env 文件不存在，也找不到 .env.example 模板');
    }
    return;
  }
  
  const envContent = fs.readFileSync(envPath, 'utf8');
  const requiredVars = ['DB_HOST', 'DB_USER', 'JWT_SECRET'];
  const missing = [];
  
  requiredVars.forEach(varName => {
    if (!envContent.includes(varName)) {
      missing.push(varName);
    }
  });
  
  if (missing.length > 0) {
    warnings.push(`环境变量缺少配置: ${missing.join(', ')}`);
  } else {
    success.push('.env 配置完整 ✓');
  }
}

// 4. 检查文件结构
function checkFileStructure() {
  const requiredDirs = [
    'config',
    'controllers',
    'models',
    'routes',
    'middlewares',
    'utils',
    'scripts',
    'uploads'
  ];
  
  const requiredFiles = [
    'app.js',
    'package.json',
    'README.md'
  ];
  
  const missingDirs = [];
  const missingFiles = [];
  
  requiredDirs.forEach(dir => {
    if (!fs.existsSync(path.join(ROOT, dir))) {
      missingDirs.push(dir);
    }
  });
  
  requiredFiles.forEach(file => {
    if (!fs.existsSync(path.join(ROOT, file))) {
      missingFiles.push(file);
    }
  });
  
  if (missingDirs.length > 0 || missingFiles.length > 0) {
    const missing = [...missingDirs, ...missingFiles].join(', ');
    issues.push(`缺少必要的文件或目录: ${missing}`);
  } else {
    success.push('项目文件结构完整 ✓');
  }
}

// 5. 检查 app.js 语法
function checkAppSyntax() {
  try {
    const appPath = path.join(ROOT, 'app.js');
    execSync(`node -c "${appPath}"`, { stdio: 'pipe' });
    success.push('app.js 语法检查通过 ✓');
  } catch (err) {
    issues.push(`app.js 语法错误: ${err.message}`);
  }
}

// 6. 检查控制器语法
function checkControllersSyntax() {
  try {
    const controllersDir = path.join(ROOT, 'controllers');
    const files = fs.readdirSync(controllersDir).filter(f => f.endsWith('.js'));
    let errors = [];
    
    files.forEach(file => {
      try {
        execSync(`node -c "${path.join(controllersDir, file)}"`, { stdio: 'pipe' });
      } catch (err) {
        errors.push(file);
      }
    });
    
    if (errors.length > 0) {
      issues.push(`控制器语法错误: ${errors.join(', ')}`);
    } else {
      success.push(`${files.length} 个控制器语法检查通过 ✓`);
    }
  } catch (err) {
    warnings.push(`检查控制器时出错: ${err.message}`);
  }
}

// 7. 检查数据库配置
function checkDatabaseConfig() {
  try {
    const configPath = path.join(ROOT, 'config', 'db.js');
    if (!fs.existsSync(configPath)) {
      issues.push('数据库配置文件不存在: config/db.js');
      return;
    }
    
    execSync(`node -c "${configPath}"`, { stdio: 'pipe' });
    success.push('数据库配置文件语法检查通过 ✓');
  } catch (err) {
    issues.push(`数据库配置错误: ${err.message}`);
  }
}

// 8. 测试数据库连接（可选）
async function testDatabaseConnection() {
  try {
    // 检查是否可以加载 config
    require('dotenv').config();
    const dbConfig = require(path.join(ROOT, 'config', 'db.js'));
    
    if (dbConfig && dbConfig.testConnection) {
      const result = await dbConfig.testConnection();
      success.push(`数据库连接测试通过 ✓`);
    }
  } catch (err) {
    warnings.push(`数据库连接测试失败（可能尚未启动 MySQL）: ${err.message}`);
  }
}

// 9. 检查上传目录权限
function checkUploadDirectory() {
  try {
    const uploadsDir = path.join(ROOT, 'uploads');
    if (!fs.existsSync(uploadsDir)) {
      fs.mkdirSync(uploadsDir, { recursive: true });
      success.push('上传目录已创建 ✓');
    } else {
      // 测试写入权限
      const testFile = path.join(uploadsDir, '.test');
      fs.writeFileSync(testFile, 'test');
      fs.unlinkSync(testFile);
      success.push('上传目录权限正常 ✓');
    }
  } catch (err) {
    warnings.push(`上传目录权限问题: ${err.message}`);
  }
}

// 10. 生成诊断报告
function generateReport() {
  console.log('\n');
  log('═'.repeat(60), 'blue');
  log('  📋 项目诊断报告', 'cyan');
  log('═'.repeat(60), 'blue');
  console.log('');
  
  if (success.length > 0) {
    log('✅ 正常项目:', 'green');
    success.forEach(msg => log(`   ${msg}`, 'green'));
    console.log('');
  }
  
  if (warnings.length > 0) {
    log('⚠️  警告信息:', 'yellow');
    warnings.forEach(msg => log(`   ${msg}`, 'yellow'));
    console.log('');
  }
  
  if (issues.length > 0) {
    log('❌ 错误信息:', 'red');
    issues.forEach(msg => log(`   ${msg}`, 'red'));
    console.log('');
  }
  
  log('═'.repeat(60), 'blue');
  
  // 总结
  const status = issues.length === 0 ? '✅ 诊断完成' : '❌ 诊断发现问题';
  const color = issues.length === 0 ? 'green' : 'red';
  log(`${status}`, color);
  
  console.log('');
  log('建议操作:', 'cyan');
  if (issues.length === 0 && warnings.length === 0) {
    log('   所有检查通过！可以运行 npm run dev 启动服务', 'green');
  } else {
    if (!fs.existsSync(path.join(ROOT, '.env'))) {
      log('   1. 运行: cp .env.example .env', 'yellow');
      log('   2. 编辑 .env 填入正确的数据库配置', 'yellow');
    }
    if (!fs.existsSync(path.join(ROOT, 'node_modules'))) {
      log('   运行: npm install', 'yellow');
    }
    if (issues.length > 0) {
      log('   请根据上述错误信息进行修正', 'red');
    }
  }
  console.log('');
}

// 主程序
async function main() {
  console.clear();
  log('\n🔍 正在诊断项目...', 'cyan');
  
  checkNodeVersion();
  checkDependencies();
  checkEnvFile();
  checkFileStructure();
  checkAppSyntax();
  checkControllersSyntax();
  checkDatabaseConfig();
  checkUploadDirectory();
  
  // 数据库连接测试（异步）
  if (fs.existsSync(path.join(ROOT, '.env'))) {
    await testDatabaseConnection();
  }
  
  generateReport();
  
  // 返回退出码
  process.exit(issues.length > 0 ? 1 : 0);
}

// 运行诊断
main().catch(err => {
  console.error('诊断过程出错:', err);
  process.exit(1);
});
