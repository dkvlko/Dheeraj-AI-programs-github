import javax.net.ssl.*;
import java.io.*;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.*;
import java.security.cert.Certificate;
import java.security.cert.CertificateFactory;
import java.security.cert.X509Certificate;
import java.security.interfaces.RSAPublicKey;
import java.util.*;

public class MiBoxPairing {

    // ============================================================
    // SETTINGS
    // ============================================================

    private static final String TV_IP = "192.168.0.100";

    private static final int PAIRING_PORT = 6467;

    private static final int PROTOCOL_VERSION = 2;

    private static final String SERVICE_NAME = "atvremote";

    private static final String CLIENT_NAME = "JavaRemote";

    private static final Path BASE_DIR =
            Path.of("/home/dkvlko/live_code/TVAndroidRemote");

    private static final Path KEY_FILE =
            BASE_DIR.resolve("mibox_java_remote_key.pem");

    private static final Path CERT_FILE =
            BASE_DIR.resolve("mibox_java_remote_cert.pem");

    private static final Path SERVER_CERT_HASH_FILE =
            BASE_DIR.resolve("mibox_server_cert_sha256.txt");


    // ============================================================
    // MAIN
    // ============================================================

    public static void main(String[] args) throws Exception {

        Files.createDirectories(BASE_DIR);

        System.out.println();
        System.out.println("========================================");
        System.out.println(" Mi Box 4 Android TV Remote v2 PAIRING");
        System.out.println("========================================");
        System.out.println(
                "TV: " + TV_IP + ":" + PAIRING_PORT
        );
        System.out.println();

        // --------------------------------------------------------
        // 1. Generate RSA-2048 client key
        // --------------------------------------------------------

        System.out.println(
                "Generating RSA-2048 client key..."
        );

        KeyPairGenerator kpg =
                KeyPairGenerator.getInstance("RSA");

        kpg.initialize(2048);

        KeyPair clientKeyPair =
                kpg.generateKeyPair();

        writePrivateKeyPem(
                clientKeyPair.getPrivate(),
                KEY_FILE
        );

        System.out.println(
                "Private key created."
        );


        // --------------------------------------------------------
        // 2. Create self-signed certificate
        // --------------------------------------------------------

        createCertificateWithOpenSSL();

        X509Certificate clientCertificate =
                loadCertificate(CERT_FILE);

        System.out.println(
                "Client certificate created."
        );

        System.out.println(
                "Client certificate SHA-256: " +
                sha256Hex(
                        clientCertificate.getEncoded()
                )
        );


        // --------------------------------------------------------
        // 3. TLS context
        // --------------------------------------------------------

        SSLContext sslContext =
                createSSLContext(
                        clientKeyPair.getPrivate(),
                        clientCertificate
                );


        // --------------------------------------------------------
        // 4. Connect to port 6467
        // --------------------------------------------------------

        System.out.println();
        System.out.println(
                "Connecting to Mi Box pairing port 6467..."
        );

        try (
                SSLSocket socket =
                        (SSLSocket)
                                sslContext
                                        .getSocketFactory()
                                        .createSocket()
        ) {

            socket.connect(
                    new InetSocketAddress(
                            TV_IP,
                            PAIRING_PORT
                    ),
                    10000
            );

            socket.setSoTimeout(15000);

            socket.startHandshake();

            System.out.println(
                    "TLS connection established."
            );


            // ----------------------------------------------------
            // 5. Get server certificate
            // ----------------------------------------------------

            X509Certificate serverCertificate =
                    (X509Certificate)
                            socket
                                    .getSession()
                                    .getPeerCertificates()[0];

            String serverHash =
                    sha256Hex(
                            serverCertificate.getEncoded()
                    );

            System.out.println();
            System.out.println(
                    "Mi Box server certificate SHA-256:"
            );
            System.out.println(serverHash);

            Files.writeString(
                    SERVER_CERT_HASH_FILE,
                    serverHash + "\n"
            );


            InputStream in =
                    socket.getInputStream();

            OutputStream out =
                    socket.getOutputStream();


            // ====================================================
            // 6. PAIRING REQUEST
            // ====================================================

            System.out.println();
            System.out.println(
                    "Sending PAIRING_REQUEST..."
            );

            sendFrame(
                    out,
                    outerMessage(
                            10,
                            pairingRequestMessage()
                    )
            );

            byte[] response =
                    readFrame(in);

            byte[] payload =
                    checkResponse(
                            response,
                            11,
                            "PAIRING_REQUEST_ACK"
                    );

            String serverName =
                    getStringField(
                            payload,
                            1
                    );

            if (serverName != null) {

                System.out.println(
                        "Server name: " +
                        serverName
                );
            }


            // ====================================================
            // 7. OPTIONS
            // ====================================================

            System.out.println();
            System.out.println(
                    "Sending OPTIONS..."
            );

            sendFrame(
                    out,
                    outerMessage(
                            20,
                            optionsMessage()
                    )
            );

            response =
                    readFrame(in);

            checkResponse(
                    response,
                    20,
                    "OPTIONS"
            );


            // ====================================================
            // 8. CONFIGURATION
            // ====================================================

            System.out.println();
            System.out.println(
                    "Sending CONFIGURATION..."
            );

            sendFrame(
                    out,
                    outerMessage(
                            30,
                            configurationMessage()
                    )
            );

            response =
                    readFrame(in);

            checkResponse(
                    response,
                    31,
                    "CONFIGURATION_ACK"
            );


            // ====================================================
            // 9. PIN
            // ====================================================

            System.out.println();
            System.out.println(
                    "========================================"
            );

            System.out.println(
                    " Enter the 6-character PIN displayed"
            );

            System.out.println(
                    " on the Mi Box"
            );

            System.out.println(
                    "========================================"
            );

            System.out.println();

            System.out.print("PIN: ");

            Scanner scanner =
                    new Scanner(System.in);

            String pin =
                    scanner.nextLine()
                            .trim()
                            .toUpperCase(
                                    Locale.ROOT
                            );

            validatePin(pin);


            // ====================================================
            // 10. Calculate secret
            // ====================================================

            byte[] secret =
                    calculatePairingSecret(
                            clientKeyPair,
                            serverCertificate,
                            pin
                    );

            System.out.println();

            System.out.println(
                    "Pairing secret:"
            );

            System.out.println(
                    hex(secret)
            );


            /*
             * Android TV Remote v2 PIN verification:
             *
             * The first byte of the SHA-256 pairing secret must
             * equal the first two hexadecimal characters of the
             * six-character PIN.
             *
             * Example:
             *
             * PIN       = 3DA55A
             * PIN check = 3D
             *
             * Therefore:
             *
             * secret[0] must be 0x3D.
             */

            int expectedFirstByte =
                    Integer.parseInt(
                            pin.substring(0, 2),
                            16
                    );

            int actualFirstByte =
                    secret[0] & 0xFF;

            System.out.println();

            System.out.printf(
                    Locale.ROOT,
                    "PIN check: expected=%02X actual=%02X%n",
                    expectedFirstByte,
                    actualFirstByte
            );

            if (expectedFirstByte != actualFirstByte) {

                throw new IOException(
                        String.format(
                                Locale.ROOT,
                                "Incorrect PIN or incorrect pairing-secret calculation. " +
                                "PIN=%s expected first byte=%02X actual=%02X",
                                pin,
                                expectedFirstByte,
                                actualFirstByte
                        )
                );
            }

            System.out.println(
                    "PIN check passed."
            );


// ====================================================
// 11. SECRET
// ====================================================
            /*
             * The first byte of SHA-256 is the check byte
             * represented by the first two hex characters
             * of the six-character PIN.
             */

            System.out.println();
            System.out.println(
                    "Sending SECRET..."
            );

            sendFrame(
                    out,
                    outerMessage(
                            40,
                            secretMessage(secret)
                    )
            );

            response =
                    readFrame(in);



            // ====================================================
            // 12. SECRET ACK
            // ====================================================

            byte[] ackPayload =
                    checkResponse(
                            response,
                            41,
                            "SECRET_ACK"
                    );

            byte[] returnedSecret =
                    getBytesField(
                            ackPayload,
                            1
                    );

            if (returnedSecret != null) {

                System.out.println(
                        "SECRET_ACK secret:"
                );

                System.out.println(
                        hex(returnedSecret)
                );
            }


            // ====================================================
            // SUCCESS
            // ====================================================

            System.out.println();
            System.out.println(
                    "========================================"
            );

            System.out.println(
                    " PAIRING SUCCESSFUL"
            );

            System.out.println(
                    "========================================"
            );

            System.out.println();

            System.out.println(
                    "Private key:"
            );

            System.out.println(
                    KEY_FILE
            );

            System.out.println();

            System.out.println(
                    "Certificate:"
            );

            System.out.println(
                    CERT_FILE
            );

            System.out.println();

            System.out.println(
                    "Server certificate SHA-256:"
            );

            System.out.println(
                    serverHash
            );

            System.out.println();

            System.out.println(
                    "Server hash saved to:"
            );

            System.out.println(
                    SERVER_CERT_HASH_FILE
            );
        }
    }


