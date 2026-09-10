from app.security import otp


def test_generate_code_is_six_digits():
    code = otp.generate_code()
    assert len(code) == 6
    assert code.isdigit()


def test_generate_code_zero_padded(monkeypatch):
    monkeypatch.setattr(otp.secrets, "randbelow", lambda _: 42)
    assert otp.generate_code() == "000042"


def test_hash_then_verify_roundtrip():
    code = "042817"
    hashed = otp.hash_code(code)
    assert hashed != code
    assert otp.verify_code(code, hashed) is True


def test_verify_rejects_wrong_code():
    hashed = otp.hash_code("111111")
    assert otp.verify_code("222222", hashed) is False
