# Runtime Directory

本目录用于本机运行产物，不作为源码逻辑的一部分。

- `logs/`：blackbox、recce、ArduPilot BIN 等日志。
- `sitl/`：SITL 生成的 `mav.tlog`、`mav.parm`、`eeprom.bin` 等状态文件。

`logs/` 和 `sitl/` 默认被 `.gitignore` 忽略。
