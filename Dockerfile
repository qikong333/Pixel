# 显式指定 amd64 架构，确保在 Mac M 系列芯片上打包也能在普通服务器上运行
FROM --platform=linux/amd64 python:3.12-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8082

# 安装系统依赖（针对 OpenCV 和 git 依赖）
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装
COPY requirements.txt .

# 升级 pip 并安装依赖 (使用 no-cache-dir 减小镜像体积)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 复制项目源代码
COPY . .

# 暴露服务端口
EXPOSE ${PORT}

# 启动服务
CMD ["python", "server.py"]
