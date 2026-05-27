ThisBuild / scalaVersion := "2.13.16"

Test / parallelExecution := false

libraryDependencies ++= Seq(
  // AppKit 5.0.3 resolves fully from Maven Central for reproducible CI.
  "org.ergoplatform" %% "ergo-appkit" % "5.0.3" % Test,
  "org.scalatest" %% "scalatest" % "3.2.19" % Test
)
