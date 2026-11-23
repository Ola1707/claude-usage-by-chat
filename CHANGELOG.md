# Changelog

## Unreleased

- Fix: a new chat no longer shows another open chat's `chat` percent when VS Code shortens both tab titles to the same text (e.g. "Nightshift start-review …"). It shows `chat: ?`, and the tooltip explains why.

## 0.0.3

- New order in the status bar: 🦄 `chat`, `chats`, then `5h`/`week`, then `cost est`. The 🦄 leads the first section shown.
- New icon: a 5h ring with this chat's share.
- README: a Questions section (how it counts) and a link to GitHub issues for bugs and questions.
- `chat` and `chats` count each open chat from its first message, so a 5h reset no longer zeroes them. The tooltip shows the part in the current 5h window.
- Clearer description and README start: how much of your 5h limit each chat uses, what sets it apart.
- More search keywords.

## 0.0.2

- Choose which sections the status bar shows (settings **Show …**), each with an example.
- CPU and memory is off by default (setting **Show Cpu Memory**).
- The ⚙ stays right after the last section, even with other extensions' items in the status bar.
- README: a short explanation first, with pictures of each section.

## 0.0.1

First Marketplace release: 5h and weekly usage, chats and focused chat usage, cost estimate, CPU and memory of the chats.
