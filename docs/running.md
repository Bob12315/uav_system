# 运行手册

以下命令默认工作目录为：

```bash
cd ~/uav_project/src
```

## 1. 启动 YOLO

YOLO 建议在独立 conda 环境中运行：

```bash
conda activate yolo
cd ~/uav_project/src/yolo_app
python main.py
```

确认 `yolo_app/config.yaml` 中 UDP 输出端口与 `config/app.yaml` 一致。控制端默认监听：

```yaml
runtime:
  yolo_udp_ip: "0.0.0.0"
  yolo_udp_port: 5005
```

## 2. app dry-run，不连接飞控

```bash
conda activate uav-control
cd ~/uav_project/src
python -m app.main --send-commands false
```

自动退出 smoke test：

```bash
python -m app.main --no-yolo-udp --run-seconds 2 --send-commands false
```

## 3. app 连接 telemetry，但不发控制

```bash
python -m app.main --connect-telemetry --send-commands false
```

如果 SITL/飞控尚未启动，telemetry 会在后台重连，app 主循环仍会运行。

## 4. app + UI

```bash
python -m app.main --connect-telemetry --ui --send-commands false
```

这是 curses 终端 UI，不是网页 GUI。当前 UI 依赖 `LinkManager`，所以需要 `--connect-telemetry`。

## 5. app + Web UI

先安装 Web UI 依赖：

```bash
pip install -r requirements/web.txt
```

默认启动控制端 Web UI：

```bash
cd ~/uav_project/src
python -m app.main
```

浏览器打开：

```text
http://127.0.0.1:8000
```

在 Web UI 左侧 `Services / 服务` 点击 `Start YOLO / 启动 YOLO`，后端会执行等价命令：

```bash
conda activate yolo
python3 ~/uav_project/src/yolo_app/main.py --show false
```

YOLO 默认会同时输出 UDP JSON 和 MJPEG 标注画面。MJPEG 默认地址：

```text
http://127.0.0.1:8010/video.mjpeg
```

可选参数：

```bash
python -m app.main \
  --web-host 127.0.0.1 \
  --web-port 8000 \
  --yolo-mjpeg-url http://127.0.0.1:8010/video.mjpeg \
  --send-commands false
```

Web UI 默认只监听本机。`control send on`、`mission start`、`arm`、`takeoff`、`land`、`disarm`、payload/servo/relay 等危险命令会在前端二次确认。

## 6. 独立 telemetry 服务

```bash
python -m telemetry_link.main --config config/telemetry.yaml
```

打开 telemetry UI：

```bash
python -m telemetry_link.main --config config/telemetry.yaml --ui
```

## 7. SITL 低风险顺序

1. 启动 SITL。
2. 启动 YOLO 或用 `--no-yolo-udp` 做空输入测试。
3. 运行：

```bash
python -m app.main --connect-telemetry --ui --send-commands false
```

4. 确认状态正常后，只测某个模式：

```bash
python -m app.main --connect-telemetry --force-mode APPROACH_TRACK --send-commands false
```

5. 确认 raw/shaped 命令方向正确后，再打开实发：

```bash
python -m app.main --connect-telemetry --force-mode APPROACH_TRACK --send-commands true
```

## 8. 常用组合

只看 YOLO/fusion/control 计算，不连飞控：

```bash
python -m app.main --send-commands false
```

连飞控但不发命令：

```bash
python -m app.main --connect-telemetry --send-commands false
```

强制 overhead dry-run：

```bash
python -m app.main --connect-telemetry --force-mode OVERHEAD_HOLD --send-commands false
```

禁用 YOLO UDP：

```bash
python -m app.main --no-yolo-udp --run-seconds 2 --send-commands false
```

选择 mission：

```bash
python -m app.main --mission-name visual_tracking --send-commands false
```

使用指定 mission 配置：

```bash
python -m app.main --mission-config missions/visual_tracking/config.yaml --send-commands false
```

rescue competition 骨架 dry-run：

```bash
python -m app.main \
  --mission-config missions/rescue_competition/config.yaml \
  --no-yolo-udp \
  --run-seconds 2 \
  --send-commands false
```

注意：`rescue_competition` 默认 `auto_start: false`，不会自动起飞。它目前是阶段框架，不是完整比赛自动化。

## 9. 排查提示

没有 UI：

- 确认是否传了 `--ui`。
- 确认是否传了 `--connect-telemetry`。

没有 Web UI：

- 确认是否安装 `requirements/web.txt`。
- 确认浏览器访问的是 `http://127.0.0.1:8000` 或你指定的 `--web-port`。

Web UI 没有视频：

- 确认 YOLO 已启动且 `mjpeg_enabled: true`。
- 直接访问 `http://127.0.0.1:8010/video.mjpeg` 检查 MJPEG 输出。
- 检查控制端 `--yolo-mjpeg-url` 是否与 YOLO 的 `mjpeg_host/mjpeg_port/mjpeg_path` 一致。

收不到 YOLO：

- 检查 `yolo_app/config.yaml` 的 UDP 目标 IP/端口。
- 检查 `config/app.yaml` 的 `yolo_udp_port`。
- 本机运行时建议 YOLO 发到 `127.0.0.1:5005`。

telemetry 连接不上：

- SITL 默认检查 `config/telemetry.yaml` 的 `sitl.tcp_port`。
- 当前默认是 `127.0.0.1:5762`。
- 没开 SITL 时看到 reconnect warning 是正常的。
