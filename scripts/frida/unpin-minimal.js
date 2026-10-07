// Minimal SSL pinning bypass - only TrustManagerImpl + OkHttp CertificatePinner
// No reflection-heavy crashy code

setTimeout(function() {
    Java.perform(function() {
        console.log('[*] Minimal unpin loaded');

        // 1. Conscrypt TrustManagerImpl (Android 7+) - the core trust check
        try {
            var TrustManagerImpl = Java.use('com.android.org.conscrypt.TrustManagerImpl');
            TrustManagerImpl.checkTrustedRecursive.implementation = function(certs, ocspData, tlsSctData, host, clientAuth, untrustedChain, trustAnchorChain, used) {
                console.log('[+] TrustManagerImpl bypass: ' + host);
                return Java.use('java.util.ArrayList').$new();
            };
            console.log('[*] Hooked TrustManagerImpl.checkTrustedRecursive');
        } catch (e) {
            console.log('[-] TrustManagerImpl hook failed: ' + e);
        }

        // 2. OkHttp 3 CertificatePinner.check() - direct OkHttp pinning
        try {
            var CertificatePinner = Java.use('okhttp3.CertificatePinner');
            CertificatePinner.check.overload('java.lang.String', 'java.util.List').implementation = function(host, peerCertificates) {
                console.log('[+] OkHttp CertificatePinner.check bypass: ' + host);
                return;
            };
            console.log('[*] Hooked okhttp3.CertificatePinner.check');
        } catch (e) {
            console.log('[-] OkHttp CertificatePinner not found (ok if not used)');
        }

        // 3. OkHttp CertificatePinner.check$okhttp() - newer OkHttp variant
        try {
            var CertificatePinner = Java.use('okhttp3.CertificatePinner');
            var checkOk = CertificatePinner['check$okhttp'];
            if (checkOk) {
                checkOk.implementation = function(host, cleanedPeerCertificatesFn) {
                    console.log('[+] OkHttp CertificatePinner.check$okhttp bypass: ' + host);
                    return;
                };
                console.log('[*] Hooked okhttp3.CertificatePinner.check$okhttp');
            }
        } catch (e) { /* ignore */ }

        // 4. X509TrustManager fallback
        try {
            var X509TrustManager = Java.use('javax.net.ssl.X509TrustManager');
            var SSLContext = Java.use('javax.net.ssl.SSLContext');
            var TrustManager = Java.registerClass({
                name: 'org.local.NoOpTM',
                implements: [X509TrustManager],
                methods: {
                    checkClientTrusted: function() {},
                    checkServerTrusted: function() {},
                    getAcceptedIssuers: function() { return []; }
                }
            });
            console.log('[*] Registered NoOp TrustManager (available for fallback)');
        } catch (e) { /* ignore */ }

        console.log('[*] Minimal unpin ready');
    });
}, 0);