    // ============================================================
    // PAIRING REQUEST
    // ============================================================

    private static byte[] pairingRequestMessage() {

        ByteArrayOutputStream out =
                new ByteArrayOutputStream();

        /*
         * PairingRequest
         *
         * field 1 = service_name
         * field 2 = client_name
         */

        writeStringField(
                out,
                1,
                SERVICE_NAME
        );

        writeStringField(
                out,
                2,
                CLIENT_NAME
        );

        return out.toByteArray();
    }


    // ============================================================
    // OPTIONS
    // ============================================================

    private static byte[] optionsMessage() {

        ByteArrayOutputStream out =
                new ByteArrayOutputStream();


        /*
         * Options.Encoding
         *
         * field 1 = type
         * field 2 = symbol_length
         */

        ByteArrayOutputStream encoding =
                new ByteArrayOutputStream();

        writeVarintField(
                encoding,
                1,
                3       // HEXADECIMAL
        );

        writeVarintField(
                encoding,
                2,
                6       // six characters
        );


        /*
         * Options
         *
         * field 1 = input_encodings
         * field 3 = preferred_role
         */

        writeBytesField(
                out,
                1,
                encoding.toByteArray()
        );

        writeVarintField(
                out,
                3,
                1       // ROLE_TYPE_INPUT
        );

        return out.toByteArray();
    }


