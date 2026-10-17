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

// Keycodes
private const val KEY_POWER = 26
private const val KEY_WAKEUP = 224
private const val DIRECTION_SHORT = 3

fun main(args: Array<String>) {
    println("==============================================")
    println(" Mi Box 4 HDMI-Wake + Power Test")
    println("==============================================")
    println("Target   : $TV_IP:$REMOTE_PORT")
    println("Sequence : Standby -> Wait 15s -> HDMI Wake -> Remote Reconnect")
    println()

    try {
        runFullPowerCycleTest()
    } catch (e: Exception) {
        System.err.println("Fatal Error: ${e.message}")
        e.printStackTrace()
    }
}

/**
 * Executes the verified HDMI-1-1 clock toggle directly on Ubuntu
 */
fun wakeTvViaHdmiClock(): Boolean {
    println("[HDMI] Pulsing HDMI-1-1 output to wake TV panel...")
    val cmd = listOf(
        "bash", "-c",
        "xset dpms force on && xrandr --output HDMI-1-1 --off && sleep 1 && xrandr --output HDMI-1-1 --auto"
    )
    return try {
        val process = ProcessBuilder(cmd)
            .redirectErrorStream(true)
            .start()
        val exitCode = process.waitFor()
        if (exitCode == 0) {
            println("[HDMI] TMDS clock cycle completed successfully.")
            true
        } else {
            System.err.println("[HDMI] Command returned exit code: $exitCode")
            false
        }
    } catch (e: Exception) {
        System.err.println("[HDMI] Failed to execute xrandr toggle: ${e.message}")
        false
    }
}

private fun runFullPowerCycleTest() {
    println("[1] Connecting to Mi Box...")
    withRemoteConnection { input, output, _ ->
        val stopReceiver = java.util.concurrent.atomic.AtomicBoolean(false)
        val writeLock = Any()

        val pingReceiver = Thread({
            try {
                while (!stopReceiver.get()) {
                    val message = readMessage(input)
                    if (firstFieldNumber(message) == 8) {
                        val ping = getFieldPayload(message, 8)
                        val value = extractFirstInt32Field(ping, 1)
                        synchronized(writeLock) {
                            writeMessage(output, buildPingResponse(value))
                        }
                    }
                }
            } catch (_: Exception) {}
        }, "MiBox-Ping-Responder").apply { isDaemon = true; start() }

        println("[2] Dispatching KEY_POWER (26) to enter standby...")
        synchronized(writeLock) {
            sendKey(output, KEY_POWER)
        }

        println("[3] Power command sent. Closing initial socket gracefully.")
        stopReceiver.set(true)
        pingReceiver.interrupt()
    }

    println()
    println("[4] Waiting 15 seconds while Mi Box settles in standby...")
    Thread.sleep(15_000L)

    println()
    println("[5] Triggering HDMI wake via verified HDMI-1-1 output...")
    wakeTvViaHdmiClock()

    println("[6] Allowing 4 seconds for TV to boot and send HDMI-CEC wake packet to Mi Box...")
    Thread.sleep(4000L)

    println("[7] Attempting to reconnect to Mi Box on port $REMOTE_PORT...")
    var reconnected = false
    val deadline = System.currentTimeMillis() + 12_000L

    while (!reconnected && System.currentTimeMillis() < deadline) {
        try {
            withRemoteConnection { _, output, _ ->
            println("[8] Connected to Mi Box! Sending interactive wake burst (WAKEUP -> HOME -> DPAD_CENTER)...")

            // 1. Wake power manager
            sendKey(output, KEY_WAKEUP)
            Thread.sleep(150)

            // 2. KEY_HOME (3) triggers Android TV HdmiControlService to assert <Active Source>
            sendKey(output, 3) 
            Thread.sleep(200)

            // 3. DPAD_CENTER (23) dismisses screensaver/ambient mode
            sendKey(output, 23)
            Thread.sleep(200)

            // 4. Send HOME once more to ensure launcher is rendered
            sendKey(output, 3)
            Thread.sleep(300)
                reconnected = true
                println("[SUCCESS] Mi Box is awake and responding to commands.")
            }
        } catch (e: Exception) {
            print(".")
            Thread.sleep(1000L)
        }
    }

    if (!reconnected) {
        println("\n[FAIL] Port $REMOTE_PORT not responding. Verify TV HDMI-CEC 'Auto Power On' is enabled.")
    }
}

