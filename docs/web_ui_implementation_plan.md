# Web UI Implementation Plan for Codex

本文档给后续 Codex 会话使用。目标是在当前项目中一次性实现一个可运行的 Web 地面站 MVP，替代终端 UI 作为主要软件入口，同时保留 terminal UI 作为 fallback。

## 0. Current Context

仓库根目录是：

```text
/home/level6/uav_project/src
```

当前项目已经整理为：

```text
app/              control 主进程、mission runner、system runner
telemetry_link/   MAVLink 连接、状态缓存、命令发送
yolo_app/         YOLO + ByteTrack 感知进程
missions/         mission 和 stage controller
uav_ui/           legacy terminal UI 与命令分发
config/           app / telemetry 配置
data/             terrain、YOLO model 等运行资产
requirements/     control / yolo Python 依赖
runtime/          SITL、日志、黑盒输出等运行产物
scripts/          环境安装和 smoke test
tests/            单元测试
docs/             文档
```

已有命令分发链路必须复用：

```text
uav_ui.ui_commands.build_ui_command_handler
telemetry_link.command_dispatcher.dispatch_text_command
app.system_runner.SystemRunner mission/stage handlers
```

不要重写飞控命令体系，不要让 Web UI 直接操作 MAVLink 细节。

## 1. Product Goal

实现一个浏览器 Web UI，作为无人机地面站软件入口。

用户打开：

```text
http://127.0.0.1:8000
```

可以完成：

- 查看 telemetry / link / mode / armed / battery
- 查看 mission / stage / controller / SEND 状态
- 查看 YOLO 处理后的实时画面
- 发送文本命令
- 使用快捷按钮发送常用命令
- target next / prev / unlock / lock
- controller gimbal/body/approach on/off
- control send on/off
- mission start/reset/switch
- stage override / auto
- 查看命令历史和最近日志
- 使用右侧可展开边框打开参数、设置、日志、任务、调试面板

第一版重点是 MVP 可运行，不追求完整地图、WebRTC、权限系统、桌面打包。

## 2. Architecture

### 2.1 Process Model

第一版保留两个 Python 环境/进程：

```text
uav-control 环境
  app / telemetry_link / mission / web_ui

yolo 环境
  yolo_app / UDP target JSON / UDP command receiver / MJPEG video
```

不要在第一版强行把 YOLO 合并进 control 进程。YOLO 依赖重，且可能需要独立 conda/CUDA 环境。

### 2.2 Web UI Backend

新增模块：

```text
web_ui/
  __init__.py
  server.py
  state.py
  commands.py
  config_store.py
  video_proxy.py
  static/
    index.html
    styles.css
    app.js
```

后端使用 FastAPI：

- 提供静态页面
- 提供 REST API
- 提供 WebSocket 实时状态
- 可选代理 YOLO MJPEG 流

依赖新增：

```text
requirements/web.txt
```

建议内容：

```text
fastapi
uvicorn
```

如果实现中需要 HTTP proxy，可再加：

```text
httpx
```

### 2.3 YOLO Video Path

当前 YOLO 输入类型：

```text
Gazebo UDP RTP/H264 :5600
  -> yolo_app GStreamer decode
  -> OpenCV BGR frame
  -> YOLO track
```

第一版输出给浏览器使用 MJPEG：

```text
yolo_app annotated BGR frame
  -> JPEG encode
  -> MJPEG HTTP :8010/video.mjpeg
  -> browser <img>
```

不要第一版实现 WebRTC。

## 3. UI Design

实现单页地面站 Shell，不做多页面后台。

布局：

```text
┌──────────────────────────────────────────────────────────────┐
│ TopStatusBar: source | link | mode | armed | battery | SEND   │
├───────────────┬──────────────────────────────┬───────────────┤
│ QuickControls │ Main Live Area                │ Inspector     │
│ mission       │ YOLO annotated video           │ expandable    │
│ target        │ target/state overlay           │ params/logs   │
│ stage         │ mission/stage summary          │ settings      │
├───────────────┴──────────────────────────────┴───────────────┤
│ CommandConsole: input | result | history | recent logs         │
└──────────────────────────────────────────────────────────────┘
```

右侧 Inspector 默认收起，只露出 tab 按钮：

- Params
- Settings
- Logs
- Mission
- Debug

点击 tab 后展开。主视频和关键状态不能被路由切走。

第一版可以用原生 HTML/CSS/JS，不必引入 React/Vite，除非实现者判断现有环境适合。界面要能长期扩展。

