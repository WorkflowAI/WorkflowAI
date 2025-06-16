from typing import Generator
from unittest.mock import Mock

import pytest
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePublicKey
from freezegun import freeze_time
from pytest_httpx import HTTPXMock

from api.dependencies.security import UserClaims
from core.domain.users import User

from .keys import Claims, InvalidToken, JWTHeader, KeyRing, verify_signature

pytestmark = pytest.mark.httpx_mock(assert_all_responses_were_requested=False)


@pytest.fixture(scope="function")
def mock_client(httpx_mock: HTTPXMock) -> Generator[HTTPXMock, None, None]:
    httpx_mock.add_response(
        url="https://example.com/jwks",
        json={
            "keys": [
                {
                    "kty": "EC",
                    "x": "KUJYc7vWDxRny5nAt-U4b80thCVnhDTL0sRfAF4vp7U",
                    "y": "34uluT82ODEDRWUOJ4Lkg1ijycrXj1g52fQnZjxW9q0",
                    "crv": "P-256",
                    "id": "1",
                },
            ],
        },
    )
    yield httpx_mock


@freeze_time("2024-05-22T12:00:00")
async def test_verify_token(mock_client: HTTPXMock) -> None:
    token = "eyJhbGciOiJFUzI1NiJ9.eyJ0ZW5hbnQiOiJoZWxsby5jb20iLCJzdWIiOiJoZWxsb0BoZWxsby5jb20iLCJpYXQiOjE3MTM5OTA2NDEsImV4cCI6MTcxOTE3NDY0MX0.pxG-M8aas3i7yFI-DjhCS_0BCcHITwVUMjnu7ev87rEV5H-JvnJLhgTSbqI8N6Z9Kn5wSIRksa2W4UyU1CG5eA"

    ring = KeyRing("https://example.com/jwks")

    claims = await ring.verify(token, returns=UserClaims)
    assert claims.tenant == "hello.com"


@freeze_time("2024-05-22T12:00:00")
async def test_verity_anon_token(mock_client: HTTPXMock):
    token = "eyJhbGciOiJFUzI1NiJ9.eyJ1bmtub3duVXNlcklkIjoiOGM5NGQ1MjMtZGE2YS00MDg5LWIxZDMtMzRhM2ZmYmNlNDg0IiwiaWF0IjoxNjI4NzA3ODQ2LCJleHAiOjE4OTEyNDM4NDZ9.n4DJt-4H_3-u_3KBRQvT_xwDQb2ogBtAFhByBDYeEtqblp4auz6okicNeJygfowgIJfNYAGDr7FH1e37qQkuDg"
    ring = KeyRing("https://example.com/jwks")

    claims = await ring.verify(token, returns=UserClaims)
    assert claims.tenant is None
    assert claims.unknown_user_id == "8c94d523-da6a-4089-b1d3-34a3ffbce484"
    assert claims.to_domain() == User(
        tenant=None,
        sub="8c94d523-da6a-4089-b1d3-34a3ffbce484",
        unknown_user_id="8c94d523-da6a-4089-b1d3-34a3ffbce484",
    )


# token expires in june
@freeze_time("2024-09-22T12:00:00")
async def test_verify_token_expired(mock_client: HTTPXMock) -> None:
    token = "eyJhbGciOiJFUzI1NiJ9.eyJ0ZW5hbnQiOiJoZWxsby5jb20iLCJzdWIiOiJoZWxsb0BoZWxsby5jb20iLCJpYXQiOjE3MTM5OTA2NDEsImV4cCI6MTcxOTE3NDY0MX0.pxG-M8aas3i7yFI-DjhCS_0BCcHITwVUMjnu7ev87rEV5H-JvnJLhgTSbqI8N6Z9Kn5wSIRksa2W4UyU1CG5eA"

    ring = KeyRing("https://example.com/jwks")

    with pytest.raises(InvalidToken) as e:
        await ring.verify(token, returns=Claims)

    assert str(e.value) == "Token expired"


@pytest.fixture(scope="function")
def public_key() -> EllipticCurvePublicKey:
    key = """-----BEGIN PRIVATE KEY-----
MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgselKFg5Ve0M3/1/X
NR8jT8pC+bqWeLi8ohVBJOJ+YCuhRANCAAQpQlhzu9YPFGfLmcC35ThvzS2EJWeE
NMvSxF8AXi+ntd+Lpbk/NjgxA0VlDieC5INYo8nK149YOdn0J2Y8Vvat
-----END PRIVATE KEY-----"""
    private_key = serialization.load_pem_private_key(
        key.encode(),
        password=None,
        backend=default_backend(),
    )
    return private_key.public_key()  # type:ignore


async def test_verify_signature(public_key: EllipticCurvePublicKey) -> None:
    payload = bytes.fromhex(
        "2e53585469674a6c7a494745675a4746755a3256796233567a49474a3163326c755a584e7a4c434247636d396b627977675a323970626d63676233563049486c76645849675a473976636934",
    )
    raw_signature = bytes.fromhex(
        "fd4a10ce6daec11803d49afc810d753882e73825b3cf8f60f16f52a897f63795faf993c81af76bf84af35a5feb42b4cbd48100ab63cd4853e59a6598d7af9403",
    )

    verify_signature(
        payload,
        signature=raw_signature,
        key=public_key,
    )


