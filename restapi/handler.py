from abc import ABC, abstractmethod
from http.server import BaseHTTPRequestHandler
from enum import Enum

from restapi import auth

LOGIN_ENDPOINT = "/login"
MAX_BODY_SIZE = 128 * 1024

class AuthFailureResponse(Enum):
    AlwaysAllowed = 0
    RedirectToLogin = 1,
    Unauthorized = 2

class Handler(BaseHTTPRequestHandler):
    def do(self, method: str):
        if self.path in endpoints:
            function = endpoints[self.path]
            access_token = self.request.headers.get("Access-Token")
            try:
                user = auth.get_access_token_user(access_token)
            except auth.ExpiredAccessTokenException or auth.InvalidAccessTokenException:
                if function.on_auth_failure() == AuthFailureResponse.Unauthorized:
                    self.send_response(401)
                    return
                elif function.on_auth_failure() == AuthFailureResponse.RedirectToLogin:
                    self.send_response(302)
                    self.send_header("Location", f"{LOGIN_ENDPOINT}?redirect={self.path}")
                    return
                elif function.on_auth_failure() == AuthFailureResponse.AlwaysAllowed:
                    user = None
            try:
                content_length = int(self.headers.get("Content-Length"))
                if content_length > MAX_BODY_SIZE:
                    raise Exception(f"Content length {content_length} exceeds 128KB")
                body = self.rfile.read(content_length)
            except Exception:
                self.send_response(400)

            function.execute(self, body, method, user)
        else:
            self.send_response(404)
        self.end_headers()

    def do_GET(self):
        self.do('GET')

    def do_POST(self):
        self.do('POST')

    def do_DELETE(self):
        self.do('DELETE')

    def do_PUT(self):
        self.do('PUT')

class APIFunction(ABC):
    def __init__(self):
        pass

    @abstractmethod
    def endpoints(self, handler: Handler, function: str) -> list[str]: ...

    @abstractmethod
    def auth_types_allowed(self) -> list[str]: ...

    @abstractmethod
    def on_auth_failure(self) -> AuthFailureResponse: ...

    @abstractmethod
    def execute(self, handler: Handler, body: bytes, method: str, user: auth.User): ...

endpoints: dict[str, APIFunction] = {}

def register_endpoint(endpoint: str, function: APIFunction):
    if endpoint in endpoints:
        raise Exception(f"Endpoint {endpoint} already registered")
    endpoints[endpoint] = function