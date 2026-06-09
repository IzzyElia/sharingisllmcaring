from server import auth, storage
import server.api
from server.server import start_server

if __name__ == '__main__':
    static_server_obj = server.api.APIServeStaticFile()
    for endpoint in static_server_obj.endpoints():
        print(endpoint)

    start_server()





