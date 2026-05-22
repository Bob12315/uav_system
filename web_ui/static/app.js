const $ = (id) => document.getElementById(id);

let lastState = null;
let ws = null;
let language = localStorage.getItem("uav-ui-language") || "zh";
let completionState = {prefix: "", index: 0, matches: []};
let lastYoloRunning = false;
let missionCatalog = [];

const I18N = {
  zh: {
    navControl: "实时控制",
    navMissionConfig: "飞行模式参数",
    navSystemConfig: "系统参数",
    source: "来源",
    linkConnected: "链路已连接",
    linkDisconnected: "链路未连接",
    mode: "模式",
    armed: "已解锁",
    disarmed: "未解锁",
    battery: "电量",
    sendOnStatus: "发送 ON",
    sendOffStatus: "发送 OFF",
    yoloRunning: "YOLO 运行中",
    yoloStopped: "YOLO 未运行",
    yoloStarting: "正在启动 YOLO",
    yoloStopping: "正在停止 YOLO",
    controlActions: "控制操作",
    services: "服务",
    startYolo: "启动 YOLO",
    stopYolo: "停止 YOLO",
    mission: "任务",
    switchMission: "切换任务",
    start: "开始",
    reset: "重置",
    current: "当前任务",
    stage: "阶段",
    auto: "自动阶段",
    approach: "接近",
    overhead: "上方悬停",
    flightCommands: "基础命令",
    applyMode: "切换模式",
    takeoff: "起飞",
    arm: "解锁",
    disarm: "上锁",
    land: "降落",
    stop: "停止",
    control: "控制",
    sendOff: "停止发送",
    sendOn: "开始发送",
    sendCommands: "控制发送",
    gimbal: "云台",
    body: "机体",
    target: "目标",
    prev: "上一个",
    next: "下一个",
    unlock: "解锁目标",
    status: "状态",
    recentResult: "最近结果",
    droneCommands: "发往无人机的命令",
    missionConfig: "飞行模式参数",
    systemConfig: "系统参数",
    configFile: "配置文件",
    reload: "读取",
    save: "保存",
    apply: "应用运行时",
    restartHint: "系统参数保存后通常需要重启 app 或 YOLO 才会生效。",
    commandPlaceholder: "输入命令后回车，Tab 补全",
    sendCommand: "发送",
    ready: "就绪",
    confirm: "确认执行命令",
    completionNone: "没有可补全项",
    completionMatches: "个匹配",
    langButton: "English",
    saved: "已保存",
    loaded: "已读取",
    failed: "失败",
    noData: "--",
    targetValid: "目标有效",
    targetLost: "目标丢失",
  },
  en: {
    navControl: "Live Control",
    navMissionConfig: "Flight Mode Params",
    navSystemConfig: "System Params",
    source: "source",
    linkConnected: "link connected",
    linkDisconnected: "link disconnected",
    mode: "mode",
    armed: "ARMED",
    disarmed: "disarmed",
    battery: "battery",
    sendOnStatus: "SEND ON",
    sendOffStatus: "SEND OFF",
    yoloRunning: "YOLO running",
    yoloStopped: "YOLO stopped",
    yoloStarting: "Starting YOLO",
    yoloStopping: "Stopping YOLO",
    controlActions: "Control Actions",
    services: "Services",
    startYolo: "Start YOLO",
    stopYolo: "Stop YOLO",
    mission: "Mission",
    switchMission: "Switch Mission",
    start: "Start",
    reset: "Reset",
    current: "Current",
    stage: "Stage",
    auto: "Auto Stage",
    approach: "Approach",
    overhead: "Overhead",
    flightCommands: "Flight Commands",
    applyMode: "Set Mode",
    takeoff: "Takeoff",
    arm: "Arm",
    disarm: "Disarm",
    land: "Land",
    stop: "Stop",
    control: "Control",
    sendOff: "SEND Off",
    sendOn: "SEND On",
    sendCommands: "Command Send",
    gimbal: "Gimbal",
    body: "Body",
    target: "Target",
    prev: "Prev",
    next: "Next",
    unlock: "Unlock",
    status: "Status",
    recentResult: "Recent Result",
    droneCommands: "Commands Sent to Drone",
    missionConfig: "Flight Mode Params",
    systemConfig: "System Params",
    configFile: "Config File",
    reload: "Reload",
    save: "Save",
    apply: "Apply Runtime",
    restartHint: "System config changes usually require restarting app or YOLO.",
    commandPlaceholder: "type command and press Enter, Tab completes",
    sendCommand: "Send",
    ready: "ready",
    confirm: "Confirm command",
    completionNone: "no completion",
    completionMatches: "matches",
    langButton: "中文",
    saved: "saved",
    loaded: "loaded",
    failed: "failed",
    noData: "--",
    targetValid: "target valid",
    targetLost: "target lost",
  },
};

