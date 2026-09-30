# 阿里云 ACR 镜像部署操作手册

适用于当前 `token.tsctt.icu` 的单台 ECS：Mac 构建 `linux/amd64` 后端和前端镜像，推送到阿里云容器镜像服务（ACR），ECS 只拉取并运行镜像。前后端使用**同一个 Git 提交号**作为版本，仍是两个容器；MySQL、Redis、备份及数据卷继续沿用现有 Compose 项目。宿主机 Nginx 保持 HTTPS 入口，代理到项目容器的 `127.0.0.1:8083`。

本文的“迁移现有 ECS”只替换应用容器，不重新初始化数据库。新机器可按“首次部署新机器”操作。命令分别标明在 Mac 或 ECS 执行；不要把 `.env`、ACR 密码或私钥写入仓库或发到聊天中。

## 1. 准备 ACR 仓库

1. 在 ACR 控制台选择与 ECS 相同的地域，创建一个命名空间及两个**私有**镜像仓库：`token-backend`、`token-frontend`。
2. 在“访问凭证”中设置独立的 Registry 登录密码，记录控制台给出的登录名和地址。Mac 使用公网地址；ECS 若能访问控制台给出的 VPC 地址，优先使用 VPC 地址。两种地址必须指向同一个 ACR 实例、命名空间和仓库。不要猜测地址格式。
3. 正式生产服务需核对 ACR 实例类型：阿里云将个人版定位为开发测试用途，且不提供 SLA。参见[ACR 个人版说明](https://help.aliyun.com/zh/acr/user-guide/create-a-container-registry-personal-edition-instance)和[推拉镜像说明](https://help.aliyun.com/zh/acr/user-guide/use-a-container-registry-personal-edition-instance-to-push-and-pull-images)。

下文用两个前缀表示仓库路径，均**不带** `https://` 和末尾 `/`：

```text
Mac 推送前缀：<ACR 公网域名>/<命名空间>
ECS 拉取前缀：<ACR VPC 域名或公网域名>/<命名空间>
```

## 2. 在 Mac 构建并推送一次发布

在本地仓库根目录执行。先提交本次要发布的前后端代码；版本号取该提交的前 12 位，避免 `latest` 无法确定具体内容。前端 Dockerfile 在本机架构上完成静态构建，最终 Nginx 镜像仍是 ECS 所需的 `linux/amd64`。

```bash
cd /你的路径/token_manager
git status --short
git rev-parse HEAD
RELEASE_TAG=$(git rev-parse --short=12 HEAD)
ACR_PUBLIC_HOST='<控制台给出的公网域名>'
ACR_PUBLIC_PREFIX="$ACR_PUBLIC_HOST/<命名空间>"
docker login -u '<ACR 登录名>' "$ACR_PUBLIC_HOST"
docker buildx build --platform linux/amd64 -t "$ACR_PUBLIC_PREFIX/token-backend:$RELEASE_TAG" --push ./backend
docker buildx build --platform linux/amd64 -t "$ACR_PUBLIC_PREFIX/token-frontend:$RELEASE_TAG" --push ./frontend
docker buildx imagetools inspect "$ACR_PUBLIC_PREFIX/token-backend:$RELEASE_TAG"
docker buildx imagetools inspect "$ACR_PUBLIC_PREFIX/token-frontend:$RELEASE_TAG"
```

`git status --short` 应没有尚未提交的**应用代码**改动；确认两次 `imagetools inspect` 均包含 `linux/amd64`。两个 `--push` 都成功后，再更新 ECS。构建时不传生产 `.env` 或密钥。Apple 芯片和 Intel Mac 均使用上述命令。[Docker Buildx 平台说明](https://docs.docker.com/build/building/multi-platform/)

## 3. 迁移当前已运行的 ECS（只做一次）

当前 ECS 已有 `/opt/token-manager`、`/etc/token-manager/.env`、MySQL/Redis 数据卷、宿主机 Nginx 和 `token.tsctt.icu` 证书。**保留**原 `.env` 里的 MySQL、Redis、`SECRET_KEY` 和 `SECRET_ENCRYPTION_KEY`，不要重新生成；只改镜像来源和前端文件来源。

### 3.1 更新部署配置并备份数据库

先把包含本手册和 `deploy/compose.acr.yaml` 的提交推送到代码仓库，再在 ECS 执行：

```bash
cd /opt/token-manager
git status --short
git pull --ff-only
test -f deploy/compose.acr.yaml
test -s /etc/token-manager/.env
sudo install -d -m 700 /opt/token-manager/backups
sudo install -d -m 755 /var/log/token-manager/nginx
```

若 `git pull --ff-only` 因本机改动或分支不同而失败，先核对 ECS 当前分支和文件，不要强制覆盖。切换前做一次逻辑备份：

```bash
set -o pipefail
sudo docker exec token-mysql sh -c 'exec mysqldump --single-transaction --routines --triggers --no-tablespaces -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"' | gzip | sudo tee "/opt/token-manager/backups/pre-acr-$(date +%F-%H%M%S).sql.gz" > /dev/null
ls -lh /opt/token-manager/backups/pre-acr-*.sql.gz
```

如果备份命令失败，停止迁移；不要用 `docker compose down -v`，它会删除数据库卷。

### 3.2 登录 ACR 并指定发布版本

在 ECS 执行。先从 Mac 上的 `RELEASE_TAG` 命令结果取得**同一个** 12 位版本号。`release.env` 只放镜像地址和版本，不放密码：

```bash
ACR_ECS_HOST='<控制台给出的 ECS 可访问域名>'
sudo docker login -u '<ACR 登录名>' "$ACR_ECS_HOST"
sudoedit /etc/token-manager/release.env
```

写入以下两行，替换尖括号内容；域名部分应与刚才登录的地址相同：

```dotenv
ACR_IMAGE_PREFIX=<ECS 可访问域名>/<命名空间>
RELEASE_TAG=<Mac 构建时的 12 位提交号>
```

```bash
sudo chmod 600 /etc/token-manager/release.env
```

当前运行 `sudo docker compose`，所以 ECS 上也用 `sudo docker login`：登录信息由 Docker 保存给 root 用户，不能把 Registry 密码写进 Compose 或应用 `.env`。

### 3.3 拉取并切换应用容器

在 ECS 的 `/opt/token-manager` 执行以下完整命令。`config --quiet` 没有错误才继续；`pull` 必须同时完成前后端两个镜像，再运行 `up`。首次切换时后端会执行 `alembic upgrade head`。

```bash
cd /opt/token-manager
sudo docker compose --env-file /etc/token-manager/.env --env-file /etc/token-manager/release.env -f docker-compose.yml -f deploy/compose.acr.yaml config --quiet
sudo docker compose --env-file /etc/token-manager/.env --env-file /etc/token-manager/release.env -f docker-compose.yml -f deploy/compose.acr.yaml pull backend nginx
sudo docker compose --env-file /etc/token-manager/.env --env-file /etc/token-manager/release.env -f docker-compose.yml -f deploy/compose.acr.yaml up -d --no-build --pull never backend nginx
sudo docker compose --env-file /etc/token-manager/.env --env-file /etc/token-manager/release.env -f docker-compose.yml -f deploy/compose.acr.yaml ps
curl --fail http://127.0.0.1:8083/health
curl --fail https://token.tsctt.icu/health
curl -I https://token.tsctt.icu/
```

健康接口应返回 `status: healthy`，首页应返回 HTTP 200。`upstream: not_configured` 只表示尚未配置上游渠道。若失败，查看日志：

```bash
sudo docker compose --env-file /etc/token-manager/.env --env-file /etc/token-manager/release.env -f docker-compose.yml -f deploy/compose.acr.yaml logs --tail=100 backend nginx
```

本次切换会重建 `token-backend` 和 `token-nginx`，有短暂中断。MySQL、Redis、数据卷、`127.0.0.1:8083` 和宿主机 HTTPS 配置不变；旧 `/etc/token-manager/compose.aliyun.yaml` 不再用于新命令。`frontend/dist` 不再从 ECS 目录挂载，页面文件来自前端镜像。

## 4. 以后每次发布

1. Mac 按第 2 节为新 Git 提交构建并推送两个相同版本号的镜像。
2. 若本次只改前后端应用代码，ECS 无需 `git pull`；若改了 `docker-compose.yml`、`deploy/` 或备份脚本，先更新 ECS 的仓库文件并核对变更。
3. 在 ECS 用 `sudoedit /etc/token-manager/release.env` **只修改** `RELEASE_TAG`，保留 `ACR_IMAGE_PREFIX` 和生产 `.env`。如果本次包含数据库迁移，先按第 3.1 节备份。
4. 执行：

   ```bash
   cd /opt/token-manager
   sudo docker compose --env-file /etc/token-manager/.env --env-file /etc/token-manager/release.env -f docker-compose.yml -f deploy/compose.acr.yaml config --quiet
   sudo docker compose --env-file /etc/token-manager/.env --env-file /etc/token-manager/release.env -f docker-compose.yml -f deploy/compose.acr.yaml pull backend nginx
   sudo docker compose --env-file /etc/token-manager/.env --env-file /etc/token-manager/release.env -f docker-compose.yml -f deploy/compose.acr.yaml up -d --no-build --pull never backend nginx
   curl --fail https://token.tsctt.icu/health
   curl -I https://token.tsctt.icu/
   ```

每次先推送**两个**镜像，再改 `RELEASE_TAG`；不要让前后端指向不同提交。不要用 `latest` 或 `docker compose down -v`。低配置 ECS 仍需留出下载和保留上一个版本镜像的磁盘空间；用 `df -h /var/lib/docker` 和 `docker stats --no-stream` 检查。把构建移到 Mac 只能减少部署时的负担，不能降低 MySQL、Grafana 等服务的运行内存。

## 5. 回滚

若新版本健康检查失败，打开 `/etc/token-manager/release.env`，把 `RELEASE_TAG` 改回上一个已验证版本，然后在 ECS 执行：

```bash
cd /opt/token-manager
sudo docker compose --env-file /etc/token-manager/.env --env-file /etc/token-manager/release.env -f docker-compose.yml -f deploy/compose.acr.yaml pull backend nginx
sudo docker compose --env-file /etc/token-manager/.env --env-file /etc/token-manager/release.env -f docker-compose.yml -f deploy/compose.acr.yaml up -d --no-build --pull never backend nginx
curl --fail https://token.tsctt.icu/health
```

镜像回滚**不会**回滚数据库结构。如果本次迁移与旧后端不兼容，先停止发布并按[灾备恢复手册](灾备恢复手册.md)评估数据库恢复。保留至少一个上一个版本的镜像和备份，再清理旧镜像。

## 6. 首次部署新机器的差异

新机器先安装 Docker Compose 2.24.4 或更高版本、宿主机 Nginx 和 Certbot；将本仓库克隆到 `/opt/token-manager`，并配置 `token.tsctt.icu` 的 DNS A 记录指向 ECS 公网 IP。创建 `/etc/token-manager/.env`，分别运行五次 `openssl rand -hex 32` 生成五个独立密码或密钥，再运行一次 `openssl rand -base64 32` 生成 `SECRET_ENCRYPTION_KEY`；**不要**使用仓库默认密码：

```dotenv
MYSQL_ROOT_PASSWORD=<独立随机值>
MYSQL_DATABASE=token_db
MYSQL_USER=token_user
MYSQL_PASSWORD=<独立随机值>
REDIS_PASSWORD=<独立随机值>
SECRET_KEY=<独立随机值>
SECRET_ENCRYPTION_KEY=<openssl rand -base64 32 的结果>
GRAFANA_PASSWORD=<独立随机值>
```

```bash
sudo install -d -m 700 /etc/token-manager /opt/token-manager/backups
sudo install -d -m 755 /var/log/token-manager/nginx
sudoedit /etc/token-manager/.env
sudo chmod 600 /etc/token-manager/.env
```

按第 1–2 节创建仓库并推送镜像，按第 3.2 节创建 `release.env`。新机器还需拉取 MySQL、Redis、Prometheus、Grafana 等基础镜像，因此第一次启动执行：

```bash
cd /opt/token-manager
sudo docker compose --env-file /etc/token-manager/.env --env-file /etc/token-manager/release.env -f docker-compose.yml -f deploy/compose.acr.yaml config --quiet
sudo docker compose --env-file /etc/token-manager/.env --env-file /etc/token-manager/release.env -f docker-compose.yml -f deploy/compose.acr.yaml up -d --no-build
curl --fail http://127.0.0.1:8083/health
```

当前 ECS 已遇到 Docker Hub 镜像加速源把存在的 `redis:7-alpine` 错报为 `not found`。新机器若遇到类似错误，应先核对加速源；必要时一次性从可访问的机器预载基础镜像。应用镜像的日常更新只从 ACR 拉取。

宿主机 Nginx 为 `token.tsctt.icu` 单独建站，不修改其他域名的 `server`。确认 `/etc/nginx/conf.d/token-manager.conf` 不存在后创建：

```bash
sudo tee /etc/nginx/conf.d/token-manager.conf > /dev/null <<'NGINX'
server {
    listen 80;
    server_name token.tsctt.icu;

    location / {
        proxy_pass http://127.0.0.1:8083;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 300s;
        proxy_buffering off;
    }
}
NGINX
sudo nginx -t
sudo systemctl enable --now nginx
curl --fail -H 'Host: token.tsctt.icu' http://127.0.0.1/health
```

确认 `certbot plugins` 列出 `nginx`；若 Ubuntu 上缺少插件，先执行 `sudo apt install python3-certbot-nginx`。随后申请证书并验证：

```bash
sudo certbot --nginx -d token.tsctt.icu
sudo nginx -t
curl --fail https://token.tsctt.icu/health
sudo certbot renew --dry-run
```

现有 ECS 已完成域名和证书设置，迁移时不要重复创建站点或申请证书。

首次启动会创建管理员 `admin`（初始密码 `admin123`）和测试用户 `testuser`（初始密码 `user123`）。上线后立即修改管理员密码，并禁用或删除测试账号；不要把初始密码留在公网服务上。`SECRET_ENCRYPTION_KEY` 后续必须保持不变，否则数据库中已加密的渠道密钥无法解密。
