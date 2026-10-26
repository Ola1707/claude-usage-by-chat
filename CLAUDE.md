# Claude usage by chat

A VS Code extension that shows Claude usage in the bottom status bar.

- The usage logic comes from `usage.py` (reference only; the extension ports the logic, it does not call Python).
- Usage is a weighted token sum: input x1, output x5, cache write x1.25, cache read x0.1.
- See `ROADMAP.md` for what we are building and in what order.
