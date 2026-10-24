# CareCompass (Android, Flutter)

Thin client for the CareCompass API: all triage and matching happens on the
server; the app sends the conversation to `POST /v1/triage?explain=true&policy=safety`
and renders the response (see `../docs/API.md`). UI text and the look come from
the web app (`../web/src/i18n.ts`, `../web/src/styles.css`).

## Build

```powershell
# This laptop only: Gradle's JDK needs a short unix-socket temp dir
$env:JAVA_TOOL_OPTIONS = "-Djdk.net.unixdomain.tmpdir=C:\tmp"

C:\flutter\bin\flutter.bat build apk --release --dart-define=API_BASE=https://carecompass.145-223-21-27.sslip.io
# -> build\app\outputs\flutter-apk\app-release.apk (debug-signed for now)
```

`API_BASE` defaults: release builds use the HTTPS server above, debug builds
use `http://10.0.2.2:8000` (the emulator's alias for this laptop). Plain HTTP
is allowed only for 10.0.2.2 / localhost / 127.0.0.1
(`android/app/src/main/res/xml/network_security_config.xml`). On a real phone
with a laptop backend, use `adb reverse tcp:8000 tcp:8000` and
`--dart-define=API_BASE=http://127.0.0.1:8000`.

## Check

```powershell
C:\flutter\bin\flutter.bat analyze
C:\flutter\bin\flutter.bat test     # parsing of real API responses, flow, layout at text x1.3
```

Fixtures in `test/fixtures/` are real responses captured from the API
(`v2_*` use the organisers' enum values). `lib/i18n.dart` is generated from
`../web/src/i18n.ts`; mobile-only labels live in `lib/strings_mobile.dart`.
