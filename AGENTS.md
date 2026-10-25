# VIC — Codex Agent Instructions

This repository develops **Virtual Industrial Camera (VIC)**: a Windows x64 virtual industrial camera with a **GenTL Producer** and a **GigE Vision simulator**, targeting external interoperability with **Harvester, HALCON, and Cognex VisionPro**.

## 1. Scope and sources of truth

- Work on **one explicitly requested stage or bug** at a time. Do not implement future stages without permission.
- Before changing code, inspect the repository, read `PROJECT_STATUS.md` (if present), the relevant task in `tasks/`, and only the applicable specifications in `docs/` (`SPEC.md`, `GENTL.md`, `GIGE.md`, etc.). Do not load every document indiscriminately.
- If filenames differ, find their actual locations; do not create duplicate specifications just to satisfy a path.
- Priority when instructions conflict: user's current request > this file > relevant task acceptance criteria > technical specifications. Flag material contradictions before making irreversible changes.
- Keep `AGENTS.md` short. Store protocol details, commands, and extensive test cases in the relevant docs.

## 2. Technical and compatibility rules

- Primary target: Windows 10/11 x64; C++17, CMake/MSVC, OpenCV; PySide6 GUI as specified by the task.
- GenTL `.cti` must use real standard ABI, handles, device/stream discovery, buffer lifecycle, events, and GenICam XML; it is not sufficient to export stub functions.
- GigE Vision implementation must use correct GVCP/GVSP and GenICam behavior, not a custom UDP protocol. Avoid invented register layouts, packet constants, or API signatures.
- Obtain constants/structs/signatures from available official specifications and headers. When an authoritative source is unavailable, record the blocker and assumptions; never present guesses as standards compliance.
- Keep GenTL and GigE Vision as separate adapters over a shared camera core; avoid breaking existing paths when changing the other.
- Preserve accurate Mono8/RGB8 byte order, frame metadata, acquisition/trigger state, and buffer ownership. Prefer safe bounded queues and explicit shutdown handling.
- **Discovery != connection != acquisition != valid image.** Test these separately. Harvester success does not prove HALCON or VisionPro success.
- Do not claim VisionPro compatibility without an actual VisionPro test on the target setup. For same-PC GigE Vision testing, verify NIC selection, UDP routing, firewall settings, and packets rather than assuming loopback works.

## 3. Workflow for every coding task

1. **Inspect:** Identify the current stage, files, existing tests, and likely regressions. State a concise plan.
2. **Implement:** Make the smallest coherent change. Avoid unnecessary refactors and out-of-scope features.
3. **Verify:** Build and run relevant automated tests where the environment permits. Record exact commands and outcomes. Never fabricate results or logs.
4. **Manual test:** Create or update a task-specific guide under `tests/manual/`. Include prerequisites, the exact executable/build to run, numbered UI/CLI steps, expected outcomes, and evidence to capture when it fails.
5. **Handoff:** Summarize modified files, tested/unverified functionality, known issues, and the next manual validation action. **Stop at the stage boundary** unless the user explicitly authorizes proceeding.

## 4. Required manual acceptance gate

- Coding completion is **not** stage acceptance. After implementation, mark the stage `AWAITING MANUAL TEST` until the user reports manual results.
- The user may explicitly waive a manual step; document the waiver, but do not convert an unrun test into `PASS`.
- Use test statuses consistently:
  - `PASS`: executed and observed passing, with evidence.
  - `FAIL`: executed and observed failing, with evidence.
  - `BLOCKED`: cannot execute due to a known prerequisite/blocker.
  - `NOT TESTED`: not executed.
- Stage-level `PASS` requires all mandatory acceptance tests passing, including user-dependent tests (or explicitly documented approved exceptions).
- For external consumers, report **device discovered**, **device opened**, **acquisition started**, and **valid frames received** separately.
- If a manual test fails, investigate the report/logs, fix only the implicated problem, rerun automated tests, update the manual guide, and ask for retesting of the failure plus affected regressions.

## 5. Test guide template

Each task's guide (`tests/manual/<stage>_<name>.md`) must contain:

- Build identifier / commit hash and exact file paths to executables or `.cti` files.
- Prerequisites: OS, dependencies, required software and version, license, network adapter, and permissions where relevant.
- Setup and startup commands; how to confirm the expected build is running.
- Numbered test steps with **expected results at each step**.
- Separate checks for detection, opening, parameters, image acquisition, trigger, stop, reconnect, and relevant regression cases.
- Failure evidence: logs, screenshot locations, errors, and (for GigE) optional packet capture instructions.
- Checklist with `PASS / FAIL / BLOCKED / NOT TESTED` and space for user comments.
- Cleanup instructions.

Do not describe GUI buttons or commands you have not verified exist; mark them for confirmation instead.

## 6. Project continuity

- After each task, update `PROJECT_STATUS.md` (create it if absent) with: current stage, state, completed work, modified files, automated test evidence, pending manual tests, blockers/known issues, and next action. Keep it short, factual, and usable in a new Codex conversation.
- Keep `docs/ROADMAP.md` aligned with actual stage status if it exists. Maintain changelog as required by the repository.
- Do not overwrite user work. Inspect Git status before changes; do not silently discard unrelated modifications.
- Commit changes only when the user has authorized commits or the repository's established workflow requires them. Do not imply manual acceptance merely because a commit exists.

## 7. End-of-task response format

Provide these headings, briefly:

1. **Implemented** — what changed and key files.
2. **Automated checks** — exact commands and `PASS/FAIL/BLOCKED/NOT TESTED`.
3. **Manual test** — link/path to guide and concise steps the user should perform.
4. **Risks / limitations** — precise outstanding issues.
5. **Status / next step** — normally `AWAITING MANUAL TEST`, pending user feedback.

Never claim a build, test, consumer connection, packet capture, or hardware/software compatibility was verified unless it actually was.
