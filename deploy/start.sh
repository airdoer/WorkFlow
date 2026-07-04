#!/bin/sh

# 确保 dist 目录存在
mkdir -p /app/dist

# 生成环境变量配置文件
cat > /app/dist/env-config.js << EOF
window.FLASK_BACKEND_URL = "${FLASK_BACKEND_URL}";
EOF

# 启动服务
npm run preview
