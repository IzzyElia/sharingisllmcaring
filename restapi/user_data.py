from .storage import Serializable
from .uids import generate_uid

class Chat(Serializable):
    def __init__(self, system_prompt: str, user_data: UserData):
        super().__init__()
        self.messages = [
            {'role': 'system', 'content': system_prompt},
        ]
        self.uid = generate_uid([x.uid for x in user_data.chats])
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
        chats = [Chat() for _ in range(len(serialized_chats))]
        for i in range(len(serialized_chats)):
            chats[i].deserialize(serialized_chats[serialized_chats[i]])
        return self