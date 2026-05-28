# RK3588 远程连接本地 SITL 和 Gazebo

本文记录本地电脑运行 SITL/Gazebo，RK3588 运行本项目 `platform/rk3588`
分支时的连接方式。

示例 IP：

```text
本地电脑: 10.31.18.107
RK3588:   10.31.18.109
```

目标拓扑：

```text
本地电脑 10.31.18.107
  ArduPilot SITL + Gazebo
  MAVLink -> 10.31.18.109:14550
  Gazebo 视频 -> 10.31.18.109:5600

RK3588 10.31.18.109
  app      接收 MAVLink、运行 Web UI、执行 mission
  yolo_app 接收 Gazebo 视频、运行 RKNN 推理、输出目标 UDP
```

## TCP 和 UDP 区别

| 项目 | TCP | UDP |
| --- | --- | --- |
| 是否建立连接 | 需要连接，例如客户端连服务器 | 不需要连接，直接往 IP:端口发包 |
| 可靠性 | 保证顺序和重传 | 不保证一定送达，也不保证顺序 |
| 延迟 | 稍高，丢包时会重传等待 | 低，适合实时数据 |
| 常见用途 | Web、SSH、文件传输 | 视频流、遥测、实时控制、广播 |
| 本项目用途 | Web UI: `8080/tcp`，MJPEG: `8081/tcp` | MAVLink: `14550/udp`，YOLO 数据: `5005/udp`，Gazebo 视频: `5600/udp` |

为什么远程 SITL 推荐 UDP：

- SITL/MAVLink 是实时遥测和控制，允许少量包丢失，更看重低延迟。
- 本地电脑可以用 `--out=udp:<rk3588-ip>:14550` 主动把 MAVLink 发到板子。
- RK3588 只需要监听 `0.0.0.0:14550`，不用让本地电脑开放 TCP server。

什么时候用 TCP：

- SITL 和 app 都在同一台电脑时，可以用 `tcp:127.0.0.1:5762`。
- 需要可靠字节流时，例如 SSH、HTTP、Web UI。

## 端口表

| 端口 | 协议 | 运行位置 | 说明 |
| --- | --- | --- | --- |
| `14550` | UDP | RK3588 | app 接收本地 SITL MAVLink |
| `5600` | UDP | RK3588 | yolo_app 接收 Gazebo H264/RTP 视频 |
| `5005` | UDP | RK3588 | app 接收 yolo_app 检测结果 |
| `5006` | UDP | RK3588 | yolo_app 接收网页目标锁定命令 |
| `8080` | TCP | RK3588 | Web UI |
| `8081` | TCP | RK3588 | YOLO MJPEG 标注视频 |

## RK3588 配置

登录板子：

```bash
ssh pi@10.31.18.109
cd ~/uav_project
git switch platform/rk3588
```

### MAVLink 配置

编辑 `config/telemetry.yaml`：

```yaml
data_source: sitl
active_source: sitl

sitl:
  connection_type: udp
  udp_mode: udpin
  udp_host: 0.0.0.0
  udp_port: 14550
  tcp_host: 127.0.0.1
  tcp_port: 5762
```

这里的含义：

- `connection_type: udp`：使用 UDP。
- `udp_mode: udpin`：RK3588 监听端口，等待本地电脑发 MAVLink 过来。
- `udp_host: 0.0.0.0`：监听所有网卡。
- `udp_port: 14550`：监听 14550 端口。

### YOLO 视频配置

编辑 `yolo_app/config.yaml`：

```yaml
source: 5600

udp_ip: "127.0.0.1"
udp_port: 5005

web_stream:
  enabled: true
  host: "0.0.0.0"
  port: 8081
```

这里的含义：

- `source: 5600`：yolo_app 从 RK3588 本机 `5600/udp` 接收 Gazebo 视频。
- `udp_ip: "127.0.0.1"`：YOLO 检测结果发给同一块板子上的 app。
- `udp_port: 5005`：对应 app 的 YOLO UDP 输入端口。

### app 安全配置

编辑 `config/app.yaml`，先保持不发控制命令：

```yaml
services:
  connect_telemetry: true
  start_yolo_udp: true

executor:
  send_commands: false
```

只在 SITL 中确认控制方向后，再打开 `send_commands: true`。

### UDP 视频依赖

当前 RK3588 分支中，`yolo_app` 主程序运行在 conda `yolo` 环境，但
`source: 5600` 会额外启动系统 Python 的 `udp_gst_bridge_helper.py`
做 GStreamer 解码。因此系统 Python 也需要 OpenCV/GStreamer 支持。

检查：

```bash
/usr/bin/python3 - <<'PY'
import cv2
print(cv2.__version__)
print([line.strip() for line in cv2.getBuildInformation().splitlines() if "GStreamer" in line])
PY
```

如果报 `ModuleNotFoundError: No module named 'cv2'`，安装：

```bash
sudo apt-get install -y python3-opencv
```

## RK3588 启动服务

