# Sift

**7,000 photos in. Only the trips come out.**

Sift is a Windows app that opens your Google Takeout zips one at a time and keeps only your travel photos and videos, filed by region and city (`Pictures\Sift Trips\Kashmir\Srinagar`, ...).

It leaves out:

- **People**: selfies, group shots and close-up faces (on-device face detection)
- **Around home**: anything within 60 km of the home you set
- **Received**: WhatsApp forwards and other images from someone else
- **Screens**: screenshots, plus blurry or dark shots
- **No location**: no GPS and no nearby photo to borrow a place from
- **Duplicates**: Takeout copies album photos twice; Sift remembers what it kept across zips

It also fixes bad GPS by checking each photo against the ones taken just before and after it.

## Download

Get **Sift.exe** from the [latest release](../../releases/latest). Windows 10 or 11, 64-bit.

Double-click it and Sift offers to install itself with a Desktop and Start menu shortcut. Sift isn't signed with a paid certificate yet, so Windows may show *Windows protected your PC*: click **More info**, then **Run anyway**.

## Privacy

Sift runs entirely on your laptop. It reads your zips, writes your Trips folder, and sends nothing anywhere. Your originals are never changed.
