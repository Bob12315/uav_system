# Project Structure

当前仓库根目录是 `src/`。结构整理后，Python 包和运行资产分开：

```text
app/              control 主进程、mission runner、system runner
telemetry_link/   MAVLink 连接、状态缓存、命令发送
yolo_app/         YOLO + ByteTrack 感知进程
fusion/           telemetry 与感知融合
missions/         mission 和 stage controller
uav_ui/           legacy terminal UI 与命令分发
config/           app / telemetry 配置入口
data/             可复用运行资产，例如 terrain、YOLO 模型权重
requirements/     control / yolo Python 依赖清单
runtime/          本机运行产物，例如 SITL 状态、日志、黑盒输出
scripts/          环境安装、依赖安装、烟测脚本
tests/            单元测试
docs/             项目文档
```

## Runtime Assets

- `data/terrain/`：SITL 地形缓存，例如 `S36E149.DAT`。
- `data/models/`：本机 YOLO 权重，例如 `best.pt`、`yolo11n.pt`。`.pt` 文件默认被 `.gitignore` 忽略。
- `runtime/sitl/`：SITL 生成的 `mav.tlog`、`mav.parm`、`eeprom.bin` 等文件。
- `runtime/logs/`：黑盒、recce、ArduPilot BIN 等运行日志。

`runtime/` 是本机运行产物目录，不作为源码提交。
