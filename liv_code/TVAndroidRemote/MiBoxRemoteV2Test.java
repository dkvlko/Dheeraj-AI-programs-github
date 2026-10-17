import javax.net.ssl.*;
import java.io.*;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.*;
import java.security.cert.Certificate;
import java.security.cert.X509Certificate;
import java.util.HexFormat;
import java.security.spec.PKCS8EncodedKeySpec;

public class MiBoxRemoteV2Test {

    private static final String TARGET_IP = "192.168.0.100";
    private static final int REMOTE_PORT = 6466;

    private static final String TARGET_MAC =
            "ec:fa:5c:c0:f7:1c";

    private static final Path BASE_DIR =
            Path.of("/home/dkvlko/live_code/TVAndroidRemote");

    private static final CERT_FILE = Path.of(
        "/home/dkvlko/live_code/TVAndroidRemote/mibox_java_remote_cert.pem"
    );

    private static final KEY_FILE = Path.of(
        "/home/dkvlko/live_code/TVAndroidRemote/mibox_java_remote_key.pem"
    );

    private static final int POWER = 26;

    // RemoteDirection.SHORT
    private static final int SHORT = 3;

    public static void main(String[] args) throws Exception {

        System.out.println("========================================");
        System.out.println(" Mi Box Android TV Remote v2 test");
        System.out.println("========================================");
        System.out.println("MAC : " + TARGET_MAC);
        System.out.println("IP  : " + TARGET_IP);
        System.out.println("CERT: " + CERT_FILE);
        System.out.println("KEY : " + KEY_FILE);
        System.out.println();

        System.out.println("Connecting to Remote v2...");
        
        try (SSLSocket socket = createTlsSocket()) {

            System.out.println("TLS connection established.");

            printServerCertificate(socket);

            // Android TV Remote v2 session initialization
            sendConfigure(socket);
            sendSetActive(socket);

            System.out.println("Remote v2 session initialized.");

            // Start reader thread.
            Thread reader = new Thread(
                    () -> readLoop(socket),
                    "MiBox-RemoteV2-Reader"
            );

            reader.setDaemon(true);
            reader.start();

            Thread.sleep(1000);

            System.out.println();
            System.out.println("Sending POWER...");
            sendKey(socket, POWER);

            System.out.println("POWER sent.");

            System.out.println();
            System.out.println("Waiting 15 seconds for standby...");
            Thread.sleep(15_000);

            System.out.println();
            System.out.println("Testing socket after standby...");

            if (!socket.isClosed()) {
                System.out.println(
                        "Java socket reports: socket still open."
                );
            } else {
                System.out.println(
                        "Java socket reports: CLOSED."
                );
            }

            System.out.println();
            System.out.println(
                    "The next step is a NEW Remote v2 connection."
            );
        }
    }


    // ------------------------------------------------------------
    // TLS
    // ------------------------------------------------------------

    private static SSLSocket createTlsSocket() throws Exception {

        X509Certificate clientCert =
                loadCertificate(CERT_FILE);

        PrivateKey privateKey =
                loadPrivateKey(KEY_FILE);

        KeyStore keyStore =
                KeyStore.getInstance(KeyStore.getDefaultType());

        keyStore.load(null, null);

        keyStore.setKeyEntry(
                "mibox-remote",
                privateKey,
                new char[0],
                new Certificate[]{clientCert}
        );

        KeyManagerFactory kmf =
                KeyManagerFactory.getInstance(
                        KeyManagerFactory.getDefaultAlgorithm()
                );

        kmf.init(keyStore, new char[0]);

        /*
         * Mi Box uses a self-signed certificate.
         *
         * ScreenCast also accepts the TLS certificate here and
         * performs its own SHA-256 certificate verification.
         */
        TrustManager[] trustAll = {
                new X509TrustManager() {

                    @Override
                    public void checkClientTrusted(
                            X509Certificate[] chain,
                            String authType) {
                    }

                    @Override
                    public void checkServerTrusted(
                            X509Certificate[] chain,
                            String authType) {
                    }

                    @Override
                    public X509Certificate[] getAcceptedIssuers() {
                        return new X509Certificate[0];
                    }
                }
        };

        SSLContext context =
                SSLContext.getInstance("TLS");

        context.init(
                kmf.getKeyManagers(),
                trustAll,
                new SecureRandom()
        );

        SSLSocketFactory factory =
                context.getSocketFactory();

        SSLSocket socket =
                (SSLSocket) factory.createSocket();

        socket.connect(
                new InetSocketAddress(
                        TARGET_IP,
                        REMOTE_PORT
                ),
                8000
        );

        socket.startHandshake();

        return socket;
    }


    // ------------------------------------------------------------
    // Remote v2 Configure
    // ------------------------------------------------------------