```bash
systemctl --user restart uav-app.service uav-yolo.service
```

看状态：

```bash
systemctl --user --no-pager --full status uav-app.service uav-yolo.service
```

看日志：

```bash
journalctl --user -u uav-app.service -f
journalctl --user -u uav-yolo.service -f
```

正常端口应类似：

```bash
ss -ltnup | grep -E ':8080|:8081|:5005|:5006|:14550|:5600'
```

期望看到：

```text
0.0.0.0:14550 udp
0.0.0.0:5005  udp
0.0.0.0:5006  udp
0.0.0.0:5600  udp
0.0.0.0:8080  tcp
0.0.0.0:8081  tcp
```

## 本地电脑启动 SITL

本地电脑 IP 是 `10.31.18.107`，RK3588 IP 是 `10.31.18.109`。

启动 SITL 时，把 MAVLink 输出到 RK3588：

```bash
sim_vehicle.py -v ArduCopter -f gazebo-iris --console --map --out=udp:10.31.18.109:14550
```

如果你原本有自己的 `sim_vehicle.py` 参数，只追加：

```bash
--out=udp:10.31.18.109:14550
```

RK3588 的 app 日志中应看到：

```text
heartbeat received
link ready connection_type=udp endpoint=udpin:0.0.0.0:14550
```

## 本地电脑发送 Gazebo 视频

先启用 Gazebo 相机流。项目中常用 topic：

```bash
gz topic \
  -t /world/iris_runway/model/iris_with_gimbal/model/gimbal/link/pitch_link/sensor/camera/image/enable_streaming \
  -m gz.msgs.Boolean -p "data: 1"
```

如果 Gazebo 插件能直接配置视频目标 IP，把视频目标设为：

```text
10.31.18.109:5600
```

如果本地已经有一路 H264/RTP 视频在本地 `5600/udp`，可以转发到 RK3588：

```bash
gst-launch-1.0 -v \
  udpsrc port=5600 caps="application/x-rtp,media=video,encoding-name=H264,payload=96" \
  ! rtph264depay \
  ! h264parse \
  ! rtph264pay config-interval=1 pt=96 \
  ! udpsink host=10.31.18.109 port=5600
```

RK3588 的 yolo 日志中应看到：

```text
frame=... fps=... tracks=...
```

`tracks=0` 只表示当前画面没有检测到目标，视频链路本身可能已经正常。

## Web UI 验证

在本地电脑浏览器打开：

```text
http://10.31.18.109:8080/
```

检查：

- telemetry 是否 connected。
- 视频画面是否出现。
- `target_valid`、`track_id`、`target_size` 是否随目标变化。
- `send_commands` 是否仍为 false。

直接检查接口：

```bash
curl -fsS http://10.31.18.109:8080/api/status
```

检查 MJPEG 视频：

```bash
curl -v http://10.31.18.109:8081/video/yolo.mjpeg
```

## 常见问题

### app 一直连 `tcp:127.0.0.1:5762`

说明 `config/telemetry.yaml` 还没改成 UDP，或改完没有重启 app。

处理：

```bash
grep -A10 '^sitl:' config/telemetry.yaml
systemctl --user restart uav-app.service
```

### app 收不到 heartbeat

检查本地 SITL 是否带了：

```bash
--out=udp:10.31.18.109:14550
```

检查 RK3588 是否监听：

```bash
ss -lunp | grep ':14550'
```

检查两边是否同一 WiFi，且本地能 ping 板子：

```bash
ping 10.31.18.109
```

### yolo_app 反复重启，日志有 `No module named cv2`

如果错误来自：

```text
/home/pi/uav_project/yolo_app/udp_gst_bridge_helper.py
ModuleNotFoundError: No module named 'cv2'
```

说明系统 Python 缺少 OpenCV。安装：

```bash
sudo apt-get install -y python3-opencv
systemctl --user restart uav-yolo.service
```

### 8081 没有视频

检查 yolo 服务和端口：

```bash
systemctl --user --no-pager --full status uav-yolo.service
ss -ltnup | grep -E ':8081|:5600'
journalctl --user -u uav-yolo.service -n 80 --no-pager
```

如果没有 `frame=... fps=...`，说明视频还没有从本地电脑发到 RK3588 的
`5600/udp`，或 GStreamer 格式不匹配。

### 有视频但 `tracks=0`

这是检测结果为空，不是网络不通。检查：

- Gazebo 画面中是否真的有目标。
- `target_class` 是否和模型类别一致。
- `class_names` 是否和 RKNN 模型类别顺序一致。
- `conf_thres` 是否过高。

## 安全顺序

建议每次按这个顺序：

1. RK3588 保持 `send_commands: false`。
2. 本地启动 SITL/Gazebo。
3. RK3588 启动 app/yolo 服务。
4. 打开 Web UI，确认 telemetry 和视频。
5. 确认目标检测和控制方向。
6. 只在 SITL 中打开 `send_commands: true`。

