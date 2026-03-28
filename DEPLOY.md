# Docker 构建与部署指南

## 方法一：本地构建 Docker 镜像

### 1. 构建镜像

在项目根目录执行：

```bash
# 构建镜像（标签为 codex-manager:latest）
docker build -t codex-manager:latest .

# 或者带版本号
docker build -t codex-manager:v2.0.0 .
```

### 2. 保存镜像（用于传输到其他服务器）

```bash
# 保存镜像为 tar 文件
docker save -o codex-manager.tar codex-manager:latest

# 压缩（可选，减小体积）
gzip codex-manager.tar
# 生成 codex-manager.tar.gz
```

### 3. 本地测试运行

```bash
# 创建数据目录
mkdir -p data logs

# 运行容器
docker run -d \
  --name codex-manager \
  -p 15555:15555 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  -e WEBUI_ACCESS_PASSWORD=your_password \
  codex-manager:latest

# 查看日志
docker logs -f codex-manager
```

---

## 方法二：使用 Docker Compose（推荐）

### 1. 启动服务

```bash
# 构建并启动
docker-compose up -d

# 查看状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

### 2. 停止服务

```bash
docker-compose down

# 停止并删除数据卷（谨慎使用）
docker-compose down -v
```

---

## 方法三：VPS 手动部署

### 步骤 1：准备 VPS

**系统要求：**
- Linux 系统（Ubuntu 20.04+/Debian 11+/CentOS 8+）
- 内存：至少 512MB（推荐 1GB+）
- 磁盘：至少 2GB 可用空间
- 网络：能够访问目标网站

**安装 Docker：**

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y docker.io docker-compose
sudo systemctl enable docker
sudo systemctl start docker

# 将当前用户加入 docker 组（免 sudo）
sudo usermod -aG docker $USER
# 重新登录或执行：
newgrp docker
```

```bash
# CentOS/RHEL
sudo yum install -y docker docker-compose
sudo systemctl enable docker
sudo systemctl start docker
```

### 步骤 2：传输镜像（如果从本地构建）

**从本地服务器上传到 VPS：**

```bash
# 在本地执行
scp codex-manager.tar.gz user@vps_ip:/home/user/

# 或者使用 rsync
rsync -avz --progress codex-manager.tar.gz user@vps_ip:/home/user/
```

**在 VPS 上加载镜像：**

```bash
# 解压（如果压缩了）
gunzip codex-manager.tar.gz

# 加载镜像
docker load -i codex-manager.tar

# 验证镜像已加载
docker images | grep codex-manager
```

### 步骤 3：在 VPS 上直接构建（推荐）

```bash
# 克隆代码（如果有 git 仓库）
git clone <your-repo-url> codex-manager
cd codex-manager

# 或者直接上传代码
# scp -r ./codex-manager user@vps_ip:/home/user/

# 构建镜像
docker build -t codex-manager:latest .
```

### 步骤 4：创建目录结构

```bash
mkdir -p ~/codex-manager
cd ~/codex-manager

# 创建必要目录
mkdir -p data logs

# 设置权限（避免权限问题）
chmod 777 data logs
```

### 步骤 5：创建 docker-compose.yml

```bash
cat > docker-compose.yml << 'EOF'
x-webui-port: &webui-port 15555

services:
  webui:
    image: codex-manager:latest
    container_name: codex-manager
    ports:
      - "15555:15555"
    environment:
      WEBUI_HOST: 0.0.0.0
      WEBUI_PORT: 15555
      WEBUI_ACCESS_PASSWORD: "your_strong_password_here"
      DEBUG: 0
      LOG_LEVEL: info
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:15555/', timeout=5)\""]
      interval: 30s
      timeout: 10s
      retries: 3
EOF
```

**修改密码：**
```bash
# 编辑 docker-compose.yml，替换 your_strong_password_here
sed -i 's/your_strong_password_here/你的实际密码/g' docker-compose.yml
```

### 步骤 6：启动服务

```bash
# 启动
docker-compose up -d

# 查看状态
docker-compose ps

# 查看日志
docker-compose logs -f

# 等待数据库初始化完成（首次启动约 10-30 秒）
```

### 步骤 7：配置防火墙

```bash
# Ubuntu/Debian (UFW)
sudo ufw allow 15555/tcp
sudo ufw reload

# CentOS (firewalld)
sudo firewall-cmd --permanent --add-port=15555/tcp
sudo firewall-cmd --reload

# 或者使用 iptables
sudo iptables -I INPUT -p tcp --dport 15555 -j ACCEPT
sudo iptables-save
```

### 步骤 8：访问 WebUI

```
http://your_vps_ip:15555
```

---

## 方法四：使用纯 Docker 命令（无 Docker Compose）

```bash
# 创建目录
mkdir -p ~/codex-manager/data ~/codex-manager/logs
cd ~/codex-manager

# 运行容器
docker run -d \
  --name codex-manager \
  --restart unless-stopped \
  -p 15555:15555 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  -e WEBUI_HOST=0.0.0.0 \
  -e WEBUI_PORT=15555 \
  -e WEBUI_ACCESS_PASSWORD="your_password" \
  -e DEBUG=0 \
  -e LOG_LEVEL=info \
  codex-manager:latest

# 查看日志
docker logs -f codex-manager
```