    // ============================================================
    // CONFIGURATION
    // ============================================================

    private static byte[] configurationMessage() {

        ByteArrayOutputStream out =
                new ByteArrayOutputStream();


        /*
         * Configuration.Encoding
         */

        ByteArrayOutputStream encoding =
                new ByteArrayOutputStream();

        writeVarintField(
                encoding,
                1,
                3       // HEXADECIMAL
        );

        writeVarintField(
                encoding,
                2,
                6
        );


        /*
         * Configuration
         *
         * field 1 = encoding
         * field 2 = client_role
         */

        writeBytesField(
                out,
                1,
                encoding.toByteArray()
        );

        writeVarintField(
                out,
                2,
                1       // ROLE_TYPE_INPUT
        );

        return out.toByteArray();
    }


    // ============================================================
    // SECRET
    // ============================================================

    private static byte[] secretMessage(
            byte[] secret) {

        ByteArrayOutputStream out =
                new ByteArrayOutputStream();

        writeBytesField(
                out,
                1,
                secret
        );

        return out.toByteArray();
    }


    // ============================================================
    // OUTER MESSAGE
    // ============================================================

    private static byte[] outerMessage(
            int messageType,
            byte[] payload) {

        ByteArrayOutputStream out =
                new ByteArrayOutputStream();


        /*
         * CURRENT Android TV Remote v2 / Polo:
         *
         * field 1 = protocol_version
         * field 2 = status
         *
         * field 10 = PairingRequest
         * field 20 = Options
         * field 30 = Configuration
         * field 40 = Secret
         *
         * field 11 = PairingRequestAck
         * field 31 = ConfigurationAck
         * field 41 = SecretAck
         */

        writeVarintField(
                out,
                1,
                PROTOCOL_VERSION
        );

        writeVarintField(
                out,
                2,
                200       // STATUS_OK
        );

        writeBytesField(
                out,
                messageType,
                payload
        );

        return out.toByteArray();
    }


