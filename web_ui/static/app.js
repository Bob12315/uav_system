const $ = id => document.getElementById(id);
let state = {};
let completions = [];
let history = [];
let historyIndex = -1;
let currentConfigPath = "";
let currentOriginal = "";

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
  return String(text ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
}
async function execute(command, source = "BUTTON") {
  if (!command) return;
  const result = await json("/api/commands/execute", {
    method: "POST", body: JSON.stringify({command, source})
  });
  $("completionHint").textContent = result.message;
  await loadAudit();
  return result;
}
function setBadge(element, text, cls) {
  element.textContent = text;
  element.className = `badge ${cls || ""}`;
}
function cards(target, values) {
  target.innerHTML = Object.entries(values).map(([label, value]) =>
    `<div class="card"><label>${escapeHtml(label)}</label>${escapeHtml(value)}</div>`).join("");
}
function infoRows(target, rows) {
  target.innerHTML = rows.map(([label, value]) =>
    `<div class="info-label">${escapeHtml(label)}</div><div class="info-value">${escapeHtml(value)}</div>`
  ).join("");
}
function num(value, digits = 2, unit = "") {
  return Number.isFinite(Number(value)) ? `${Number(value).toFixed(digits)}${unit}` : "--";
}
function boolText(value, yes = "YES", no = "NO") {
  return value ? yes : no;
}
function renderStatus(next) {
  state = next;
  const link = next.link || {};
  const drone = next.drone || {};
  const gimbal = next.gimbal || {};
  const target = next.perception || {};
  const controls = next.controllers || {};
  setBadge($("sourceBadge"), `SOURCE ${String(next.active_source || "--").toUpperCase()}`, next.active_source === "real" ? "warning" : "");
  setBadge($("linkBadge"), `LINK ${link.connected ? "OK" : "DOWN"}`, link.connected ? "ok" : "danger");
  setBadge($("sendBadge"), `SEND ${controls.send_commands ? "ON" : "OFF"}`, controls.send_commands ? "danger" : "ok");
  $("missionName").textContent = next.mission || "--";
  $("missionStage").textContent = next.stage || "--";
  $("stageController").textContent = next.stage_controller || "--";
  $("holdReason").textContent = next.hold_reason || "none";
  $("targetCurrent").textContent = target.target_valid
    ? `当前锁定: ${target.class_name} #${target.track_id} (${Number(target.confidence).toFixed(2)})`
    : "当前锁定: --";
  const scene = next.scene || {};
  const detections = scene.detections || [];
  infoRows($("targetInfo"), [
    ["目标状态", target.target_valid ? "LOCKED" : (target.tracking_state || "--").toUpperCase()],
    ["Track ID", target.target_valid ? `#${target.track_id}` : "--"],
    ["类别/置信度", target.target_valid ? `${target.class_name || "--"} / ${num(target.confidence, 2)}` : "--"],
    ["Frame", `${scene.frame_id ?? target.frame_id ?? "--"}`],
    ["检测数", `${detections.length}`],
    ["图像尺寸", `${scene.image_width || target.image_width || "--"} x ${scene.image_height || target.image_height || "--"}`],
    ["中心 cx/cy", target.target_valid ? `${num(target.cx, 1)} / ${num(target.cy, 1)}` : "--"],
    ["框 w/h", target.target_valid ? `${num(target.w, 1)} / ${num(target.h, 1)}` : "--"],
    ["误差 ex/ey", target.target_valid ? `${num(target.ex, 3)} / ${num(target.ey, 3)}` : "--"],
    ["目标尺寸", target.target_valid ? num(target.target_size, 3) : "--"],
    ["丢失计数", `${target.lost_count ?? "--"}`],
    ["Scene 时间", stamp(scene.timestamp || target.timestamp)],
  ]);
  infoRows($("aircraftInfo"), [
    ["数据源", `${String(next.active_source || "--").toUpperCase()} / ${link.status_text || "--"}`],
    ["链路", `${boolText(link.connected, "OK", "DOWN")} ${link.transport || ""}`.trim()],
    ["重连中", boolText(link.reconnecting)],
    ["目标系统", `${link.target_system ?? "--"}:${link.target_component ?? "--"}`],
    ["链路 RX/TX", `${stamp(link.last_rx_time)} / ${stamp(link.last_tx_time)}`],
    ["链路超时", `${num(link.heartbeat_timeout_sec, 1, " s")} / ${num(link.rx_timeout_sec, 1, " s")}`],
    ["飞控模式", drone.mode || "--"],
    ["解锁", boolText(drone.armed, "ARMED", "DISARMED")],
    ["控制允许", boolText(drone.control_allowed)],
    ["状态过期", boolText(drone.stale)],
    ["状态时间", stamp(drone.timestamp)],
    ["心跳/接收", `${num(drone.hb_age_sec, 2, " s")} / ${num(drone.rx_age_sec, 2, " s")}`],
    ["有效标志", `ATT:${+Boolean(drone.attitude_valid)} VEL:${+Boolean(drone.velocity_valid)} ALT:${+Boolean(drone.altitude_valid)}`],
    ["定位标志", `G:${+Boolean(drone.global_position_valid)} R:${+Boolean(drone.relative_alt_valid)} L:${+Boolean(drone.local_position_valid)}`],
    ["姿态 R/P/Y", `${num(drone.roll, 3)} / ${num(drone.pitch, 3)} / ${num(drone.yaw, 3)}`],
    ["角速度 R/P/Y", `${num(drone.roll_rate, 3)} / ${num(drone.pitch_rate, 3)} / ${num(drone.yaw_rate, 3)}`],
    ["速度 N/E/D", `${num(drone.vx, 2)} / ${num(drone.vy, 2)} / ${num(drone.vz, 2)}`],
    ["速度源/质量", `${drone.velocity_source || "--"} / ${drone.velocity_quality || "--"}`],
    ["本地位置", drone.local_position_valid ? `${num(drone.local_x, 2)} / ${num(drone.local_y, 2)} / ${num(drone.local_z, 2)}` : "--"],
    ["高度 相对/海拔", `${num(drone.relative_altitude, 2, " m")} / ${num(drone.altitude, 2, " m")}`],
    ["经纬度", drone.global_position_valid ? `${num(drone.lat, 7)}, ${num(drone.lon, 7)}` : "--"],
    ["GPS", `${drone.gps_fix_type ?? "--"} fix / ${drone.satellites_visible ?? "--"} sats`],
    ["GPS EPH/EPV", `${num(drone.gps_eph, 2)} / ${num(drone.gps_epv, 2)}`],
    ["电池", drone.battery_valid ? `${num(drone.battery_voltage, 1, " V")} / ${drone.battery_remaining}%` : "--"],
    ["云台有效", boolText(gimbal.gimbal_valid)],
    ["云台 Y/P/R", gimbal.gimbal_valid ? `${num(gimbal.yaw, 3)} / ${num(gimbal.pitch, 3)} / ${num(gimbal.roll, 3)}` : "--"],
    ["云台消息", gimbal.source_msg_type || "--"],
    ["云台时间", stamp(gimbal.last_update_time || gimbal.timestamp)],
    ["最新消息", drone.last_message_type || "--"],
  ]);
  renderDetections(scene, target);
  cards($("statusCards"), {
    "链路": `${link.status_text || "--"} / ${link.transport || "--"}`,
    "心跳": link.connected ? `${num(drone.hb_age_sec, 2, " s")} ago` : "--",
    "接收": link.connected ? `${num(drone.rx_age_sec, 2, " s")} ago` : "--",
    "目标系统": `${link.target_system ?? "--"}:${link.target_component ?? "--"}`,
    "飞控模式": drone.mode || "--",
    "解锁状态": drone.armed ? "ARMED" : "DISARMED",
    "姿态 R/P/Y": `${num(drone.roll, 3)} / ${num(drone.pitch, 3)} / ${num(drone.yaw, 3)}`,
    "高度": `${num(drone.relative_altitude, 2, " m")} / ${num(drone.altitude, 2, " m")}`,
    "速度 NED": `${num(drone.vx, 2)} / ${num(drone.vy, 2)} / ${num(drone.vz, 2)}`,
    "本地位置": drone.local_position_valid ? `${num(drone.local_x, 2)} / ${num(drone.local_y, 2)} / ${num(drone.local_z, 2)}` : "--",
    "GPS": `${drone.gps_fix_type ?? "--"} / ${drone.satellites_visible ?? "--"} sats`,
    "经纬度": drone.global_position_valid ? `${num(drone.lat, 7)}, ${num(drone.lon, 7)}` : "--",
    "电池": drone.battery_valid ? `${Number(drone.battery_voltage).toFixed(1)} V / ${drone.battery_remaining}%` : "--",
    "云台 Y/P/R": gimbal.gimbal_valid ? `${num(gimbal.yaw, 3)} / ${num(gimbal.pitch, 3)} / ${num(gimbal.roll, 3)}` : "--",
    "最新消息": drone.last_message_type || "--",
    "Mission": next.mission || "--", "Stage": next.stage || "--",
    "Target": target.target_valid ? `${target.class_name} #${target.track_id}` : "--",
    "Hold": next.hold_reason || "none"
  });
  const cmd = next.command || {};
  cards($("commandCards"), {
    "VX": Number(cmd.vx_cmd || 0).toFixed(3), "VY": Number(cmd.vy_cmd || 0).toFixed(3),
    "VZ": Number(cmd.vz_cmd || 0).toFixed(3), "Yaw": Number(cmd.yaw_rate_cmd || 0).toFixed(3),
    "Gimbal Y": Number(cmd.gimbal_yaw_rate_cmd || 0).toFixed(3),
    "Gimbal P": Number(cmd.gimbal_pitch_rate_cmd || 0).toFixed(3),
    "Active": String(Boolean(cmd.active)), "SEND": controls.send_commands ? "ON" : "OFF"
  });
  $("events").innerHTML = (next.events || []).map(item =>
    `<div class="log-line">${stamp(item.timestamp)} ${escapeHtml(item.level)} &nbsp; ${escapeHtml(item.message)}</div>`).join("");
}
function renderDetections(scene, target) {
  $("frameId").textContent = scene.frame_id ?? "--";
  const detections = scene.detections || [];
  $("detCount").textContent = detections.length;
  $("detections").innerHTML = detections.map(det => {
    const locked = target.target_valid && det.track_id === target.track_id;
    return `<button class="detection ${locked ? "locked" : ""}" data-track="${det.track_id}">
      <span>#${det.track_id} ${escapeHtml(det.class_name)}</span><span>${Number(det.confidence).toFixed(2)}</span></button>`;
  }).join("") || `<div class="hint">暂无目标</div>`;
  $("detections").querySelectorAll("[data-track]").forEach(button => button.onclick = () =>
    execute(`target lock ${button.dataset.track}`, "LIST"));
}
function clickVideo(event) {
  const scene = state.scene || {};
  const img = $("video");
  if (!scene.image_width || !scene.image_height) return;
  const rect = img.getBoundingClientRect();
  const sourceRatio = scene.image_width / scene.image_height;
  const boxRatio = rect.width / rect.height;
  const shownWidth = sourceRatio > boxRatio ? rect.width : rect.height * sourceRatio;
  const shownHeight = sourceRatio > boxRatio ? rect.width / sourceRatio : rect.height;
  const offsetX = (rect.width - shownWidth) / 2;
  const offsetY = (rect.height - shownHeight) / 2;
  const displayX = event.clientX - rect.left - offsetX;
  const displayY = event.clientY - rect.top - offsetY;
  if (displayX < 0 || displayY < 0 || displayX > shownWidth || displayY > shownHeight) return;
  const x = displayX * scene.image_width / shownWidth;
  const y = displayY * scene.image_height / shownHeight;
  const hits = (scene.detections || []).filter(d => x >= d.x1 && x <= d.x2 && y >= d.y1 && y <= d.y2);
  if (!hits.length) {
    $("completionHint").textContent = "点击位置没有可锁定目标";
    return;
  }
  hits.sort((a, b) => (a.w * a.h) - (b.w * b.h));
  execute(`target lock ${hits[0].track_id}`, "VIDEO");
}
async function loadAudit() {
  const records = await json("/api/audit?limit=100");
  history = records.filter(r => ["CLI", "BUTTON"].includes(r.source)).map(r => r.action);
  $("auditLog").innerHTML = records.map(r =>
    `<div class="log-line ${r.ok ? "" : "bad"}">${stamp(r.timestamp)} ${escapeHtml(r.source)} &nbsp; ${escapeHtml(r.action)}</div>`).join("");
}
async function loadMissions() {
  const missions = await json("/api/missions");
  $("missionSelect").innerHTML = missions.map(item =>
    `<option value="${item.name}" ${item.active ? "selected" : ""}>${item.name}</option>`).join("");
}
async function loadConfigFiles() {
  const files = await json("/api/config/files");
  $("configFiles").innerHTML = files.map(path => `<button data-path="${path}">${path}</button>`).join("");
  $("configFiles").querySelectorAll("button").forEach(button => button.onclick = () => openConfig(button.dataset.path));
}
function startStatusUpdates() {
  let fallbackTimer = null;
  const pollStatus = () => json("/api/status").then(renderStatus).catch(error => {
    $("completionHint").textContent = `状态刷新失败: ${error.message}`;
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
async function openConfig(path) {
  const file = await json(`/api/config/file?path=${encodeURIComponent(path)}`);
  currentConfigPath = path;
  currentOriginal = file.content;
  $("editingPath").textContent = path;
  $("yamlEditor").value = file.content;
  $("configDiff").textContent = "";
  $("configStatus").textContent = file.has_backup ? "存在上一次保存前版本，可恢复。" : "尚无备份版本。";
  document.querySelectorAll("#configFiles button").forEach(b => b.classList.toggle("active", b.dataset.path === path));
  const action = path.startsWith("missions/") ? "保存并应用" :
    path === "config/telemetry.yaml" ? "保存并重连" :
    path === "yolo_app/config.yaml" ? "保存并重启 YOLO" :
    path === "config/app.yaml" ? "保存并重启 App" : "保存并应用";
  $("applyConfig").textContent = action;
}
function localDiff(before, after) {
  if (before === after) return "没有修改。";
  return "已修改配置；保存前后端会再次校验 YAML，并返回正式差异。";
}
async function saveConfig(action = "save") {
  if (!currentConfigPath) return;
  if (action !== "save" && !confirm(`${$("applyConfig").textContent} 将可能停止命令发送或重启服务，确认继续？`)) return;
  const result = await json(`/api/config/file?path=${encodeURIComponent(currentConfigPath)}`, {
    method: "PUT", body: JSON.stringify({content: $("yamlEditor").value, action})
  });
  currentOriginal = $("yamlEditor").value;
  $("configDiff").textContent = result.diff || "保存成功，无文本差异。";
  $("configStatus").textContent = result.message;
  await loadAudit();
}
function actionForPath() {
  if (currentConfigPath.startsWith("missions/")) return "apply";
  if (currentConfigPath === "config/telemetry.yaml") return "reconnect";
  if (currentConfigPath === "yolo_app/config.yaml" || currentConfigPath === "config/app.yaml") return "restart";
  return "save";
}
async function init() {
  const videoConfig = await json("/api/yolo/stream");
  const videoUrl = `${location.protocol}//${location.hostname}:${videoConfig.port}${videoConfig.path}`;
  $("video").src = videoUrl;
  $("video").onload = () => $("videoOffline").style.display = "none";
  $("video").onerror = () => {
    $("videoOffline").style.display = "block";
    setTimeout(() => { $("video").src = `${videoUrl}?retry=${Date.now()}`; }, 1500);
  };
  $("hitCanvas").onclick = clickVideo;
  document.querySelectorAll("[data-command]").forEach(button => button.onclick = () => {
    if (button.dataset.confirm && !confirm(button.dataset.confirm)) return;
    execute(button.dataset.command, button.dataset.origin || "BUTTON");
  });
  $("takeoffButton").onclick = () => {
    const altitude = $("takeoffAltitude").value;
    if (confirm(`确认起飞至 ${altitude} m？`)) execute(`takeoff ${altitude}`, "BUTTON");
  };
  $("missionSwitch").onclick = () => execute(`mission switch ${$("missionSelect").value}`, "BUTTON").then(loadMissions);
  $("sendCommand").onclick = () => {
    const input = $("commandInput");
    execute(input.value, "CLI"); input.value = ""; historyIndex = -1;
  };
  $("commandInput").onkeydown = event => {
    if (event.key === "Enter") { event.preventDefault(); $("sendCommand").click(); }
    if (event.key === "Tab") {
      event.preventDefault();
      const match = completions.find(item => item.toLowerCase().startsWith(event.target.value.toLowerCase()));
      if (match) { event.target.value = match; $("completionHint").textContent = `补全: ${match}`; }
    }
    if (event.key === "ArrowUp" && history.length) {
      event.preventDefault(); historyIndex = Math.min(historyIndex + 1, history.length - 1); event.target.value = history[historyIndex];
    }
    if (event.key === "ArrowDown" && historyIndex >= 0) {
      event.preventDefault(); historyIndex -= 1; event.target.value = historyIndex < 0 ? "" : history[historyIndex];
    }
  };
  document.querySelectorAll(".tab").forEach(tab => tab.onclick = () => {
    document.querySelectorAll(".tab").forEach(item => item.classList.toggle("active", item === tab));
    document.querySelectorAll(".page").forEach(page => page.classList.toggle("active", page.id === `${tab.dataset.page}Page`));
  });
  $("previewConfig").onclick = () => $("configDiff").textContent = localDiff(currentOriginal, $("yamlEditor").value);
  $("saveConfig").onclick = () => saveConfig("save");
  $("applyConfig").onclick = () => saveConfig(actionForPath());
  $("restoreConfig").onclick = async () => {
    if (!currentConfigPath || !confirm("确认恢复上一次保存前版本？")) return;
    const action = currentConfigPath.startsWith("missions/") ? "apply" : "save";
    const result = await json(`/api/config/restore?path=${encodeURIComponent(currentConfigPath)}&action=${action}`, {method: "POST"});
    $("configStatus").textContent = result.message; $("configDiff").textContent = result.diff; await openConfig(currentConfigPath); await loadAudit();
  };
  $("reconnectTelemetry").onclick = () => confirm("重连通信将关闭自动发送，确认？") && json("/api/services/telemetry/reconnect", {method: "POST"}).then(loadAudit);
  $("restartYolo").onclick = () => confirm("确认重启 YOLO 服务？") && json("/api/services/yolo/restart", {method: "POST"}).then(loadAudit);
  $("restartApp").onclick = () => confirm("重启 App 将关闭自动发送并暂时断开网页，确认？") && json("/api/services/app/restart", {method: "POST"}).then(loadAudit);
  completions = (await json("/api/commands/completions")).commands;
  await Promise.all([loadAudit(), loadMissions(), loadConfigFiles()]);
  startStatusUpdates();
}
init().catch(error => { $("completionHint").textContent = error.message; });
