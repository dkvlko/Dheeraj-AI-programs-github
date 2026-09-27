import javax.net.ssl.*;
import java.io.*;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.*;
import java.security.cert.Certificate;
import java.security.cert.CertificateFactory;
import java.security.cert.X509Certificate;
import java.security.spec.PKCS8EncodedKeySpec;
import java.util.*;
import java.security.cert.CertificateException;

/**
 * Mi Box Android TV Remote v2 Standby/Wakeup test client
 *
 * Usage:
 *
 *   java MiBoxStandbyWakeup
 *
 * The program:
 *
 *   1. Creates a fresh TLS connection to the Mi Box.
 *   2. Performs the RemoteConfigure / RemoteSetActive handshake.
 *   3. Sends KEYCODE_POWER (26) to enter standby.
 *   4. Waits 10 seconds.
 *   5. Creates a completely NEW TLS connection.
 *   6. Performs the RemoteConfigure / RemoteSetActive handshake again.
 *   7. Sends KEYCODE_WAKEUP (224).
 *   8. Closes the connection.
 */
public class MiBoxStandbyWakeup {

    // ============================================================
    // Configuration
    // ============================================================

    private static final String TV_IP = "192.168.0.100";

    private static final int REMOTE_PORT = 6466;

    private static final String BASE_DIR =
            "/home/dkvlko/live_code/TVAndroidRemote";

    private static final String CLIENT_KEY_FILE =
            BASE_DIR + "/mibox_java_remote_key.pem";

    private static final String CLIENT_CERT_FILE =
            BASE_DIR + "/mibox_java_remote_cert.pem";

    private static final String SERVER_HASH_FILE =
            BASE_DIR + "/mibox_server_cert_sha256.txt";

    /*
     * Android TV Remote v2 uses 622 for the active feature set
     * in the standard handshake.
     */
    private static final int ACTIVE_CODE = 622;

    /*
     * RemoteDirection.SHORT = 3
     */
    private static final int DIRECTION_SHORT = 3;


    // ============================================================
    // Android key codes
    // ============================================================

    private static final Map<String, Integer> KEY_CODES =
            new HashMap<>();

