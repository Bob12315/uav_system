# 运行手册

控制程序命令默认工作目录为：

```bash
cd ~/uav_project/src
```

## 1. 启动 YOLO

YOLO 在 RK3588 板载桌面会话的独立 conda 环境中运行：

```bash
conda activate yolo
cd ~/uav_project/uav_system-platform-rk3588/yolo_app
DISPLAY=:0 XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-0 \
DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus python main.py
```

确认 `yolo_app/config.yaml` 中 UDP 输出端口与 `config/app.yaml` 一致。控制端默认监听：

```yaml
runtime:
  yolo_udp_ip: "0.0.0.0"
  yolo_udp_port: 5005
```

## 2. app dry-run，不连接飞控

```bash
conda activate app
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

## 4. app + Web UI

```bash
python -m app.main --connect-telemetry --send-commands false
```

当 `config/app.yaml` 中 `ui.web_enabled: true` 时，从同一局域网的笔记本访问：

```text
http://<x86-or-rk3588-address>:8080/
```

同时启动 `yolo_app` 后，网页显示由它输出的 MJPEG 标注视频。Web 和
curses 可以用 `ui.web_enabled`、`ui.terminal_enabled` 独立启用。
`--ui` 临时打开终端 UI，`--no-ui` 同时关闭两个 UI 以便 smoke test。

网页上的 app/YOLO 重启操作要求安装 [systemd 模板](../deploy/systemd/)：

```bash
mkdir -p ~/.config/systemd/user
cp deploy/systemd/uav-*.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now uav-app.service uav-yolo.service
```

## 5. 独立 telemetry 服务

```bash
python -m telemetry_link.main --config config/telemetry.yaml
```

打开 telemetry UI：

```bash
python -m telemetry_link.main --config config/telemetry.yaml --ui
```

## 6. SITL 低风险顺序

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

## 7. 常用组合

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

## 8. 排查提示

没有 UI：

- 确认是否传了 `--ui`。
- 确认是否传了 `--connect-telemetry`。

收不到 YOLO：

- 检查 `yolo_app/config.yaml` 的 UDP 目标 IP/端口。
- 检查 `config/app.yaml` 的 `yolo_udp_port`。
- 本机运行时建议 YOLO 发到 `127.0.0.1:5005`。

telemetry 连接不上：

- SITL 默认检查 `config/telemetry.yaml` 的 `sitl.tcp_port`。
- 当前默认是 `127.0.0.1:5762`。
- 没开 SITL 时看到 reconnect warning 是正常的。
