import java.io.*
import java.net.InetSocketAddress
import java.nio.charset.StandardCharsets
import java.nio.file.Files
import java.nio.file.Path
import java.security.*
import java.security.cert.Certificate
import java.security.cert.CertificateException
import java.security.cert.CertificateFactory
import java.security.cert.X509Certificate
import java.security.spec.PKCS8EncodedKeySpec
import java.util.Base64
import java.util.Locale
import javax.net.ssl.*

private const val TV_IP = "192.168.0.100"
private const val REMOTE_PORT = 6466

private const val BASE_DIR = "/home/dkvlko/live_code/TVAndroidRemote"
private const val CLIENT_KEY_FILE = "$BASE_DIR/mibox_java_remote_key.pem"
private const val CLIENT_CERT_FILE = "$BASE_DIR/mibox_java_remote_cert.pem"
private const val SERVER_HASH_FILE = "$BASE_DIR/mibox_server_cert_sha256.txt"

private const val ACTIVE_CODE = 622

// Android TV Remote v2
private const val KEY_POWER = 26
private const val KEY_SLEEP = 223
private const val KEY_WAKEUP = 224

// RemoteDirection.SHORT
private const val DIRECTION_SHORT = 3

fun main(args: Array<String>) {
    if (args.isEmpty()) {
        usage()
        return
    }

    try {
        when (args[0].lowercase(Locale.ROOT)) {
            "connect" -> {
                println("Testing TLS + Android TV Remote v2 connection...")
                withRemoteConnection { _, _, _ ->
                    println("Connection and handshake successful.")
                }
            }

            "sleep" -> {
                println("Sending KEYCODE_SLEEP = $KEY_SLEEP")
                withRemoteConnection { input, output, _ ->
                    sendKey(output, KEY_SLEEP)
                    println("SLEEP command sent.")
                    servicePings(input, output, 300)
                }
            }

            "wake" -> {
                println("Sending KEYCODE_WAKEUP = $KEY_WAKEUP")
                withRemoteConnection { input, output, _ ->
                    sendKey(output, KEY_WAKEUP)
                    println("WAKEUP command sent.")
                    servicePings(input, output, 1000)
                }
            }

            "power" -> {
                println("Sending KEYCODE_POWER = $KEY_POWER")
                withRemoteConnection { input, output, _ ->
                    sendKey(output, KEY_POWER)
                    println("POWER command sent.")
                    servicePings(input, output, 300)
                }
            }

            "test" -> {
                runSleepWakeTest()
            }

            else -> usage()
        }
    } catch (e: Exception) {
        System.err.println()
        System.err.println("ERROR: ${e.message}")
        e.printStackTrace()
        kotlin.system.exitProcess(1)
    }
}

private fun usage() {
    println(
        """
        Usage:
          kotlin MiBoxWakeTestKt connect
          kotlin MiBoxWakeTestKt sleep
          kotlin MiBoxWakeTestKt wake
          kotlin MiBoxWakeTestKt power
          kotlin MiBoxWakeTestKt test

        test sequence:
          1. Connect
          2. Send KEYCODE_SLEEP (223)
          3. Wait 10 seconds
          4. Make a NEW connection
          5. Send KEYCODE_WAKEUP (224)
        """.trimIndent()
    )
}

private fun runSleepWakeTest() {
    println()
    println("========================================")
    println(" Mi Box Android TV Remote v2 Wake Test")
    println("========================================")
    println("TV       : $TV_IP")
    println("Port     : $REMOTE_PORT")
    println()

    println("[1] Connecting...")
    withRemoteConnection { input, output, _ ->
        sendKey(output, KEY_SLEEP)
        println("[2] KEYCODE_SLEEP (223) sent.")
        servicePings(input, output, 500)
    }

    println()
    println("[3] Remote connection closed.")
    println("[4] Waiting 10 seconds for standby...")
    Thread.sleep(10_000)

    println()
    println("[5] Creating a NEW TLS connection...")
    println("    If the Mi Box has disabled the remote port in standby,")
    println("    this step may fail. That result is useful.")
    println()

    withRemoteConnection { input, output, _ ->
        println("[6] New connection + handshake successful.")
        sendKey(output, KEY_WAKEUP)
        println("[7] KEYCODE_WAKEUP (224) sent.")
        servicePings(input, output, 1500)
    }

    println()
    println("Wake test completed.")
}

