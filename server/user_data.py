from __future__ import annotations
from .storage import Serializable
from .uids import generate_uid

class Chat(Serializable):
    def __init__(self, system_prompt: str = None, user_data: UserData = None):
        super().__init__()
        self.messages = [
            {'role': 'system', 'content': system_prompt},
        ]
        if user_data is not None:
            self.uid = generate_uid([x.uid for x in user_data.chats.values()])
        else:
            self.uid = None # Should only trigger during deserialization, which will fill in the uid later
        self.title = self.uid
        self.currently_responding: bool = False

    def serialize(self) -> dict:
        return {
            "uid": self.uid,
            "title": self.title,
            "messages": self.messages,
        }

    def deserialize(self, data: dict):
        self.uid = data["uid"]
        self.title = data["title"]
        self.messages = data["messages"]




class UserData(Serializable):
    def __init__(self):
        super().__init__()
        self.chats: dict[str, Chat] = {}

    def serialize(self) -> dict:
        return {
            "chats": [chat.serialize() for chat in self.chats.values()],
        }


    def deserialize(self, data: dict):
        serialized_chats = data["chats"]
        self.chats = {}
        for i in range(len(serialized_chats)):
            chat = Chat()
            chat.deserialize(serialized_chats[i])
            self.chats[chat.uid] = chat