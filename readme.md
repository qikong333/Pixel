# 像素画批量生成器 (Pixel Art Generator)

这是一个基于 Python 的图像处理工具，能够将普通图片批量转换为各种算法风格的像素画（并支持导出 SVG 矢量图）。它提供了一个简单的 Web 界面，方便您直观地对比不同算法的效果，并动态调整生成参数。

## 目录结构

```text
pixl/
├── .venv/            # Python 虚拟环境
├── img/              # 输入目录：将需要处理的原图放入此文件夹
├── output/           # 输出目录：生成的像素画及 SVG 矢量图会保存在这里
├── generate.py       # 核心算法处理与 HTML 页面生成脚本
├── server.py         # 本地 Web 服务器脚本
├── index.html        # 动态生成的效果预览页面
└── README.md         # 项目说明文档
```

## 运行方法

### 0. 环境准备 (如果是第一次运行)

本项目需要 Python 3 环境。在第一次运行前，请按照以下步骤安装依赖：

```bash
# 1. 进入项目根目录
cd pixl

# 2. 创建并激活虚拟环境 (推荐)
python3 -m venv .venv
source .venv/bin/activate  # Mac/Linux 系统
# .venv\Scripts\activate   # Windows 系统

# 3. 安装依赖
pip install -r requirements.txt
```

### 1. 准备图片

将您想要处理的图片（支持 `.jpg`, `.jpeg`, `.png`, `.tif`, `.tiff`）放入 `img/` 文件夹中。

### 2. 启动本地服务器

在终端中进入项目根目录，并确保虚拟环境已激活，然后运行以下命令启动服务器：

```bash
python server.py
```

### 3. 访问预览界面

服务器启动后，打开您的浏览器，访问以下地址：

👉 **[http://localhost:8082](http://localhost:8082)**

### 4. 调整参数并生成

在打开的网页中，您可以看到当前的生成效果。您可以通过页面顶部的表单调整以下参数：

- **图像宽 / 高 (px)**: 输出图像的整体分辨率尺寸。
- **像素格宽 / 高 (px)**: 每个像素格子的尺寸。
- **分色数量 (色)**: 强制量化的色彩数量（例如 5 色）。

修改完参数后，点击 **"重新生成并刷新"** 按钮，后台会自动使用新的参数处理 `img/` 目录下的所有图片，并在处理完成后刷新页面展示最新效果。

## 支持的算法

目前项目集成了以下几种像素化处理算法以供对比：

1. **Pillow + OpenCV**: 双边滤波降噪 -> 缩小 -> 提升饱和度 -> LAB 空间 KMeans 严格聚类 -> 最近邻放大。
2. **scikit-image**: skimage 抗锯齿缩小 -> 提升饱和度 -> LAB 空间 KMeans 严格聚类 -> 最近邻放大。
3. **pixelate**: 使用第三方 `pixelate` 逻辑缩小 -> 提升饱和度 -> LAB 空间 KMeans 严格聚类 -> 最近邻放大。
4. **清晰图案 (边缘保留法)**: 双边滤波平滑去噪 -> 缩小 -> 提升饱和度与锐化 -> LAB空间 KMeans 严格聚类 -> 改善图案轮廓消失问题。

_(注：每种算法都会同时生成对应的 `.jpg` 预览图和 `.svg` 矢量图供下载)_

## 部署到服务器 (生产环境)

如果需要将此项目部署到云服务器供多人访问，强烈推荐使用 **Docker** 进行部署。这可以避免环境依赖冲突（例如 OpenCV 依赖的系统动态库等问题）。

### 方案一：使用 Docker (推荐)

项目已强制配置为构建 **`amd64` (x86_64)** 架构镜像。这意味着即使您在 Mac M 系列芯片上本地打包，打出的镜像也可以直接在绝大多数普通云服务器上运行。

#### 方法 A：在服务器上直接构建（最简单）

1. 在服务器上安装 [Docker](https://docs.docker.com/engine/install/) 和 [Docker Compose](https://docs.docker.com/compose/install/)。
2. 将整个项目代码上传到服务器。
3. 在项目根目录下，直接运行以下命令：
   ```bash
   docker-compose up -d --build
   ```
4. 容器启动后，项目会默认运行在服务器的 `8082` 端口。

#### 方法 B：在本地打包并推送至服务器

如果您不想在服务器上安装编译依赖或受限于服务器网络，可以在本地 Mac/PC 上打包好镜像后再传输。

1. 在本地项目根目录打包镜像（由于指定了 platform，会自动跨平台编译为 amd64）：
   ```bash
   docker build -t pixl-server:latest .
   ```
2. 将镜像导出为 tar 文件：
   ```bash
   docker save -o pixl-server.tar pixl-server:latest
   ```
3. 将 `pixl-server.tar` 和 `docker-compose.yml` 上传到服务器（例如使用 scp）：
   ```bash
   scp pixl-server.tar docker-compose.yml root@你的服务器IP:/root/pixl/
   ```
4. 在服务器上导入镜像并启动：
   ```bash
   # 如果服务器(如 Red Hat) 尚未安装 Docker，请先执行 yum install docker 等安装步骤
   docker load -i pixl-server.tar
   docker-compose up -d
   ```

_注：`docker-compose.yml` 中默认限制了最大内存为 4GB，以防多人同时处理超大图片导致宿主机 OOM。_

### 方案二：传统 Nginx + 虚拟环境 (裸机部署)

如果您不想使用 Docker，可以直接在服务器上运行：

1. **安装系统依赖** (以 Red Hat / CentOS / RHEL 为例)：
   ```bash
   sudo yum update
   # 或者使用 dnf: sudo dnf update
   sudo yum install -y python3 python3-devel git mesa-libGL glib2 nginx
   ```
2. **安装 Python 依赖**：
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. **后台运行服务** (可以使用 `nohup` 或 `systemd` 或 `pm2` / `supervisor`)：
   ```bash
   nohup python server.py > server.log 2>&1 &
   ```
4. **配置 Nginx 反向代理**：
   修改 `/etc/nginx/sites-available/default`，将 80 端口的请求转发给 8082 端口：

   ```nginx
   server {
       listen 80;
       server_name your_domain_or_ip;

       # 允许上传大文件
       client_max_body_size 20M;

       location / {
           proxy_pass http://127.0.0.1:8082;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;

           # 延长超时时间以防大图处理时间过长导致 504 错误
           proxy_read_timeout 300;
           proxy_connect_timeout 300;
       }
   }
   ```

5. 重启 Nginx：`sudo systemctl restart nginx`。