private fun withRemoteConnection(
    action: (InputStream, OutputStream, SSLSocket) -> Unit
) {
    val privateKey = loadPrivateKey(CLIENT_KEY_FILE)
    val clientCertificate = loadCertificate(CLIENT_CERT_FILE)

    val expectedServerHash = Files.readString(
        Path.of(SERVER_HASH_FILE),
        StandardCharsets.UTF_8
    ).trim().replace("\\s+".toRegex(), "").lowercase(Locale.ROOT)

    println("Expected server SHA-256:")
    println(expectedServerHash)

    val keyStore = KeyStore.getInstance(KeyStore.getDefaultType())
    keyStore.load(null, null)
    keyStore.setKeyEntry(
        "mibox-client",
        privateKey,
        CharArray(0),
        arrayOf<Certificate>(clientCertificate)
    )

    val kmf = KeyManagerFactory.getInstance(
        KeyManagerFactory.getDefaultAlgorithm()
    )
    kmf.init(keyStore, CharArray(0))

    val sslContext = SSLContext.getInstance("TLS")
    sslContext.init(
        kmf.keyManagers,
        arrayOf<TrustManager>(MiBoxTrustManager(expectedServerHash)),
        SecureRandom()
    )

    val factory = sslContext.socketFactory

    println("Connecting to $TV_IP:$REMOTE_PORT ...")

    val socket = factory.createSocket() as SSLSocket

    try {
        socket.soTimeout = 10_000
        socket.connect(InetSocketAddress(TV_IP, REMOTE_PORT), 8_000)

        println("TCP connection established.")
        socket.startHandshake()

        val serverCertificate =
            socket.session.peerCertificates[0] as X509Certificate

        val actualHash = sha256Certificate(serverCertificate)

        println("Server certificate SHA-256:")
        println(actualHash)

        require(actualHash.equals(expectedServerHash, ignoreCase = true)) {
            "Server certificate hash does not match the paired certificate."
        }

        println("TLS certificate pin verified.")

        val input = socket.inputStream
        val output = socket.outputStream

        performRemoteHandshake(input, output)

        println("Remote connection is ACTIVE.")

        action(input, output, socket)
    } finally {
        try {
            socket.close()
        } catch (_: Exception) {
        }
    }
}

private fun performRemoteHandshake(input: InputStream, output: OutputStream) {
    println()
    println("Waiting for Mi Box RemoteConfigure...")

    while (true) {
        val message = readMessage(input)
        val field = firstFieldNumber(message)

        when (field) {
            1 -> {
                println("RemoteConfigure received.")
                writeMessage(output, buildRemoteConfigure())
                println("RemoteConfigure sent.")
                break
            }

            8 -> {
                println("RemotePingRequest received.")
                val ping = getFieldPayload(message, 8)
                val value = extractFirstInt32Field(ping, 1)
                writeMessage(output, buildPingResponse(value))
                println("RemotePingResponse sent.")
            }

            else -> {
                println("Received RemoteMessage field $field")
            }
        }
    }

    println("Waiting for RemoteSetActive...")

    while (true) {
        val message = readMessage(input)
        val field = firstFieldNumber(message)

        when (field) {
            2 -> {
                println("RemoteSetActive received.")
                return
            }

            8 -> {
                println("RemotePingRequest received.")
                val ping = getFieldPayload(message, 8)
                val value = extractFirstInt32Field(ping, 1)
                writeMessage(output, buildPingResponse(value))
                println("RemotePingResponse sent.")
            }

            else -> {
                println("Received RemoteMessage field $field")
            }
        }
    }
}

