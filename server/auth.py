import bcrypt
import hashlib
import time
import hmac
from dotenv import load_dotenv
import os

from server.user_data import UserData
from . import storage
from . import uids
from .user_data import UserData
load_dotenv()

# Config -------------------------------

PASSWORD_ENCODING = 'utf-8'
HASHING_SECRET: str = os.getenv('HASHING_SECRET')
if HASHING_SECRET is None:
    print("HASHING_SECRET environment variable not set, usernames will not be secure")
    HASHING_SECRET = "xiWah4LieLo9zei0caegadaequ4aech5ath0cux4mi5ua7kaekue4loliCe7eing4Ma0Aim4ar6ahMiej4mo8hago1ohg9ax5Eeg6airao4PhoBauquoK3Sai5theele"


# Classes ------------------------------
class User(storage.Savable):
    def __init__(self, uid: str = None, auth_types: list[str] = None, hashed_username: str = None, hashed_password: str = None):
        super().__init__()
        self.uid: str = uid
        self.hashed_username: str = hashed_username
        self.hashed_password: str = hashed_password
        self.auth_types: list[str] = auth_types
        self.user_data: UserData = UserData()

    def category(self) -> str: return "user"

    def id(self) -> str: return self.uid

    def serialize(self) -> dict:
        return {
            "uid": self.uid,
            "auth_types": self.auth_types,
            "hashed_username": self.hashed_username,
            "hashed_password": self.hashed_password,
            "user_data": self.user_data.serialize(),
        }

    def deserialize(self, data: dict):
        self.uid = data["uid"]
        self.auth_types = data["auth_types"]
        self.hashed_username = data["hashed_username"]
        self.hashed_password = data["hashed_password"]
        user_data = UserData()
        user_data.deserialize(data["user_data"])
        self.user_data = user_data

class AccessToken:
    def __init__(self, access_token: str, user_uid: str, expires_at: float):
        self.access_token_key = access_token
        self.user_uid = user_uid
        self.expires_at = expires_at

class ExpiredAccessTokenException(Exception):
    pass

class InvalidAccessTokenException(Exception):
    pass

# Globals ------------------------------
_users_by_uid: dict[str, User] = {}
_user_uid_by_hashed_username: dict[str, str] = {}
_access_tokens: dict[str, AccessToken] = {}

def hash_plaintext_username(plaintext_username: str) -> str:
    return hmac.new(HASHING_SECRET.encode(), plaintext_username.encode(), hashlib.sha256).hexdigest()

def get_user(plaintext_username: str) -> User:
    hashed_username = hash_plaintext_username(plaintext_username)

    if hashed_username in _user_uid_by_hashed_username:
        uid = _user_uid_by_hashed_username[hashed_username]
        try:
            return _users_by_uid[uid]
        except KeyError:
            raise Exception(f"_user_uid_by_hashed_username references the UID of {uid} which doesn't exist in the users table")
    else: return None

def add_user(plaintext_username: str, plaintext_password: str, auth_types: list[str]) -> User:
    hashed_username = hash_plaintext_username(plaintext_username)
    hashed_password = bcrypt.hashpw(plaintext_password.encode(PASSWORD_ENCODING), bcrypt.gensalt()).decode(PASSWORD_ENCODING)
    uid = uids.generate_uid(list(_users_by_uid.keys()))
    user = User(uid, auth_types, hashed_username, hashed_password)
    _users_by_uid[uid] = user
    _user_uid_by_hashed_username[hashed_username] = uid
    return user

def delete_user(uid: str):
    user = _users_by_uid.pop(uid)
    _user_uid_by_hashed_username.pop(user.hashed_username)

def check_password(user: User, plaintext_password: str) -> bool:
    return bcrypt.checkpw(plaintext_password.encode(PASSWORD_ENCODING), user.hashed_password.encode(PASSWORD_ENCODING))

def generate_access_token(user_uid: str, expires_at: float) -> AccessToken:
    access_token_string = uids.generate_uid(list(_access_tokens.keys()))
    access_token = AccessToken(access_token_string, user_uid, expires_at)
    _access_tokens[access_token_string] = access_token
    return access_token

def get_access_token_user(access_token_string: str | None) -> User:
    if access_token_string is None:
        raise InvalidAccessTokenException(f"The access token is not valid")
    if access_token_string in _access_tokens:
        access_token = _access_tokens[access_token_string]
        if access_token.expires_at > time.time():
            user = _users_by_uid[access_token.user_uid]
            return user
        else: raise ExpiredAccessTokenException(f"The access token has expired")
    else: raise InvalidAccessTokenException(f"The access token is not valid")

def routine_cleanup():
    for token in list(_access_tokens.values()):
        if token.expires_at < time.time():
            _access_tokens.pop(token.access_token_key, None)

if __name__ == "__main__":
    user = add_user(plaintext_username="test", plaintext_password="password", auth_types=["user", "admin"])
    storage.save_serializable_object(user)