    static {

        KEY_CODES.put("UNKNOWN", 0);

        KEY_CODES.put("HOME", 3);
        KEY_CODES.put("BACK", 4);

        KEY_CODES.put("0", 7);
        KEY_CODES.put("1", 8);
        KEY_CODES.put("2", 9);
        KEY_CODES.put("3", 10);
        KEY_CODES.put("4", 11);
        KEY_CODES.put("5", 12);
        KEY_CODES.put("6", 13);
        KEY_CODES.put("7", 14);
        KEY_CODES.put("8", 15);
        KEY_CODES.put("9", 16);

        KEY_CODES.put("DPAD_UP", 19);
        KEY_CODES.put("UP", 19);

        KEY_CODES.put("DPAD_DOWN", 20);
        KEY_CODES.put("DOWN", 20);

        KEY_CODES.put("DPAD_LEFT", 21);
        KEY_CODES.put("LEFT", 21);

        KEY_CODES.put("DPAD_RIGHT", 22);
        KEY_CODES.put("RIGHT", 22);

        KEY_CODES.put("DPAD_CENTER", 23);
        KEY_CODES.put("CENTER", 23);
        KEY_CODES.put("OK", 23);
        KEY_CODES.put("ENTER", 66);

        KEY_CODES.put("VOLUME_UP", 24);
        KEY_CODES.put("VOLUMEUP", 24);

        KEY_CODES.put("VOLUME_DOWN", 25);
        KEY_CODES.put("VOLUMEDOWN", 25);

        KEY_CODES.put("POWER", 26);

        KEY_CODES.put("CAMERA", 27);
        KEY_CODES.put("CLEAR", 28);

        KEY_CODES.put("MENU", 82);
        KEY_CODES.put("SEARCH", 84);

        KEY_CODES.put("MEDIA_PLAY_PAUSE", 85);
        KEY_CODES.put("PLAY_PAUSE", 85);

        KEY_CODES.put("MEDIA_STOP", 86);
        KEY_CODES.put("STOP", 86);

        KEY_CODES.put("MEDIA_NEXT", 87);
        KEY_CODES.put("NEXT", 87);

        KEY_CODES.put("MEDIA_PREVIOUS", 88);
        KEY_CODES.put("PREVIOUS", 88);

        KEY_CODES.put("MEDIA_REWIND", 89);
        KEY_CODES.put("REWIND", 89);

        KEY_CODES.put("MEDIA_FAST_FORWARD", 90);
        KEY_CODES.put("FAST_FORWARD", 90);

        KEY_CODES.put("MUTE", 91);

        KEY_CODES.put("CHANNEL_UP", 166);
        KEY_CODES.put("CHANNEL_DOWN", 167);

        KEY_CODES.put("TV", 170);

        KEY_CODES.put("GUIDE", 172);

        KEY_CODES.put("INFO", 165);

        KEY_CODES.put("LAST_CHANNEL", 229);

        KEY_CODES.put("CAPTIONS", 175);

        KEY_CODES.put("APP_SWITCH", 187);

        KEY_CODES.put("ESCAPE", 111);
        KEY_CODES.put("TAB", 61);
        KEY_CODES.put("SPACE", 62);
        KEY_CODES.put("DEL", 67);

        KEY_CODES.put("A", 29);
        KEY_CODES.put("B", 30);
        KEY_CODES.put("C", 31);
        KEY_CODES.put("D", 32);
        KEY_CODES.put("E", 33);
        KEY_CODES.put("F", 34);
        KEY_CODES.put("G", 35);
        KEY_CODES.put("H", 36);
        KEY_CODES.put("I", 37);
        KEY_CODES.put("J", 38);
        KEY_CODES.put("K", 39);
        KEY_CODES.put("L", 40);
        KEY_CODES.put("M", 41);
        KEY_CODES.put("N", 42);
        KEY_CODES.put("O", 43);
        KEY_CODES.put("P", 44);
        KEY_CODES.put("Q", 45);
        KEY_CODES.put("R", 46);
        KEY_CODES.put("S", 47);
        KEY_CODES.put("T", 48);
        KEY_CODES.put("U", 49);
        KEY_CODES.put("V", 50);
        KEY_CODES.put("W", 51);
        KEY_CODES.put("X", 52);
        KEY_CODES.put("Y", 53);
        KEY_CODES.put("Z", 54);
    }


    // ============================================================
    // Main
    // ============================================================

    public static void main(String[] args) {

        try {

            System.out.println();
            System.out.println("========================================");
            System.out.println(" Mi Box Standby -> Wakeup Test");
            System.out.println("========================================");
            System.out.println("TV       : " + TV_IP);
            System.out.println("Port     : " + REMOTE_PORT);
            System.out.println();

            /*
             * First connection:
             * KEYCODE_POWER = 26
             *
             * This puts the Mi Box into standby.
             */
            System.out.println("STEP 1: Sending POWER (26)...");
            sendCommand(26);

            System.out.println();
            System.out.println("Mi Box should now be in STANDBY.");
            System.out.println("Waiting 10 seconds before wakeup...");

            for (int i = 10; i >= 1; i--) {
                System.out.println("  " + i + "...");
                Thread.sleep(1000);
            }

            /*
             * IMPORTANT:
             *
             * Do NOT reuse the previous TLS connection.
             * sendCommand() creates a completely new connection,
             * performs the TLS handshake, and performs the
             * Android TV Remote v2 handshake again.
             *
             * KEYCODE_WAKEUP = 224
             */
            System.out.println();
            System.out.println("STEP 2: Creating a NEW connection for WAKEUP...");
            System.out.println("Sending KEYCODE_WAKEUP (224)...");

            sendCommand(224);

            System.out.println();
            System.out.println("========================================");
            System.out.println(" Standby -> Wakeup sequence completed.");
            System.out.println("========================================");

        } catch (Exception e) {

            System.err.println();
            System.err.println("ERROR: " + e.getMessage());
            e.printStackTrace();
            System.exit(1);
        }
    }


    // ============================================================
    // Parse command
    // ============================================================