private fun sendKey(output: OutputStream, keyCode: Int) {
    writeMessage(
        output,
        buildRemoteKeyInject(keyCode, DIRECTION_SHORT)
    )
}

private fun servicePings(
    input: InputStream,
    output: OutputStream,
    milliseconds: Long
) {
    val oldTimeout = (input as? FilterInputStream)?.let { null }
    // The socket already has a 10-second timeout. We deliberately do not
    // wait for incoming data here; the short delay gives the TV time to
    // consume the key command before the TLS connection is closed.
    Thread.sleep(milliseconds)
}

private fun buildRemoteConfigure(): ByteArray {
    val deviceInfo = ByteArrayOutputStream()

    writeStringField(deviceInfo, 1, "KotlinRemote")
    writeStringField(deviceInfo, 2, "KotlinRemote")
    writeInt32Field(deviceInfo, 3, 1)
    writeStringField(deviceInfo, 4, "1")
    writeStringField(deviceInfo, 5, "atvremote")
    writeStringField(deviceInfo, 6, "1.0.0")

    val configure = ByteArrayOutputStream()
    writeInt32Field(configure, 1, ACTIVE_CODE)
    writeMessageField(configure, 2, deviceInfo.toByteArray())

    val message = ByteArrayOutputStream()
    writeMessageField(message, 1, configure.toByteArray())

    return message.toByteArray()
}

private fun buildRemoteKeyInject(
    keyCode: Int,
    direction: Int
): ByteArray {
    val keyInject = ByteArrayOutputStream()

    writeInt32Field(keyInject, 1, keyCode)
    writeInt32Field(keyInject, 2, direction)

    val message = ByteArrayOutputStream()
    writeMessageField(message, 10, keyInject.toByteArray())

    return message.toByteArray()
}

private fun buildPingResponse(value: Int): ByteArray {
    val ping = ByteArrayOutputStream()
    writeInt32Field(ping, 1, value)

    val message = ByteArrayOutputStream()
    writeMessageField(message, 9, ping.toByteArray())

    return message.toByteArray()
}

// ------------------------------------------------------------
// Protobuf encoding
// ------------------------------------------------------------

private fun writeMessageField(
    out: OutputStream,
    fieldNumber: Int,
    value: ByteArray
) {
    writeTag(out, fieldNumber, 2)
    writeVarint(out, value.size.toLong())
    out.write(value)
}

private fun writeStringField(
    out: OutputStream,
    fieldNumber: Int,
    value: String
) {
    writeMessageField(
        out,
        fieldNumber,
        value.toByteArray(StandardCharsets.UTF_8)
    )
}

private fun writeInt32Field(
    out: OutputStream,
    fieldNumber: Int,
    value: Int
) {
    writeTag(out, fieldNumber, 0)
    writeVarint(out, value.toLong())
}

private fun writeTag(
    out: OutputStream,
    fieldNumber: Int,
    wireType: Int
) {
    writeVarint(out, ((fieldNumber shl 3) or wireType).toLong())
}

private fun writeVarint(
    out: OutputStream,
    value: Long
) {
    var v = value

    while ((v and 0x7FL.inv()) != 0L) {
        out.write(((v and 0x7F) or 0x80).toInt())
        v = v ushr 7
    }

    out.write(v.toInt())
}

// ------------------------------------------------------------
// Android TV Remote v2 length-delimited framing
// ------------------------------------------------------------

private fun readMessage(input: InputStream): ByteArray {
    val length = readVarint(input)

    require(length <= 65_536) {
        "Remote frame is too large: $length bytes"
    }

    val result = ByteArray(length.toInt())
    var offset = 0

    while (offset < result.size) {
        val n = input.read(result, offset, result.size - offset)
        if (n < 0) {
            throw EOFException("Mi Box closed the remote connection.")
        }
        offset += n
    }

    return result
}

private fun writeMessage(
    output: OutputStream,
    message: ByteArray
) {
    writeVarint(output, message.size.toLong())
    output.write(message)
    output.flush()
}

