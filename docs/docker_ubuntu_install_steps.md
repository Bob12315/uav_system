# 新装 Ubuntu Docker 部署步骤

本文面向一台新装 Ubuntu 22.04/24.04 机器，用 Docker Compose 启动本项目。默认先启动安全 dry-run 的 `uav-control` 主控/Web UI；YOLO、GPU、摄像头、串口和 SITL 在后面单独开启。

## 1. 系统准备

更新系统包，并安装基础工具：

```bash
sudo apt-get update
sudo apt-get install -y \
  ca-certificates \
  curl \
  gnupg \
  git \
  lsb-release
```

如果机器之前装过 Docker Desktop 的 `.deb`，不建议混用 Docker Desktop 和服务器版 Docker Engine。可以先检查：

```bash
docker --version || true
systemctl status docker --no-pager || true
```

如果 `docker --version` 有输出，但 `docker.service could not be found`，说明只有客户端或安装不完整，继续按下面步骤安装 Docker Engine。

## 2. 安装 Docker Engine（国内推荐：Aliyun 镜像）

国内访问 Docker 官方源可能较慢，推荐使用 Docker 官方安装脚本，并指定 Aliyun 镜像：

```bash
curl -fsSL https://get.docker.com | bash -s docker --mirror Aliyun

安装完成后，确认 Docker 服务已启动：

sudo systemctl enable --now docker

结果
Synchronizing state of docker.service with SysV service script with /lib/systemd/systemd-sysv-install.
Executing: /lib/systemd/systemd-sysv-install enable docker


验证安装结果：

docker --version
docker compose version
systemctl is-active docker

systemctl is-active docker 应输出：active

## 3. 配置当前用户使用 Docker

把当前用户加入 `docker` 组：

```bash
sudo groupadd docker 2>/dev/null || true
sudo usermod -aG docker "$USER"
```

刷新当前 shell 的组权限：

```bash
newgrp docker
```

验证无需 sudo 可以访问 Docker：

```bash
docker ps
```

如果仍提示 permission denied，注销并重新登录，或临时用：

```bash
sg docker -c 'docker ps'
```

## 4. 获取项目代码


```bash
mkdir -p ~/uav_project
cd ~/uav_project
git clone https://github.com/Bob12315/uav_system.git src
cd src
```

切换到 Docker 分支：

```bash
git fetch --all
git checkout docker
```

确认 Docker 文件存在：

```bash
ls Dockerfile.control Dockerfile.yolo docker-compose.yml
ls config/app.docker.yaml yolo_app/config.docker.yaml
```

## 5. 准备模型目录

主控容器不需要模型，但 YOLO 容器需要。先创建目录：

```bash
mkdir -p data/models runtime
```

如果已有训练权重，把它放到：

```bash
cp /path/to/best.pt data/models/best.pt
```

没有模型也可以先只启动 `uav-control`。

## 6. 构建并启动主控 Web UI

首次构建：

```bash
docker compose up --build uav-control
```

看到类似日志说明主控已经正常运行：

```text
uav-control | ... Web UI listening at http://0.0.0.0:8000
uav-control | ... mode=IDLE mission=IDLE ...
```

浏览器打开：

```text
http://127.0.0.1:8000
```

确认页面正常后，按 `Ctrl+C` 停止前台运行，再后台启动：

```bash
docker compose up -d uav-control
```

查看状态：

```bash
docker compose ps
docker compose logs --tail=50 uav-control
```

停止：

```bash
docker compose down
```

## 7. 如果 Docker Hub 拉镜像很慢

本项目的 Dockerfile 默认使用华为云 Docker Hub 代理基础镜像：

```text
swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/library/python:3.10-slim
swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/library/python:3.11-slim
```

如果你想改回官方 Docker Hub，可构建时覆盖 build arg：

```bash
docker compose build \
  --build-arg CONTROL_BASE_IMAGE=python:3.10-slim \
  uav-control
```

如果容器内 `apt-get update` 很慢，可以临时多等一会儿；第一次构建成功后会有缓存。必要时再把 Dockerfile 内 Debian 源切到国内镜像。

## 8. 启动 YOLO 容器

确认模型存在：

```bash
ls data/models/best.pt
```

默认 YOLO 配置在：

```text
yolo_app/config.docker.yaml
```

默认配置：

- 模型：`../data/models/best.pt`
- 推理设备：`cpu`
- 输入源：UDP/RTP H264 `5600`
- 目标输出：`uav-control:5005`
- MJPEG：`http://127.0.0.1:8010/video.mjpeg`

启动主控 + YOLO：

```bash
docker compose --profile yolo up --build
```