    private static int parseCommand(String command)
            throws IllegalArgumentException {

        String normalized =
                command.trim()
                        .toUpperCase(Locale.ROOT)
                        .replace('-', '_')
                        .replace(' ', '_');

        /*
         * Accept:
         *
         * 24
         * KEYCODE_VOLUME_UP
         * VOLUME_UP
         * Volume Up
         */

        if (normalized.startsWith("KEYCODE_")) {

            normalized =
                    normalized.substring("KEYCODE_".length());
        }

        /*
         * Direct numeric Android key code.
         *
         * This allows commands that are not included in the
         * convenience table above.
         */

        try {

            return Integer.parseInt(normalized);

        } catch (NumberFormatException ignored) {
        }

        Integer keyCode = KEY_CODES.get(normalized);

        if (keyCode != null) {

            return keyCode;
        }

        throw new IllegalArgumentException(
                "Unknown Android key command: " + command
                        + "\n"
                        + "You can also supply the numeric Android "
                        + "key code.");
    }


    // ============================================================
    // Connect and send command
    // ============================================================

    private static void sendCommand(int keyCode)
            throws Exception {

        System.out.println(
                "Loading client private key...");

        PrivateKey privateKey =
                loadPrivateKey(CLIENT_KEY_FILE);

        System.out.println(
                "Loading client certificate...");

        X509Certificate clientCertificate =
                loadCertificate(CLIENT_CERT_FILE);

        System.out.println(
                "Loading Mi Box server certificate hash...");

        String expectedServerHash =
                Files.readString(
                        Path.of(SERVER_HASH_FILE),
                        StandardCharsets.UTF_8)
                        .trim()
                        .replaceAll("\\s+", "")
                        .toLowerCase(Locale.ROOT);

        System.out.println(
                "Expected server SHA-256:");
        System.out.println(
                expectedServerHash);

        /*
         * Create KeyManager containing our client certificate
         * and private key.
         */

        KeyStore keyStore =
                KeyStore.getInstance(
                        KeyStore.getDefaultType());

        keyStore.load(null, null);

        keyStore.setKeyEntry(
                "mibox-client",
                privateKey,
                new char[0],
                new Certificate[]{
                        clientCertificate
                });

        KeyManagerFactory kmf =
                KeyManagerFactory.getInstance(
                        KeyManagerFactory.getDefaultAlgorithm());

        kmf.init(keyStore, new char[0]);

        /*
         * Trust manager which accepts the Mi Box only if
         * its certificate SHA-256 matches the saved pairing
         * certificate hash.
         */

        TrustManager[] trustManagers = {

                new MiBoxTrustManager(
                        expectedServerHash)
        };

        SSLContext sslContext =
                SSLContext.getInstance("TLS");

        sslContext.init(
                kmf.getKeyManagers(),
                trustManagers,
                new SecureRandom());

        SSLSocketFactory factory =
                sslContext.getSocketFactory();

        System.out.println();
        System.out.println(
                "Connecting to Mi Box remote port "
                        + REMOTE_PORT + "...");

        try (SSLSocket socket =
                     (SSLSocket) factory.createSocket(
                             TV_IP,
                             REMOTE_PORT)) {

            socket.setSoTimeout(10000);

            socket.startHandshake();

            System.out.println(
                    "TLS connection established.");

            X509Certificate serverCertificate =
                    (X509Certificate)
                            socket.getSession()
                                    .getPeerCertificates()[0];

            String actualHash =
                    sha256Certificate(
                            serverCertificate);

            System.out.println(
                    "Server certificate SHA-256:");
            System.out.println(actualHash);

            if (!actualHash.equalsIgnoreCase(
                    expectedServerHash)) {

                throw new SecurityException(
                        "Mi Box server certificate hash "
                                + "does not match the paired certificate.");
            }

            InputStream in =
                    socket.getInputStream();

            OutputStream out =
                    socket.getOutputStream();

            /*
             * Android TV Remote v2 is device-driven:
             * the Mi Box sends RemoteConfigure first.
             */

            System.out.println();
            System.out.println(
                    "Waiting for RemoteConfigure...");

            byte[] configureMessage =
                    readMessage(in);

            int outerField =
                    firstFieldNumber(configureMessage);

            System.out.println(
                    "Received RemoteMessage field: "
                            + outerField);

            if (outerField == 1) {

                System.out.println(
                        "RemoteConfigure received.");

                byte[] response =
                        buildRemoteConfigure();

                writeMessage(out, response);

                System.out.println(
                        "RemoteConfigure sent.");
            }

            /*
             * Wait for RemoteSetActive.
             *
             * The Mi Box can also send ping messages here,
             * so process them until RemoteSetActive arrives.
             */

            boolean active = false;

            while (!active) {

                byte[] message =
                        readMessage(in);

                int field =
                        firstFieldNumber(message);

                if (field == 2) {

                    System.out.println(
                            "RemoteSetActive received.");

                    active = true;

                } else if (field == 8) {

                    System.out.println(
                            "RemotePingRequest received.");

                    int pingValue =
                            extractFirstInt32Field(
                                    getFieldPayload(
                                            message,
                                            8),
                                    1);

                    byte[] pingResponse =
                            buildPingResponse(
                                    pingValue);

                    writeMessage(
                            out,
                            pingResponse);

                    System.out.println(
                            "RemotePingResponse sent.");

                } else {

                    System.out.println(
                            "Received RemoteMessage field "
                                    + field);
                }
            }

            /*
             * Now the remote channel is active.
             */

            System.out.println();
            System.out.println(
                    "Remote connection is ACTIVE.");

            System.out.println(
                    "Sending Android key code "
                            + keyCode + "...");

            byte[] keyMessage =
                    buildRemoteKeyInject(
                            keyCode,
                            DIRECTION_SHORT);

            writeMessage(
                    out,
                    keyMessage);

            System.out.println(
                    "KEY command sent.");

            /*
             * Give the Mi Box a short amount of time to
             * consume the command before closing TLS.
             */

            Thread.sleep(200);

            System.out.println(
                    "Closing remote connection...");
        }
    }