## 4. Backend API

实现以下接口：

```text
GET  /
GET  /api/state
POST /api/command
GET  /api/commands/history
GET  /api/config/mission
PATCH /api/config/mission
POST /api/config/reload
WS   /ws/state
GET  /video/yolo.mjpeg
```

### 4.1 POST /api/command

请求：

```json
{
  "command": "control send off"
}
```

响应：

```json
{
  "ok": true,
  "message": "control send_commands=OFF",
  "command": "control send off",
  "timestamp": 1234567890.0
}
```

必须复用已有 command handler。如果 Web UI 是从 `SystemRunner` 内启动，应传入 `build_ui_command_handler(...)` 已有处理器。

### 4.2 GET /api/state

返回当前状态快照。字段可以从当前已有对象尽量获取，缺失时返回 `null` 或 `"UNKNOWN"`，不要为了字段完整重构大量核心代码。

建议格式：

```json
{
  "link": {
    "source": "sitl",
    "connected": true,
    "mode": "GUIDED",
    "armed": false
  },
  "drone": {
    "lat": null,
    "lon": null,
    "alt": null,
    "battery": null
  },
  "mission": {
    "name": "rescue_competition",
    "stage": "PREPARE",
    "stage_controller": "IDLE",
    "hold_reason": "none"
  },
  "control": {
    "send_commands": false,
    "gimbal": true,
    "body": true,
    "approach": true
  },
  "target": {
    "valid": false,
    "track_id": null,
    "class_name": "",
    "confidence": null
  },
  "video": {
    "url": "/video/yolo.mjpeg",
    "frame_age_ms": null,
    "stream_fps": null
  }
}
```

### 4.3 WS /ws/state

每 5-10Hz 推送 state snapshot 和命令日志摘要。不要高频到影响控制循环。

### 4.4 Config APIs

第一版实现“读取 YAML、修改 YAML、reload”：

```text
GET /api/config/mission
PATCH /api/config/mission
POST /api/config/reload
```

优先支持当前 active mission config。可以先返回 YAML 文本或 JSON dict。若时间紧，第一版允许右侧 Params 面板显示 YAML textarea，然后 Apply 写回。

写文件要安全：

- 先读取当前文件
- 验证 YAML 可解析
- 原子写入临时文件再替换
- 写失败不能破坏原配置
- reload 失败要返回错误信息

## 5. YOLO MJPEG Implementation

在 `yolo_app/` 增加：

```text
yolo_app/frame_hub.py
yolo_app/mjpeg_server.py
```

### 5.1 FrameHub

要求：

- 只保存最新 JPEG 帧
- 不排队历史帧
- 慢客户端自动跳帧
- 记录 frame timestamp、frame id、encode fps
- 线程安全

建议接口：

```python
class FrameHub:
    def update_bgr(self, frame, *, frame_id: int, timestamp: float) -> None: ...
    def latest(self) -> tuple[bytes | None, dict[str, object]]: ...
```

JPEG 参数建议：

```text
quality: 75
max fps: 10-15
max width: 1280, 可配置
```

### 5.2 MJPEG Server

新增配置项到 `yolo_app/config.yaml` 和 `yolo_app/config.py`：

```yaml
mjpeg_enabled: true
mjpeg_host: "127.0.0.1"
mjpeg_port: 8010
mjpeg_path: "/video.mjpeg"
mjpeg_quality: 75
mjpeg_max_fps: 15
mjpeg_max_width: 1280
```

实现 HTTP endpoint：

```text
GET /video.mjpeg
Content-Type: multipart/x-mixed-replace; boundary=frame
```

可以使用 Python 标准库 `http.server`，避免给 yolo 环境增加 FastAPI 依赖。也可以用轻量 FastAPI，但要同步 requirements。

### 5.3 main.py Integration

在 YOLO 标注后的帧处调用：

```python
frame_hub.update_bgr(annotated_frame, frame_id=packet.frame_id, timestamp=packet.timestamp)
```

保留现有：

- UDP target JSON
- UDP command receiver
- OpenCV show
- save_video

`show=false` 时不要弹 OpenCV 窗口，但 MJPEG 仍应工作。

## 6. SystemRunner Integration

在 `app/main.py` / `app/system_runner.py` 中增加 Web UI 启动选项。

建议 CLI：