后台启动：

```bash
docker compose --profile yolo up -d
```

查看日志：

```bash
docker compose logs -f uav-yolo
```

## 9. UDP H264 视频输入

如果外部视频流发送到宿主机 UDP `5600`，打开 `docker-compose.yml` 里 `uav-yolo.ports` 的这一行：

```yaml
- "5600:5600/udp"
```

然后重新启动：

```bash
docker compose --profile yolo up -d --build
```

## 10. USB 摄像头输入

查看摄像头设备：

```bash
ls /dev/video*
v4l2-ctl --list-devices 2>/dev/null || true
```

打开 `docker-compose.yml` 中 `uav-yolo.volumes` 的设备映射：

```yaml
- /dev/video0:/dev/video0
```

修改 `yolo_app/config.docker.yaml`：

```yaml
source: "/dev/video0"
```

重启 YOLO：

```bash
docker compose --profile yolo up -d --build uav-yolo
```

## 11. NVIDIA GPU

先确认宿主机驱动：

```bash
nvidia-smi
```

安装 NVIDIA Container Toolkit：

```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

验证容器能看到 GPU：

```bash
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
```

给 `docker-compose.yml` 的 `uav-yolo` 增加：

```yaml
gpus: all
environment:
  NVIDIA_VISIBLE_DEVICES: all
  NVIDIA_DRIVER_CAPABILITIES: compute,utility,video
```

修改 `yolo_app/config.docker.yaml`：

```yaml
device: "0"
```

重建 YOLO：

```bash
docker compose --profile yolo up -d --build uav-yolo
```

## 12. 连接 SITL

如果 SITL 在宿主机运行，容器内不能用 `127.0.0.1` 指向宿主机，应使用：

```text
host.docker.internal
```

配置模板：

```text
config/telemetry.docker.yaml
```

以 dry-run 方式连接 telemetry：

```bash
docker compose run --rm uav-control \
  python -m app.main \
  --app-config config/app.docker.yaml \
  --telemetry-config config/telemetry.docker.yaml \
  --connect-telemetry \
  --send-commands false
```

实发控制前必须保持 `--send-commands false` 完成方向和安全验证。

## 13. 真机串口

查看飞控串口：

```bash
ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || true
```

给 `docker-compose.yml` 的 `uav-control` 增加：

```yaml
devices:
  - /dev/ttyUSB0:/dev/ttyUSB0
```

确认用户有串口权限：

```bash
groups
sudo usermod -aG dialout "$USER"
```

加入 `dialout` 后需要重新登录才会生效。

实机前确认：

```yaml
send_commands: false
```

不要在首次连真机时直接打开 `send_commands: true`。

## 14. 常用命令

查看服务：

```bash
docker compose ps
```

看主控日志：

```bash
docker compose logs -f uav-control
```

看 YOLO 日志：

```bash
docker compose logs -f uav-yolo
```

重启主控：

```bash
docker compose restart uav-control
```

停止全部服务：

```bash
docker compose down
```

重新构建：

```bash
docker compose build --no-cache uav-control
docker compose --profile yolo build --no-cache
```

清理未使用镜像和缓存：

```bash
docker system prune
```

## 15. 常见问题

### permission denied while trying to connect to the Docker daemon

当前用户组没生效。执行：

```bash
newgrp docker
docker ps
```

如果还不行，注销重新登录。

临时办法：

```bash
sg docker -c 'docker compose ps'
```

### docker.service could not be found

Docker Engine 没装完整。回到第 2 步安装 `docker-ce`、`docker-ce-cli`、`containerd.io`、`docker-buildx-plugin`、`docker-compose-plugin`。

### NO_PUBKEY 或 Docker APT 源没有数字签名

重新执行第 2 步的 Docker GPG key 和 source list 命令，确保 `signed-by=/etc/apt/keyrings/docker.gpg` 存在。

### Web UI 能打开但没有视频

先确认 YOLO 是否启动：

```bash
docker compose --profile yolo ps
docker compose logs --tail=100 uav-yolo
```

再确认 MJPEG：

```text
http://127.0.0.1:8010/video.mjpeg
```

如果没有视频源，YOLO 可能会报无法打开 `source`，需要检查 `yolo_app/config.docker.yaml` 的 `source` 和 compose 端口/设备映射。

### 容器里连接不到宿主机 SITL

不要用 `127.0.0.1`，改用：

```text
host.docker.internal
```

本项目 compose 已配置：

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

### 普通 docker 命令不行，但 sg docker 可以

说明 `level6` 已加入 `docker` 组，但当前 shell 没刷新。执行 `newgrp docker` 或重新登录。
