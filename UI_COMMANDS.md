# UI Commands

本文档列出终端 UI 输入框中可以输入的命令。命令来自：

- `uav_ui/terminal_ui.py`：UI 退出和输入行为
- `uav_ui/ui_commands.py`：app/control UI 扩展命令
- `telemetry_link/command_dispatcher.py`：MAVLink 手动命令

部分命令只在 app/control 启动 UI 时可用；只启动 `telemetry_link` UI 时，通常只支持 MAVLink 手动命令。

## UI 通用命令

输入框支持 `Tab` 自动补全。单个候选会直接补全，多个候选可以连续按 `Tab` 循环切换。

```text
quit
exit
```

`quit` 和 `exit` 会退出终端 UI。

## 目标切换命令

仅 app/control UI 支持。命令会通过 UDP 发给 `yolo_app`。

```text
target next
target prev
target previous
target lock <track_id>
target unlock
```

示例：

```text
target lock 7
target unlock
```

## Controller 运行时开关

仅 app/control UI 支持。`controller` 也可以写成 `controllers`。

格式：

```text
controller <gimbal|body|approach|all> <on|off|toggle>
controllers <gimbal|body|approach|all> <on|off|toggle>
```

支持的动作别名：

```text
on      enable enabled 1 true
off     disable disabled 0 false
toggle  tog
```

常用命令：

```text
controller gimbal on
controller gimbal off
controller gimbal toggle
controller body on
controller body off
controller body toggle
controller approach on
controller approach off
controller approach toggle
controller all on
controller all off
controller all toggle
```

## Control 发送开关

仅 app/control UI 支持。控制是否真的下发连续控制命令。

格式：

```text
control send <on|off|toggle>
control send_commands <on|off|toggle>
control commands <on|off|toggle>
```

支持的动作别名：

```text
on      enable enabled 1 true
off     disable disabled 0 false
toggle  tog
```

常用命令：

```text
control send on
control send off
control send toggle
```

## Stage Override

仅 app/control UI 支持。用于临时强制当前 mission 的 stage controller，主要用于调试控制模块，不是切换 mission。

`task` 仍可作为兼容别名，但建议新命令统一用 `stage`。

格式：

```text
stage <STAGE_CONTROLLER>
stage mode <STAGE_CONTROLLER>
stage auto
stage clear
```

当前 app stage controller 支持：

```text
APPROACH_TRACK
OVERHEAD_HOLD
CORRIDOR_FOLLOW
IDLE
auto
clear
```

示例：

```text
stage mode APPROACH_TRACK
stage mode OVERHEAD_HOLD
stage mode CORRIDOR_FOLLOW
stage mode IDLE
stage auto
```

`auto` 和 `clear` 会取消强制 stage override，恢复 mission 自动选择 stage controller。

## Mission 切换

仅 app/control UI 支持。用于运行中切换当前 mission。

```text
mission list
mission current
mission status
mission switch <MISSION_NAME>
mission select <MISSION_NAME>
mission use <MISSION_NAME>
mission start
mission reset
```

当前支持：

```text
visual_tracking
rescue_competition
```

示例：

```text
mission list
mission switch visual_tracking
mission switch rescue_competition
mission start
mission reset
```

切换或重置 mission 时会清掉当前连续控制队列、重置 stage controller/shaper 状态，并把 `SEND` 置为 `OFF`。确认状态安全后再输入：

`mission start` 会请求当前 mission 开始执行。对 `rescue_competition` 来说，它会从 `PREPARE` 等待本地位置有效后进入 `TAKEOFF`。

```text
control send on
```

## Stage 参数重载

仅 app/control UI 支持。用于运行中重载 [missions/<mission_name>/config.yaml](missions/<mission_name>/config.yaml)。

```text
pid reload
stage reload
stage config reload
stage controllers reload
```

## MAVLink 手动命令

这些命令会走 `telemetry_link.command_dispatcher`，最终进入 `LinkManager` 的 MAVLink 发送链路。

### 链路和飞控模式

```text
switch_source <source_name>
mode <MODE_NAME>
```

示例：

```text
switch_source real
switch_source sitl
mode GUIDED
mode LOITER
mode RTL
```

### 解锁、起飞、降落

```text
arm
arm throttle
disarm
takeoff <altitude_m>
land
```

示例：

```text
arm
takeoff 5
land
disarm
```

### 偏航和速度

```text
condition_yaw <yaw_deg> [speed_deg_s] [cw|ccw|shortest] [absolute|relative]
change_speed <speed_mps> [ground|air|climb|descent]
```

示例：

```text
condition_yaw 90
condition_yaw 45 20 shortest relative
change_speed 3 ground
change_speed 1.5 air
```

### Home 和位置命令

```text
set_home current
set_home <lat> <lon> <alt_m>
global_goto <lat> <lon> <alt_m> [relative|global|terrain]
local_pos <x_m> <y_m> <z_m> [local|offset|body|body_offset]
reposition <lat> <lon> <rel_alt_m> [groundspeed_mps] [yaw_deg]
```

示例：

```text
set_home current
set_home -35.363262 149.165237 584
global_goto -35.363262 149.165237 20 relative
local_pos 5 0 -2 body
reposition -35.363262 149.165237 20 3 90
```

### ROI 和云台管理