    // ============================================================
    // RESPONSE CHECK
    // ============================================================

    private static byte[] checkResponse(
            byte[] response,
            int expectedField,
            String name)
            throws IOException {

        int protocolVersion =
                getIntField(
                        response,
                        1
                );

        int status =
                getIntField(
                        response,
                        2
                );

        System.out.println(
                "<< " +
                name +
                " protocol_version=" +
                protocolVersion +
                " status=" +
                status
        );

        if (status != 200) {

            throw new IOException(
                    name +
                    " failed. Mi Box returned status=" +
                    status +
                    ". Raw=" +
                    hex(response)
            );
        }

        byte[] payload =
                getBytesField(
                        response,
                        expectedField
                );

        if (payload == null) {

            throw new IOException(
                    name +
                    " field " +
                    expectedField +
                    " missing. Raw=" +
                    hex(response)
            );
        }

        return payload;
    }


// ============================================================
// PAIRING SECRET
// ============================================================
private static String bytesToHex(byte[] bytes) {
    StringBuilder sb = new StringBuilder(bytes.length * 2);

    for (byte b : bytes) {
        sb.append(String.format("%02x", b & 0xFF));
    }

    return sb.toString();
}

private static byte[] calculatePairingSecret(
        KeyPair clientKeyPair,
        X509Certificate serverCertificate,
        String pin)
        throws Exception {

    RSAPublicKey clientKey =
            (RSAPublicKey) clientKeyPair.getPublic();

    if (!(serverCertificate.getPublicKey()
            instanceof RSAPublicKey serverKey)) {
        throw new GeneralSecurityException(
                "Mi Box certificate does not contain an RSA public key."
        );
    }

    byte[] clientModulus =
            unsignedBytes(clientKey.getModulus());

    byte[] clientExponent =
            unsignedBytes(clientKey.getPublicExponent());

    byte[] serverModulus =
            unsignedBytes(serverKey.getModulus());

    byte[] serverExponent =
            unsignedBytes(serverKey.getPublicExponent());

    // The Android TV Remote v2 pairing protocol uses
    // only the final four hexadecimal characters of the PIN.
    byte[] pinBytes =
            hexToBytes(pin.substring(2));

    /*
     * SHA-256 input:
     *
     * client modulus
     * client exponent
     * server modulus
     * server exponent
     * PIN bytes (last 4 hexadecimal characters)
     *
     * IMPORTANT:
     * There are NO 0x00 separator bytes.
     */
    ByteArrayOutputStream input =
            new ByteArrayOutputStream();

    input.writeBytes(clientModulus);
    input.writeBytes(clientExponent);
    input.writeBytes(serverModulus);
    input.writeBytes(serverExponent);
    input.writeBytes(pinBytes);

    byte[] hashInput = input.toByteArray();

    System.out.println();
    System.out.println("========================================");
    System.out.println(" PAIRING SECRET INPUT DIAGNOSTICS");
    System.out.println("========================================");

    System.out.println();
    System.out.println("Client RSA modulus:");
    System.out.println("  Length = " + clientModulus.length + " bytes");
    System.out.println("  Hex    = " + bytesToHex(clientModulus));

    System.out.println();
    System.out.println("Client RSA exponent:");
    System.out.println("  Length = " + clientExponent.length + " bytes");
    System.out.println("  Hex    = " + bytesToHex(clientExponent));

    System.out.println();
    System.out.println("Server RSA modulus:");
    System.out.println("  Length = " + serverModulus.length + " bytes");
    System.out.println("  Hex    = " + bytesToHex(serverModulus));

    System.out.println();
    System.out.println("Server RSA exponent:");
    System.out.println("  Length = " + serverExponent.length + " bytes");
    System.out.println("  Hex    = " + bytesToHex(serverExponent));

    System.out.println();
    System.out.println("PIN:");
    System.out.println("  " + pin);

    System.out.println();
    System.out.println("PIN bytes used in SHA-256:");
    System.out.println("  Length = " + pinBytes.length + " bytes");
    System.out.println("  Hex    = " + bytesToHex(pinBytes));

    System.out.println();
    System.out.println("Complete SHA-256 input:");
    System.out.println("  Length = " + hashInput.length + " bytes");
    System.out.println("  Hex    = " + bytesToHex(hashInput));

    MessageDigest md =
            MessageDigest.getInstance("SHA-256");

    byte[] secret = md.digest(hashInput);

    System.out.println();
    System.out.println("SHA-256 result:");
    System.out.println("  " + bytesToHex(secret));

    return secret;
}
    // ============================================================
    // TLS
    // ============================================================

