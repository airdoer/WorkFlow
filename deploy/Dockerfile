# ===========================
# 开发环境镜像
# ===========================
FROM node:22 AS develop
WORKDIR /app
RUN echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始构建 develop 阶段镜像..."
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
COPY . .
RUN npm run build
COPY deploy/start.sh /app/start.sh
RUN chmod +x /app/start.sh
EXPOSE 8000
CMD ["/app/start.sh"]

# ===========================
# 开发环境镜像 家里
# ===========================
FROM node:22 AS develop_home
WORKDIR /app
RUN echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始构建 develop_home 阶段镜像..."
COPY package.json package-lock.json ./
RUN npm install --include=optional || npm install --legacy-peer-deps --include=optional
COPY . .
RUN npm run build
COPY deploy/start.sh /app/start.sh
RUN chmod +x /app/start.sh
EXPOSE 8000
CMD ["/app/start.sh"]

# ===========================
# 生产运行镜像
# ===========================
FROM node:22 AS publish
WORKDIR /app
RUN echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始构建 publish 阶段镜像..."
# 只复制构建产物，避免带上 devDependencies
COPY package.json package-lock.json ./

# 设置代理
ENV http_proxy="http://10.52.57.90:11080"
ENV https_proxy="http://10.52.57.90:11080"
ENV HTTP_PROXY="http://10.52.57.90:11080"
ENV HTTPS_PROXY="http://10.52.57.90:11080"
ENV no_proxy="localhost,127.0.0.1,localaddress,localdomain.com,.internal,.corp.kuaishou.com,.test.gifshow.com,.staging.kuaishou.com"
ENV NO_PROXY="localhost,127.0.0.1,localaddress,localdomain.com,.internal,.corp.kuaishou.com,.test.gifshow.com,.staging.kuaishou.com"
RUN npm install --include=optional || npm install --legacy-peer-deps --include=optional
COPY . .
RUN npm run build
COPY deploy/start.sh /app/start.sh
RUN chmod +x /app/start.sh
EXPOSE 8000
CMD ["/app/start.sh"]
