# Model Assets

把本机 YOLO 权重放在这里，例如：

```text
best.pt
yolo11n.pt
```

`.pt` 文件默认被 `.gitignore` 忽略。默认 `yolo_app/config.yaml` 使用：

```yaml
model_path: "../data/models/best.pt"
```
