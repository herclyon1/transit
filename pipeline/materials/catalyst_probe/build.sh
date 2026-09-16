#!/bin/sh
# Build the Mac Catalyst probe app into $1 (default: /tmp/probe.app) and run it, writing $2 (default /tmp/catalyst-materials.json)
set -e
APP=${1:-/tmp/probe.app}
OUT=${2:-/tmp/catalyst-materials.json}
HERE=$(cd "$(dirname "$0")" && pwd)
SDK=$(xcrun --sdk macosx --show-sdk-path)
mkdir -p "$APP/Contents/MacOS"
cat > "$APP/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleExecutable</key><string>probe</string>
<key>CFBundleIdentifier</key><string>local.transit.materials-probe</string>
<key>CFBundleName</key><string>probe</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleShortVersionString</key><string>1.0</string>
<key>CFBundleVersion</key><string>1</string>
<key>LSMinimumSystemVersion</key><string>26.0</string>
<key>UIDeviceFamily</key><array><integer>2</integer><integer>6</integer></array>
<key>UIApplicationSceneManifest</key><dict><key>UIApplicationSupportsMultipleScenes</key><false/></dict>
<key>LSBackgroundOnly</key><false/>
<key>NSSupportsAutomaticTermination</key><false/>
</dict></plist>
EOF
clang -fobjc-arc -Wno-arc-performSelector-leaks -target arm64-apple-ios26.0-macabi -isysroot "$SDK" \
  -iframework "$SDK/System/iOSSupport/System/Library/Frameworks" -F "$SDK/System/iOSSupport/System/Library/Frameworks" \
  -framework UIKit -framework Foundation -framework QuartzCore -framework CoreGraphics \
  -o "$APP/Contents/MacOS/probe" "$HERE/main.m"
codesign -s - --force "$APP" >/dev/null 2>&1 || true
"$APP/Contents/MacOS/probe" "$OUT"
