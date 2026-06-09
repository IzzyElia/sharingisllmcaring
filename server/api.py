import os
import time
import ollama
import json
import asyncio
from dotenv import load_dotenv
import os

from .handler import APIFunction, Handler, AuthFailureResponse
from . import auth, user_data
from .user_data import UserData, Chat

load_dotenv()

_model: str | None = os.getenv("MODEL")
if _model is None: raise Exception("Please set the MODEL environment variable (ollama llm model to use)")

class APICreateRegistrationToken(APIFunction):
    def endpoints(self) -> list[str]:
        return [
            '/api/create_registration_token',
        ]
    def auth_types_allowed(self) -> list[str]:
        return [
            'admin'
        ]
    def on_auth_failure(self) -> AuthFailureResponse:
        return AuthFailureResponse.Unauthorized
    def execute(self, handler: Handler, body: bytes, method: str, user: auth.User):
        try:
            num_allowed_uses = int(handler.headers.get("Registration-Token-Allowed-Uses"))
        except ValueError:
            handler.send_response(400)
            handler.end_headers()
            return

        auth_types = handler.headers.get("Registration-Token-Auth-Types")
        if num_allowed_uses is None or auth_types is None:
            handler.send_response(400)
            handler.end_headers()
            return

        auth_types = [x.strip() for x in auth_types.split(',')]
        auth.generate_registration_token(uses_allowed=num_allowed_uses, auth_types=auth_types)
        handler.send_response(200)
        handler.end_headers()
        return

class APIDeleteRegistrationToken(APIFunction):
    def endpoints(self) -> list[str]:
        return [
            '/api/delete_registration_token',
        ]
    def auth_types_allowed(self) -> list[str]:
        return [
            'admin'
        ]
    def on_auth_failure(self) -> AuthFailureResponse:
        return AuthFailureResponse.Unauthorized
    def execute(self, handler: Handler, body: bytes, method: str, user: auth.User):
        registration_token_key = handler.headers.get("Registration-Token-Key")
        if registration_token_key is None:
            handler.send_response(400)
            handler.end_headers()
            return

        try:
            auth.delete_registration_token(registration_token_key)
        except KeyError:
            handler.send_response(404)
            handler.send_header('API-Error', 'Registration Token Doesn\'t Exist')
            handler.end_headers()
            return

        handler.send_response(200)
        handler.end_headers()
        return

class APIDeleteUser(APIFunction):
    def endpoints(self) -> list[str]:
        return [
            '/api/delete_user',
        ]
    def auth_types_allowed(self) -> list[str]:
        return [
            'admin'
        ]
    def on_auth_failure(self) -> AuthFailureResponse:
        return AuthFailureResponse.Unauthorized
    def execute(self, handler: Handler, body: bytes, method: str, user: auth.User):
        user_uid = handler.headers.get("Delete-User-ID")
        if user_uid is None:
            handler.send_response(400)
            handler.end_headers()
            return

        auth.delete_user(user_uid)
        handler.send_response(200)
        handler.end_headers()
        return

class APIListRegistrationTokens(APIFunction):
    def endpoints(self) -> list[str]:
        return [
            '/api/list_registration_tokens',
        ]
    def auth_types_allowed(self) -> list[str]:
        return [
            'admin'
        ]
    def on_auth_failure(self) -> AuthFailureResponse:
        return AuthFailureResponse.Unauthorized
    def execute(self, handler: Handler, body: bytes, method: str, user: auth.User):
        body_content = {'registration_tokens': [
            {'token_key': t.token_key, 'uses_remaining': t.uses_remaining, 'auth_types': t.auth_types}
            for t in auth.list_registration_tokens()
        ]}
        handler.send_response(200)
        handler.send_header('Content-Type', 'application/json')
        handler.end_headers()
        handler.wfile.write(json.dumps(body_content).encode())
        handler.wfile.flush()
        return

class APIListUsers(APIFunction):
    def endpoints(self) -> list[str]:
        return [
            '/api/list_users',
        ]
    def auth_types_allowed(self) -> list[str]:
        return [
            'admin'
        ]
    def on_auth_failure(self) -> AuthFailureResponse:
        return AuthFailureResponse.Unauthorized
    def execute(self, handler: Handler, body: bytes, method: str, user: auth.User):
        body_content = {'users': [
            {'uid': u.uid, 'auth_types': u.auth_types, 'hashed_username': u.hashed_username}
            for u in auth.list_users()
        ]}
        handler.send_response(200)
        handler.send_header('Content-Type', 'application/json')
        handler.end_headers()
        handler.wfile.write(json.dumps(body_content).encode())
        handler.wfile.flush()
        return


