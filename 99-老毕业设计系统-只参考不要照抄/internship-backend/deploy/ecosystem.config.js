// 不使用 Docker 时的 PM2 部署：pm2 start deploy/ecosystem.config.js
module.exports = {
  apps: [{
    name: 'internship-platform',
    script: 'app.js',
    instances: 'max',          // 集群模式跑满 CPU，应对早八集中打卡
    exec_mode: 'cluster',
    max_memory_restart: '512M',
    env: { NODE_ENV: 'production' },
    error_file: 'logs/err.log',
    out_file: 'logs/out.log',
    merge_logs: true,
    time: true
  }]
};
