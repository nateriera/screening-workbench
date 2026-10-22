# Security and privacy model

## Supported trust boundary

Screening Workbench is a local-first desktop application. Project records, reviewer votes, event history, and project metadata are stored in a local SQLite database; attached PDF bytes are stored beside it in a local attachments directory. Core screening runs without accounts, cloud sync, telemetry, or remote model inference. Data is sent elsewhere only through explicit user exports or transfers of reviewer packet/vote files.

Blind mode provides **application-level isolation**: Screening Workbench's UI, reviewer-scoped views, derived data, exports, and diagnostics are expected not to expose or permit inference of another reviewer's decisions to a blinded reviewer. Blind mode must be selected before the first screening vote and locks when screening begins. The project owner retains the access permitted by the application; explicitly authorized auditors receive only their granted scopes.

## Accepted limitation: local file access

The local project database is not encrypted by Screening Workbench. Blind mode is not a cryptographic boundary and does not protect votes from someone who can directly read or copy the SQLite database or the machine's files (including a user with the same OS account, an administrator, malware, or an unprotected backup). The shared database intentionally retains reviewer decisions and event history for audit replay and possible later unblinding. Attachment files and exported reviewer packets/vote files are likewise local files and require appropriate handling.

This limitation is accepted for the v1 local/offline product model; Screening Workbench does not promise physical absence of other reviewers' decision bytes from the project database. Use operating-system account/device protections and protect backups and exported files. Do not treat blind mode as suitable for adversaries with access to the host, database, or copies of those files.

## Reporting a vulnerability

Do not include project databases, reviewer packets, vote exports, PDFs, or other user data in a vulnerability report. Provide a minimal synthetic reproduction and the affected Screening Workbench version/commit instead. Coordinate disclosure privately with the repository owner before public disclosure. Use GitHub's private vulnerability reporting for this repository (the **Security** tab → **Report a vulnerability**). If that route is unavailable, open a public issue titled "Security contact request" containing no vulnerability details, and a private channel will be arranged.
