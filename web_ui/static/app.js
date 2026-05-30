const $ = id => document.getElementById(id);

let state = {};
let completions = [];
let history = [];
let historyIndex = -1;
let missionCatalog = [];
let allConfigFiles = [];
let missionConfigPath = "";
let missionConfigOriginal = "";
let systemConfigPath = "";
let systemConfigOriginal = "";
let lang = localStorage.getItem("uav_ui_lang") || "zh";

const i18n = {
  zh: {
    controlNav: "实时控制",
    controlTitle: "实时控制",
    mission: "任务",
    switchMission: "切换任务",
    listMissions: "列出任务",
    startMission: "开始任务",
    resetMission: "重置任务",
    stage: "阶段",
    autoStage: "自动阶段",
    flightCommands: "飞控命令",
    switchMode: "切换模式",
    takeoff: "起飞",
    arm: "解锁",
    land: "降落",
    stop: "停止",
    controlSwitches: "控制开关",
    controlSend: "控制发送",
    gimbal: "云台",
    body: "机体",
    approach: "接近",
    services: "服务",
    startYolo: "启动 YOLO",
    target: "目标",
    prevTarget: "上一个",
    nextTarget: "下一个",
    unlockTarget: "解除锁定",
    waitingVideo: "等待 YOLO Web 视频流",
    droneCommands: "发往无人机的命令",
    status: "状态",
    aircraftInfo: "飞机信息",
    targetInfo: "目标信息",
    missionStatus: "任务状态",
    commandLine: "命令行",
    commandPlaceholder: "输入命令，Tab 补全，↑ ↓ 历史",
    send: "发送",
    completionHint: "Tab 补全 / ↑ ↓ 查看输入记录",
    missionParams: "飞行模式参数",
    systemParams: "系统参数",
    reload: "读取",
    save: "保存",
    saveApply: "保存并应用",
    saveAction: "保存并执行动作",
    selectMissionConfig: "选择 missions 里的配置文件。",
    selectSystemConfig: "选择 config 或 yolo_app 配置文件。",
    systemConfigHint: "系统参数通常需要重启 app / YOLO 或重连 telemetry 才会生效。",
    readOk: "已读取。",
    hasBackup: "存在上一次保存前版本，可恢复。",
    noChange: "没有修改。",
    modified: "已修改配置；保存后后端会校验 YAML 并返回正式差异。",
    noCommandLog: "暂无控制命令。",
    fallbackEvents: "暂无控制命令，显示系统事件。",
    confirmStartMission: "确认开始当前任务？",
    confirmResetMission: "重置任务会关闭自动发送，确认？",
    confirmArm: "确认解锁飞行器？",
    confirmDisarm: "强制 Disarm 可能导致坠落，确认发送？",
    confirmLand: "确认降落？",
    confirmTakeoff: altitude => `确认起飞至 ${altitude} m？`,
    confirmSendOn: "确认开启自动控制命令发送？请确认链路、模式和参数安全。",
    confirmMissionApply: "保存并应用任务参数会关闭自动发送，确认？",
    confirmSystemApply: "保存并执行动作可能会重启服务或重连 telemetry，确认？",
    complete: match => `补全: ${match}`,
    refreshFailed: message => `状态刷新失败: ${message}`,
    labels: {
      link: "链路",
      flightMode: "飞控模式",
      armed: "解锁",
      battery: "电池",
      gps: "GPS",
      globalPosition: "经纬度",
      altitude: "高度",
      velocity: "速度 NED",
      gimbalYpr: "云台 Y/P/R",
      targetState: "目标状态",
      trackId: "Track ID",
      classConfidence: "类别/置信度",
      frame: "Frame",
      detections: "检测数",
      imageSize: "图像尺寸",
      error: "误差 ex/ey",
      targetSize: "目标尺寸",
    },
  },
  en: {
    controlNav: "Live Control",
    controlTitle: "Live Control",
    mission: "Mission",
    switchMission: "Switch Mission",
    listMissions: "List Missions",
    startMission: "Start Mission",
    resetMission: "Reset Mission",
    stage: "Stage",
    autoStage: "Auto Stage",
    flightCommands: "Flight Commands",
    switchMode: "Set Mode",
    takeoff: "Takeoff",
    arm: "Arm",
    land: "Land",
    stop: "Stop",
    controlSwitches: "Control Switches",
    controlSend: "Command Send",
    gimbal: "Gimbal",
    body: "Body",
    approach: "Approach",
    services: "Services",
    startYolo: "Start YOLO",
    target: "Target",
    prevTarget: "Previous",
    nextTarget: "Next",
    unlockTarget: "Unlock",
    waitingVideo: "Waiting for YOLO web stream",
    droneCommands: "Commands Sent to Drone",
    status: "Status",
    aircraftInfo: "Aircraft",
    targetInfo: "Target",
    missionStatus: "Mission Status",
    commandLine: "Command",
    commandPlaceholder: "Type a command, Tab completes, ↑ ↓ history",
    send: "Send",
    completionHint: "Tab completion / ↑ ↓ command history",
    missionParams: "Flight Mode Params",
    systemParams: "System Params",
    reload: "Reload",
    save: "Save",
    saveApply: "Save and Apply",
    saveAction: "Save and Run Action",
    selectMissionConfig: "Select a config file under missions.",
    selectSystemConfig: "Select a config or yolo_app file.",
    systemConfigHint: "System params usually require app / YOLO restart or telemetry reconnect.",
    readOk: "Loaded.",
    hasBackup: "A pre-save backup exists and can be restored.",
    noChange: "No changes.",
    modified: "Config changed; after saving, the backend validates YAML and returns the official diff.",
    noCommandLog: "No control commands yet.",
    fallbackEvents: "No control commands yet; showing system events.",
    confirmStartMission: "Start the current mission?",
    confirmResetMission: "Resetting the mission disables automatic sending. Continue?",
    confirmArm: "Arm the aircraft?",
    confirmDisarm: "Forced disarm may crash the aircraft. Send anyway?",
    confirmLand: "Land now?",
    confirmTakeoff: altitude => `Take off to ${altitude} m?`,
    confirmSendOn: "Enable automatic command sending? Confirm link, mode, and params are safe.",
    confirmMissionApply: "Saving and applying mission params disables automatic sending. Continue?",
    confirmSystemApply: "Saving and applying may restart services or reconnect telemetry. Continue?",
    complete: match => `Completed: ${match}`,
    refreshFailed: message => `Status refresh failed: ${message}`,
    labels: {
      link: "Link",
      flightMode: "Mode",
      armed: "Armed",
      battery: "Battery",
      gps: "GPS",
      globalPosition: "Lat/Lon",
      altitude: "Altitude",
      velocity: "Velocity NED",
      gimbalYpr: "Gimbal Y/P/R",
      targetState: "Target State",
      trackId: "Track ID",
      classConfidence: "Class/Confidence",
      frame: "Frame",
      detections: "Detections",
      imageSize: "Image Size",
      error: "Error ex/ey",
      targetSize: "Target Size",
    },
  },
};

