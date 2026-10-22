# ==========================================
# 阶段 1: 构建前端静态资源 (宿主原生架构编译，无需 QEMU 模拟)
# ==========================================
FROM --platform=$BUILDPLATFORM node:20-alpine AS frontend-builder

WORKDIR /build/frontend

# 安装依赖
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

# 复制源码并执行构建
COPY frontend/ ./
RUN npm run build

# ==========================================
# 阶段 2: 运行后端与提供服务
# ==========================================
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    DATA_DIR=/app/data

ARG TARGETARCH

# 安装基础工具并下载适配目标架构的 Mihomo 核心 (amd64 / arm64)
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl gzip ca-certificates && \
    mkdir -p /app/backend/bin && \
    ARCH="${TARGETARCH:-amd64}" && \
    ( curl -fsSL "https://github.com/MetaCubeX/mihomo/releases/download/v1.19.16/mihomo-linux-${ARCH}-v1.19.16.gz" -o /tmp/mihomo.gz && \
      gzip -d /tmp/mihomo.gz && \
      mv /tmp/mihomo /app/backend/bin/mihomo && \
      chmod +x /app/backend/bin/mihomo || echo "Notice: Mihomo binary download skipped" ) && \
    rm -rf /var/lib/apt/lists/*

# 安装后端依赖
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码与母本模板
COPY backend/ ./backend/
COPY 母本模板.yml ./

# 复制前端编译好的静态资源到 backend/app/static
COPY --from=frontend-builder /build/backend/app/static ./backend/app/static

# 持久化数据目录
VOLUME ["/app/data"]

EXPOSE 8080

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8080"]
