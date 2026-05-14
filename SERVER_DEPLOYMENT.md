# 服务器部署与自动化打包指南 (基于 Red Hat Linux)

本文档详细介绍了如何在一台全新的 Red Hat / CentOS 服务器上，通过拉取 GitHub 源码并使用 Docker 进行自动化构建和部署。这是**最推荐、最干净**的部署方式。

## 1. 准备工作：安装基础环境

如果您的服务器尚未安装 Git 和 Docker，请先通过 SSH 登录服务器并执行以下命令：

### 安装 Git
```bash
sudo yum update -y
sudo yum install -y git
```

### 安装 Docker 与 Docker Compose
```bash
# 安装 yum-utils 工具
sudo yum install -y yum-utils

# 添加 Docker 官方镜像源 (CentOS 源兼容 Red Hat)
sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo

# 安装 Docker 引擎及 Compose 插件
sudo yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# 启动 Docker 并设置开机自启
sudo systemctl start docker
sudo systemctl enable docker
```

---

## 2. 部署流程：拉取源码并运行

在服务器上选择一个存放项目的目录（例如 `/opt/` 或您的用户主目录 `~`）：

### 第一步：克隆代码仓库
```bash
git clone git@github.com:qikong333/Pixel.git
cd Pixel
```
*(注：如果服务器没有配置 GitHub 的 SSH Key，您也可以使用 HTTPS 地址免密/账号密码克隆：`git clone https://github.com/qikong333/Pixel.git`)*

### 第二步：一键打包并启动服务
在 `Pixel` 项目根目录下执行以下命令，Docker 会自动读取 `Dockerfile` 下载运行环境、安装依赖并启动服务：
```bash
sudo docker compose up -d --build
```
> **提示**：首次执行 `--build` 时，服务器会从公网拉取 Python 镜像并安装 OpenCV 等依赖，需要等待几分钟。后续更新秒开。

构建完成后，服务将静默运行在服务器的 `8082` 端口。在浏览器访问 `http://<您的服务器IP>:8082` 即可使用。

---

## 3. 日常维护与热更新

当您在本地 Mac 修改了代码并 `git push` 到 GitHub 后，在服务器上更新服务只需简单的两步（无需重新传文件）：

```bash
# 1. 进入项目目录并拉取最新代码
cd Pixel
git pull

# 2. 重新构建并重启容器 (Docker 会利用缓存，瞬间完成更新)
sudo docker compose up -d --build
```

---

## 4. 常用管理命令

- **查看实时运行日志**（可用来排查报错）：
  ```bash
  sudo docker logs -f pixl_server
  ```
- **停止服务**：
  ```bash
  sudo docker compose down
  ```
- **查看服务状态**：
  ```bash
  sudo docker ps
  ```