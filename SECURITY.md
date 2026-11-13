# Security policy

Downloads Manager moves and deletes files on your computer, so security reports matter.

Please do not open a public issue for a vulnerability. Use GitHub's private reporting instead: **Security** tab, then **Report a vulnerability**. Describe the issue and how to reproduce it; you will get an answer within a week.

## What the app protects

- The local server only listens on `127.0.0.1`.
- It refuses requests with a non-local `Host` (DNS rebinding), a foreign `Origin`, and any action sent without the app's own header, so a web page open in your browser cannot drive it.
- Files are never deleted directly: everything goes to a 30-day quarantine first, and every action is journaled and undoable.
