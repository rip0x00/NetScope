#!/bin/bash
# Manual APK build for the NetScope Android app (new repo lineage).
#
# There is no Gradle build: in the development environment used for
# this project the Gradle daemon cannot run (ADR-002), so the APK
# is assembled with the manual pipeline — kotlinc (embeddable
# compiler jars from the local Maven repository), aapt2 link, d8,
# zipalign, apksigner. Framework APIs only: no AndroidX, no
# third-party dependencies.
#
# Output: dist/NetScope.apk (and a copy in ~/workspace/your_files/).
set -e
P=$HOME/workspace/NetScope/apps/android
JDK=$HOME/workspace/tools/android/jdk
BT=$HOME/workspace/tools/android/sdk/build-tools/35.0.0
AJAR=$HOME/workspace/tools/android/sdk/platforms/android-35/android.jar
M2=$HOME/workspace/tools/m2repo
STDLIB=$M2/org/jetbrains/kotlin/kotlin-stdlib/2.4.10/kotlin-stdlib-2.4.10.jar
KOTLINC_CP="$M2/org/jetbrains/kotlin/kotlin-compiler-embeddable/2.4.10/kotlin-compiler-embeddable-2.4.10.jar:$STDLIB:$M2/org/jetbrains/kotlin/kotlin-reflect/2.4.10/kotlin-reflect-2.4.10.jar:$M2/org/jetbrains/intellij/deps/trove4j/1.0.20200330/trove4j-1.0.20200330.jar:$M2/org/jetbrains/kotlinx/kotlinx-coroutines-core-jvm/1.8.1/kotlinx-coroutines-core-jvm-1.8.1.jar:$M2/org/jetbrains/annotations/13.0/annotations-13.0.jar"
export JAVA_HOME=$JDK
export PATH=$JDK/bin:$PATH
cd "$P"
mkdir -p build dist

echo "=== 1/5 kotlinc ==="
$JDK/bin/java -Xmx2g -cp "$KOTLINC_CP" \
  org.jetbrains.kotlin.cli.jvm.K2JVMCompiler \
  -classpath "$AJAR:$STDLIB" -jvm-target 17 -no-stdlib -no-reflect -nowarn \
  -d build/classes.jar src/*.kt
echo "kotlinc OK"

echo "=== 2/5 aapt2 compile + link ==="
rm -rf build/res.zip build/unsigned.apk
$BT/aapt2 compile --dir res -o build/res.zip
$BT/aapt2 link -o build/unsigned.apk \
  -I "$AJAR" --manifest AndroidManifest.xml \
  --min-sdk-version 26 --target-sdk-version 34 \
  --version-code 1 --version-name 0.4.0 \
  build/res.zip
echo "link OK"

echo "=== 3/5 d8 ==="
rm -rf build/dex && mkdir build/dex
$BT/d8 --min-api 26 --lib "$AJAR" --output build/dex build/classes.jar "$STDLIB"

echo "=== 4/5 package + align ==="
cp build/unsigned.apk build/with-dex.apk
cd build/dex && zip -j "$P/build/with-dex.apk" classes.dex > /dev/null && cd "$P"
$BT/zipalign -f 4 build/with-dex.apk build/aligned.apk

echo "=== 5/5 sign + verify ==="
# Release signing. The keystore and its password file live outside
# this repository (~/workspace/netscope-release-key/, mode 600) and
# must never be committed. apksigner reads the password from the
# file so it never appears on a command line.
KEYDIR=$HOME/workspace/netscope-release-key
if [ ! -f "$KEYDIR/netscope-release.keystore" ]; then
  echo "error: release keystore not found at $KEYDIR/netscope-release.keystore" >&2
  exit 1
fi
$BT/apksigner sign --ks "$KEYDIR/netscope-release.keystore" \
  --ks-pass "file:$KEYDIR/keystore-password.txt" \
  --key-pass "file:$KEYDIR/keystore-password.txt" \
  --out dist/NetScope.apk build/aligned.apk
$BT/apksigner verify --print-certs dist/NetScope.apk
$BT/aapt2 dump badging dist/NetScope.apk | head -5
if [ -d "$HOME/workspace/your_files" ]; then
  cp dist/NetScope.apk "$HOME/workspace/your_files/NetScope.apk"
fi
ls -la dist/NetScope.apk
echo "NETSCOPE_ANDROID_BUILD_DONE"
