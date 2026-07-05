# Docker 镜像源配置

## 配置国内镜像加速

如果在国内服务器遇到拉取镜像失败的问题，可以配置 Docker 镜像加速：

### 1. 编辑 Docker 配置文件

```bash
sudo vim /etc/docker/daemon.json
```

### 2. 添加以下内容

```json
{
  "registry-mirrors": [
    "https://docker.mirrors.ustc.edu.cn",
    "https://hub-mirror.c.163.com",
    "https://mirror.ccs.tencentyun.com"
  ]
}
```

### 3. 重启 Docker 服务

```bash
sudo systemctl daemon-reload
sudo systemctl restart docker
```

### 4. 验证配置

```bash
docker info | grep -A 10 "Registry Mirrors"
```

## 常用国内镜像源

- **中科大**: https://docker.mirrors.ustc.edu.cn
- **网易**: https://hub-mirror.c.163.com
- **腾讯云**: https://mirror.ccs.tencentyun.com
- **阿里云**: 需要登录获取专属地址 https://cr.console.aliyun.com/cn-hangzhou/instances/mirrors

## 或者直接使用预拉取的镜像

如果镜像源也不行，可以：

1. 从其他机器导出镜像
```bash
docker save node:22-alpine > node-22-alpine.tar
```

2. 传输到目标机器后导入
```bash
docker load < node-22-alpine.tar
```
