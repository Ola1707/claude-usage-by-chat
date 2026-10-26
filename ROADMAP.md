# Roadmap

Goal: a status bar item in VS Code showing four usage values:
5h usage, weekly usage, active chats usage, current chat usage.

## Now

1. Show the 5h usage
2. Show the weekly usage
3. Show the usage percentage of the latest session (same as `python3 usage.py --last`)

## Next: current chat usage (the chat I am using)

Replaces the "latest session by date" logic from step 3. `updatedAt` in `~/.claude/sessions` is last activity, not focus, so it is not used.

1. The focused chat is the active editor tab (`vscode.window.tabGroups`) whose viewType ends with `claudeVSCodePanel`.
2. Its tab title is the session's last `ai-title` entry in `~/.claude/projects/<workspace path with / and . replaced by ->/*.jsonl`. Match them to find the session file.
3. Sum the weighted tokens of that file plus its subagents; show as a percentage of the 5h limit: `chat: N%`.
4. Focus on a non-chat tab (or the sidebar chat, which is not a tab) keeps the last chat seen.

Status: implemented, untested in the real VS Code (tab title vs `ai-title` match is unverified). Two chats with the same title are ambiguous.

## Done (untested in VS Code)

- Active chats usage: still-running chats (live process in `~/.claude/sessions`) whose `cwd` is this window's workspace folder (or below) summed, as % of the 5h limit, with their count (`chats: N% (count)`). Limitation: two VS Code windows on the same folder count each other's chats (session files do not say which window a chat belongs to).
- Current chat usage (see above)
- 5h limit calibration: on each server fetch, limit = local weighted usage since the window start (`resetsAt` − 5h) / server 5h percent. Only from 10% up; within a window the highest percent wins, a new window replaces the old value. Stored in `globalState` and shown in the tooltip; used instead of the `limit5h` setting only with `claudeUsage.autoCalibrate` (off by default until verified after a reset). Usage from other machines or claude.ai is not in the local logs, so it makes the limit look smaller. The weekly limit is not calibrated (not used).
- Server fetch every 10 min (20 after an error), to avoid 429s.