    private static SSLContext createSSLContext(
            PrivateKey privateKey,
            X509Certificate certificate)
            throws Exception {

        KeyStore keyStore =
                KeyStore.getInstance(
                        "PKCS12"
                );

        keyStore.load(
                null,
                null
        );

        keyStore.setKeyEntry(
                "client",
                privateKey,
                new char[0],
                new Certificate[]{
                        certificate
                }
        );


        KeyManagerFactory kmf =
                KeyManagerFactory.getInstance(
                        KeyManagerFactory
                                .getDefaultAlgorithm()
                );

        kmf.init(
                keyStore,
                new char[0]
        );


        /*
         * The Mi Box certificate is self-signed.
         *
         * During initial pairing we accept it so that we can
         * obtain its certificate and calculate the pairing secret.
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
                    public X509Certificate[]
                    getAcceptedIssuers() {

                        return new X509Certificate[0];
                    }
                }
        };


        SSLContext context =
                SSLContext.getInstance(
                        "TLS"
                );

        context.init(
                kmf.getKeyManagers(),
                trustAll,
                new SecureRandom()
        );

        return context;
    }


    // ============================================================
    // CREATE CERTIFICATE
    // ============================================================

    private static void createCertificateWithOpenSSL()
            throws Exception {

        System.out.println(
                "Creating self-signed X.509 certificate..."
        );

        ProcessBuilder pb =
                new ProcessBuilder(
                        "openssl",
                        "req",
                        "-new",
                        "-x509",
                        "-sha256",
                        "-days",
                        "3650",
                        "-key",
                        KEY_FILE.toString(),
                        "-out",
                        CERT_FILE.toString(),
                        "-subj",
                        "/CN=" + CLIENT_NAME
                );

        pb.redirectErrorStream(true);

        Process process =
                pb.start();

        String output =
                new String(
                        process.getInputStream()
                                .readAllBytes(),
                        StandardCharsets.UTF_8
                );

        int exitCode =
                process.waitFor();

        if (exitCode != 0) {

            throw new IOException(
                    "OpenSSL failed:\n" +
                    output
            );
        }
    }


    // ============================================================
    // FRAME SEND
    // ============================================================

    private static void sendFrame(
            OutputStream out,
            byte[] message)
            throws IOException {

        /*
         * Length-prefixed protobuf message.
         */

        writeVarint(
                out,
                message.length
        );

        out.write(message);

        out.flush();
    }


    // ============================================================
    // FRAME RECEIVE
    // ============================================================

