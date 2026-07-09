# builtin
# import logging

# 3rd ext
import gevent
import gevent.monkey

import sys
libPath = "./lib"
sys.path.append(libPath)

# int
import config
if config.enableMonkeyPatch:
    gevent.monkey.patch_all(thread=False)

from appImp import app, socketio  # 因为现在路由注册的import机制, 单独拆了appImp
from tools.TelnetHandler import run_telnet_server



def printConfig():
    app.logger.info("config info:")
    app.logger.info(f"Server: {config.host}:{config.flask_port}")
    app.logger.info(f"Redis: {config.redis_host}:{config.redis_port}")
    app.logger.info(f"Mysql: {config.HOSTNAME}:{config.PORT}")


def run_flask_app():
    # Use socketio.run so WebSocket upgrades are handled by flask-socketio/gevent-websocket
    socketio.run(
        app,
        host=config.host,
        port=config.flask_port,
        debug=False,
        use_reloader=False,
    )


if __name__ == '__main__':
    printConfig()
    telnet_task = run_telnet_server()
    # socketio.run blocks, so run it in a greenlet alongside telnet
    flask_greenlet = gevent.spawn(run_flask_app)
    gevent.joinall([telnet_task, flask_greenlet])
