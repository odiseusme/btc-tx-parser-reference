import org.ergoplatform.appkit.{AppkitHelpers, NetworkType}
import org.ergoplatform.validation.ValidationRules
import org.ergoplatform.{ErgoBox, ErgoLikeContext, ErgoLikeInterpreter, ErgoLikeTransaction, Input}
import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers
import sigmastate.eval.{CPreHeader, CostingSigmaDslBuilder, Colls}
import sigmastate.interpreter.{ContextExtension, ProverResult}
import sigmastate.{AvlTreeData, SType, TrivialProp}
import sigmastate.Values.{ByteArrayConstant, ErgoTree, EvaluatedValue, LongConstant}
import scorex.util.bytesToId
import special.collection.Coll
import special.sigma.{Header, HeaderRType}

import java.nio.charset.StandardCharsets
import java.nio.file.{Files, Path, Paths}
import java.util.Collections
import scala.jdk.CollectionConverters._
import scala.util.Try

/**
 * Cross-implementation conformance harness.
 *
 * Unlike BtcErgoContractsSpec (which only proves the contracts COMPILE), this
 * spec EXECUTES the two parser contracts against every public test vector by
 * performing a full sigma reduction of the compiled ErgoTree inside a real
 * ErgoLikeContext. A valid vector must reduce to TrivialProp.TrueProp; an
 * invalid vector must reduce to FalseProp or throw during evaluation (several
 * invalid vectors deliberately drive out-of-bounds reads).
 */
class BtcVectorEvaluationSpec extends AnyFlatSpec with Matchers {

  private val VectorsRoot = Paths.get("test-vectors")

  private def discoverVectors(category: String): Seq[Path] = {
    val dir = VectorsRoot.resolve(category)
    val stream = Files.walk(dir)
    try {
      stream
        .iterator()
        .asScala
        .filter(p => Files.isRegularFile(p) && p.getFileName.toString.endsWith(".proof.json"))
        .toVector
        .sortBy(_.toString)
    } finally stream.close()
  }

  private def hexToBytes(hex: String): Array[Byte] = {
    require(hex.length % 2 == 0, s"odd-length hex: $hex")
    hex.grouped(2).map(h => Integer.parseInt(h, 16).toByte).toArray
  }

  /** Wrap a raw byte array as the sigma runtime Coll[Byte] type. */
  private def bytesColl(bytes: Array[Byte]): Coll[Byte] =
    ByteArrayConstant(bytes).value.asInstanceOf[Coll[Byte]]

  private def compileContract(contractName: String): ErgoTree = {
    val source = Files.readString(Paths.get(s"$contractName.ergo"), StandardCharsets.UTF_8)
    AppkitHelpers.compile(
      Collections.emptyMap[String, Object](),
      source,
      NetworkType.MAINNET.networkPrefix
    )
  }

