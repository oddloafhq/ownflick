# Android with Termux

OwnFlick runs on an Android phone with [Termux](https://termux.dev). An old phone
on a charger becomes a small always-on media server, and a phone on the road
can share its videos with a tablet over its hotspot. This setup has run for
more than a year on a Pixel 4a.

## Install

Install Termux from [F-Droid](https://f-droid.org/packages/com.termux/) or its
[GitHub releases](https://github.com/termux/termux-app/releases). The Google
Play build is experimental.

```bash
pkg update && pkg upgrade
pkg install python python-pillow ffmpeg
pip install ownflick
termux-setup-storage          # allow access to shared storage
```

`python-pillow` from Termux avoids compiling Pillow on the phone.

## Run

```bash
termux-wake-lock              # keep running with the screen off
ownflick ~/storage/shared/Movies --name Pixel
```

Add more folders with `--media-source`, for example
`--media-source camera=~/storage/shared/DCIM/Camera`. The first start prints
the access password.

Open `http://<phone-address>:8000` on another device on the same Wi-Fi. The
phone's address is under **Settings → Network & internet → Internet → (your
Wi-Fi)**. On the phone itself use `http://127.0.0.1:8000`.

OwnFlick's data lives in Termux's private storage (`~/.spooly`). Uninstalling
Termux deletes it, but not your media.

## Keep it running

- Exempt Termux from battery optimization in Android settings.
- To start OwnFlick when the phone boots, install
  [Termux:Boot](https://f-droid.org/packages/com.termux.boot/), open it once,
  then create `~/.termux/boot/ownflick`:

  ```sh
  #!/data/data/com.termux/files/usr/bin/sh
  termux-wake-lock
  ownflick ~/storage/shared/Movies --name Pixel > ~/ownflick.log 2>&1
  ```

  and make it executable with `chmod +x ~/.termux/boot/ownflick`.
- If Termux shows `[Process completed (signal 9)]`, Android 12 or later
  stopped its child processes. See Termux's notes on the
  [phantom process killer](https://github.com/agnostic-apollo/Android-Docs/blob/master/en/docs/apps/processes/phantom-cached-and-empty-processes.md).

## URL downloads

```bash
pip install "yt-dlp[default]" gallery-dl
pkg install nodejs
mkdir -p ~/.config/yt-dlp
echo "--js-runtimes node" >> ~/.config/yt-dlp/config
```

yt-dlp needs a JavaScript runtime for YouTube. Deno, its default, does not run
on Android, so the config line tells it to use Node instead.