const COMMAND_COMPLETIONS = [
  "control send off",
  "control send on",
  "control send toggle",
  "controller gimbal on",
  "controller gimbal off",
  "controller gimbal toggle",
  "controller body on",
  "controller body off",
  "controller body toggle",
  "controller approach on",
  "controller approach off",
  "controller approach toggle",
  "controller all on",
  "controller all off",
  "controller all toggle",
  "target next",
  "target prev",
  "target unlock",
  "target lock ",
  "stage auto",
  "stage mode APPROACH_TRACK",
  "stage mode OVERHEAD_HOLD",
  "stage mode IDLE",
  "stage reload",
  "mission list",
  "mission current",
  "mission start",
  "mission reset",
  "mission switch visual_tracking",
  "mission switch rescue_competition",
  "mission stage APPROACH_TRACK",
  "mission stage OVERHEAD_HOLD",
  "mission stage CORRIDOR_FOLLOW",
  "mission stage IDLE",
  "mission stage PREPARE",
  "mission stage TAKEOFF",
  "mission stage FOLLOW_ROUTE_TO_DROP_ZONE",
  "mission stage SEARCH_DROP_TARGETS",
  "mission stage ALIGN_AND_DROP",
  "mission stage WAIT_PAYLOAD_RELEASE",
  "mission stage RESUME_ROUTE_TO_RECCE_ZONE",
  "mission stage SCAN_RECCE_AREA",
  "mission stage FOLLOW_ROUTE_HOME",
  "mission stage LAND",
  "mission stage DONE",
  "mission stage ABORT",
  "pid reload",
  "mode GUIDED",
  "mode LOITER",
  "mode BRAKE",
  "arm",
  "disarm",
  "takeoff ",
  "land",
  "stop",
  "body_vel ",
  "yaw_rate ",
  "gimbal_rate ",
  "set_servo ",
  "set_relay ",
  "release_payload",
];

function t(key) {
  return (I18N[language] && I18N[language][key]) || I18N.en[key] || key;
}

function fmt(value, fallback = "--") {
  return value === null || value === undefined || value === "" ? fallback : value;
}

function setPill(id, text, level = "") {
  const el = $(id);
  el.textContent = text;
  el.className = `pill ${level}`.trim();
}

function render(state) {
  lastState = state;
  setPill("source", `${t("source")} ${fmt(state.link.source, "UNKNOWN")}`);
  setPill("link", state.link.connected ? t("linkConnected") : t("linkDisconnected"), state.link.connected ? "ok" : "danger");
  setPill("mode", `${t("mode")} ${fmt(state.link.mode, "UNKNOWN")}`);
  setPill("armed", state.link.armed ? t("armed") : t("disarmed"), state.link.armed ? "danger" : "");
  setPill("battery", `${t("battery")} ${state.drone.battery ?? "--"}%`);
  setPill("send", state.control.send_commands ? t("sendOnStatus") : t("sendOffStatus"), state.control.send_commands ? "danger" : "warn");
  renderSwitch("toggle-send", state.control.send_commands);
  renderSwitch("toggle-gimbal", state.control.gimbal);
  renderSwitch("toggle-body", state.control.body);
  renderSwitch("toggle-approach", state.control.approach);
  renderStatusGrid(state);
  renderHistory(state.commands.history || []);
  renderDroneCommands(state.logs.recent || []);
}