class APIRegister(APIFunction):
    def endpoints(self) -> list[str]:
        return [
            "/api/register",
        ]

    def auth_types_allowed(self) -> list[str]:
        return []

    def on_auth_failure(self) -> AuthFailureResponse:
        return AuthFailureResponse.AlwaysAllowed

    def execute(self, handler: Handler, body: bytes, method: str, user: auth.User):
        registration_token = handler.headers.get("Registration-Token")
        username = handler.headers.get("Registration-Username")
        password = handler.headers.get("Registration-Password")
        if registration_token is None or username is None or password is None:
            handler.send_response(400)
            handler.end_headers()
            return
        user_or_error = auth.try_consume_registration_token_and_create_user(
            token_key=registration_token,
            requested_username=username,
            plaintext_password=password
        )
        if isinstance(user_or_error, auth.User):
            user: auth.User = user_or_error
            access_token = auth.generate_access_token(user.uid, expires_at=time.time()+600*60)
            handler.send_response(200)
            handler.send_header("Content-Type", "application/json")
            handler.send_header('Access-Token', access_token.access_token_key)
            handler.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            handler.send_header('Pragma', 'no-cache')
            handler.end_headers()
            return
        elif isinstance(user_or_error, auth.RegisterUserErrorType):
            if user_or_error == auth.RegisterUserErrorType.UsernameTaken:
                handler.send_response(400)
                handler.end_headers()
                return
            elif user_or_error == auth.RegisterUserErrorType.InvalidRegistrationToken:
                handler.send_response(401)
                handler.end_headers()
                return
            else:
                handler.send_response(500)
                handler.end_headers()
                return
            return


class APILogin(APIFunction):
    def endpoints(self) -> list[str]:
        return [
            "/api/login",
        ]

    def auth_types_allowed(self) -> list[str]:
        return []

    def on_auth_failure(self) -> AuthFailureResponse:
        return AuthFailureResponse.AlwaysAllowed

    def execute(self, handler: Handler, body: bytes, method: str, user: auth.User):
        plaintext_username = handler.headers.get("Login-Username")
        plaintext_password = handler.headers.get("Login-Password")
        if plaintext_username is None or plaintext_password is None:
            handler.send_response(400)
            handler.end_headers()
            return

        user = auth.get_user(plaintext_username)
        if user is None:
            handler.send_response(401)
            handler.end_headers()
            return

        if not auth.check_password(user, plaintext_password):
            handler.send_response(401)
            handler.end_headers()
            return

        # Login correct
        access_token = auth.generate_access_token(user.uid, expires_at=time.time()+600*60)
        handler.send_response(200)
        handler.send_header("Granted-Access-Token", access_token.access_token_key)
        handler.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        handler.send_header('Pragma', 'no-cache')
        handler.send_header('Access-Token-Expires-At', str(access_token.expires_at))
        handler.end_headers()

class APICreateChat(APIFunction):
    def __init__(self):
        super().__init__()

    def endpoints(self) -> list[str]:
        return [
            "/create_chat",
        ]

    def auth_types_allowed(self) -> list[str]:
        return [
            'can_chat'
        ]

    def on_auth_failure(self) -> AuthFailureResponse:
        return AuthFailureResponse.Unauthorized

    def execute(self, handler: Handler, body: bytes, method: str, user: auth.User):
        body_json = json.loads(body)
        chat = Chat(system_prompt=body_json["system_prompt"], user_data=user.user_data)
        user.user_data.chats[str(chat.uid)] = chat
        handler.send_response(200)
        handler.send_header("Content-Type", "application/json")
        handler.send_header('Chat-UID', str(chat.uid))
        handler.end_headers()
        return








class APIGetChats(APIFunction):
    def endpoints(self) -> list[str]:
        return [
            "/list_chats",
        ]

    def auth_types_allowed(self) -> list[str]:
        return [
            'can_chat'
        ]

    def on_auth_failure(self) -> AuthFailureResponse:
        return AuthFailureResponse.Unauthorized

    def execute(self, handler: Handler, body: bytes, method: str, user: auth.User):
        # body_json = json.loads(body)
        chats = user.user_data.chats.values()
        chats_list = []
        for chat in chats: chats_list.append({
            'uid': str(chat.uid),
            'title': chat.title,
            'last_used': str(chat.last_used)
        })
        handler.send_response(200)
        handler.end_headers()
        body_content = {
            'chats': chats_list
        }
        handler.wfile.write(json.dumps(body_content).encode())
        handler.wfile.flush()