async def test_invalid_header() -> None:
    token = "header=eyJhbGciOiJFUzI1NiJ9.eyJ0ZW5hbnQiOiJoZWxsby5jb20iLCJzdWIiOiJoZWxsb0BoZWxsby5jb20iLCJpYXQiOjE3MTM5OTA2NDEsImV4cCI6MTcxOTE3NDY0MX0.pxG-M8aas3i7yFI-DjhCS_0BCcHITwVUMjnu7ev87rEV5H-JvnJLhgTSbqI8N6Z9Kn5wSIRksa2W4UyU1CG5eA"

    ring = KeyRing("https://example.com/jwks")
    with pytest.raises(InvalidToken):
        await ring.verify(token, returns=Claims)


@pytest.mark.parametrize(
    "token",
    [
        # invalid signature
        "eyJhbGciOiJFUzI1NiJ9.eyJ0ZW5hbnQiOiJoZWxsby5jb20iLCJzdWIiOiJoZWxsb0BoZWxsby5jb20iLCJpYXQiOjE3MTM5OTA2NDEsImV4cCI6MTcxOTE3NDY0MX0.pxG-M8aas3i7yFI-DjhCS_0BCcHITwVUMjnu7ev87rEV5H-JvnJLhgTSbqI8N6Z9Kn5wSIRksa2W4UyU1CG5e",
        # invalid claim
        "eyJhbGciOiJFUzI1NiJ9.eyJ0ZW5hbnQiOiJoZWxsby5jb20iLCJzdWIiOiJoZWxsb0BoZWxsby5jb20iLCJpYXQiOjE3MTM5OTA2NDEsImV4cCI6MTxOTE3NDY0MX0.pxG-M8aas3i7yFI-DjhCS_0BCcHITwVUMjnu7ev87rEV5H-JvnJLhgTSbqI8N6Z9Kn5wSIRksa2W4UyU1CG5eA",
    ],
)
async def test_verify_invalid_b64(mock_client: HTTPXMock, token: str) -> None:
    ring = KeyRing("https://example.com/jwks")

    with pytest.raises(InvalidToken):
        await ring.verify(token, returns=Claims)


class TestGetKey:
    @pytest.fixture(scope="function")
    def mock_key(self):
        return Mock()

    @pytest.fixture(scope="function")
    def key_ring(self, mock_key: EllipticCurvePublicKey):
        ring = KeyRing("https://example.com/jwks")
        ring._logger = Mock()  # pyright: ignore [reportPrivateUsage]
        ring.key_cache = {"1": mock_key}
        return ring

    async def test_get_key_in_cache(self, key_ring: KeyRing, httpx_mock: HTTPXMock, mock_key: Mock) -> None:
        header = JWTHeader(
            alg="ES256",
            kid="1",
        )

        key = await key_ring._get_key(header)  # pyright: ignore [reportPrivateUsage]
        assert key is not None
        assert key == mock_key
        assert len(httpx_mock.get_requests()) == 0

    async def test_get_key_not_in_cache(self, key_ring: KeyRing, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://example.com/jwks",
            json={
                "keys": [
                    {
                        "kty": "EC",
                        "x": "KUJYc7vWDxRny5nAt-U4b80thCVnhDTL0sRfAF4vp7U",
                        "y": "34uluT82ODEDRWUOJ4Lkg1ijycrXj1g52fQnZjxW9q0",
                        "crv": "P-256",
                        "id": "2",
                    },
                ],
            },
        )

        header = JWTHeader(
            alg="ES256",
            kid="2",
        )

        key = await key_ring._get_key(header)  # pyright: ignore [reportPrivateUsage]
        assert isinstance(key, EllipticCurvePublicKey)
        assert len(httpx_mock.get_requests()) == 1

    async def test_get_key_failed(self, key_ring: KeyRing, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(url="https://example.com/jwks", status_code=404)

        header = JWTHeader(alg="ES256", kid="2")

        with pytest.raises(ValueError) as e:
            await key_ring._get_key(header)  # pyright: ignore [reportPrivateUsage]

        assert str(e.value) == "Kid 2 not available, Available key ids: ['1']"

        # Check that the key ring still has the old key
        assert await key_ring._get_key(header=JWTHeader(alg="ES256", kid="1"))  # pyright: ignore [reportPrivateUsage]

    async def test_get_key_empty(self, key_ring: KeyRing, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(url="https://example.com/jwks", json={"keys": []})

        header = JWTHeader(alg="ES256", kid="2")

        with pytest.raises(ValueError) as e:
            await key_ring._get_key(header)  # pyright: ignore [reportPrivateUsage]

        assert str(e.value) == "Kid 2 not available, Available key ids: ['1']"

        # Check that the key ring still has the old key
        assert await key_ring._get_key(header=JWTHeader(alg="ES256", kid="1"))  # pyright: ignore [reportPrivateUsage]