    // ============================================================
    // RemoteConfigure
    // ============================================================

    private static byte[] buildRemoteConfigure()
            throws IOException {

        ByteArrayOutputStream deviceInfo =
                new ByteArrayOutputStream();

        /*
         * RemoteDeviceInfo:
         *
         * field 1 = model
         * field 2 = vendor
         * field 3 = unknown1
         * field 4 = unknown2
         * field 5 = package_name
         * field 6 = app_version
         */

        writeStringField(
                deviceInfo,
                1,
                "JavaRemote");

        writeStringField(
                deviceInfo,
                2,
                "JavaRemote");

        writeInt32Field(
                deviceInfo,
                3,
                1);

        writeStringField(
                deviceInfo,
                4,
                "1");

        writeStringField(
                deviceInfo,
                5,
                "atvremote");

        writeStringField(
                deviceInfo,
                6,
                "1.0.0");

        /*
         * RemoteConfigure:
         *
         * field 1 = code1
         * field 2 = device_info
         */

        ByteArrayOutputStream configure =
                new ByteArrayOutputStream();

        writeInt32Field(
                configure,
                1,
                ACTIVE_CODE);

        writeMessageField(
                configure,
                2,
                deviceInfo.toByteArray());

        /*
         * RemoteMessage:
         *
         * field 1 = RemoteConfigure
         */

        ByteArrayOutputStream message =
                new ByteArrayOutputStream();

        writeMessageField(
                message,
                1,
                configure.toByteArray());

        return message.toByteArray();
    }


    // ============================================================
    // RemoteKeyInject
    // ============================================================

    private static byte[] buildRemoteKeyInject(
            int keyCode,
            int direction)
            throws IOException {

        ByteArrayOutputStream keyInject =
                new ByteArrayOutputStream();

        /*
         * RemoteKeyInject:
         *
         * field 1 = key_code
         * field 2 = direction
         */

        writeInt32Field(
                keyInject,
                1,
                keyCode);

        writeInt32Field(
                keyInject,
                2,
                direction);

        /*
         * RemoteMessage:
         *
         * field 10 = RemoteKeyInject
         */

        ByteArrayOutputStream message =
                new ByteArrayOutputStream();

        writeMessageField(
                message,
                10,
                keyInject.toByteArray());

        return message.toByteArray();
    }


    // ============================================================
    // Ping response
    // ============================================================

