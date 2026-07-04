# builtin
# import logging

# 3rd ext
import gevent
import gevent.monkey
from gevent.pywsgi import WSGIServer

import sys
libPath = "./lib"
sys.path.append(libPath)

# int
import config
if config.enableMonkeyPatch:
    gevent.monkey.patch_all(thread=False)

from appImp import app  # 因为现在路由注册的import机制, 单独拆了appImp
from tools.TelnetHandler import run_telnet_server



def printConfig():
    app.logger.info("config info:")
    app.logger.info(f"Server: {config.host}:{config.flask_port}")
    app.logger.info(f"Redis: {config.redis_host}:{config.redis_port}")
    app.logger.info(f"Mysql: {config.HOSTNAME}:{config.PORT}")


def run_flask_app():
    http_server = WSGIServer((config.host, config.flask_port), app, spawn=100)
    http_task = gevent.spawn(http_server.serve_forever())
    return http_task


if __name__ == '__main__':
    # 不用app.run，原因是它是用于测试和开发目的的简单服务器，不建议在生产环境中使用。app.run默认在单线程模式下运行，处理请求时是阻塞的
    # 生产环境中，应该使用像Gunicorn、uWSGI等成熟的WSGI服务器来部署Flask应用，以获得更好的性能和稳定性。

    printConfig()
    telnet_task = run_telnet_server()
    flask_task = run_flask_app()
    # 等待两个服务器都退出
    gevent.joinall([telnet_task, flask_task])

# endregion
