# Docker 运行说明

本项目的 Docker 形态采用两个服务：

- `uav-control`：主控、Web UI、MAVLink/telemetry、YOLO UDP 接收。
- `uav-yolo`：YOLO/ByteTrack、视频输入、MJPEG 输出、目标 UDP 发布。

默认配置是安全的 dry-run 入口：Web UI 会启动，`send_commands` 为 `false`，默认不连接 telemetry。

## 准备

将模型权重放到：

```bash
mkdir -p data/models
cp /path/to/best.pt data/models/best.pt
```

模型文件通过 volume 挂载，不会打进镜像。

## 启动主控和 Web UI

```bash
docker compose up --build uav-control
```

浏览器打开：

```text
http://127.0.0.1:8000
```

## 同时启动 YOLO

```bash
docker compose --profile yolo up --build
```

YOLO 默认：

- 读取 UDP/RTP H264 `5600`，需要在 `docker-compose.yml` 里打开 `5600:5600/udp`。
- 输出目标 JSON 到 `uav-control:5005`。
- 输出 MJPEG 到 `http://127.0.0.1:8010/video.mjpeg`。

## 使用 USB 摄像头

在 `docker-compose.yml` 的 `uav-yolo.volumes` 中打开：

```yaml
- /dev/video0:/dev/video0
```

然后把 `yolo_app/config.docker.yaml` 改为：

```yaml
source: "/dev/video0"
```

## 使用 GPU

宿主机需要先安装 NVIDIA driver 和 NVIDIA Container Toolkit。之后给 `uav-yolo` 增加：

```yaml
gpus: all
environment:
  NVIDIA_VISIBLE_DEVICES: all
  NVIDIA_DRIVER_CAPABILITIES: compute,utility,video
```

再把 `yolo_app/config.docker.yaml` 改为：

```yaml
device: "0"
```

## 连接宿主机 SITL

Docker 容器内的 `127.0.0.1` 是容器自己。连接宿主机 SITL 时使用：

```text
host.docker.internal:5762
```

配置模板见 `config/telemetry.docker.yaml`。启动主控时可以显式指定：

```bash
docker compose run --rm uav-control \
  python -m app.main \
  --app-config config/app.docker.yaml \
  --telemetry-config config/telemetry.docker.yaml \
  --connect-telemetry \
  --send-commands false
```

## 真机串口

给 `uav-control` 挂载串口，例如：

```yaml
devices:
  - /dev/ttyUSB0:/dev/ttyUSB0
```

然后使用 `config/telemetry.docker.yaml` 的 `real` 配置。实机前保持：

```yaml
send_commands: false
```

确认 telemetry、姿态、云台反馈、控制方向都正确后，再考虑打开实发。

## 当前限制

Web UI 的 `Start YOLO` 按钮在 Docker 形态下不负责创建另一个容器；YOLO 应由 Compose 管理。按钮状态可以作为后续增强项，改成查询 compose 服务或只显示提示。
