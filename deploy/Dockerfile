# ===========================
# 开发环境镜像 - 支持热更新
# ===========================
FROM node:22 AS dev-hot-reload
WORKDIR /app
RUN echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始构建 dev-hot-reload 阶段镜像..."

# 只复制依赖配置文件
COPY package.json package-lock.json ./

# 设置代理
ENV http_proxy="http://10.52.57.90:11080"
ENV https_proxy="http://10.52.57.90:11080"
ENV HTTP_PROXY="http://10.52.57.90:11080"
ENV HTTPS_PROXY="http://10.52.57.90:11080"
ENV no_proxy="localhost,127.0.0.1,localaddress,localdomain.com,.internal,.corp.kuaishou.com,.test.gifshow.com,.staging.kuaishou.com"
ENV NO_PROXY="localhost,127.0.0.1,localaddress,localdomain.com,.internal,.corp.kuaishou.com,.test.gifshow.com,.staging.kuaishou.com"

# 安装依赖（包括可选依赖）
RUN npm install --include=optional || npm install --legacy-peer-deps --include=optional

# 注意：此镜像依赖 volume 挂载来获取源代码
# 不在构建时复制源代码，而是通过 docker-compose volumes 挂载

EXPOSE 8000

# 开发模式：使用 npm run dev 启动热更新
CMD ["npm", "run", "dev"]