---

## 常用管理命令

### 查看状态
```bash
# 查看容器状态
docker ps | grep codex-manager

# 查看资源使用
docker stats codex-manager

# 查看日志
docker logs -f codex-manager

# 查看最后 100 行日志
docker logs --tail 100 codex-manager
```

### 重启服务
```bash
# 使用 docker-compose
docker-compose restart

# 或者纯 docker
docker restart codex-manager
```

### 更新版本
```bash
# 1. 备份数据
cp -r data data-backup-$(date +%Y%m%d)

# 2. 停止服务
docker-compose down

# 3. 拉取/加载新镜像
docker pull your-registry/codex-manager:latest
# 或者加载本地镜像
docker load -i codex-manager-new.tar

# 4. 重新启动
docker-compose up -d

# 5. 验证
docker-compose logs -f
```

### 进入容器调试
```bash
# 进入容器
docker exec -it codex-manager bash

# 查看数据库
ls -la /app/data/

# 查看配置文件
cat /app/data/settings.json

# 退出
exit
```

### 备份数据
```bash
# 备份整个数据目录
tar -czvf codex-backup-$(date +%Y%m%d-%H%M%S).tar.gz data/ logs/

# 自动备份脚本（添加到 crontab）
# 每天凌晨 3 点备份
0 3 * * * cd /home/user/codex-manager && tar -czvf backups/codex-backup-$(date +\%Y\%m\%d).tar.gz data/ logs/
```

### 恢复数据
```bash
# 停止服务
docker-compose down

# 恢复数据
tar -xzvf codex-backup-20240101.tar.gz

# 重新启动
docker-compose up -d
```

---

## 配置反向代理（Nginx）

如果需要使用域名访问，配置 Nginx：

```bash
# 安装 nginx
sudo apt install -y nginx

# 创建配置文件
sudo tee /etc/nginx/sites-available/codex-manager << 'EOF'
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:15555;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}
EOF

# 启用配置
sudo ln -s /etc/nginx/sites-available/codex-manager /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# 配置 HTTPS（使用 Certbot）
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

---

## 环境变量说明

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `WEBUI_HOST` | 0.0.0.0 | 监听地址 |
| `WEBUI_PORT` | 15555 | 监听端口 |
| `WEBUI_ACCESS_PASSWORD` | - | 访问密码（必需） |
| `DEBUG` | 0 | 调试模式（0/1） |
| `LOG_LEVEL` | info | 日志级别（debug/info/warning/error） |
| `DATABASE_URL` | sqlite:///app/data/database.db | 数据库连接字符串 |

---

## 故障排查

### 容器无法启动
```bash
# 查看详细日志
docker logs codex-manager

# 检查端口占用
sudo netstat -tlnp | grep 15555
# 或
sudo ss -tlnp | grep 15555

# 修改端口（如果 15555 被占用）
# 编辑 docker-compose.yml，将 ports 改为 "15556:15555"
```

### 数据库权限错误
```bash
# 修复权限
sudo chown -R 1000:1000 data logs
sudo chmod -R 777 data logs

# 重启容器
docker-compose restart
```

### 内存不足
```bash
# 查看内存使用
free -h

# 添加 Swap（如果内存小于 1GB）
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

---

## 完整部署脚本

创建一键部署脚本 `deploy.sh`：

```bash
#!/bin/bash

# Codex Manager 一键部署脚本

set -e

echo "=== Codex Manager 部署脚本 ==="

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo "安装 Docker..."
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker $USER
fi

if ! command -v docker-compose &> /dev/null; then
    echo "安装 Docker Compose..."
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
fi

# 创建目录
INSTALL_DIR="${1:-$HOME/codex-manager}"
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# 设置密码
if [ -z "$WEBUI_PASSWORD" ]; then
    read -sp "请输入 WebUI 访问密码: " WEBUI_PASSWORD
    echo
fi

# 创建 docker-compose.yml
cat > docker-compose.yml << EOF
x-webui-port: &webui-port 15555

services:
  webui:
    image: codex-manager:latest
    container_name: codex-manager
    ports:
      - "15555:15555"
    environment:
      WEBUI_HOST: 0.0.0.0
      WEBUI_PORT: 15555
      WEBUI_ACCESS_PASSWORD: "$WEBUI_PASSWORD"
      DEBUG: 0
      LOG_LEVEL: info
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    restart: unless-stopped
EOF

# 创建目录
mkdir -p data logs

# 加载镜像或构建
if [ -f "codex-manager.tar" ]; then
    echo "加载本地镜像..."
    docker load -i codex-manager.tar
elif [ -f "codex-manager.tar.gz" ]; then
    echo "加载本地压缩镜像..."
    gunzip -c codex-manager.tar.gz | docker load
else
    echo "请在当前目录放置 codex-manager.tar 或 codex-manager.tar.gz"
    exit 1
fi

# 启动
docker-compose up -d

echo "=== 部署完成 ==="
echo "访问地址: http://$(curl -s ifconfig.me):15555"
echo "数据目录: $INSTALL_DIR/data"
echo "日志查看: docker-compose logs -f"
```

使用方法：
```bash
chmod +x deploy.sh
./deploy.sh
```
