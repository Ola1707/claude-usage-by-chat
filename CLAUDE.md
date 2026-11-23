# Claude usage by chat

A VS Code extension that shows Claude usage in the bottom status bar.

- The usage logic comes from `usage.py` (reference only; the extension ports the logic, it does not call Python).
- Usage is a weighted token sum at per-model API prices (`PRICES` in `usage.js`), in units of one Opus 5.5 input token ($4/MTok). Cache writes are the model's input price x1.25 (5m TTL) or x2 (1h TTL); cache reads x0.1 input unless the price list says otherwise. Unknown models cost as the newest of their family. Haiku 5.5 costs 5x above a 100K-token prompt (`LONG_PROMPT`); fast mode 2x. `usage.py` still uses the old flat weights.
- See `ROADMAP.md` for what we are building and in what order.

## Testing a build

- Never install a test build into Ola's own VS Code; don't touch it unless Ola asks. Test in a separate VS Code with its own settings and extensions:
  ```sh
  D=~/.claude-usage-test-vscode
  npx --yes @vscode/vsce package -o $D/test.vsix
  code --user-data-dir $D/data --extensions-dir $D/ext --install-extension anthropic.claude-code --install-extension $D/test.vsix --force
  code --user-data-dir $D/data --extensions-dir $D/ext --new-window <folder>
  ```
  Repeat the package and install lines after every change, then reload that window.
- Never match a chat by its title: only by the session id VS Code saves with each tab (`chatFileForTab`). Tests fail if title matching comes back.