    private static byte[] buildPingResponse(
            int value)
            throws IOException {

        ByteArrayOutputStream ping =
                new ByteArrayOutputStream();

        /*
         * RemotePingResponse:
         *
         * field 1 = val1
         */

        writeInt32Field(
                ping,
                1,
                value);

        /*
         * RemoteMessage:
         *
         * field 9 = RemotePingResponse
         */

        ByteArrayOutputStream message =
                new ByteArrayOutputStream();

        writeMessageField(
                message,
                9,
                ping.toByteArray());

        return message.toByteArray();
    }


    // ============================================================
    // Protobuf encoding
    // ============================================================

    private static void writeMessageField(
            OutputStream out,
            int fieldNumber,
            byte[] value)
            throws IOException {

        writeTag(
                out,
                fieldNumber,
                2);

        writeVarint(
                out,
                value.length);

        out.write(value);
    }


    private static void writeStringField(
            OutputStream out,
            int fieldNumber,
            String value)
            throws IOException {

        writeMessageField(
                out,
                fieldNumber,
                value.getBytes(
                        StandardCharsets.UTF_8));
    }


    private static void writeInt32Field(
            OutputStream out,
            int fieldNumber,
            int value)
            throws IOException {

        writeTag(
                out,
                fieldNumber,
                0);

        writeVarint(
                out,
                value);
    }


    private static void writeTag(
            OutputStream out,
            int fieldNumber,
            int wireType)
            throws IOException {

        writeVarint(
                out,
                ((long) fieldNumber << 3)
                        | wireType);
    }


    private static void writeVarint(
            OutputStream out,
            long value)
            throws IOException {

        while ((value & ~0x7FL) != 0) {

            out.write(
                    (int) ((value & 0x7F) | 0x80));

            value >>>= 7;
        }

        out.write((int) value);
    }


    // ============================================================
    // Length-delimited message framing
    // ============================================================

    private static void writeMessage(
            OutputStream out,
            byte[] message)
            throws IOException {

        writeVarint(
                out,
                message.length);

        out.write(message);
        out.flush();
    }


    private static byte[] readMessage(
            InputStream in)
            throws IOException {

        long length =
                readVarint(in);

        if (length < 0 ||
                length > 1024 * 1024) {

            throw new IOException(
                    "Invalid protobuf message length: "
                            + length);
        }

        byte[] message =
                in.readNBytes((int) length);

        if (message.length != length) {

            throw new EOFException(
                    "Incomplete protobuf message. "
                            + "Expected " + length
                            + " bytes, got "
                            + message.length);
        }

        return message;
    }


    private static long readVarint(
            InputStream in)
            throws IOException {

        long result = 0;
        int shift = 0;

        while (shift < 64) {

            int b = in.read();

            if (b < 0) {

                throw new EOFException(
                        "Connection closed while "
                                + "reading protobuf varint.");
            }

            result |=
                    ((long) (b & 0x7F)) << shift;

            if ((b & 0x80) == 0) {

                return result;
            }

            shift += 7;
        }

        throw new IOException(
                "Invalid protobuf varint.");
    }


    // ============================================================
    // Minimal protobuf parsing
    // ============================================================

    private static int firstFieldNumber(
            byte[] message)
            throws IOException {

        int[] position = {0};

        long tag =
                readVarint(
                        new ByteArrayInputStream(
                                message));

        return (int) (tag >>> 3);
    }


    /*
     * Returns the protobuf payload of a length-delimited
     * outer field.
     */
    private static byte[] getFieldPayload(
            byte[] message,
            int wantedField)
            throws IOException {

        ByteArrayInputStream in =
                new ByteArrayInputStream(message);

        while (in.available() > 0) {

            long tag =
                    readVarint(in);

            int fieldNumber =
                    (int) (tag >>> 3);

            int wireType =
                    (int) (tag & 7);

            if (wireType == 2) {

                long length =
                        readVarint(in);

                byte[] payload =
                        in.readNBytes(
                                (int) length);

                if (fieldNumber ==
                        wantedField) {

                    return payload;
                }

            } else if (wireType == 0) {

                readVarint(in);

            } else {

                throw new IOException(
                        "Unsupported protobuf wire type: "
                                + wireType);
            }
        }

        return null;
    }


