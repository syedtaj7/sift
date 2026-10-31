# Sift

**7,000 photos in. Only the trips come out.**

Sift is a Windows app that opens your Google Takeout zips one at a time (or any folder of photos) and keeps only your travel photos and videos, filed by region and city (`Pictures\Sift Trips\Kashmir\Srinagar`, ...).

It leaves out:

- **People**: selfies, group shots and close-up faces (on-device face detection)
- **Around home**: anything within the radius you set around your home city
- **Received**: WhatsApp forwards and other images from someone else
- **Screens**: screenshots, plus blurry or dark shots
- **No location**: no GPS and no nearby photo to borrow a place from
- **Duplicates**: Takeout copies album photos twice; Sift remembers what it kept across zips

It also fixes bad GPS by checking each photo against the ones taken just before and after it.

## Download

Get **Sift.exe** from the [latest release](https://github.com/syedtaj7/sift/releases/latest). Windows 10 or 11, 64-bit, with Microsoft Edge (built in).

Double-click it and Sift offers to install itself with a Desktop and Start menu shortcut. Sift isn't signed with a paid certificate yet, so Windows may show *Windows protected your PC*: click **More info**, then **Run anyway**.

Each release lists the SHA-256 fingerprint of `Sift.exe`. To check your copy, run this in PowerShell and compare:

```powershell
Get-FileHash .\Sift.exe -Algorithm SHA256
```

## Privacy and security

- Sift runs entirely on your PC. It reads your zips, writes your Trips folder, and sends nothing anywhere. No accounts, no analytics.
- Your originals are never changed. The only thing Sift ever deletes is a Takeout zip, and only when you click **Delete zip** and confirm.
- The app's window talks to a small server on your own PC (`127.0.0.1:8765`) that nothing on your network can reach. It only answers Sift's own window: requests from other websites are refused (Host, Origin and Sec-Fetch-Site checks against DNS rebinding and cross-site requests), it sends a strict Content Security Policy, and it will only open folders inside your trip collection.
- Your home city is stored only in `%LOCALAPPDATA%\Sift\settings.json`.

Found a security problem? Please open an issue without the details and ask for a private contact.

## The download website

`website/` is the download page, a single static HTML file. It needs no build step.

- **Vercel**: *Add New Project*, import this repo, keep the defaults. `vercel.json` already points at `website/` and adds security headers.
- **Netlify**: *Add new site*, *Import an existing project*, pick this repo. `netlify.toml` already sets the publish folder and headers.
- **Any static host**: upload the contents of `website/`.

The Download buttons link to `releases/latest/download/Sift.exe`, so a new release needs no website change. To edit the page, change `site/index.html` and run `python make_website.py`.

## Run or build from source

```bat
Start Sift.bat
```

runs Sift from source (it creates a Python venv on first run). To build `Sift.exe`:

```powershell
.\build.ps1
```

| File | What it is |
|---|---|
| `engine.py` | Sorting: metadata, location repair, face and blur checks, extraction |
| `server.py` | Local server for the app window, with the safety checks |
| `app.py` | Desktop launcher: install, app window, auto-quit |
| `web/` | The app's interface |
| `travel_places.csv` | Extra small towns and landmarks for naming trips |
| `site/`, `website/` | The download page (artifact source and static build) |

## License

Sift is [MIT licensed](LICENSE). The app bundles open-source components under their own licenses, listed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Place names © [GeoNames](https://www.geonames.org) (CC BY 4.0). Sift is not affiliated with or endorsed by Google.
