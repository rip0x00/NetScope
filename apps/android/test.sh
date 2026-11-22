#!/bin/bash
# JVM unit tests for the Android app's pure logic: statistics
# (Stats.kt), the DNS wire parser (DnsWire.kt), the result models
# (Models.kt), the verdict classifier (Verdict.kt), the
# troubleshooting rules (Rules.kt), the block-marker scan
# (HttpProbe.kt), the socket-error classifier (NetErrors.kt) and
# the route stop-point classification (RouteProbe.kt).
#
# Every logic-layer source is compiled here — including the probes,
# which use only java.* APIs — so the whole layer is type-checked
# on a plain JVM. Only the Android-UI sources (MainActivity.kt,
# Tokens.kt, ChartView.kt, HistoryDb.kt) are excluded; they are
# compiled by build.sh against android.jar. Nothing in the tests
# touches a network.
set -e
P=$HOME/workspace/NetScope/apps/android
JDK=$HOME/workspace/tools/android/jdk
M2=$HOME/workspace/tools/m2repo
STDLIB=$M2/org/jetbrains/kotlin/kotlin-stdlib/2.4.10/kotlin-stdlib-2.4.10.jar
KOTLINC_CP="$M2/org/jetbrains/kotlin/kotlin-compiler-embeddable/2.4.10/kotlin-compiler-embeddable-2.4.10.jar:$STDLIB:$M2/org/jetbrains/kotlin/kotlin-reflect/2.4.10/kotlin-reflect-2.4.10.jar:$M2/org/jetbrains/intellij/deps/trove4j/1.0.20200330/trove4j-1.0.20200330.jar:$M2/org/jetbrains/kotlinx/kotlinx-coroutines-core-jvm/1.8.1/kotlinx-coroutines-core-jvm-1.8.1.jar:$M2/org/jetbrains/annotations/13.0/annotations-13.0.jar"
export JAVA_HOME=$JDK
export PATH=$JDK/bin:$PATH
cd "$P"
mkdir -p build

$JDK/bin/java -Xmx2g -cp "$KOTLINC_CP" \
  org.jetbrains.kotlin.cli.jvm.K2JVMCompiler \
  -classpath "$STDLIB" -jvm-target 17 -no-stdlib -no-reflect -nowarn \
  -d build/test-classes.jar \
  src/Stats.kt src/DnsWire.kt src/Models.kt src/Verdict.kt src/Rules.kt \
  src/NetErrors.kt src/TcpProbe.kt src/DnsProbe.kt src/TlsProbe.kt \
  src/HttpProbe.kt src/RouteProbe.kt src/Checks.kt \
  tests/TestMain.kt

$JDK/bin/java -cp "build/test-classes.jar:$STDLIB" com.netscope.app.TestMainKt
echo "NETSCOPE_JVM_TESTS_DONE"