```text
--web-ui
--web-host 127.0.0.1
--web-port 8000
--no-terminal-ui
--yolo-mjpeg-url http://127.0.0.1:8010/video.mjpeg
```

默认策略：

- 第一版不改变现有默认启动行为，避免破坏当前工作流。
- 用户显式传 `--web-ui` 才启动 Web UI。
- terminal UI 保留 fallback。

如果 `--web-ui` 和 terminal UI 同时开启会抢主线程/终端，优先让 Web UI 和 control loop 跑，terminal UI 可禁用或只保留非 curses fallback。

## 7. Safety Requirements

Web UI 默认只监听：

```text
127.0.0.1
```

危险命令必须在前端二次确认：

- `arm`
- `takeoff`
- `land`
- `disarm`
- `control send on`
- `mission start`
- `set_servo`
- `set_relay`
- `release_payload`

页面必须醒目显示：

- SITL / real source
- link connected
- mode
- armed
- SEND
- target lock

后端也应标记危险命令。第一版至少在返回结果和日志中记录 command、timestamp、ok、message。

## 8. Frontend MVP Details

使用 `web_ui/static/` 原生前端即可。

建议文件：

```text
index.html
styles.css
app.js
```

必需功能：

- 页面加载后连接 `/ws/state`
- WebSocket 断开时自动重连
- 顶部状态栏实时刷新
- YOLO 画面 `<img src="/video/yolo.mjpeg">`
- 快捷按钮发送命令：
  - `control send off`
  - `control send on`
  - `controller gimbal toggle`
  - `controller body toggle`
  - `controller approach toggle`
  - `target next`
  - `target prev`
  - `target unlock`
  - `stage auto`
  - `mission start`
  - `mission reset`
- 命令输入框支持 Enter 发送任意文本命令
- 命令历史列表
- 右侧 Inspector tabs：
  - Params: YAML textarea + Save + Reload
  - Settings: video URL、web host、yolo mjpeg URL 展示
  - Logs: command history / recent messages
  - Mission: mission current/start/reset/switch
  - Debug: raw state JSON

## 9. Tests

新增或更新测试：

```text
tests/test_web_ui_state.py
tests/test_web_ui_commands.py
tests/test_yolo_mjpeg.py
```

至少验证：

- `/api/command` 调用 command handler 并返回结果
- command history 记录成功和失败
- state snapshot 能在缺失对象时返回安全默认值
- config patch 拒绝非法 YAML
- yolo FrameHub 只保留最新帧
- MJPEG response 包含 multipart boundary

运行测试：

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q
```

当前全量测试基线应通过。

## 10. Acceptance Criteria

完成后必须满足：

1. `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q` 通过。
2. `python -m yolo_app.main --show false` 时，如果 Gazebo UDP 视频存在，MJPEG endpoint 能访问。
3. 浏览器打开 `http://127.0.0.1:8000` 能看到 Web UI。
4. Web UI 能发送文本命令并显示结果。
5. Web UI 能显示 telemetry/mission/control/target 状态，缺失时不崩溃。
6. Web UI 能显示 YOLO MJPEG 画面，YOLO 不运行时页面显示 disconnected/placeholder。
7. Params 面板能读取 mission config，保存合法 YAML，并触发 reload。
8. 危险命令前端有确认。
9. terminal UI 仍可作为 fallback 使用，不删除 `uav_ui/terminal_ui.py`。
10. 不引入无关重构，不改写飞控核心命令逻辑。

## 11. Suggested Implementation Order

请按以下顺序执行，避免视频、控制、配置同时混在一起：

1. 新增 `requirements/web.txt`。
2. 新增 `web_ui/` 后端和静态前端骨架。
3. 实现 `/api/command` 和 command history。
4. 实现 state snapshot 和 `/ws/state`。
5. 集成 `app.main --web-ui` 启动。
6. 实现前端 Shell、状态栏、命令栏、Inspector。
7. 在 `yolo_app` 实现 FrameHub 和 MJPEG server。
8. 前端接入 MJPEG 画面。
9. 实现 config read/patch/reload。
10. 补测试并跑全量测试。
11. 更新 README / docs/running.md，说明 Web UI 启动方式。

## 12. Non-Goals for First Pass

第一版不要做：

- WebRTC
- 地图
- 多用户权限
- Electron/Tauri 桌面壳
- YOLO 和 control 单进程合并
- 复杂图表回放
- 完整任务规划器
- 删除 terminal UI

这些后续可以在 Web UI Shell 稳定后扩展。

