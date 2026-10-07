"""Only the exact local disposable schema may be seeded; no network/DB imports."""
from urllib.parse import urlsplit, unquote, parse_qs


def assert_ephemeral_target(env):
    if env.get("APP_ENV") != "test" or env.get("DEPLOYMENT_MODE") != "local":
        raise ValueError("capacity seed requires APP_ENV=test and DEPLOYMENT_MODE=local")
    if env.get("CAPACITY_EPHEMERAL_ACK") != "student_lifecycle_test":
        raise ValueError("explicit CAPACITY_EPHEMERAL_ACK=student_lifecycle_test required")
    raw=env.get("DATABASE_URL", "")
    if not raw or raw != env.get("TEST_DATABASE_URL"):
        raise ValueError("DATABASE_URL must equal the explicit TEST_DATABASE_URL")
    try:
        url=urlsplit(raw)
        valid=(url.scheme == "mysql+pymysql" and url.hostname in {"127.0.0.1", "localhost", "::1"}
               and url.port in {None,3306} and unquote(url.path)=="/student_lifecycle_test"
               and not url.fragment and set(parse_qs(url.query)).issubset({"charset"}))
    except ValueError:
        valid=False
    if not valid:
        raise ValueError("capacity seed refuses non-local, alternate schema, socket or connection overrides")
    return True
