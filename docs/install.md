# 安装说明

建议分两个环境：app 环境和 YOLO 环境。用户先自行安装 Miniconda/Anaconda，并自行创建两个 conda 环境；本项目脚本只负责在已经激活的 `app` 环境里安装 app 侧依赖。

## app 环境

```bash
conda create -n app python=3.10 -y
conda activate app
bash scripts/install_app_env.sh
```

用途：

- `app`
- `missions`
- `fusion`
- `telemetry_link`
- `uav_ui`
- `tests`

脚本会先检查：

- 当前系统架构是 `x86_64/amd64`。
- 当前已经激活 conda 环境 `app`。
- 当前 Python 版本是 `3.10.x`。

脚本安装 app 依赖时使用清华 conda 镜像作为临时 channel，不修改用户全局 `.condarc`。

验证：

```bash
cd ~/uav_project/src
python -m app.main --help
python -m telemetry_link.main --help
python -m pytest -q
```

## YOLO 环境

```bash
conda create -n yolo python=3.10 -y
conda activate yolo
```

YOLO 环境依赖安装脚本暂不提供，后续按模型、CUDA、相机和推理方式单独整理。

如果使用 GPU，请按本机 CUDA 版本安装合适的 PyTorch。可以先确认：

```bash
python - <<'PY'
import torch
print(torch.__version__)
print(torch.cuda.is_available())
PY
```

## 模型文件

建议路径：

```text
~/models/best.pt
```

然后在 `yolo_app/config.yaml` 中配置：

```yaml
model_path: "~/models/best.pt"
```

不建议把 `.pt` 模型提交到 Git。

## 可选依赖

如果要运行视频源、GStreamer 或特定相机，可能还需要系统包。具体取决于硬件和视频输入方式。

## 快速验证

控制环境：

```bash
conda activate app
cd ~/uav_project/src
python -m app.main --no-yolo-udp --run-seconds 1 --send-commands false
```

YOLO 环境：

```bash
conda activate yolo
cd ~/uav_project/src/yolo_app
python main.py
```