function renderSwitch(id, enabled) {
  const button = $(id);
  if (!button) return;
  button.classList.toggle("on", Boolean(enabled));
  const label = button.querySelector("strong");
  if (label) label.textContent = enabled ? "ON" : "OFF";
}

function renderStatusGrid(state) {
  const rows = [
    [t("mission"), state.mission.name],
    [t("stage"), state.mission.stage],
    [I18N[language].controller || "Controller", state.mission.stage_controller],
    [I18N[language].hold || "Hold", state.mission.hold_reason || "none"],
    [t("target"), state.target.valid ? `${t("targetValid")} #${fmt(state.target.track_id)}` : t("targetLost")],
    ["Class", state.target.class_name],
    ["Confidence", state.target.confidence == null ? "--" : `${(Number(state.target.confidence) * 100).toFixed(0)}%`],
    ["ex / ey", `${fmt(state.target.ex)} / ${fmt(state.target.ey)}`],
    ["Scene", `${state.scene.count ?? 0}`],
    ["GPS", `${fmt(state.drone.lat)} / ${fmt(state.drone.lon)}`],
    ["Alt", fmt(state.drone.alt)],
    ["Voltage", fmt(state.drone.voltage)],
    ["Gimbal", state.control.gimbal ? "ON" : "OFF"],
    ["Body", state.control.body ? "ON" : "OFF"],
    ["Approach", state.control.approach ? "ON" : "OFF"],
  ];
  $("status-grid").innerHTML = rows.map(([k, v]) => (
    `<div class="status-item"><span>${escapeHtml(k)}</span><span>${escapeHtml(fmt(v))}</span></div>`
  )).join("");
}

function renderHistory(items) {
  $("history").innerHTML = items.slice(0, 6).map(item => {
    const mark = item.ok ? "OK" : "ERR";
    return `<li>${escapeHtml(`${new Date(item.timestamp * 1000).toLocaleTimeString()} ${mark} ${item.command} -> ${item.message}`)}</li>`;
  }).join("");
}

function renderDroneCommands(items) {
  const list = $("drone-command-list");
  if (!list) return;
  list.innerHTML = items.slice(0, 30).map(item => `<li>${escapeHtml(item)}</li>`).join("");
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, ch => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  }[ch]));
}

async function sendCommand(command, force = false) {
  const text = command.trim();
  if (!text) return;
  if (!force && isDangerous(text) && !window.confirm(`${t("confirm")}: ${text}`)) return;
  const response = await fetch("/api/command", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({command: text}),
  });
  const result = await response.json();
  $("result").textContent = `${result.ok ? "OK" : "ERR"} ${result.message}`;
  const state = await fetch("/api/state").then(r => r.json());
  render(state);
}

function isDangerous(command) {
  const text = command.toLowerCase().trim().replace(/\s+/g, " ");
  return ["arm", "takeoff", "land", "disarm", "control send on", "mission start", "set_servo", "set_relay", "release_payload"]
    .some(prefix => text === prefix || text.startsWith(`${prefix} `));
}

