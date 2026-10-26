const vscode = require("vscode");
const { projectDir, findSessionByTitle, sessionUsage, activeUsage, fetchServerUsage, estimateLimit5h } = require("./usage");

// The chat tab's title is the session's ai-title. Keep the last chat seen, so
// focusing a non-chat tab (or the sidebar chat, which is not a tab) keeps the value.
let lastChatFile;
function focusedChatFile() {
  const tab = vscode.window.tabGroups.activeTabGroup.activeTab;
  const folder = vscode.workspace.workspaceFolders?.[0];
  if (tab && folder && /claudeVSCodePanel$/.test(tab.input?.viewType || "")) {
    lastChatFile = findSessionByTitle(tab.label, projectDir(folder.uri.fsPath)) || lastChatFile;
  }
  return lastChatFile;
}

// TEMP debug: what the extension sees, for diagnosing the chat tab match
function debugDump(o) {
  try {
    const f = require("path").join(require("os").tmpdir(), "claude-usage-debug.json");
    const prev = (() => { try { return JSON.parse(require("fs").readFileSync(f, "utf8")); } catch { return {}; } })();
    require("fs").writeFileSync(f, JSON.stringify({ ...prev, ...o, at: new Date().toISOString() }, null, 1));
  } catch { /* ignore */ }
}

// The usage endpoint rate-limits (429). Fetch at most every 10 minutes (20 after an error), keep the last good value.
let server, serverAt = 0, serverError;
async function cachedServerUsage(onFetched) {
  const wait = serverError ? 20 * 60 * 1000 : 10 * 60 * 1000;
  if (Date.now() - serverAt >= wait) {
    serverAt = Date.now();
    try { server = await fetchServerUsage(); serverError = undefined; onFetched(server); }
    catch (err) { serverError = err; }
  }
  if (!server) throw serverError;
  return server;
}

// 5h limit calibrated from the server's 5h percent: { limit, percent, resetsAt } in globalState.
// Within a window the highest percent wins (most accurate); a new window's first estimate replaces the old one.
function calibrate(state, fiveHour) {
  const limit = estimateLimit5h(fiveHour);
  if (!limit) return;
  const prev = state.get("limit5h");
  if (prev && prev.resetsAt === fiveHour.resetsAt && prev.percent > fiveHour.percent) return;
  state.update("limit5h", { limit, percent: fiveHour.percent, resetsAt: fiveHour.resetsAt });
}

/** Calibrated 5h limit (if claudeUsage.autoCalibrate), else the claudeUsage.limit5h setting. */
function limit5h(state) {
  const config = vscode.workspace.getConfiguration("claudeUsage");
  return (config.get("autoCalibrate", false) && state.get("limit5h")?.limit) || config.get("limit5h", 7500000);
}

function activate(context) {
  const item = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 0);
  item.tooltip = "Claude usage (5h and weekly)";
  item.show();
  // the focused chat in its own item, so only its text gets colored
  const chatItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, -1);
  chatItem.tooltip = "Focused chat, as % of the 5h limit";
  chatItem.show();

  // the focused chat is local only (no server call), so it has its own, faster timer
  const refreshChat = () => {
    // chat in the focused editor tab, as % of the 5h limit (like `usage.py <file>`)
    // always shown: "?" means no chat tab matched (see the tooltip for what the active tab reports)
    let chat = "chat: ?", color;
    try {
      const file = focusedChatFile();
      if (file) {
        const percent = (sessionUsage(file) / limit5h(context.globalState)) * 100;
        chat = `chat: ${percent.toFixed(1)}%`;
        color = percent > 20 ? "charts.red" : percent > 10 ? "charts.orange" : percent > 5 ? "charts.yellow" : "charts.green";
      }
    } catch { /* keep "?" */ }
    chatItem.text = chat;
    chatItem.color = color && new vscode.ThemeColor(color);
    return chat;
  };

  const refresh = async () => {
    const chat = refreshChat();
    let chats = "";
    const tab = vscode.window.tabGroups.activeTabGroup.activeTab;
    const tabInfo = `\nActive tab: "${tab?.label}" (${tab?.input?.viewType || tab?.input?.constructor?.name || "none"})`;
    debugDump({ tabs: vscode.window.tabGroups.all.flatMap((g) => g.tabs.map((t) => ({ label: t.label, active: t.isActive, groupActive: g.isActive, viewType: t.input?.viewType, kind: t.input?.constructor?.name }))), chat });
    // still-running chats of this window's workspace summed, as % of the 5h limit, with their count
    // (no folder open: leave the chats part out rather than show every window's chats)
    try {
      const folders = vscode.workspace.workspaceFolders;
      if (!folders) throw new Error("no workspace folder");
      const { count, total } = activeUsage(folders.map((f) => f.uri.fsPath));
      chats = ` | chats: ${((total / limit5h(context.globalState)) * 100).toFixed(0)}% (${count})`;
    } catch { /* leave the chats part out */ }
    try {
      const { fiveHour, weekly } = await cachedServerUsage((s) => calibrate(context.globalState, s.fiveHour));
      const cal = context.globalState.get("limit5h");
      const auto = vscode.workspace.getConfiguration("claudeUsage").get("autoCalibrate", false);
      const calInfo = cal && `${Math.round(cal.limit).toLocaleString()} (calibrated at ${Math.round(cal.percent)}%)`;
      const limitInfo = auto && cal
        ? `5h limit: ${calInfo}`
        : `5h limit: ${limit5h(context.globalState).toLocaleString()} (setting)` +
          (cal ? `\nCalibrated estimate, not used: ${calInfo}` : "");
      item.text = `🦄 5h: ${Math.round(fiveHour.percent)}% | week: ${Math.round(weekly.percent)}%${chats}`;
      item.tooltip = `Claude usage\n5h resets ${new Date(fiveHour.resetsAt).toLocaleTimeString()}\nWeek resets ${new Date(weekly.resetsAt).toLocaleString()}\n${limitInfo}${tabInfo}`;
    } catch (err) {
      // server unavailable: show "?" rather than a wrong number, with the error on hover
      debugDump({ serverError: String(err && (err.stack || err)), cause: String(err && err.cause) });
      item.text = `$(warning) 5h: ? | week: ?${chats}`;
      item.tooltip = `Claude usage unavailable: ${err && err.message}${tabInfo}`;
    }
  };

  let timer, chatTimer;
  const schedule = () => {
    clearInterval(timer);
    clearInterval(chatTimer);
    const config = vscode.workspace.getConfiguration("claudeUsage");
    timer = setInterval(refresh, Math.max(5, config.get("refreshSeconds", 60)) * 1000);
    chatTimer = setInterval(refreshChat, Math.max(1, config.get("chatRefreshSeconds", 5)) * 1000);
  };

  refresh();
  schedule();
  context.subscriptions.push(
    item,
    chatItem,
    { dispose: () => { clearInterval(timer); clearInterval(chatTimer); } },
    vscode.window.tabGroups.onDidChangeTabs(() => refresh()),
    vscode.window.tabGroups.onDidChangeTabGroups(() => refresh()),
    vscode.workspace.onDidChangeConfiguration((e) => {
      if (e.affectsConfiguration("claudeUsage")) { refresh(); schedule(); }
    })
  );
}

function deactivate() {}

module.exports = { activate, deactivate };