    private static int extractFirstInt32Field(
            byte[] message,
            int wantedField)
            throws IOException {

        if (message == null) {

            return 1;
        }

        ByteArrayInputStream in =
                new ByteArrayInputStream(message);

        while (in.available() > 0) {

            long tag =
                    readVarint(in);

            int fieldNumber =
                    (int) (tag >>> 3);

            int wireType =
                    (int) (tag & 7);

            if (wireType == 0) {

                long value =
                        readVarint(in);

                if (fieldNumber ==
                        wantedField) {

                    return (int) value;
                }

            } else if (wireType == 2) {

                long length =
                        readVarint(in);

                in.skipNBytes(length);

            } else {

                throw new IOException(
                        "Unsupported protobuf wire type: "
                                + wireType);
            }
        }

        return 1;
    }


    // ============================================================
    // Private key loading
    // ============================================================

    private static PrivateKey loadPrivateKey(
            String filename)
            throws Exception {

        String pem =
                Files.readString(
                        Path.of(filename),
                        StandardCharsets.US_ASCII);

        pem = pem
                .replace(
                        "-----BEGIN PRIVATE KEY-----",
                        "")
                .replace(
                        "-----END PRIVATE KEY-----",
                        "")
                .replaceAll("\\s+", "");

        byte[] der =
                Base64.getDecoder().decode(pem);

        PKCS8EncodedKeySpec spec =
                new PKCS8EncodedKeySpec(der);

        KeyFactory keyFactory =
                KeyFactory.getInstance("RSA");

        return keyFactory.generatePrivate(spec);
    }


    // ============================================================
    // Certificate loading
    // ============================================================

    private static X509Certificate loadCertificate(
            String filename)
            throws Exception {

        try (InputStream in =
                     Files.newInputStream(
                             Path.of(filename))) {

            CertificateFactory factory =
                    CertificateFactory.getInstance(
                            "X.509");

            return (X509Certificate)
                    factory.generateCertificate(in);
        }
    }


    // ============================================================
    // Certificate SHA-256
    // ============================================================

    private static String sha256Certificate(
            X509Certificate certificate)
            throws Exception {

        byte[] digest =
                MessageDigest.getInstance(
                        "SHA-256")
                        .digest(
                                certificate.getEncoded());

        return bytesToHex(digest);
    }


    // ============================================================
    // Hex helper
    // ============================================================

    private static String bytesToHex(
            byte[] bytes) {

        StringBuilder sb =
                new StringBuilder(
                        bytes.length * 2);

        for (byte b : bytes) {

            sb.append(
                    String.format(
                            "%02x",
                            b & 0xFF));
        }

        return sb.toString();
    }


    // ============================================================
    // Mi Box certificate trust manager
    // ============================================================

    private static class MiBoxTrustManager
            implements X509TrustManager {

        private final String expectedHash;

        MiBoxTrustManager(
                String expectedHash) {

            this.expectedHash =
                    expectedHash
                            .toLowerCase(
                                    Locale.ROOT);
        }

        @Override
        public void checkClientTrusted(
                X509Certificate[] chain,
                String authType) {

            /*
             * Not used by this client.
             */
        }

        @Override
        public void checkServerTrusted(
                X509Certificate[] chain,
                String authType)
                throws CertificateException {

            if (chain == null ||
                    chain.length == 0) {

                throw new CertificateException(
                        "Mi Box did not provide "
                                + "a server certificate.");
            }

            try {

                String actual =
                        sha256Certificate(
                                chain[0]);

                if (!actual.equalsIgnoreCase(
                        expectedHash)) {

                    throw new CertificateException(
                            "Mi Box certificate SHA-256 "
                                    + "does not match the "
                                    + "paired certificate.\n"
                                    + "Expected: "
                                    + expectedHash
                                    + "\n"
                                    + "Actual:   "
                                    + actual);
                }

            } catch (CertificateException e) {

                throw e;

            } catch (Exception e) {

                throw new CertificateException(
                        "Unable to verify Mi Box "
                                + "certificate.",
                        e);
            }
        }

        @Override
        public X509Certificate[] getAcceptedIssuers() {

            return new X509Certificate[0];
        }
    }
}
