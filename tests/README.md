# Download Manager tests

Run from the repository root with Python 3.12 and **one Qt binding per environment**:

```powershell
py -3.12 -m venv "$env:TEMP\mo2-download-tests-qt6"
& "$env:TEMP\mo2-download-tests-qt6\Scripts\python.exe" -m pip install "PyQt6>=6.8,<7"
& "$env:TEMP\mo2-download-tests-qt6\Scripts\python.exe" -B -m unittest discover -s tests -v
```

Repeat with a separate `mo2-download-tests-qt5` environment and `PyQt5>=5.15,<6` to exercise the fallback binding. Installing both into one environment only tests Qt6. No global Python changes, MO2 launch, Nexus credentials, or pytest installation are needed. CI runs both bindings on Windows/Python 3.12.

The tests use real temporary archives/sidecars and Qt, with a controlled MO2 host adapter. Action/window tests forbid HTTP connections; re-query tests replace the external HTTP connection with the synthetic response in `fixtures/nexus-md5.json`. No test contacts Nexus. Failure injection is limited to filesystem/Qt behavior and external adapters; assertions exercise model operations and table/window behavior, not extracted helpers.

Coverage includes exact sidecar deletion, absent files, partial failures, archive replacement, invalid/missing metadata, verified and uncertain hiding, failed scan recovery, checked targets hidden by filters, selection/sort retention, confirmation and summaries, conflicting operations, and hash cancellation/error cleanup.

Public-report regressions also cover re-query writing Qt root metadata and the matched file description (PR #22), and actual rendered alternating-row contrast (issue #20). Theme tests use self-contained stylesheets, verify real foreground/background pixels, restore application styling afterward, and cover theme/palette changes and existing selection colours. They do not require the developer's installed MO2 stylesheets. See [`docs/bug-report-triage.md`](../docs/bug-report-triage.md) for sources, reproduction evidence, and unresolved reports.

Qt6 uses the offscreen platform by default. Qt5 on Windows uses the Windows platform: Qt 5.15.2 can crash when showing a message box under offscreen/minimal. Small test dialogs may briefly appear and are dismissed automatically. `QT_QPA_PLATFORM` can override the default, but do not force offscreen for Qt5 on Windows.

These tests do not replace a smoke test inside MO2. They do not prove atomicity against other processes: identity checks are best-effort, and an interrupted in-place metadata write is reported as uncertain rather than rolled back. Existing installation-result semantics, live Nexus/network behavior, and general metadata-format compatibility are outside these tests.