    private static void sendConfigure(
            SSLSocket socket) throws IOException {

        /*
         * RemoteConfigure:
         *
         * field 1 = code1 = 622
         * field 2 = RemoteDeviceInfo
         *
         * RemoteMessage:
         * field 1 = RemoteConfigure
         */

        ByteArrayOutputStream deviceInfo =
                new ByteArrayOutputStream();

        writeStringField(
                deviceInfo,
                1,
                "ScreenCast"
        );

        writeStringField(
                deviceInfo,
                2,
                "ScreenCast"
        );

        writeVarintField(
                deviceInfo,
                3,
                1
        );

        writeStringField(
                deviceInfo,
                4,
                "1"
        );

        writeStringField(
                deviceInfo,
                5,
                "io.github.ddagunts.screencast"
        );

        writeStringField(
                deviceInfo,
                6,
                "1.0.0"
        );

        ByteArrayOutputStream configure =
                new ByteArrayOutputStream();

        writeVarintField(
                configure,
                1,
                622
        );

        writeBytesField(
                configure,
                2,
                deviceInfo.toByteArray()
        );

        byte[] message =
                wrapField(
                        1,
                        configure.toByteArray()
                );

        writeFrame(socket, message);

        System.out.println(
                "RemoteConfigure(code1=622) sent."
        );
    }


    // ------------------------------------------------------------
    // Remote v2 SetActive
    // ------------------------------------------------------------

    private static void sendSetActive(
            SSLSocket socket) throws IOException {

        ByteArrayOutputStream active =
                new ByteArrayOutputStream();

        writeVarintField(
                active,
                1,
                622
        );

        byte[] message =
                wrapField(
                        2,
                        active.toByteArray()
                );

        writeFrame(socket, message);

        System.out.println(
                "RemoteSetActive(active=622) sent."
        );
    }


    // ------------------------------------------------------------
    // RemoteKeyInject
    // ------------------------------------------------------------

    private static void sendKey(
            SSLSocket socket,
            int keyCode) throws IOException {

        /*
         * RemoteKeyInject:
         *
         * field 1 = key_code
         * field 2 = direction
         *
         * RemoteMessage:
         *
         * field 10 = RemoteKeyInject
         */

        ByteArrayOutputStream keyInject =
                new ByteArrayOutputStream();

        writeVarintField(
                keyInject,
                1,
                keyCode
        );

        writeVarintField(
                keyInject,
                2,
                SHORT
        );

        byte[] message =
                wrapField(
                        10,
                        keyInject.toByteArray()
                );

        writeFrame(socket, message);

        System.out.println(
                "RemoteKeyInject: key=" +
                keyCode +
                " direction=SHORT"
        );
    }


    // ------------------------------------------------------------
    // Read Remote v2 messages
    // ------------------------------------------------------------

    private static void readLoop(
            SSLSocket socket) {

        try {

            InputStream in =
                    socket.getInputStream();

            while (!socket.isClosed()) {

                byte[] frame =
                        readFrame(in);

                System.out.println(
                        "<< Remote frame: " +
                        HexFormat.of().formatHex(frame)
                );

                /*
                 * We particularly care about:
                 *
                 * field 8 = PingRequest
                 *
                 * If received, respond with:
                 *
                 * field 9 = PingResponse
                 */

                int field =
                        firstFieldNumber(frame);

                if (field == 8) {

                    int value =
                            extractFirstInt(frame);

                    System.out.println(
                            "<< PingRequest value=" +
                            value
                    );

                    ByteArrayOutputStream ping =
                            new ByteArrayOutputStream();

                    writeVarintField(
                            ping,
                            1,
                            value
                    );

                    byte[] response =
                            wrapField(
                                    9,
                                    ping.toByteArray()
                            );

                    writeFrame(
                            socket,
                            response
                    );

                    System.out.println(
                            ">> PingResponse value=" +
                            value
                    );
                }
            }

        } catch (Exception e) {

            System.out.println(
                    "Remote v2 reader stopped: " +
                    e
            );
        }
    }


    // ------------------------------------------------------------
    // Frame handling
    // ------------------------------------------------------------

    private static void writeFrame(
            SSLSocket socket,
            byte[] message) throws IOException {

        OutputStream out =
                socket.getOutputStream();

        ByteBuffer header =
                ByteBuffer.allocate(4);

        header.putInt(message.length);

        out.write(header.array());
        out.write(message);
        out.flush();
    }


    private static byte[] readFrame(
            InputStream in) throws IOException {

        byte[] header =
                readExactly(in, 4);

        int length =
                ByteBuffer.wrap(header).getInt();

        if (length <= 0 || length > 1024 * 1024) {
            throw new IOException(
                    "Invalid Remote v2 frame length: " +
                    length
            );
        }

        return readExactly(in, length);
    }


