from abc import ABC, abstractmethod
from http.server import BaseHTTPRequestHandler
from enum import Enum

from server import auth

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

            if method == "OPTIONS":
                origin = self.headers.get("Origin")
                requested_method = self.headers.get("Access-Control-Request-Method")
                if origin is None or requested_method is None:
                    self.send_response(400)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Allow", function.allowed_methods())
                self.end_headers()
                return

            access_token = self.headers.get("Access-Token")
            if access_token is None and function.on_auth_failure() != AuthFailureResponse.AlwaysAllowed:
                self.send_response(401)
                self.end_headers()
                return
            try:
                user = auth.get_access_token_user(access_token)
                authorized = False
                for potential_auth_type in function.auth_types_allowed():
                    if potential_auth_type in user.auth_types:
                        authorized = True
                        break
                if not authorized: raise auth.InvalidAccessTokenException
            except (auth.ExpiredAccessTokenException, auth.InvalidAccessTokenException):
                if function.on_auth_failure() == AuthFailureResponse.Unauthorized:
                    self.send_response(401)
                    self.end_headers()
                    return
                elif function.on_auth_failure() == AuthFailureResponse.RedirectToLogin:
                    self.send_response(302)
                    self.send_header("Location", f"{LOGIN_ENDPOINT}?redirect={self.path}")
                    self.end_headers()
                    return
                elif function.on_auth_failure() == AuthFailureResponse.AlwaysAllowed:
                    user = None
                else: raise NotImplementedError()

            try:
                content_length_str = self.headers.get("Content-Length")
                if content_length_str is None:
                    content_length = 0
                else:
                    content_length = int(content_length_str)
                if content_length > MAX_BODY_SIZE:
                    raise Exception(f"Content length {content_length} exceeds 128KB")
                body = self.rfile.read(content_length)
            except Exception:
                self.send_response(400)
                self.end_headers()
                return

            function.execute(self, body, method, user)
        else:
            self.send_response(404)
            self.end_headers()
            return

    def do_GET(self):
        self.do('GET')

    def do_POST(self):
        self.do('POST')

    def do_DELETE(self):
        self.do('DELETE')

    def do_PUT(self):
        self.do('PUT')

    def do_OPTIONS(self):
        self.do('OPTIONS')

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()
        return

class APIFunction(ABC):
    def __init__(self):
        pass

    @abstractmethod
    def endpoints(self) -> list[str]: ...

    @abstractmethod
    def auth_types_allowed(self) -> list[str]: ...

    @abstractmethod
    def on_auth_failure(self) -> AuthFailureResponse: ...

    @abstractmethod
    def execute(self, handler: Handler, body: bytes, method: str, user: auth.User): ...

    @abstractmethod
    def allowed_methods(self): ...


endpoints: dict[str, APIFunction] = {}

def register_endpoint(endpoint: str, function: APIFunction):
    if endpoint in endpoints:
        raise Exception(f"Endpoint {endpoint} already registered")
    endpoints[endpoint] = function