// ------------------------------------------------------------
// Networking, TLS, and Protobuf Framing
// ------------------------------------------------------------

private fun withRemoteConnection(action: (InputStream, OutputStream, SSLSocket) -> Unit) {
    val privateKey = loadPrivateKey(CLIENT_KEY_FILE)
    val clientCertificate = loadCertificate(CLIENT_CERT_FILE)

    val expectedServerHash = Files.readString(
        Path.of(SERVER_HASH_FILE),
        StandardCharsets.UTF_8
    ).trim().replace("\\s+".toRegex(), "").lowercase(Locale.ROOT)

    val keyStore = KeyStore.getInstance(KeyStore.getDefaultType()).apply {
        load(null, null)
        setKeyEntry("mibox-client", privateKey, CharArray(0), arrayOf<Certificate>(clientCertificate))
    }

    val kmf = KeyManagerFactory.getInstance(KeyManagerFactory.getDefaultAlgorithm()).apply {
        init(keyStore, CharArray(0))
    }

    val sslContext = SSLContext.getInstance("TLS").apply {
        init(kmf.keyManagers, arrayOf<TrustManager>(MiBoxTrustManager(expectedServerHash)), SecureRandom())
    }

    val socket = sslContext.socketFactory.createSocket() as SSLSocket

    try {
        socket.soTimeout = 8_000
        socket.connect(InetSocketAddress(TV_IP, REMOTE_PORT), 5_000)
        socket.startHandshake()

        val serverCertificate = socket.session.peerCertificates[0] as X509Certificate
        val actualHash = sha256Certificate(serverCertificate)

        require(actualHash.equals(expectedServerHash, ignoreCase = true)) {
            "Server certificate mismatch"
        }

        val input = socket.inputStream
        val output = socket.outputStream

        performRemoteHandshake(input, output)
        action(input, output, socket)
    } finally {
        try { socket.close() } catch (_: Exception) {}
    }
}

private fun performRemoteHandshake(input: InputStream, output: OutputStream) {
    var configured = false
    while (!configured) {
        val message = readMessage(input)
        when (firstFieldNumber(message)) {
            1 -> {
                writeMessage(output, buildRemoteConfigure())
                configured = true
            }
            8 -> {
                val ping = getFieldPayload(message, 8)
                val value = extractFirstInt32Field(ping, 1)
                writeMessage(output, buildPingResponse(value))
            }
        }
    }

    while (true) {
        val message = readMessage(input)
        when (firstFieldNumber(message)) {
            2 -> return
            8 -> {
                val ping = getFieldPayload(message, 8)
                val value = extractFirstInt32Field(ping, 1)
                writeMessage(output, buildPingResponse(value))
            }
        }
    }
}

