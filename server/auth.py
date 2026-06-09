import threading

import bcrypt
import hashlib
import time
import hmac
from enum import Enum
from dotenv import load_dotenv
import os
import threading

from . import storage
from . import uids
from .user_data import UserData
load_dotenv()

# Config -------------------------------

PASSWORD_ENCODING = 'utf-8'
HASHING_SECRET: str = os.getenv('HASHING_SECRET')
if HASHING_SECRET is None: raise Exception("Please set the HASHING_SECRET environment variable (random secret key for hash operations)")

# Globals
mutex = threading.RLock()

# Classes ------------------------------
class User(storage.Savable):
    def __init__(self, uid: str = None, auth_types: list[str] = None, hashed_username: str = None, hashed_password: str = None, should_be_saved_to_disk: bool = True):
        super().__init__()
        self.uid: str = uid
        self.hashed_username: str = hashed_username
        self.hashed_password: str = hashed_password
        self.auth_types: list[str] = auth_types
        self.user_data: UserData = UserData()
        self.should_be_saved_to_disk: bool = should_be_saved_to_disk

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
        self.should_be_saved_to_disk = True


class AccessToken:
    def __init__(self, access_token: str, user_uid: str, expires_at: float):
        self.access_token_key = access_token
        self.user_uid = user_uid
        self.expires_at = expires_at

class RegistrationToken(storage.Savable):
    def __init__(self, registration_token: str, uses_allowed: int, auth_types: list[str]):
        super().__init__()
        self.token_key = registration_token
        self.uses_remaining = uses_allowed
        self.auth_types = auth_types

    def category(self) -> str:
        return 'registration_token'

    def id(self) -> str:
        return self.token_key

    def serialize(self) -> dict:
        return {
            'token_key': self.token_key,
            'uses_remaining': self.uses_remaining,
            'auth_types': self.auth_types
        }

    def deserialize(self, data: dict):
        self.token_key = data['token_key']
        self.uses_remaining = int(data['uses_remaining'])
        self.auth_types = data['auth_types']


class ExpiredAccessTokenException(Exception):
    pass

class InvalidAccessTokenException(Exception):
    pass

# Globals ------------------------------
_users_by_uid: dict[str, User] = {}
_user_uid_by_hashed_username: dict[str, str] = {}
_access_tokens: dict[str, AccessToken] = {}
_registration_tokens: dict[str, RegistrationToken] = {}

def hash_plaintext(plaintext: str) -> str:
    return hmac.new(HASHING_SECRET.encode(), plaintext.encode(), hashlib.sha256).hexdigest()

def get_user(plaintext_username: str) -> User | None:
    with mutex:
        hashed_username = hash_plaintext(plaintext_username)

        if hashed_username in _user_uid_by_hashed_username:
            uid = _user_uid_by_hashed_username[hashed_username]
            try:
                return _users_by_uid[uid]
            except KeyError:
                raise Exception(f"_user_uid_by_hashed_username references the UID of {uid} which doesn't exist in the users table")
        else: return None

def add_user(plaintext_username: str, plaintext_password: str, auth_types: list[str], should_be_saved_to_disk: bool = True) -> User:
    with mutex:
        uid = uids.generate_uid(list(_users_by_uid.keys()))

        hashed_username = hash_plaintext(plaintext_username)
        hashed_password = bcrypt.hashpw(plaintext_password.encode(PASSWORD_ENCODING), bcrypt.gensalt()).decode(PASSWORD_ENCODING)
        user = User(uid=uid,
                    auth_types=auth_types,
                    hashed_username=hashed_username,
                    hashed_password=hashed_password,
                    should_be_saved_to_disk=should_be_saved_to_disk)
        _users_by_uid[uid] = user
        _user_uid_by_hashed_username[hashed_username] = uid
        return user

def delete_user(uid: str):
    with mutex:
        user = _users_by_uid.pop(uid)
        storage.delete_serializable_object_data(user)
        _user_uid_by_hashed_username.pop(user.hashed_username)


def check_password(user: User, plaintext_password: str) -> bool:
    with mutex:
        return bcrypt.checkpw(plaintext_password.encode(PASSWORD_ENCODING), user.hashed_password.encode(PASSWORD_ENCODING))

def generate_registration_token(uses_allowed: int, auth_types: list[str], forced_token_key: str | None) -> RegistrationToken:
    with mutex:
        if forced_token_key is None:
            forced_token_key = uids.generate_uid(list(_registration_tokens.keys()))
        new_token = RegistrationToken(
            registration_token=forced_token_key,
            uses_allowed=uses_allowed,
            auth_types=auth_types)
        _registration_tokens[new_token.token_key] = new_token
        return new_token

def delete_registration_token(token_key: str):
    with mutex:
        if token_key in _registration_tokens:
            storage.delete_serializable_object_data(_registration_tokens[token_key])
            del _registration_tokens[token_key]
        else:
            raise KeyError

def list_registration_tokens() -> list[RegistrationToken]:
    with mutex:
        return list(_registration_tokens.values())

def list_users() -> list[User]:
    with mutex:
        return list(_users_by_uid.values())

class RegisterUserErrorType(Enum):
    InvalidRegistrationToken = 0
    UsernameTaken = 1
    UnhandledException = 2

def try_consume_registration_token_and_create_user(token_key: str, requested_username: str, plaintext_password: str) -> User | RegisterUserErrorType:
    with mutex:
        token = _registration_tokens.get(token_key)
        if token is None:
            return RegisterUserErrorType.InvalidRegistrationToken

        hashed_requested_username = hash_plaintext(requested_username)
        if hashed_requested_username in _user_uid_by_hashed_username.keys():
            return RegisterUserErrorType.UsernameTaken
        try:
            new_user = add_user(
                plaintext_username=requested_username,
                plaintext_password=plaintext_password,
                auth_types=token.auth_types)
        except:
            return RegisterUserErrorType.UnhandledException

        _registration_tokens.pop(token_key, None)
        return new_user

def generate_access_token(user_uid: str, expires_at: float) -> AccessToken:
    with mutex:
        access_token_string = uids.generate_uid(list(_access_tokens.keys()))
        access_token = AccessToken(access_token_string, user_uid, expires_at)
        _access_tokens[access_token_string] = access_token
        return access_token

def get_access_token_user(access_token_string: str | None) -> User:
    with mutex:
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
    with mutex:
        for token in list(_access_tokens.values()):
            if token.expires_at < time.time():
                _access_tokens.pop(token.access_token_key, None)

def save():
    with mutex:
        for user in list_users():
            if user.should_be_saved_to_disk:
                storage.save_serializable_object(user)
        for registration_token in list_registration_tokens():
            storage.save_serializable_object(registration_token)
def load():
    with mutex:
        for user in storage.load_all_objects_of_category('user', User):
            _users_by_uid[user.uid] = user
            _user_uid_by_hashed_username[user.hashed_username] = user.uid
        for registration_token in storage.load_all_objects_of_category('registration_token', RegistrationToken):
            _registration_tokens[registration_token.token_key] = registration_token

if __name__ == "__main__":
    user = add_user(plaintext_username="test", plaintext_password="password", auth_types=["user", "admin"])
    storage.save_serializable_object(user)