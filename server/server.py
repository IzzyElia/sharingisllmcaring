import threading
import time
from http.server import ThreadingHTTPServer
from . import storage, auth
from . import handler



# API module imports for APIFunction.subclasses discovery

from . import api

# ------------------------------------------------

def get_subclasses_recursive(super_class):
    for subclass in super_class.__subclasses__():
        yield subclass
        yield from get_subclasses_recursive(subclass)

server: ThreadingHTTPServer | None = None

def start_server(address: str, port: int):
    auth.load()

    for api_function in get_subclasses_recursive(handler.APIFunction):
        instance = api_function()
        for endpoint in instance.endpoints():
            handler.register_endpoint(endpoint, instance)

    server = ThreadingHTTPServer((address, port), handler.Handler)
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.start()
    print('Server started at http://localhost:8080')

    def save():
        auth.save()

    try:
        while True:
            time.sleep(300)
            save()
    except KeyboardInterrupt:
        print("Shutting down...")
        if isinstance(server, ThreadingHTTPServer):
            server.shutdown()
            server.server_close()
        save()
        print("Stopped successfully")
