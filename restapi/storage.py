from abc import abstractmethod, ABC
import os
import json

DATA_DIR = os.getenv('DATA_DIR')
if DATA_DIR is None: DATA_DIR = "data"

class Serializable(ABC):
    def __init__(self):
        pass

    @abstractmethod
    def serialize(self) -> dict: ...

    @abstractmethod
    def deserialize(self, data: dict): ...

class Savable(Serializable):
    def __init__(self):
        super().__init__()
        pass

    @abstractmethod
    def category(self) -> str: ...

    @abstractmethod
    def id(self) -> str: ...

import re
import unicodedata


def sanitize(name: str, max_length: int = 255) -> str:
    # Normalize unicode (e.g. combining chars -> single chars)
    name = unicodedata.normalize("NFKC", name)

    # Strip directory separators and parent refs outright
    name = name.replace("/", "_").replace("\\", "_")

    # Remove characters illegal on Windows (also covers most Unix concerns):
    # < > : " | ? *  and control chars 0-31
    name = re.sub(r'[<>:"|?*\x00-\x1f]', "_", name)

    # Collapse whitespace runs to a single underscore
    name = re.sub(r"\s+", "_", name)

    # Strip leading/trailing dots and spaces (Windows hates trailing dots/spaces)
    name = name.strip(". ")

    # Guard against Windows reserved device names
    reserved = {
        "CON", "PRN", "AUX", "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
    stem = name.split(".")[0].upper()
    if stem in reserved:
        name = f"_{name}"

    # Truncate, preserving the extension if possible
    if len(name) > max_length:
        root, dot, ext = name.rpartition(".")
        if dot and len(ext) < max_length:
            root = root[: max_length - len(ext) - 1]
            name = f"{root}.{ext}"
        else:
            name = name[:max_length]
    if not name: return ""
    return name


def save_serializable_object(obj: Savable):
    category = sanitize(obj.category())
    id = sanitize(obj.id())
    data = obj.serialize()
    dir_path = os.path.join(DATA_DIR, category)
    file_path = os.path.join(dir_path, id + f".{category.lower()}")
    os.makedirs(dir_path, exist_ok=True)
    with open(file_path, 'w') as f:
        json_string = json.dumps(data, ensure_ascii=False, indent=4)
        f.write(json_string)

def load_serializable_object_data(filepath: str, t: type[Savable]):
    with open(filepath, 'r') as f:
        json_string = f.read()
        dictionary = json.loads(json_string)
        obj = t()
        obj.deserialize(dictionary)
        return obj

def load_all_objects_of_category(category: str, t: type[Savable]):
    category = sanitize(category)
    dir_path = os.path.join(DATA_DIR, category)
    if not os.path.exists(dir_path):
        return

    for filename in os.listdir(dir_path):
        if filename.endswith("." + category.lower()):
            filepath = os.path.join(dir_path, filename)
            try:
                yield load_serializable_object_data(filepath, t)
            except Exception as e:
                print(f"Failed to load {filename} as {t}", e)

def delete_serializable_object_data(obj: Savable):
    filepath = os.path.join(DATA_DIR, obj.category(), f"{obj.id()}.{obj.category().lower()}")
    if not os.path.exists(filepath):
        raise Exception(f"No file for {obj.category():{obj.id()}} to delete")
    try:
        os.remove(filepath)
    except Exception as e:
        print(f"Failed to delete {filepath}: {e}", e)