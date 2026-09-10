from itsdangerous import BadSignature, URLSafeTimedSerializer

COOKIE_NAME = "mesh_session"
MAX_AGE_SECONDS = 8 * 3600


def _serializer(secret: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret, salt="mesh-scheduler-session")


def sign(secret: str, payload: dict) -> str:
    return _serializer(secret).dumps(payload)


def unsign(secret: str, token: str) -> dict | None:
    try:
        return _serializer(secret).loads(token, max_age=MAX_AGE_SECONDS)
    except BadSignature:
        return None
