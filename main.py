from dotenv import load_dotenv
import os
import server.api
import server.auth
from server.server import start_server

load_dotenv()
admin_username = os.getenv("ADMIN_USERNAME")
admin_password = os.getenv("ADMIN_PASSWORD")
if admin_username is None or admin_password is None: raise Exception("Please set ADMIN_USERNAME and ADMIN_PASSWORD environment variables")

server_address = os.getenv("SERVER_ADDRESS")

server_port = os.getenv("SERVER_PORT")
if server_address is None or server_port is None: raise Exception("Please set SERVER_ADDRESS and SERVER_PORT environment variables")

if __name__ == '__main__':
    static_server_obj = server.api.APIServeStaticFile()
    for endpoint in static_server_obj.endpoints():
        print(endpoint)
    server.auth.add_user(admin_username, admin_password, auth_types=['admin'], should_be_saved_to_disk=False)
    try: server_port_int = int(server_port)
    except ValueError: raise Exception(f"SERVER_PORT not a valid port number ({server_port})")
    start_server(server_address, server_port_int)