```text
set_roi_location <lat> <lon> <alt_m>
roi_none [gimbal_device_id]
gimbal_manager_configure
gimbal_manager_configure [gimbal_device_id]
gimbal_manager_configure [gimbal_device_id] [primary_sysid] [primary_compid]
```

示例：

```text
set_roi_location -35.363262 149.165237 584
roi_none
roi_none 1
gimbal_manager_configure
gimbal_manager_configure 1
gimbal_manager_configure 1 1 1
```

### 载荷和通道动作

这些是低层 MAVLink action 命令，可从 UI 手动输入。`set_servo` 和 `set_relay` 会直接排队发送；`release_payload` 当前没有通用 `payload_id -> servo/relay` 映射，因此会安全拒绝。比赛 mission 应优先通过 `missions/rescue_competition/config.yaml` 配置载荷映射，让 mission 输出 `set_servo` 或 `set_relay`。

```text
set_servo <channel> <pwm>
set_relay <relay_id> <on|off>
release_payload <payload_id>
```

示例：

```text
set_servo 9 1900
set_relay 0 on
release_payload 1
```

### MAVLink 消息频率

`message_interval` 是 `set_message_interval` 的别名。

```text
set_message_interval <MESSAGE_NAME> <rate_hz|default>
message_interval <MESSAGE_NAME> <rate_hz|default>
```

示例：

```text
set_message_interval ATTITUDE 10
message_interval GLOBAL_POSITION_INT 5
set_message_interval ATTITUDE default
```

### 连续机体控制

```text
body_vel <forward_mps> <right_mps> <down_mps>
yaw_rate <rad_per_sec>
stop
```

示例：

```text
body_vel 1 0 0
body_vel 0 1 0
yaw_rate 0.2
stop
```

### 云台角度和角速度

```text
gimbal <pitch_deg> <yaw_deg> [roll_deg]
gimbal_rate <pitch_rate_deg_s> <yaw_rate_deg_s> [follow|lock]
```

示例：

```text
gimbal -20 0
gimbal -20 30 0
gimbal_rate 0 20
gimbal_rate 0 20 lock
```

## 注意

在 app/control UI 中，输入手动 MAVLink 命令后，系统会自动关闭 control 连续命令发送，避免自动控制和人工输入同时争用飞控命令。

## 命令整理结论

### 保留

- `quit` / `exit`：UI 本地退出命令。
- `target next|prev|previous|lock|unlock`：已由 `yolo_app.command_receiver` 接收，其中 `previous` 是 UI 友好别名，实际发送 `switch_prev`。
- `controller/controllers ...`：运行时 controller 开关，`controllers` 是复数别名。
- `control send|send_commands|commands ...`：运行时发送开关。
- `stage ...`、`stage mode ...`、`pid reload`、`stage reload`、`stage config reload`、`stage controllers reload`：app/control 调试和参数重载命令。
- `mission list|ls|current|status|switch|select|use|start|reset`：mission 管理命令。
- MAVLink 手动命令：`switch_source`、`mode`、`arm`、`disarm`、`takeoff`、`land`、`condition_yaw`、`change_speed`、`set_home`、`global_goto`、`local_pos`、`reposition`、`set_roi_location`、`roi_none`、`gimbal_manager_configure`、`set_servo`、`set_relay`、`set_message_interval/message_interval`、`body_vel`、`yaw_rate`、`stop`、`gimbal`、`gimbal_rate`。

### 建议删除或逐步废弃

- `task ...`：仍在 `uav_ui/ui_commands.py` 里作为 stage override 的旧别名，但自动补全已经不推荐它。建议保留一段兼容期后删除，统一使用 `stage ...`。
- `release_payload <payload_id>`：当前手动输入一定会返回“payload mapping is not configured”。如果后续不打算做全局 payload 映射，建议从 UI 自动补全和用户文档中移除，只保留底层 action 类型；如果要保留，则需要补齐配置映射和测试。
- `controllers ...`、`control send_commands ...`、`control commands ...`、`mission select/use ...` 属于易懂但重复的别名。它们不是坏命令，但会增加记忆负担；若要精简 UI，可只保留主命令 `controller`、`control send`、`mission switch`，其余作为隐式兼容别名。
- `pid reload` 名字偏旧，实际重载的是 mission stage/controller 配置，不只是 PID。建议文档和日常使用改为 `stage config reload`，`pid reload` 作为兼容别名。

### 建议改进

- 自动补全和文档应跟 `command_dispatcher.py` 同步；新增手动命令时同时更新 `_MANUAL_COMMANDS`，确保 app/control UI 会自动关闭 `SEND`。
- `stage config reload` 目前只更新 `input_adapter`、`approach_track`、`overhead_hold`、`shaper`，没有重载 `corridor_follow`。如果 `CORRIDOR_FOLLOW` 需要运行时调参，应把它纳入 `load_mission_stage_runtime_config` 和 `StageRegistry.apply_configs`。
- `mission current/status` 当前只返回 active mission name。可以增强为同时返回 mission stage、stage controller、`SEND` 状态和 override 状态。
- `target lock <track_id>` 建议在 UI 侧允许显示当前可选 track id，或在失败时展示最近一次 YOLO 状态，减少盲输。
- `set_servo` / `set_relay` 风险较高，建议增加二次确认、只在 debug 模式开放，或至少在 UI 日志中更醒目地区分它们。
