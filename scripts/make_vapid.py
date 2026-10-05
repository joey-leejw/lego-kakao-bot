"""웹푸시 발송용 VAPID 키 한 쌍 만들기 (최초 1회, 내 컴퓨터에서 실행)

  pip install cryptography
  python make_vapid.py

출력된 두 값을 GitHub에 저장:
  VAPID_PUBLIC_KEY  → Variables (공개해도 되는 값)
  VAPID_PRIVATE_KEY → Secrets   (절대 공개 금지)
"""
import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def b64e(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


key = ec.generate_private_key(ec.SECP256R1())
priv = key.private_numbers().private_value.to_bytes(32, "big")
pub = key.public_key().public_bytes(serialization.Encoding.X962,
                                    serialization.PublicFormat.UncompressedPoint)
print("\nVAPID_PUBLIC_KEY  =", b64e(pub))
print("VAPID_PRIVATE_KEY =", b64e(priv))
print("\n※ 한 번 정하면 바꾸지 마세요. 바꾸면 기존 구독자에게 알림이 안 갑니다.")