private fun readVarint(input: InputStream): Long {
    var result = 0L
    var shift = 0

    while (shift < 64) {
        val b = input.read()

        if (b < 0) {
            throw EOFException("Unexpected end of stream while reading varint.")
        }

        result = result or ((b.toLong() and 0x7F) shl shift)

        if ((b and 0x80) == 0) {
            return result
        }

        shift += 7
    }

    throw IOException("Invalid protobuf varint.")
}

private fun firstFieldNumber(message: ByteArray): Int {
    val input = ByteArrayInputStream(message)
    val tag = readVarint(input)
    return (tag ushr 3).toInt()
}

private fun getFieldPayload(
    message: ByteArray,
    wantedField: Int
): ByteArray? {
    val input = ByteArrayInputStream(message)

    while (input.available() > 0) {
        val tag = readVarint(input)
        val fieldNumber = (tag ushr 3).toInt()
        val wireType = (tag and 7).toInt()

        when (wireType) {
            0 -> {
                readVarint(input)
            }

            2 -> {
                val length = readVarint(input).toInt()
                val payload = input.readNBytes(length)

                if (fieldNumber == wantedField) {
                    return payload
                }
            }

            else -> throw IOException(
                "Unsupported protobuf wire type: $wireType"
            )
        }
    }

    return null
}

private fun extractFirstInt32Field(
    message: ByteArray?,
    wantedField: Int
): Int {
    if (message == null) return 1

    val input = ByteArrayInputStream(message)

    while (input.available() > 0) {
        val tag = readVarint(input)
        val fieldNumber = (tag ushr 3).toInt()
        val wireType = (tag and 7).toInt()

        when (wireType) {
            0 -> {
                val value = readVarint(input)
                if (fieldNumber == wantedField) {
                    return value.toInt()
                }
            }

            2 -> {
                val length = readVarint(input).toInt()
                input.skipNBytes(length.toLong())
            }

            else -> throw IOException(
                "Unsupported protobuf wire type: $wireType"
            )
        }
    }

    return 1
}

// ------------------------------------------------------------
// Key and certificate loading
// ------------------------------------------------------------

private fun loadPrivateKey(filename: String): PrivateKey {
    var pem = Files.readString(
        Path.of(filename),
        StandardCharsets.US_ASCII
    )

    pem = pem
        .replace("-----BEGIN PRIVATE KEY-----", "")
        .replace("-----END PRIVATE KEY-----", "")
        .replace("\\s+".toRegex(), "")

    val der = Base64.getDecoder().decode(pem)
    val spec = PKCS8EncodedKeySpec(der)

    return KeyFactory.getInstance("RSA").generatePrivate(spec)
}

private fun loadCertificate(filename: String): X509Certificate {
    Files.newInputStream(Path.of(filename)).use { input ->
        val factory = CertificateFactory.getInstance("X.509")
        return factory.generateCertificate(input) as X509Certificate
    }
}

private fun sha256Certificate(
    certificate: X509Certificate
): String {
    val digest = MessageDigest.getInstance("SHA-256")
        .digest(certificate.encoded)

    return digest.joinToString("") {
        "%02x".format(it.toInt() and 0xFF)
    }
}

// ------------------------------------------------------------
// Certificate pinning trust manager
// ------------------------------------------------------------

private class MiBoxTrustManager(
    private val expectedHash: String
) : X509TrustManager {

    override fun checkClientTrusted(
        chain: Array<X509Certificate>,
        authType: String
    ) {
    }

    override fun checkServerTrusted(
        chain: Array<X509Certificate>,
        authType: String
    ) {
        if (chain.isEmpty()) {
            throw CertificateException(
                "Mi Box did not provide a server certificate."
            )
        }

        val actual = sha256Certificate(chain[0])

        if (!actual.equals(expectedHash, ignoreCase = true)) {
            throw CertificateException(
                "Mi Box certificate SHA-256 does not match.\n" +
                    "Expected: $expectedHash\n" +
                    "Actual:   $actual"
            )
        }
    }

    override fun getAcceptedIssuers(): Array<X509Certificate> =
        emptyArray()
}
