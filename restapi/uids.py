import base64
import secrets

def generate_uid(collision_table: list[str]):
    def _generate() -> str:
        secure_random_bytes = secrets.token_bytes(32)
        return base64.urlsafe_b64encode(secure_random_bytes).decode('utf-8')

    failsafe = 3
    while True:
        uid = _generate()
        if uid not in collision_table:
            return uid
        if failsafe <= 0:
            raise Exception("Failed to generate unique uid")
        failsafe -= 1