  /**
   * Reduce `contractName` against the registers + context var 1 from a vector.
   * Returns true iff the script reduces to the trivially-true sigma proposition.
   * Any evaluation exception (e.g. an out-of-bounds parser read on malformed
   * input) propagates to the caller, which treats it as rejection.
   */
  private def evaluate(
      contractName: String,
      r4: Array[Byte],
      r5: Array[Byte],
      r6: Option[Long],
      txBytes: Array[Byte]
  ): Boolean = {
    val tree = compileContract(contractName)

    var registers = Map[ErgoBox.NonMandatoryRegisterId, EvaluatedValue[_ <: SType]](
      ErgoBox.R4 -> ByteArrayConstant(r4),
      ErgoBox.R5 -> ByteArrayConstant(r5)
    )
    r6.foreach(v => registers += (ErgoBox.R6 -> LongConstant(v)))

    val self = new ErgoBox(
      value = 1000000L,
      ergoTree = tree,
      additionalRegisters = registers,
      transactionId = bytesToId(Array.fill[Byte](32)(0)),
      index = 0.toShort,
      creationHeight = 0
    )

    val extension = ContextExtension(
      Map(1.toByte -> (ByteArrayConstant(txBytes): EvaluatedValue[_ <: SType]))
    )

    val spendingTx = ErgoLikeTransaction(
      IndexedSeq(Input(self.id, ProverResult.empty)),
      IndexedSeq(self)
    )

    val preHeader = CPreHeader(
      version = 0.toByte,
      parentId = bytesColl(Array.fill[Byte](32)(0)),
      timestamp = 0L,
      nBits = 0L,
      height = 0,
      minerPk = CostingSigmaDslBuilder.groupGenerator,
      votes = bytesColl(Array.fill[Byte](3)(0))
    )

    val ctx = new ErgoLikeContext(
      lastBlockUtxoRoot = AvlTreeData.dummy,
      headers = Colls.emptyColl[Header](HeaderRType),
      preHeader = preHeader,
      dataBoxes = IndexedSeq.empty,
      boxesToSpend = IndexedSeq(self),
      spendingTransaction = spendingTx,
      selfIndex = 0,
      extension = extension,
      validationSettings = ValidationRules.currentSettings,
      costLimit = 100000000L,
      initCost = 0L,
      activatedScriptVersion = tree.version
    )

    val interpreter = new ErgoLikeInterpreter()
    // CTX is an abstract path-dependent type on the Interpreter trait; for
    // ErgoLikeInterpreter it is ErgoLikeContext (the param erases to
    // InterpreterContext), so this cast is a no-op at runtime.
    interpreter.fullReduction(tree, ctx.asInstanceOf[interpreter.CTX]).value == TrivialProp.TrueProp
  }

  private final case class ProofVector(
      file: Path,
      contract: String,
      r4: Array[Byte],
      r5: Array[Byte],
      r6: Option[Long],
      txBytes: Array[Byte]
  )

  private def parseVector(file: Path): ProofVector = {
    val json = ujson.read(Files.readString(file, StandardCharsets.UTF_8))
    val registers = json("registers")
    ProofVector(
      file = file,
      contract = json("contract").str,
      r4 = hexToBytes(registers("R4").str),
      r5 = hexToBytes(registers("R5").str),
      r6 = registers.obj.get("R6").map(_.num.toLong),
      txBytes = hexToBytes(json("context")("1").str)
    )
  }

  "Valid vectors" should "verify against their declared contract" in {
    val vectors = discoverVectors("valid")
    vectors should not be empty
    vectors.foreach { file =>
      withClue(s"$file: ") {
        val v = parseVector(file)
        val verified = Try(evaluate(v.contract, v.r4, v.r5, v.r6, v.txBytes)).getOrElse(false)
        verified shouldBe true
      }
    }
  }

  "Invalid vectors" should "be rejected by their declared contract" in {
    val vectors = discoverVectors("invalid")
    vectors should not be empty
    vectors.foreach { file =>
      withClue(s"$file: ") {
        val v = parseVector(file)
        // Rejection == reduction to false OR a thrown evaluation exception.
        val verified = Try(evaluate(v.contract, v.r4, v.r5, v.r6, v.txBytes)).getOrElse(false)
        verified shouldBe false
      }
    }
  }

  "Mutation canary" should "fail verification when R5 is corrupted" in {
    val file = VectorsRoot.resolve("valid/rosen-bridge-output1.proof.json")
    val v = parseVector(file)

    // Sanity: the pristine vector must verify, otherwise the canary is meaningless.
    evaluate(v.contract, v.r4, v.r5, v.r6, v.txBytes) shouldBe true

    val corruptedR5 = v.r5.clone()
    corruptedR5(0) = (corruptedR5(0) ^ 0x01).toByte // flip one bit of one byte

    val verified =
      Try(evaluate(v.contract, v.r4, corruptedR5, v.r6, v.txBytes)).getOrElse(false)
    withClue("corrupting R5 must break the script-hash match: ") {
      verified shouldBe false
    }
  }
}
