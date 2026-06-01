<p align="center">
  <a href="../README.md">README</a> &nbsp;·&nbsp;
  <a href="install.md">Install</a> &nbsp;·&nbsp;
  <a href="input-data.md">Input data</a> &nbsp;·&nbsp;
  <a href="web-interface.md">Web interface</a> &nbsp;·&nbsp;
  <strong>Troubleshooting</strong> &nbsp;·&nbsp;
  <a href="command-line.md">Command-line</a> &nbsp;·&nbsp;
  <a href="../LICENSE">License</a>
</p>

---

## Troubleshooting

| If you see… | Do this |
|--------------|--------|
| `Python 3.10+ required` | Install [Python 3.10+](https://www.python.org/downloads/), close and reopen any Terminal, run again. |
| Blank page on `localhost:5000` | Visit **`http://127.0.0.1:5000/pipeline-config`** instead (IPv6/IPv4 quirk on some Macs). |
| **macOS:** Gatekeeper / “cannot check for malicious software” / no **Open** in the right-click menu | **1.** In **Finder**, try **control-click** **`narRater.app`** → **Open**, then confirm **Open** if the dialog offers it — [Apple’s Gatekeeper overrides](https://support.apple.com/guide/mac-help/mh40617/mac). **2.** If that path is missing or still blocks: **System Settings** → **Privacy & Security** → scroll to **Security** — after a failed launch, macOS often shows **`narRater` was blocked** (wording varies) with **Allow Anyway** or **Open Anyway**; click it, enter your password, then launch **`narRater.app`** again (that button may only appear for a limited time after the block). **3.** Downloaded folder still quarantined: in Terminal, `xattr -dr com.apple.quarantine /path/to/narRaters-main`, then try **1** or **2** again. |
| **macOS:** “narRater couldn't find the narRaters project folder” | macOS **App Translocation** ran the app from a temp copy. Run `xattr -dr com.apple.quarantine ~/Downloads/narRaters-main` (adjust path) and double-click again, or use the [command-line install](install.md#alternate-install-command-line). |
| **Windows:** SmartScreen warns about `narRaters_installer.bat` | Click **More info** → **Run anyway**. |
| Port 5000 already in use | The installer auto-tries 5001–5010 and prints the URL. To free 5000: macOS → System Settings → General → AirDrop & Handoff → turn off **AirPlay Receiver**. |

For the full install walkthrough (ZIP, PyPI, optional extras), see **[Install](install.md)**.