    private static byte[] readExactly(
            InputStream in,
            int length) throws IOException {

        byte[] result =
                new byte[length];

        int offset = 0;

        while (offset < length) {

            int n =
                    in.read(
                            result,
                            offset,
                            length - offset
                    );

            if (n < 0) {
                throw new EOFException(
                        "Remote v2 connection closed"
                );
            }

            offset += n;
        }

        return result;
    }


    // ------------------------------------------------------------
    // Protobuf helpers
    // ------------------------------------------------------------

    private static byte[] wrapField(
            int field,
            byte[] value) throws IOException {

        ByteArrayOutputStream out =
                new ByteArrayOutputStream();

        writeBytesField(
                out,
                field,
                value
        );

        return out.toByteArray();
    }


    private static void writeBytesField(
            ByteArrayOutputStream out,
            int field,
            byte[] value) throws IOException {

        writeVarint(
                out,
                ((long) field << 3) | 2
        );

        writeVarint(
                out,
                value.length
        );

        out.write(value);
    }


    private static void writeStringField(
            ByteArrayOutputStream out,
            int field,
            String value) throws IOException {

        writeBytesField(
                out,
                field,
                value.getBytes(
                        StandardCharsets.UTF_8
                )
        );
    }


    private static void writeVarintField(
            ByteArrayOutputStream out,
            int field,
            long value) throws IOException {

        writeVarint(
                out,
                ((long) field << 3)
        );

        writeVarint(
                out,
                value
        );
    }


    private static void writeVarint(
            OutputStream out,
            long value) throws IOException {

        while ((value & ~0x7FL) != 0) {

            out.write(
                    (int) ((value & 0x7F) | 0x80)
            );

            value >>>= 7;
        }

        out.write((int) value);
    }


    // ------------------------------------------------------------
    // Very small decoder used only for ping detection
    // ------------------------------------------------------------

    private static int firstFieldNumber(
            byte[] data) {

        long tag =
                readVarint(
                        data,
                        0
                )[0];

        return (int) (tag >> 3);
    }


    private static int extractFirstInt(
            byte[] data) {

        int pos = 0;

        long[] tag =
                readVarint(data, pos);

        pos += (int) tag[1];

        long[] length =
                readVarint(data, pos);

        pos += (int) length[1];

        long[] innerTag =
                readVarint(data, pos);

        pos += (int) innerTag[1];

        long[] value =
                readVarint(data, pos);

        return (int) value[0];
    }


    private static long[] readVarint(
            byte[] data,
            int start) {

        long result = 0;
        int shift = 0;
        int pos = start;

        while (true) {

            int b =
                    data[pos++] & 0xFF;

            result |=
                    (long) (b & 0x7F) << shift;

            if ((b & 0x80) == 0) {
                break;
            }

            shift += 7;
        }

        return new long[]{
                result,
                pos - start
        };
    }


    // ------------------------------------------------------------
    // Certificate handling
    // ------------------------------------------------------------

    private static X509Certificate loadCertificate(
            Path path) throws Exception {

        String pem =
                Files.readString(path);

        String base64 =
                pem
                        .replace("-----BEGIN CERTIFICATE-----", "")
                        .replace("-----END CERTIFICATE-----", "")
                        .replaceAll("\\s", "");

        byte[] der =
                java.util.Base64
                        .getDecoder()
                        .decode(base64);

        var factory =
                java.security.cert.CertificateFactory
                        .getInstance("X.509");

        return (X509Certificate)
                factory.generateCertificate(
                        new ByteArrayInputStream(der)
                );
    }


    private static PrivateKey loadPrivateKey(
            Path path) throws Exception {

        String pem =
                Files.readString(path);

        String base64 =
                pem
                        .replace(
                                "-----BEGIN PRIVATE KEY-----",
                                ""
                        )
                        .replace(
                                "-----END PRIVATE KEY-----",
                                ""
                        )
                        .replaceAll("\\s", "");

        byte[] der =
                java.util.Base64
                        .getDecoder()
                        .decode(base64);

        PKCS8EncodedKeySpec spec =
                new PKCS8EncodedKeySpec(der);

        return KeyFactory
                .getInstance("EC")
                .generatePrivate(spec);
    }


    private static void printServerCertificate(
            SSLSocket socket) throws Exception {

        SSLSession session =
                socket.getSession();

        Certificate cert =
                session.getPeerCertificates()[0];

        byte[] encoded =
                cert.getEncoded();

        byte[] digest =
                MessageDigest
                        .getInstance("SHA-256")
                        .digest(encoded);

        System.out.println(
                "Mi Box server certificate SHA-256:"
        );

        System.out.println(
                HexFormat.of()
                        .withUpperCase()
                        .formatHex(digest)
        );
    }
}
