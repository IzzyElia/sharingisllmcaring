import ollama
import json
import asyncio
from collections.abc import AsyncIterator
from .handler import APIFunction, Handler, AuthFailureResponse
from . import auth
from .user_data import UserData, Chat
from dotenv import load_dotenv
load_dotenv()
from os import getenv

_model: str = getenv("MODEL")
if _model is None: raise Exception("Environment variable MODEL is not set")


class APICreateChat(APIFunction):
    def __init__(self):
        super().__init__()

    def endpoints(self, handler: Handler, function: str) -> list[str]:
        return [
            "/create_chat",
        ]

    def auth_types_allowed(self) -> list[str]:
        return [
            'can_chat'
        ]

    def on_auth_failure(self) -> AuthFailureResponse:
        return AuthFailureResponse.Unauthorized

    def execute(self, handler: Handler, body: bytes, function: str, user: auth.User):
        body_json = json.loads(body)
        chat = Chat(system_prompt=body_json["system_prompt"], user_data=user.user_data)
        user.user_data.chats[chat.uid] = chat
        handler.send_header("Content-Type", "application/json")
        handler.send_response(200)
        handler.end_headers()
        body_content = {'chat_uid': chat.uid}
        handler.wfile.write(json.dumps(body_content).encode())
        handler.wfile.flush()








class APIGetChats(APIFunction):
    def endpoints(self, handler: Handler, function: str) -> list[str]:
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
        handler.send_response(200)
        handler.end_headers()
        body_content = {'chat_uids': [{'uid': x.uid, 'title': x.title if x.title is not None else x.uid} for x in user.user_data.chats]}
        handler.wfile.write(json.dumps(body_content).encode())
        handler.wfile.flush()


class APIGetChat(APIFunction):
    def endpoints(self, handler: Handler, function: str) -> list[str]:
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
        handler.send_response(200)
        chat_uid = body_json["chat_uid"]
        chat = user.user_data.chats[chat_uid]
        if chat is None:
            handler.send_response(404)
            handler.end_headers()
            return
        body_content = chat.serialize()
        handler.wfile.write(json.dumps(body_content).encode())
        handler.wfile.flush()




class APISendChatMessage(APIFunction):
    def endpoints(self, handler: Handler, function: str) -> list[str]:
        return [
            "/send_chat_message",
        ]

    def auth_types_allowed(self) -> list[str]:
        return [
            'can_chat'
        ]

    def on_auth_failure(self) -> AuthFailureResponse:
        return AuthFailureResponse.Unauthorized

    async def execute(self, handler: Handler, body: bytes, method: str, user: auth.User):
        body_json = json.loads(body)
        handler.send_response(200)
        chat_uid = body_json["chat_uid"]
        user_message = body_json["message"]
        chat = user.user_data.chats[chat_uid]
        if chat is None:
            handler.send_response(404)
            handler.end_headers()
            return
        handler.send_header("Content-Type", "text/plain")
        handler.send_header("Transfer-Encoding", "chunked")
        handler.end_headers()

        try:
            client = ollama.AsyncClient()
            chat.currently_responding = True
            response_message_content = ""
            chat.messages.append({'role': 'assistant', 'content': ""})
            async for response in await client.chat(
                model=_model,
                messages=chat.messages + [{'role': 'user', 'content': user_message}],
                stream=True,
            ):
                response_message_content += response.message.content
                chat.messages[-1]['content'] = response_message_content
                encoded = {'response_to': chat_uid, 'content': response.message.content}
                chunk_data = json.dumps(encoded).encode("utf-8")
                chunk_size = f"{len(chunk_data):X}\r\n".encode("utf-8")
                handler.wfile.write(chunk_size + chunk_data + b"\r\n")
                handler.wfile.flush()
            handler.wfile.write(b"0\r\n\r\n")
            handler.wfile.flush()

        except:
            pass
        finally:
            chat.currently_responding = False