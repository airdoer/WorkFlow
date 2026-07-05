# ===========================
# 开发环境镜像 家里
# ===========================
FROM python:3.11 AS develop_home

WORKDIR /app
RUN echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始构建 develop_home 阶段镜像..."
COPY requirements.txt ./
ARG http_proxy
ARG https_proxy
ENV http_proxy=${http_proxy}
ENV https_proxy=${https_proxy}
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn
# Python 依赖
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -U cos-python-sdk-v5
# 安装基础依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*
# 把 p4 放进去 /usr/local/bin
COPY docker_appendix/p4 /usr/local/bin/p4
RUN chmod +x /usr/local/bin/p4
ENV P4CONFIG=/app/p4/.p4config
ARG DASHSCOPE_API_KEY
ENV DASHSCOPE_API_KEY=${DASHSCOPE_API_KEY}
ARG P4PASSWD
ENV P4PASSWD=${P4PASSWD}
COPY . .

# ===========================
# 开发环境镜像
# ===========================
FROM python:3.11 AS develop
WORKDIR /app
RUN echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始构建 develop 阶段镜像..."
COPY requirements.txt ./
ARG http_proxy
ARG https_proxy
ENV http_proxy=${http_proxy}
ENV https_proxy=${https_proxy}
ENV HTTP_PROXY=${http_proxy}
ENV HTTPS_PROXY=${https_proxy}
ENV no_proxy="localhost,127.0.0.1,localaddress,localdomain.com,internal,corp.kuaishou.com,test.gifshow.com,staging.kuaishou.com"
ENV NO_PROXY="localhost,127.0.0.1,localaddress,localdomain.com,internal,corp.kuaishou.com,test.gifshow.com,staging.kuaishou.com"
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn
# Python 依赖
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -U cos-python-sdk-v5
# 安装基础依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*
# 把 p4 放进去 /usr/local/bin
COPY docker_appendix/p4 /usr/local/bin/p4
RUN chmod +x /usr/local/bin/p4
# 取消代理
ENV http_proxy=""
ENV https_proxy=""
ENV HTTP_PROXY=""
ENV HTTPS_PROXY=""
ENV P4CONFIG=/app/p4/.p4config
ARG DASHSCOPE_API_KEY
ENV DASHSCOPE_API_KEY=${DASHSCOPE_API_KEY}
COPY . .
RUN chmod +x /app/entrypoint.sh
ENTRYPOINT ["/app/entrypoint.sh"]

# ===========================
# 生产运行镜像
# ===========================
FROM develop AS publish