function connectWs() {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${window.location.host}/ws/state`);
  ws.onmessage = (event) => render(JSON.parse(event.data));
  ws.onclose = () => setTimeout(connectWs, 1000);
}

async function loadMissions() {
  const data = await fetch("/api/missions").then(r => r.json());
  missionCatalog = data.items || [];
  const options = (data.items || []).map(item => `<option value="${item.name}">${item.name}</option>`).join("");
  $("mission-select").innerHTML = options;
  $("mission-config-select").innerHTML = options;
  if (data.active) {
    $("mission-select").value = data.active;
    $("mission-config-select").value = data.active;
  }
  renderStageButtons();
}

function renderStageButtons() {
  const missionName = $("mission-select").value;
  const mission = missionCatalog.find(item => item.name === missionName);
  const stages = mission?.stage_options || [];
  $("stage-buttons").innerHTML = stages.map(stage => (
    `<button type="button" data-stage-value="${escapeHtml(stage.value)}">${escapeHtml(stage.label || stage.value)}</button>`
  )).join("");
  document.querySelectorAll("[data-stage-value]").forEach(button => {
    button.addEventListener("click", () => sendCommand(`mission stage ${button.dataset.stageValue}`));
  });
}

async function loadMissionConfig() {
  const mission = $("mission-config-select").value;
  const response = await fetch(`/api/config/mission?mission=${encodeURIComponent(mission)}`);
  const data = await response.json();
  if (!response.ok) {
    $("result").textContent = `ERR ${data.detail?.message || t("failed")}`;
    return;
  }
  $("mission-config-yaml").value = data.yaml || "";
  $("mission-config-path").textContent = data.path || "--";
  $("result").textContent = `${t("loaded")} ${data.path}`;
}

async function saveMissionConfig() {
  const mission = $("mission-config-select").value;
  const response = await fetch(`/api/config/mission?mission=${encodeURIComponent(mission)}`, {
    method: "PATCH",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({yaml: $("mission-config-yaml").value}),
  });
  const data = await response.json();
  $("result").textContent = response.ok ? `${t("saved")} ${data.path}` : `ERR ${data.detail?.message || t("failed")}`;
}

async function applyMissionConfig() {
  const response = await fetch("/api/config/reload", {method: "POST"});
  const data = await response.json();
  $("result").textContent = response.ok ? `OK ${data.message}` : `ERR ${data.detail?.message || t("failed")}`;
}

async function loadSystemConfig() {
  const name = $("system-config-select").value;
  const response = await fetch(`/api/config/system?name=${encodeURIComponent(name)}`);
  const data = await response.json();
  if (!response.ok) {
    $("result").textContent = `ERR ${data.detail?.message || t("failed")}`;
    return;
  }
  $("system-config-yaml").value = data.yaml || "";
  $("system-config-path").textContent = data.path || "--";
  $("result").textContent = `${t("loaded")} ${data.path}`;
}

async function saveSystemConfig() {
  const name = $("system-config-select").value;
  const response = await fetch(`/api/config/system?name=${encodeURIComponent(name)}`, {
    method: "PATCH",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({yaml: $("system-config-yaml").value}),
  });
  const data = await response.json();
  $("result").textContent = response.ok ? `${t("saved")} ${data.path}` : `ERR ${data.detail?.message || t("failed")}`;
}

async function refreshYoloStatus() {
  try {
    const status = await fetch("/api/yolo/status").then(r => r.json());
    renderYoloStatus(status);
  } catch (_error) {
    renderYoloStatus({running: false, message: "status unavailable"});
  }
}

async function startYolo() {
  $("yolo-status").textContent = t("yoloStarting");
  const response = await fetch("/api/yolo/start", {method: "POST"});
  const data = await response.json();
  renderYoloStatus(response.ok ? data : data.detail || data);
  reloadVideo();
}

async function stopYolo() {
  $("yolo-status").textContent = t("yoloStopping");
  const response = await fetch("/api/yolo/stop", {method: "POST"});
  const data = await response.json();
  renderYoloStatus(response.ok ? data : data.detail || data);
}

function renderYoloStatus(status) {
  const running = Boolean(status.running);
  const pid = running && status.pid ? ` pid=${status.pid}` : "";
  $("yolo-status").className = `service-status ${running ? "ok" : "warn"}`;
  $("yolo-status").textContent = `${running ? t("yoloRunning") : t("yoloStopped")}${pid}`;
  setPill("yolo-pill", running ? "YOLO ON" : "YOLO OFF", running ? "ok" : "warn");
  if (status.message) $("result").textContent = status.message;
  if (running && !lastYoloRunning) reloadVideo();
  lastYoloRunning = running;
}

function reloadVideo() {
  $("video").src = `/video/yolo.mjpeg?ts=${Date.now()}`;
}

function applyLanguage() {
  document.documentElement.lang = language === "zh" ? "zh-CN" : "en";
  document.querySelectorAll("[data-i18n]").forEach(node => {
    node.textContent = t(node.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach(node => {
    node.placeholder = t(node.dataset.i18nPlaceholder);
  });
  $("lang-toggle").textContent = t("langButton");
  if ($("result").textContent === "ready" || $("result").textContent === "就绪") {
    $("result").textContent = t("ready");
  }
  if (lastState) render(lastState);
}

function completeCommandInput(event) {
  if (event.key !== "Tab") {
    completionState = {prefix: "", index: 0, matches: []};
    return;
  }
  event.preventDefault();
  const input = $("command-input");
  const cursor = input.selectionStart ?? input.value.length;
  const prefix = input.value.slice(0, cursor);
  const suffix = input.value.slice(cursor);
  const matches = COMMAND_COMPLETIONS.filter(command => command.toLowerCase().startsWith(prefix.toLowerCase()));
  if (matches.length === 0) {
    $("result").textContent = t("completionNone");
    return;
  }
  if (completionState.prefix === prefix && completionState.matches.join("\n") === matches.join("\n")) {
    completionState.index = (completionState.index + 1) % matches.length;
  } else {
    completionState = {prefix, index: 0, matches};
  }
  let completed = matches[completionState.index];
  if (matches.length > 1 && completionState.index === 0) {
    const common = longestCommonPrefix(matches);
    if (common.length > prefix.length) completed = common;
  }
  input.value = completed + suffix;
  input.selectionStart = input.selectionEnd = completed.length;
  $("result").textContent = matches.length === 1
    ? completed
    : `${matches.length} ${t("completionMatches")}: ${matches.slice(0, 6).join(" | ")}`;
}

function longestCommonPrefix(values) {
  if (values.length === 0) return "";
  let prefix = values[0];
  for (const value of values.slice(1)) {
    while (!value.toLowerCase().startsWith(prefix.toLowerCase()) && prefix.length > 0) {
      prefix = prefix.slice(0, -1);
    }
  }
  return prefix;
}

document.querySelectorAll(".nav-item").forEach(button => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".nav-item").forEach(item => item.classList.remove("active"));
    document.querySelectorAll(".page").forEach(page => page.classList.remove("active"));
    button.classList.add("active");
    $(`page-${button.dataset.page}`).classList.add("active");
  });
});

document.querySelectorAll("[data-command]").forEach(button => {
  button.addEventListener("click", () => sendCommand(button.dataset.command));
});

$("command-form").addEventListener("submit", event => {
  event.preventDefault();
  sendCommand($("command-input").value);
  $("command-input").value = "";
});

$("start-yolo").addEventListener("click", startYolo);
$("stop-yolo").addEventListener("click", stopYolo);
$("video").addEventListener("error", () => setTimeout(reloadVideo, 1200));
$("mode-apply").addEventListener("click", () => sendCommand(`mode ${$("mode-select").value}`));
$("takeoff").addEventListener("click", () => sendCommand(`takeoff ${$("takeoff-alt").value}`));
$("mission-switch").addEventListener("click", () => sendCommand(`mission switch ${$("mission-select").value}`));
$("toggle-send").addEventListener("click", () => {
  const enabled = Boolean(lastState?.control?.send_commands);
  sendCommand(`control send ${enabled ? "off" : "on"}`);
});
$("toggle-gimbal").addEventListener("click", () => sendCommand("controller gimbal toggle"));
$("toggle-body").addEventListener("click", () => sendCommand("controller body toggle"));
$("toggle-approach").addEventListener("click", () => sendCommand("controller approach toggle"));
$("mission-select").addEventListener("change", renderStageButtons);
$("mission-config-load").addEventListener("click", loadMissionConfig);
$("mission-config-save").addEventListener("click", saveMissionConfig);
$("mission-config-apply").addEventListener("click", applyMissionConfig);
$("mission-config-select").addEventListener("change", loadMissionConfig);
$("system-config-load").addEventListener("click", loadSystemConfig);
$("system-config-save").addEventListener("click", saveSystemConfig);
$("system-config-select").addEventListener("change", loadSystemConfig);
$("command-input").addEventListener("keydown", completeCommandInput);
$("lang-toggle").addEventListener("click", () => {
  language = language === "zh" ? "en" : "zh";
  localStorage.setItem("uav-ui-language", language);
  applyLanguage();
});

applyLanguage();
loadMissions().then(loadMissionConfig).catch(() => {});
loadSystemConfig().catch(() => {});
fetch("/api/state").then(r => r.json()).then(render).catch(() => {});
refreshYoloStatus();
setInterval(refreshYoloStatus, 3000);
connectWs();
