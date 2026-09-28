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
import java.util.concurrent.atomic.AtomicBoolean
import javax.net.ssl.*

private const val TV_IP = "192.168.0.100"
private const val REMOTE_PORT = 6466

private const val BASE_DIR = "/home/dkvlko/live_code/TVAndroidRemote"
private const val CLIENT_KEY_FILE = "$BASE_DIR/mibox_java_remote_key.pem"
private const val CLIENT_CERT_FILE = "$BASE_DIR/mibox_java_remote_cert.pem"
private const val SERVER_HASH_FILE = "$BASE_DIR/mibox_server_cert_sha256.txt"

private const val ACTIVE_CODE = 622

// Keycodes
private const val KEY_VOLUME_MUTE = 164
private const val KEY_HOME = 3
private const val DIRECTION_SHORT = 3

// Keep-alive period: Send benign activity every 4 minutes (before 5m/15m sleep timer)
private const val KEEP_ALIVE_INTERVAL_MS = 240_000L

fun main(args: Array<String>) {
    println("==============================================")
    println(" Mi Box 4 Persistent Keep-Alive Daemon")
    println("==============================================")
    println("Target   : $TV_IP:$REMOTE_PORT")
    println("Strategy : Display off via PC -> Heartbeat -> Display on")
    println()

    val running = AtomicBoolean(true)

    // Handle Ctrl+C cleanly
    Runtime.getRuntime().addShutdownHook(Thread {
        println("\n[SHUTDOWN] Exiting keep-alive manager...")
        running.set(false)
        setTvDisplayState(true) // Ensure display is left ON
    })

    while (running.get()) {
        try {
            runKeepAliveSession(running)
        } catch (e: Exception) {
            println("[SESSION] Disconnected: ${e.message}. Reconnecting in 5s...")
            Thread.sleep(5000L)
        }
    }
}

private fun runKeepAliveSession(running: AtomicBoolean) {
    withRemoteConnection { input, output, socket ->
        val writeLock = Any()
        val stopSession = AtomicBoolean(false)

        // 1. Thread to respond to Mi Box protobuf pings (field 8)
        val pingThread = Thread({
            try {
                while (!stopSession.get()) {
                    val message = readMessage(input)
                    if (firstFieldNumber(message) == 8) {
                        val ping = getFieldPayload(message, 8)
                        val value = extractFirstInt32Field(ping, 1)
                        synchronized(writeLock) {
                            writeMessage(output, buildPingResponse(value))
                        }
                    }
                }
            } catch (e: Exception) {
                if (!stopSession.get()) {
                    println("[PING] Read ended: ${e.message}")
                    stopSession.set(true)
                }
            }
        }, "MiBox-Ping-Responder").apply { isDaemon = true; start() }

        println("[1] Connection established and active.")

        // 2. Demonstration: Put TV display to sleep without touching Mi Box power state
        println("[2] Turning off TV display via PC HDMI-1-1 (Mi Box remains awake in background)...")
        setTvDisplayState(false)

        var lastKeepAlive = System.currentTimeMillis()
        val testDuration = System.currentTimeMillis() + 30_000L // Run for 30s demonstration

        // 3. Heartbeat loop: Keeps userActivity refreshed
        while (running.get() && !stopSession.get() && System.currentTimeMillis() < testDuration) {
            val now = System.currentTimeMillis()
            if (now - lastKeepAlive >= KEEP_ALIVE_INTERVAL_MS) {
                println("[HEARTBEAT] Refreshing userActivity timer (MUTE toggle)...")
                synchronized(writeLock) {
                    sendKey(output, KEY_VOLUME_MUTE)
                    Thread.sleep(80)
                    sendKey(output, KEY_VOLUME_MUTE)
                }
                lastKeepAlive = now
            }
            Thread.sleep(200)
        }

        // 4. Demonstration: Wake the TV back up and assert focus
        println()
        println("[3] 30 seconds elapsed. Waking TV display via HDMI-1-1...")
        setTvDisplayState(true)

        println("[4] Sending KEY_HOME to ensure Leanback Launcher is rendered...")
        synchronized(writeLock) {
            sendKey(output, KEY_HOME)
        }
        println("[SUCCESS] Mi Box remained active throughout, screen is on, and connection is ready.")

        stopSession.set(true)
        pingThread.interrupt()
    }
}

/**
 * Controls TV panel standby state via your verified Ubuntu HDMI-1-1 port
 */
private fun setTvDisplayState(turnOn: Boolean) {
    val cmd = if (turnOn) {
        listOf("bash", "-c", "xset dpms force on && xrandr --output HDMI-1-1 --auto")
    } else {
        listOf("bash", "-c", "xrandr --output HDMI-1-1 --off")
    }

    try {
        val process = ProcessBuilder(cmd).redirectErrorStream(true).start()
        process.waitFor()
    } catch (e: Exception) {
        System.err.println("[DISPLAY] Failed to toggle HDMI-1-1: ${e.message}")
    }
}

// ------------------------------------------------------------
// TLS Socket Connection & Remote Protocol
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
        socket.soTimeout = 15_000
        socket.connect(InetSocketAddress(TV_IP, REMOTE_PORT), 5_000)
        socket.startHandshake()

        val serverCertificate = socket.session.peerCertificates[0] as X509Certificate
        val actualHash = sha256Certificate(serverCertificate)

        require(actualHash.equals(expectedServerHash, ignoreCase = true)) {
            "Server certificate SHA-256 does not match pinned certificate."
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

// ------------------------------------------------------------
// Protobuf framing helpers
// ------------------------------------------------------------

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
    require(length <= 65_536) { "Remote frame exceeds size limit: $length bytes" }
    val result = ByteArray(length.toInt())
    var offset = 0
    while (offset < result.size) {
        val n = input.read(result, offset, result.size - offset)
        if (n < 0) throw EOFException("Mi Box closed the connection.")
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
        if (b < 0) throw EOFException("End of stream reading varint.")
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

// ------------------------------------------------------------
// Key and Certificate loaders
// ------------------------------------------------------------

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
        if (chain.isEmpty()) throw CertificateException("No certificate received from Mi Box.")
        val actual = sha256Certificate(chain[0])
        if (!actual.equals(expectedHash, ignoreCase = true)) {
            throw CertificateException("Server SHA-256 mismatch.")
        }
    }
    override fun getAcceptedIssuers(): Array<X509Certificate> = emptyArray()
}