class APIGetChat(APIFunction):
    def endpoints(self) -> list[str]:
        return [
            "/get_chat",
        ]

    def auth_types_allowed(self) -> list[str]:
        return [
            'can_chat'
        ]

    def on_auth_failure(self) -> AuthFailureResponse:
        return AuthFailureResponse.Unauthorized

    def execute(self, handler: Handler, body: bytes, method: str, user: auth.User):
        body_json = json.loads(body)
        chat_uid = body_json["chat_uid"]
        try:
            chat = user.user_data.chats[chat_uid]
        except KeyError:
            handler.send_response(404)
            handler.end_headers()
            return

        handler.send_response(200)
        handler.end_headers()

        body_content = chat.serialize()
        handler.wfile.write(json.dumps(body_content).encode())
        handler.wfile.flush()




class APISendChatMessage(APIFunction):
    def endpoints(self) -> list[str]:
        return [
            "/send_chat_message",
        ]

    def auth_types_allowed(self) -> list[str]:
        return [
            'can_chat'
        ]

    def on_auth_failure(self) -> AuthFailureResponse:
        return AuthFailureResponse.Unauthorized

    def execute(self, handler: Handler, body: bytes, method: str, user: auth.User):
        body_json = json.loads(body)
        handler.send_response(200)
        chat_uid = body_json["chat_uid"]
        user_message = body_json["message"]
        chat = user.user_data.chats[chat_uid]
        if chat is None:
            handler.send_response(404)
            handler.end_headers()
            return
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Transfer-Encoding", "chunked")
        handler.end_headers()
        asyncio.run(self._run_llm(chat=chat, user_message=user_message, handler=handler, user=user))



    async def _run_llm(self, chat: user_data.Chat, handler: Handler, user_message: str, user: auth.User):
        timeout = 30
        while chat.currently_responding:
            await asyncio.sleep(1)
            timeout -= 1
            if timeout <= 0:
                handler.send_response(404)
                handler.end_headers()
                return
        try:
            chat.currently_responding = True
            client = ollama.AsyncClient()
            response_message_content = ""
            chat.messages.append({'role': 'user', 'content': user_message})
            async for response in await client.chat(
                model=_model,
                messages=chat.messages,
                stream=True,
            ):
                response_message_content += response.message.content
                encoded = {'response_to': chat.uid, 'content': response.message.content, 'error': False}
                chunk_data = json.dumps(encoded).encode("utf-8")
                chunk_size = f"{len(chunk_data):X}\r\n".encode("utf-8")
                handler.wfile.write(chunk_size + chunk_data + b"\r\n")
                handler.wfile.flush()
            handler.wfile.write(b"0\r\n\r\n")
            handler.wfile.flush()
            chat.messages.append({'role': 'assistant', 'content': response_message_content})

        except Exception:
            encoded = {'response_to': chat.uid, 'content': '', 'error': True}
            chunk_data = json.dumps(encoded).encode("utf-8")
            chunk_size = f"{len(chunk_data):X}\r\n".encode("utf-8")
            handler.wfile.write(chunk_size + chunk_data + b"\r\n")
            handler.wfile.flush()
            handler.wfile.write(b"0\r\n\r\n")
            handler.wfile.flush()
        finally:
            chat.currently_responding = False

root_static_directory = './client/static'
class APIServeStaticFile(APIFunction):
    def endpoints(self) -> list[str]:
        endpoints = []
        def get_files_in_directory_recursive(directory):
            for entry in os.scandir(directory):
                if entry.is_file():
                    yield entry.path
                elif entry.is_dir():
                    yield from get_files_in_directory_recursive(entry.path)


        for path in get_files_in_directory_recursive(root_static_directory):
            subpath = path[len(root_static_directory):]
            endpoints.append(subpath)
            if os.path.splitext(subpath)[1] == '.html':
                endpoints.append(subpath[:-5])
        return endpoints

    def auth_types_allowed(self) -> list[str]:
        return []

    def on_auth_failure(self) -> AuthFailureResponse:
        return AuthFailureResponse.AlwaysAllowed

    def execute(self, handler: Handler, body: bytes, method: str, user: auth.User):
        file_path = root_static_directory + handler.path
        if len(os.path.splitext(file_path)[1]) == 0:
            file_path = file_path + '.html'
        try:
            with open(file_path, 'rb') as file:
                data = file.read()
                handler.send_response(200)
                handler.end_headers()
                handler.wfile.write(data)
                handler.wfile.flush()
        except Exception:
            handler.send_response(404)
            handler.end_headers()
            return

        return