    private static byte[] readFrame(
            InputStream in)
            throws IOException {

        long length =
                readVarint(in);

        if (length < 0 ||
                length > 1024 * 1024) {

            throw new IOException(
                    "Invalid frame length: " +
                    length
            );
        }

        byte[] data =
                new byte[(int) length];

        int offset = 0;

        while (offset < data.length) {

            int n =
                    in.read(
                            data,
                            offset,
                            data.length - offset
                    );

            if (n < 0) {

                throw new EOFException(
                        "Mi Box closed connection."
                );
            }

            offset += n;
        }

        return data;
    }


    // ============================================================
    // PROTOBUF ENCODING
    // ============================================================

    private static void writeStringField(
            ByteArrayOutputStream out,
            int field,
            String value) {

        writeBytesField(
                out,
                field,
                value.getBytes(
                        StandardCharsets.UTF_8
                )
        );
    }


    private static void writeBytesField(
            ByteArrayOutputStream out,
            int field,
            byte[] value) {

        writeVarint(
                out,
                ((long) field << 3) | 2
        );

        writeVarint(
                out,
                value.length
        );

        out.writeBytes(value);
    }


    private static void writeVarintField(
            ByteArrayOutputStream out,
            int field,
            long value) {

        writeVarint(
                out,
                (long) field << 3
        );

        writeVarint(
                out,
                value
        );
    }


    private static void writeVarint(
            OutputStream out,
            long value) {

        try {

            while ((value & ~0x7FL) != 0) {

                out.write(
                        (int)
                                ((value & 0x7F) |
                                        0x80)
                );

                value >>>= 7;
            }

            out.write(
                    (int) value
            );

        } catch (IOException e) {

            throw new UncheckedIOException(e);
        }
    }


    // ============================================================
    // PROTOBUF DECODING
    // ============================================================

    private record Varint(
            long value,
            int next) {
    }


    private static int getIntField(
            byte[] data,
            int wantedField) {

        int pos = 0;

        while (pos < data.length) {

            Varint tag =
                    readVarint(
                            data,
                            pos
                    );

            pos = tag.next;

            int field =
                    (int)
                            (tag.value >>> 3);

            int wireType =
                    (int)
                            (tag.value & 7);

            if (field == wantedField &&
                    wireType == 0) {

                return (int)
                        readVarint(
                                data,
                                pos
                        ).value;
            }

            pos =
                    skipField(
                            data,
                            pos,
                            wireType
                    );
        }

        return -1;
    }


    private static byte[] getBytesField(
            byte[] data,
            int wantedField) {

        int pos = 0;

        while (pos < data.length) {

            Varint tag =
                    readVarint(
                            data,
                            pos
                    );

            pos = tag.next;

            int field =
                    (int)
                            (tag.value >>> 3);

            int wireType =
                    (int)
                            (tag.value & 7);

            if (field == wantedField &&
                    wireType == 2) {

                Varint length =
                        readVarint(
                                data,
                                pos
                        );

                pos = length.next;

                if (length.value < 0 ||
                        length.value >
                                Integer.MAX_VALUE ||
                        pos + length.value >
                                data.length) {

                    return null;
                }

                return Arrays.copyOfRange(
                        data,
                        pos,
                        pos + (int) length.value
                );
            }

            pos =
                    skipField(
                            data,
                            pos,
                            wireType
                    );
        }

        return null;
    }


    private static String getStringField(
            byte[] data,
            int field) {

        byte[] bytes =
                getBytesField(
                        data,
                        field
                );

        if (bytes == null) {
            return null;
        }

        return new String(
                bytes,
                StandardCharsets.UTF_8
        );
    }


    private static int skipField(
            byte[] data,
            int pos,
            int wireType) {

        return switch (wireType) {

            case 0 ->
                    readVarint(
                            data,
                            pos
                    ).next;

            case 1 ->
                    pos + 8;

            case 2 -> {

                Varint length =
                        readVarint(
                                data,
                                pos
                        );

                yield length.next +
                        (int) length.value;
            }

            case 5 ->
                    pos + 4;

            default ->
                    throw new IllegalArgumentException(
                            "Unsupported protobuf wire type: " +
                            wireType
                    );
        };
    }


