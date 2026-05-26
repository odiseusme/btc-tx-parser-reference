import org.ergoplatform.appkit.{AppkitHelpers, NetworkType}
import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers

import java.nio.charset.StandardCharsets
import java.nio.file.{Files, Paths}
import java.util.Collections

class BtcErgoContractsSpec extends AnyFlatSpec with Matchers {
  private val CompileCheckedContracts = Seq(
    "btc_txid_verify.ergo",
    "btc_verify_parser.ergo",
    "btc_verify_full.ergo",
    "btc_verify_outputs.ergo"
  )

  "ErgoScript contracts" should "compile with AppKit" in {
    CompileCheckedContracts.foreach { fileName =>
      withClue(fileName) {
        noException should be thrownBy compileContract(fileName)
      }
    }
  }

  private def compileContract(fileName: String): Unit = {
    val source = Files.readString(Paths.get(fileName), StandardCharsets.UTF_8)
    AppkitHelpers.compile(
      Collections.emptyMap[String, Object](),
      source,
      NetworkType.MAINNET.networkPrefix
    )
  }
}
