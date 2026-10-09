# OpenAvisio Mobile

Capacitor shell around the web frontend — see ADR 023. The shell ships a single
local page (`www/index.html`) that asks for the Deployment URL, checks
reachability, stores it, and navigates the WebView there. On the next launch it
reconnects automatically.

App ID: `org.openavisio.app` (never change — store identity).

## Workflow

```bash
pnpm install
pnpm exec cap sync        # copy www/ + config into android/ and ios/
```

`www/` is plain HTML/JS — no build step. After editing it, run `cap sync` again.

## Android

Requires JDK 21 and the Android SDK (`compileSdk 36`, see `android/variables.gradle`).
Android Studio brings both; if you only want to build, the command-line tools are
enough and cost ~500 MB:

```bash
# one-off: SDK without Android Studio
export ANDROID_HOME=~/Android/Sdk
mkdir -p "$ANDROID_HOME/cmdline-tools"
curl -sSLo /tmp/cmdline.zip https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip
unzip -q /tmp/cmdline.zip -d "$ANDROID_HOME/cmdline-tools"
mv "$ANDROID_HOME/cmdline-tools/cmdline-tools" "$ANDROID_HOME/cmdline-tools/latest"
printf 'y\n%.0s' $(seq 50) | "$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" --licenses
"$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" "platform-tools" "platforms;android-36" "build-tools;36.0.0"
```

Then, from `mobile/`:

```bash
export ANDROID_HOME=~/Android/Sdk
CI=true pnpm exec cap sync android     # copies www/ into the shell
cd android && ./gradlew assembleDebug
# → app/build/outputs/apk/debug/app-debug.apk
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

Two things that will bite you, both learned the hard way:

- **`CI=true` in front of `cap sync`.** It shells out to `pnpm install`, which
  refuses to purge `node_modules` without a TTY and aborts the whole sync — while
  Gradle happily builds on with the *old* web assets, so you ship yesterday's UI.
- **`yes | sdkmanager --licenses` dies of SIGPIPE** under `pipefail` (exit 141).
  Hence the finite number of y's above.

No local SDK, or no cable to the phone? CI builds it too, on every push to
`mobile/**` and on demand — `.forgejo/workflows/mobile-apk.yml` — and publishes it:

    (build it with the steps above, or grab it from the project releases)

Release builds need a signing keystore — keep it out of the repo and back it up;
losing it means losing the Play Store identity. That is why CI builds debug only:
the keystore is not going into a workflow file (#59).

## App icon

Launcher icons are generated from `assets/` (the OpenAvisio shield) into the
native `res/mipmap-*` folders. `@capacitor/assets` is **not** a committed
dependency — it pulls in ~300 packages plus a native `sharp` build for a job
that runs maybe once a year. Regenerate one-off:

```bash
pnpm add -D @capacitor/assets      # then in pnpm-workspace.yaml: allowBuilds: { sharp: true }; pnpm install
pnpm exec capacitor-assets generate --android
git checkout -- android/app/src/main/AndroidManifest.xml   # it reformats the manifest; keep only the icons
pnpm remove @capacitor/assets && rm pnpm-workspace.yaml
```

`assets/icon-foreground.png` is near full-bleed on purpose — the adaptive-icon
template adds its own 16.7% safe-zone inset, so pre-padding it renders the
shield tiny. `assets/icon-background.png` is the app ivory `#f5f4ee`. The shield is drawn as a
vector in `business/corporate-design/logo/`; export new PNGs from there.

## iOS

Requires a Mac with Xcode + CocoaPods:

```bash
pnpm exec cap open ios
```

## Deep links

The shell registers the `openavisio://` scheme on both platforms:

- `openavisio://connect?url=<deployment>&token=<invite>` — store the Deployment
  URL and open its registration page. The web register page renders this as an
  "Open in the OpenAvisio app" link on mobile browsers.
- `openavisio://reset` — forget the stored Deployment URL and lock setting.

## Biometric app lock

Opt-in checkbox on the connect screen (shown only when the device supports
biometry). When enabled, launching the app requires Face ID / fingerprint /
device credential before the WebView navigates to the Deployment. Resume from
background does not re-lock (launch-gate only).