    private static Varint readVarint(
            byte[] data,
            int start) {

        long value = 0;

        int shift = 0;

        int pos = start;

        while (true) {

            if (pos >= data.length) {

                throw new IllegalArgumentException(
                        "Truncated protobuf varint."
                );
            }

            int b =
                    data[pos++] & 0xff;

            value |=
                    (long)
                            (b & 0x7f)
                            << shift;

            if ((b & 0x80) == 0) {

                return new Varint(
                        value,
                        pos
                );
            }

            shift += 7;

            if (shift >= 64) {

                throw new IllegalArgumentException(
                        "Invalid protobuf varint."
                );
            }
        }
    }


    private static long readVarint(
            InputStream in)
            throws IOException {

        long result = 0;

        int shift = 0;

        while (true) {

            int b =
                    in.read();

            if (b < 0) {

                throw new EOFException(
                        "Connection closed while " +
                        "reading varint."
                );
            }

            result |=
                    (long)
                            (b & 0x7F)
                            << shift;

            if ((b & 0x80) == 0) {

                return result;
            }

            shift += 7;

            if (shift >= 64) {

                throw new IOException(
                        "Invalid varint."
                );
            }
        }
    }


    // ============================================================
    // KEY / CERTIFICATE
    // ============================================================

    private static void writePrivateKeyPem(
            PrivateKey key,
            Path path)
            throws IOException {

        String base64 =
                Base64.getMimeEncoder(
                        64,
                        "\n".getBytes(
                                StandardCharsets.US_ASCII
                        )
                ).encodeToString(
                        key.getEncoded()
                );

        Files.writeString(
                path,
                "-----BEGIN PRIVATE KEY-----\n" +
                base64 +
                "\n-----END PRIVATE KEY-----\n"
        );
    }


    private static X509Certificate loadCertificate(
            Path path)
            throws Exception {

        try (
                InputStream in =
                        Files.newInputStream(path)
        ) {

            return
                    (X509Certificate)
                            CertificateFactory
                                    .getInstance(
                                            "X.509"
                                    )
                                    .generateCertificate(
                                            in
                                    );
        }
    }


    // ============================================================
    // RSA
    // ============================================================

    private static byte[] unsignedBytes(
            java.math.BigInteger value) {

        byte[] bytes =
                value.toByteArray();

        if (bytes.length > 1 &&
                bytes[0] == 0) {

            return Arrays.copyOfRange(
                    bytes,
                    1,
                    bytes.length
            );
        }

        return bytes;
    }


    // ============================================================
    // PIN
    // ============================================================

    private static void validatePin(
            String pin) {

        if (!pin.matches(
                "[0-9A-F]{6}"
        )) {

            throw new IllegalArgumentException(
                    "PIN must be exactly " +
                    "6 hexadecimal characters."
            );
        }
    }


    // ============================================================
    // HEX
    // ============================================================

    private static byte[] hexToBytes(
            String value) {

        if ((value.length() & 1) != 0) {

            throw new IllegalArgumentException(
                    "Odd hexadecimal length."
            );
        }

        byte[] result =
                new byte[value.length() / 2];

        for (int i = 0;
             i < result.length;
             i++) {

            result[i] =
                    (byte)
                            Integer.parseInt(
                                    value.substring(
                                            i * 2,
                                            i * 2 + 2
                                    ),
                                    16
                            );
        }

        return result;
    }


    private static String sha256Hex(
            byte[] data)
            throws Exception {

        return hex(
                MessageDigest
                        .getInstance("SHA-256")
                        .digest(data)
        );
    }


    private static String hex(
            byte[] data) {

        StringBuilder sb =
                new StringBuilder(
                        data.length * 2
                );

        for (byte b : data) {

            sb.append(
                    String.format(
                            Locale.ROOT,
                            "%02x",
                            b & 0xff
                    )
            );
        }

        return sb.toString();
    }
}
