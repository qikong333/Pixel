## 1. 准备工作：安装 Docker 环境

如果您的服务器尚未安装 Docker，请先通过 SSH 登录服务器并执行以下命令：

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

## 2. 部署流程：上传源码并运行

### 第一步：将源码上传至服务器

将您本地的 `pixl` 项目文件夹（包含 `Dockerfile`、`docker-compose.yml` 及代码）压缩为 `pixl.zip`，然后上传到服务器。
在服务器上解压并进入该目录：

```bash
unzip pixl.zip
cd pixl
```

### 第二步：一键打包并启动服务

在项目根目录下执行以下命令，Docker 会自动读取 `Dockerfile` 下载运行环境、安装依赖并启动服务：

```bash
sudo docker compose up -d --build
```

> **提示**：首次执行 `--build` 时，服务器会从公网拉取 Python 镜像并安装 OpenCV 等依赖，需要等待几分钟。后续更新秒开。

构建完成后，服务将静默运行在服务器的 `8082` 端口。在浏览器访问 `http://<您的服务器IP>:8082` 即可使用。

---

## 3. 日常维护与热更新

当您在本地修改了代码后，只需将修改后的代码文件重新上传覆盖服务器上的旧文件，然后再次执行：

```bash
sudo docker compose up -d --build
```

_(Docker 会利用缓存，瞬间完成更新和重启)_

---

## 4. 常用管理命令

- **查看实时运行日志**（排查报错）：
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