function t(key, ...args) {
  const value = i18n[lang]?.[key] ?? i18n.zh[key] ?? key;
  return typeof value === "function" ? value(...args) : value;
}

function label(key) {
  return i18n[lang]?.labels?.[key] ?? i18n.zh.labels[key] ?? key;
}

function applyLanguage() {
  document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
  document.querySelectorAll("[data-i18n]").forEach(element => {
    element.textContent = t(element.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach(element => {
    element.setAttribute("placeholder", t(element.dataset.i18nPlaceholder));
  });
  $("completionHint").textContent = t("completionHint");
  if (state && Object.keys(state).length) renderStatus(state);
}

async function json(url, options = {}) {
  const response = await fetch(url, {headers: {"Content-Type": "application/json"}, ...options});
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || "request failed");
  return data;
}

function stamp(seconds) {
  return seconds ? new Date(seconds * 1000).toLocaleTimeString() : "--";
}

function escapeHtml(text) {
  return String(text ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function num(value, digits = 2, unit = "") {
  return Number.isFinite(Number(value)) ? `${Number(value).toFixed(digits)}${unit}` : "--";
}

async function execute(command, source = "BUTTON") {
  if (!command) return null;
  const result = await json("/api/commands/execute", {
    method: "POST",
    body: JSON.stringify({command, source}),
  });
  $("completionHint").textContent = result.message;
  await loadAudit();
  return result;
}

function setBadge(element, text, cls = "") {
  element.textContent = text;
  element.className = `badge ${cls}`;
}

function setSwitch(id, enabled) {
  const button = $(id);
  button.classList.toggle("active-choice", Boolean(enabled));
  button.querySelector("strong").textContent = enabled ? "ON" : "OFF";
}

function updateControllerRows(controls) {
  ["gimbal", "body", "approach"].forEach(name => {
    const enabled = Boolean(controls[name]);
    const row = document.querySelector(`[data-controller-row="${name}"]`);
    if (!row) return;
    row.classList.toggle("enabled", enabled);
    row.querySelectorAll("button").forEach(button => {
      const command = button.dataset.command || "";
      button.classList.toggle("active-choice", command.endsWith(enabled ? " on" : " off"));
    });
  });
  const allEnabled = Boolean(controls.gimbal && controls.body && controls.approach);
  const allDisabled = Boolean(!controls.gimbal && !controls.body && !controls.approach);
  const allRow = document.querySelector('[data-controller-row="all"]');
  if (!allRow) return;
  allRow.classList.toggle("enabled", allEnabled);
  allRow.querySelectorAll("button").forEach(button => {
    const command = button.dataset.command || "";
    button.classList.toggle(
      "active-choice",
      (allEnabled && command.endsWith(" on")) || (allDisabled && command.endsWith(" off")),
    );
  });
}

function cardHtml(label, value) {
  return `<div class="card"><label>${escapeHtml(label)}</label>${escapeHtml(value)}</div>`;
}

function infoRows(target, rows) {
  target.innerHTML = rows.map(([label, value]) =>
    `<div class="info-label">${escapeHtml(label)}</div><div class="info-value">${escapeHtml(value)}</div>`
  ).join("");
}

function renderStatus(next) {
  state = next;
  const link = next.link || {};
  const drone = next.drone || {};
  const gimbal = next.gimbal || {};
  const target = next.perception || {};
  const scene = next.scene || {};
  const controls = next.controllers || {};
  const cmd = next.command || {};

  setBadge($("sourceBadge"), `SOURCE ${String(next.active_source || "--").toUpperCase()}`, next.active_source === "real" ? "warning" : "");
  setBadge($("linkBadge"), `LINK ${link.connected ? "OK" : "DOWN"}`, link.connected ? "ok" : "danger");
  setBadge($("modeBadge"), `MODE ${drone.mode || "--"}`, "");
  setBadge($("armedBadge"), drone.armed ? "ARMED" : "DISARMED", drone.armed ? "danger" : "");
  setBadge($("batteryBadge"), drone.battery_valid ? `BAT ${drone.battery_remaining}%` : "BAT --", "");
  setBadge($("sendBadge"), `SEND ${controls.send_commands ? "ON" : "OFF"}`, controls.send_commands ? "danger" : "ok");

  setSwitch("sendToggle", controls.send_commands);
  updateControllerRows(controls);

  $("missionName").textContent = next.mission || "--";
  $("missionStage").textContent = next.stage || "--";
  $("stageController").textContent = next.stage_controller || "--";
  $("stageOverride").textContent = next.stage_override || "AUTO";
  $("holdReason").textContent = next.hold_reason || "none";

  infoRows($("aircraftInfo"), [
    [label("gps"), `${drone.gps_fix_type ?? "--"} fix / ${drone.satellites_visible ?? "--"} sats`],
    [label("battery"), drone.battery_valid ? `${num(drone.battery_voltage, 1, " V")} / ${drone.battery_remaining}%` : "--"],
    [label("altitude"), `${num(drone.relative_altitude, 2, " m")} / ${num(drone.altitude, 2, " m")}`],
    [label("flightMode"), drone.mode || "--"],
    [label("armed"), drone.armed ? "ARMED" : "DISARMED"],
  ]);

  infoRows($("targetInfo"), [
    [label("targetState"), target.target_valid ? "LOCKED" : (target.tracking_state || "--").toUpperCase()],
    [label("trackId"), target.target_valid ? `#${target.track_id}` : "--"],
    [label("classConfidence"), target.target_valid ? `${target.class_name || "--"} / ${num(target.confidence, 2)}` : "--"],
    [label("frame"), `${scene.frame_id ?? target.frame_id ?? "--"}`],
    [label("detections"), `${(scene.detections || []).length}`],
    [label("imageSize"), `${scene.image_width || target.image_width || "--"} x ${scene.image_height || target.image_height || "--"}`],
    [label("error"), target.target_valid ? `${num(target.ex, 3)} / ${num(target.ey, 3)}` : "--"],
    [label("targetSize"), target.target_valid ? num(target.target_size, 3) : "--"],
  ]);

  $("commandCards").innerHTML = [
    cardHtml("VX", num(cmd.vx_cmd || 0, 3)),
    cardHtml("VY", num(cmd.vy_cmd || 0, 3)),
    cardHtml("VZ", num(cmd.vz_cmd || 0, 3)),
    cardHtml("Yaw", num(cmd.yaw_rate_cmd || 0, 3)),
    cardHtml("Gimbal Y", num(cmd.gimbal_yaw_rate_cmd || 0, 3)),
    cardHtml("Gimbal P", num(cmd.gimbal_pitch_rate_cmd || 0, 3)),
    cardHtml("Active", String(Boolean(cmd.active))),
    cardHtml("SEND", controls.send_commands ? "ON" : "OFF"),
  ].join("");

  const commandLines = next.control_commands || [];
  if (commandLines.length) {
    $("events").innerHTML = commandLines.map(item =>
      `<div class="log-line">${escapeHtml(item)}</div>`
    ).join("");
  } else if ((next.events || []).length) {
    $("events").innerHTML = `<div class="log-line muted">${escapeHtml(t("fallbackEvents"))}</div>` + next.events.map(item =>
      `<div class="log-line">${stamp(item.timestamp)} ${escapeHtml(item.level)} &nbsp; ${escapeHtml(item.message)}</div>`
    ).join("");
  } else {
    $("events").innerHTML = `<div class="log-line muted">${escapeHtml(t("noCommandLog"))}</div>`;
  }

  renderMissionSteps(next, next.mission);
}

function stageModesForMission(missionName) {
  const selected = missionName || state.mission || $("missionSelect").value;
  const mission = missionCatalog.find(item => item.name === selected);
  if (mission && Array.isArray(mission.stage_modes)) return mission.stage_modes;
  if (Array.isArray(state.stage_modes)) return state.stage_modes.filter(mode => mode !== "AUTO");
  return [];
}

function renderMissionSteps(next, missionName) {
  const override = next.stage_override || "";
  const active = override || next.stage || next.stage_controller || "";
  const modes = stageModesForMission(missionName);
  $("missionSteps").innerHTML = modes.map(mode => {
    const current = String(mode).toUpperCase() === String(active).toUpperCase();
    return `<button class="${current ? "active-choice" : ""}" data-mission-stage="${escapeHtml(mode)}">${escapeHtml(mode)}</button>`;
  }).join("");
  $("missionSteps").querySelectorAll("[data-mission-stage]").forEach(button => {
    button.onclick = () => execute(`mission stage ${button.dataset.missionStage}`, "STAGE");
  });
}

async function loadAudit() {
  const records = await json("/api/audit?limit=100");
  history = records.filter(r => ["CLI", "BUTTON"].includes(r.source)).map(r => r.action);
}

async function loadMissions() {
  missionCatalog = await json("/api/missions");
  $("missionSelect").innerHTML = missionCatalog.map(item =>
    `<option value="${item.name}" ${item.active ? "selected" : ""}>${item.name}</option>`
  ).join("");
  const activeMission = missionCatalog.find(item => item.active)?.name || state.mission || $("missionSelect").value;
  renderMissionSteps(state || {}, activeMission);
}

async function loadConfigFiles() {
  allConfigFiles = await json("/api/config/files");
  renderConfigFileButtons(
    "missionConfigFiles",
    allConfigFiles.filter(path => path.startsWith("missions/")),
    path => openMissionConfig(path),
  );
  renderConfigFileButtons(
    "systemConfigFiles",
    allConfigFiles.filter(path => !path.startsWith("missions/")),
    path => openSystemConfig(path),
  );
}

function renderConfigFileButtons(containerId, files, onClick) {
  const container = $(containerId);
  container.innerHTML = files.map(path => `<button data-path="${escapeHtml(path)}">${escapeHtml(path)}</button>`).join("");
  container.querySelectorAll("button").forEach(button => button.onclick = () => onClick(button.dataset.path));
}

async function readConfig(path) {
  return json(`/api/config/file?path=${encodeURIComponent(path)}`);
}

async function openMissionConfig(path) {
  const file = await readConfig(path);
  missionConfigPath = path;
  missionConfigOriginal = file.content;
  $("missionEditingPath").textContent = path;
  $("missionYamlEditor").value = file.content;
  $("missionConfigDiff").textContent = "";
  $("missionConfigStatus").textContent = file.has_backup ? t("hasBackup") : t("readOk");
  markActiveFile("missionConfigFiles", path);
}

async function openSystemConfig(path) {
  const file = await readConfig(path);
  systemConfigPath = path;
  systemConfigOriginal = file.content;
  $("systemEditingPath").textContent = path;
  $("systemYamlEditor").value = file.content;
  $("systemConfigDiff").textContent = "";
  $("systemConfigStatus").textContent = file.has_backup ? t("hasBackup") : t("readOk");
  markActiveFile("systemConfigFiles", path);
}

function markActiveFile(containerId, path) {
  document.querySelectorAll(`#${containerId} button`).forEach(button => {
    button.classList.toggle("active", button.dataset.path === path);
  });
}

function localDiff(before, after) {
  return before === after ? t("noChange") : t("modified");
}

async function saveConfig(path, content, action, statusId, diffId) {
  if (!path) return;
  const result = await json(`/api/config/file?path=${encodeURIComponent(path)}`, {
    method: "PUT",
    body: JSON.stringify({content, action}),
  });
  $(diffId).textContent = result.diff || "保存成功，无文本差异。";
  $(statusId).textContent = result.message;
  await loadAudit();
}

function systemActionForPath(path) {
  if (path === "config/telemetry.yaml") return "reconnect";
  if (path === "yolo_app/config.yaml" || path === "config/app.yaml") return "restart";
  return "save";
}

function startStatusUpdates() {
  let fallbackTimer = null;
  const pollStatus = () => json("/api/status").then(renderStatus).catch(error => {
    $("completionHint").textContent = t("refreshFailed", error.message);
  });
  const startFallback = () => {
    if (fallbackTimer !== null) return;
    pollStatus();
    fallbackTimer = setInterval(pollStatus, 500);
  };
  try {
    const socket = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/status`);
    socket.onmessage = event => renderStatus(JSON.parse(event.data));
    socket.onerror = startFallback;
    socket.onclose = startFallback;
  } catch {
    startFallback();
  }
}

async function initVideo() {
  const videoConfig = await json("/api/yolo/stream");
  const videoUrl = `${location.protocol}//${location.hostname}:${videoConfig.port}${videoConfig.path}`;
  $("video").src = videoUrl;
  $("video").onload = () => $("videoOffline").style.display = "none";
  $("video").onerror = () => {
    $("videoOffline").style.display = "block";
    setTimeout(() => { $("video").src = `${videoUrl}?retry=${Date.now()}`; }, 1500);
  };
}

function wireControls() {
  document.querySelectorAll(".nav-item").forEach(tab => tab.onclick = () => {
    document.querySelectorAll(".nav-item").forEach(item => item.classList.toggle("active", item === tab));
    document.querySelectorAll(".page").forEach(page => page.classList.toggle("active", page.id === `${tab.dataset.page}Page`));
  });
  document.querySelectorAll("[data-command]").forEach(button => button.onclick = () => {
    const message = button.dataset.confirmKey ? t(button.dataset.confirmKey) : button.dataset.confirm;
    if (message && !confirm(message)) return;
    execute(button.dataset.command, "BUTTON");
  });
  $("langSelect").value = lang;
  $("langSelect").onchange = event => {
    lang = event.target.value;
    localStorage.setItem("uav_ui_lang", lang);
    applyLanguage();
  };
  $("missionSwitch").onclick = () => execute(`mission switch ${$("missionSelect").value}`, "BUTTON").then(loadMissions);
  $("missionSelect").onchange = () => renderMissionSteps(state || {}, $("missionSelect").value);
  $("modeButton").onclick = () => execute(`mode ${$("modeSelect").value}`, "BUTTON");
  $("takeoffButton").onclick = () => {
    const altitude = $("takeoffAltitude").value;
    if (confirm(t("confirmTakeoff", altitude))) execute(`takeoff ${altitude}`, "BUTTON");
  };
  $("sendToggle").onclick = () => {
    if (state.controllers?.send_commands || confirm(t("confirmSendOn"))) {
      execute(`control send ${state.controllers?.send_commands ? "off" : "on"}`, "BUTTON");
    }
  };
  $("yoloStartButton").onclick = async () => {
    const result = await json("/api/services/yolo/restart", {method: "POST"});
    $("completionHint").textContent = result.message;
    await loadAudit();
    await initVideo();
  };
  $("sendCommand").onclick = () => {
    const input = $("commandInput");
    execute(input.value, "CLI");
    input.value = "";
    historyIndex = -1;
  };
  $("commandInput").onkeydown = event => {
    if (event.key === "Enter") { event.preventDefault(); $("sendCommand").click(); }
    if (event.key === "Tab") {
      event.preventDefault();
      const match = completions.find(item => item.toLowerCase().startsWith(event.target.value.toLowerCase()));
      if (match) { event.target.value = match; $("completionHint").textContent = t("complete", match); }
    }
    if (event.key === "ArrowUp" && history.length) {
      event.preventDefault();
      historyIndex = Math.min(historyIndex + 1, history.length - 1);
      event.target.value = history[historyIndex];
    }
    if (event.key === "ArrowDown" && historyIndex >= 0) {
      event.preventDefault();
      historyIndex -= 1;
      event.target.value = historyIndex < 0 ? "" : history[historyIndex];
    }
  };
  $("missionConfigReload").onclick = () => missionConfigPath && openMissionConfig(missionConfigPath);
  $("missionConfigSave").onclick = () => saveConfig(missionConfigPath, $("missionYamlEditor").value, "save", "missionConfigStatus", "missionConfigDiff");
  $("missionConfigApply").onclick = () => {
    if (missionConfigPath && confirm(t("confirmMissionApply"))) {
      saveConfig(missionConfigPath, $("missionYamlEditor").value, "apply", "missionConfigStatus", "missionConfigDiff");
    }
  };
  $("systemConfigReload").onclick = () => systemConfigPath && openSystemConfig(systemConfigPath);
  $("systemConfigSave").onclick = () => saveConfig(systemConfigPath, $("systemYamlEditor").value, "save", "systemConfigStatus", "systemConfigDiff");
  $("systemConfigApply").onclick = () => {
    if (systemConfigPath && confirm(t("confirmSystemApply"))) {
      saveConfig(systemConfigPath, $("systemYamlEditor").value, systemActionForPath(systemConfigPath), "systemConfigStatus", "systemConfigDiff");
    }
  };
}

async function init() {
  wireControls();
  applyLanguage();
  await initVideo();
  completions = (await json("/api/commands/completions")).commands;
  await Promise.all([loadAudit(), loadMissions(), loadConfigFiles()]);
  const firstMissionConfig = allConfigFiles.find(path => path.startsWith("missions/"));
  const firstSystemConfig = allConfigFiles.find(path => !path.startsWith("missions/"));
  if (firstMissionConfig) await openMissionConfig(firstMissionConfig);
  if (firstSystemConfig) await openSystemConfig(firstSystemConfig);
  startStatusUpdates();
}

init().catch(error => { $("completionHint").textContent = error.message; });
