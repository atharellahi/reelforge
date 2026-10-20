"""Hand-signed S3 PUT (AWS Signature V4). No SDK: the SDK pulls in dozens of
packages for one request, and this is one request."""
import datetime
import hashlib
import hmac
import urllib.parse

import requests


def _sign(key, msg):
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def put_object(bucket, region, access_key, secret_key, key, body, content_type="video/mp4",
               cache_control="public, max-age=31536000, immutable"):
    host = f"{bucket}.s3.{region}.amazonaws.com"
    now = datetime.datetime.utcnow()
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date = now.strftime("%Y%m%d")
    payload_hash = hashlib.sha256(body).hexdigest()
    canonical_uri = "/" + urllib.parse.quote(key, safe="/-_.~")
    headers = {
        "host": host, "x-amz-content-sha256": payload_hash, "x-amz-date": amz_date,
        "content-type": content_type, "cache-control": cache_control,
    }
    signed = ";".join(sorted(headers))
    canonical_headers = "".join(f"{k}:{headers[k].strip()}\n" for k in sorted(headers))
    canonical_request = "\n".join(["PUT", canonical_uri, "", canonical_headers, signed, payload_hash])
    scope = f"{date}/{region}/s3/aws4_request"
    string_to_sign = "\n".join(["AWS4-HMAC-SHA256", amz_date, scope,
                                hashlib.sha256(canonical_request.encode()).hexdigest()])
    k = _sign(("AWS4" + secret_key).encode(), date)
    k = _sign(k, region); k = _sign(k, "s3"); k = _sign(k, "aws4_request")
    signature = hmac.new(k, string_to_sign.encode(), hashlib.sha256).hexdigest()
    auth = (f"AWS4-HMAC-SHA256 Credential={access_key}/{scope}, "
            f"SignedHeaders={signed}, Signature={signature}")
    h = {"Authorization": auth, "x-amz-date": amz_date, "x-amz-content-sha256": payload_hash,
         "Content-Type": content_type, "Cache-Control": cache_control}
    r = requests.put(f"https://{host}{canonical_uri}", data=body, headers=h, timeout=300)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"S3 PUT {r.status_code}: {r.text[:300]}")
    return f"https://{host}{canonical_uri}"