private fun sendKey(output: OutputStream, keyCode: Int) {
    writeMessage(output, buildRemoteKeyInject(keyCode, DIRECTION_SHORT))
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

private fun buildRemoteKeyInject(keyCode: Int, direction: Int): ByteArray {
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

private fun writeMessageField(out: OutputStream, fieldNumber: Int, value: ByteArray) {
    writeTag(out, fieldNumber, 2)
    writeVarint(out, value.size.toLong())
    out.write(value)
}

private fun writeStringField(out: OutputStream, fieldNumber: Int, value: String) {
    writeMessageField(out, fieldNumber, value.toByteArray(StandardCharsets.UTF_8))
}

private fun writeInt32Field(out: OutputStream, fieldNumber: Int, value: Int) {
    writeTag(out, fieldNumber, 0)
    writeVarint(out, value.toLong())
}

private fun writeTag(out: OutputStream, fieldNumber: Int, wireType: Int) {
    writeVarint(out, ((fieldNumber shl 3) or wireType).toLong())
}

private fun writeVarint(out: OutputStream, value: Long) {
    var v = value
    while ((v and 0x7FL.inv()) != 0L) {
        out.write(((v and 0x7F) or 0x80).toInt())
        v = v ushr 7
    }
    out.write(v.toInt())
}

private fun readMessage(input: InputStream): ByteArray {
    val length = readVarint(input)
    require(length <= 65_536) { "Frame too large: $length bytes" }
    val result = ByteArray(length.toInt())
    var offset = 0
    while (offset < result.size) {
        val n = input.read(result, offset, result.size - offset)
        if (n < 0) throw EOFException("Remote connection closed.")
        offset += n
    }
    return result
}

private fun writeMessage(output: OutputStream, message: ByteArray) {
    writeVarint(output, message.size.toLong())
    output.write(message)
    output.flush()
}

private fun readVarint(input: InputStream): Long {
    var result = 0L
    var shift = 0
    while (shift < 64) {
        val b = input.read()
        if (b < 0) throw EOFException("End of stream.")
        result = result or ((b.toLong() and 0x7F) shl shift)
        if ((b and 0x80) == 0) return result
        shift += 7
    }
    throw IOException("Invalid varint.")
}

private fun firstFieldNumber(message: ByteArray): Int {
    val input = ByteArrayInputStream(message)
    val tag = readVarint(input)
    return (tag ushr 3).toInt()
}

private fun getFieldPayload(message: ByteArray, wantedField: Int): ByteArray? {
    val input = ByteArrayInputStream(message)
    while (input.available() > 0) {
        val tag = readVarint(input)
        val fieldNumber = (tag ushr 3).toInt()
        val wireType = (tag and 7).toInt()
        when (wireType) {
            0 -> readVarint(input)
            2 -> {
                val length = readVarint(input).toInt()
                val payload = input.readNBytes(length)
                if (fieldNumber == wantedField) return payload
            }
            else -> throw IOException("Unsupported wire type: $wireType")
        }
    }
    return null
}

private fun extractFirstInt32Field(message: ByteArray?, wantedField: Int): Int {
    if (message == null) return 1
    val input = ByteArrayInputStream(message)
    while (input.available() > 0) {
        val tag = readVarint(input)
        val fieldNumber = (tag ushr 3).toInt()
        val wireType = (tag and 7).toInt()
        when (wireType) {
            0 -> {
                val value = readVarint(input)
                if (fieldNumber == wantedField) return value.toInt()
            }
            2 -> {
                val length = readVarint(input).toInt()
                input.skipNBytes(length.toLong())
            }
            else -> throw IOException("Unsupported wire type: $wireType")
        }
    }
    return 1
}

private fun loadPrivateKey(filename: String): PrivateKey {
    val pem = Files.readString(Path.of(filename), StandardCharsets.US_ASCII)
        .replace("-----BEGIN PRIVATE KEY-----", "")
        .replace("-----END PRIVATE KEY-----", "")
        .replace("\\s+".toRegex(), "")
    val der = Base64.getDecoder().decode(pem)
    return KeyFactory.getInstance("RSA").generatePrivate(PKCS8EncodedKeySpec(der))
}

private fun loadCertificate(filename: String): X509Certificate {
    Files.newInputStream(Path.of(filename)).use { input ->
        return CertificateFactory.getInstance("X.509").generateCertificate(input) as X509Certificate
    }
}

private fun sha256Certificate(certificate: X509Certificate): String {
    val digest = MessageDigest.getInstance("SHA-256").digest(certificate.encoded)
    return digest.joinToString("") { "%02x".format(it.toInt() and 0xFF) }
}

private class MiBoxTrustManager(private val expectedHash: String) : X509TrustManager {
    override fun checkClientTrusted(chain: Array<X509Certificate>, authType: String) {}
    override fun checkServerTrusted(chain: Array<X509Certificate>, authType: String) {
        if (chain.isEmpty()) throw CertificateException("Empty server certificate chain.")
        val actual = sha256Certificate(chain[0])
        if (!actual.equals(expectedHash, ignoreCase = true)) {
            throw CertificateException("Server SHA-256 mismatch.")
        }
    }
    override fun getAcceptedIssuers(): Array<X509Certificate> = emptyArray()
}
