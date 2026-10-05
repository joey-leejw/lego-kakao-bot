"""웹푸시 발송 최소 구현 (RFC 8291 aes128gcm 암호화 + RFC 8292 VAPID).
외부 라이브러리는 cryptography 하나만 사용.
"""
import base64
import hashlib
import hmac
import json
import os
import struct
import time
import urllib.error
import urllib.parse
import urllib.request

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def b64d(s: str) -> bytes:
    s = s.strip()
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _hmac(key, data):
    return hmac.new(key, data, hashlib.sha256).digest()


def _pub_bytes(pub) -> bytes:
    return pub.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)


def load_private_key(raw_b64: str):
    """VAPID 개인키(32바이트 base64url) → 키 객체"""
    return ec.derive_private_key(int.from_bytes(b64d(raw_b64), "big"), ec.SECP256R1())


def encrypt(payload: bytes, p256dh: str, auth: str, salt: bytes = None, as_key=None) -> bytes:
    ua_pub_bytes = b64d(p256dh)
    auth_secret = b64d(auth)
    ua_pub = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_pub_bytes)
    as_key = as_key or ec.generate_private_key(ec.SECP256R1())
    as_pub_bytes = _pub_bytes(as_key.public_key())
    shared = as_key.exchange(ec.ECDH(), ua_pub)
    prk_key = _hmac(auth_secret, shared)
    ikm = _hmac(prk_key, b"WebPush: info\x00" + ua_pub_bytes + as_pub_bytes + b"\x01")
    salt = salt or os.urandom(16)
    prk = _hmac(salt, ikm)
    cek = _hmac(prk, b"Content-Encoding: aes128gcm\x00\x01")[:16]
    nonce = _hmac(prk, b"Content-Encoding: nonce\x00\x01")[:12]
    ciphertext = AESGCM(cek).encrypt(nonce, payload + b"\x02", None)
    header = salt + struct.pack("!I", 4096) + bytes([len(as_pub_bytes)]) + as_pub_bytes
    return header + ciphertext


def vapid_header(endpoint: str, private_key, public_b64: str, subject: str) -> str:
    u = urllib.parse.urlparse(endpoint)
    claims = {"aud": f"{u.scheme}://{u.netloc}", "exp": int(time.time()) + 12 * 3600, "sub": subject}
    signing_input = (b64e(json.dumps({"typ": "JWT", "alg": "ES256"}).encode()) + "." +
                     b64e(json.dumps(claims, separators=(",", ":")).encode()))
    der = private_key.sign(signing_input.encode(), ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    jwt = signing_input + "." + b64e(r.to_bytes(32, "big") + s.to_bytes(32, "big"))
    return f"vapid t={jwt}, k={public_b64}"


def send(sub: dict, data: dict, private_key, public_b64: str, subject: str, ttl: int = 43200) -> int:
    """sub = {endpoint, p256dh, auth}. 성공/실패 HTTP 상태코드를 돌려준다."""
    body = encrypt(json.dumps(data, ensure_ascii=False).encode(), sub["p256dh"], sub["auth"])
    req = urllib.request.Request(sub["endpoint"], data=body, method="POST", headers={
        "Content-Encoding": "aes128gcm",
        "Content-Type": "application/octet-stream",
        "TTL": str(ttl),
        "Urgency": "normal",
        "Authorization": vapid_header(sub["endpoint"], private_key, public_b64, subject),
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0
