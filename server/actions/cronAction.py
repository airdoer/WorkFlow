from exts import db
from datetime import datetime, timedelta
from models.c1.battle import Battle as C1_Battle
from models.c1.player import Player as C1_Player
from models.c1.room import Room as C1_Room
from dbImp import redisImp
from sqlalchemy import and_
from utility import const
import logging
from dbImp.mongoImp import get_hotfix_mongo
from managers.timeMgr import cron

CLEAR_DAYS = 7

app = None


BATTLE_LOCK_NAME = "cleanup_battle_task_lock"

PLAYER_LOCK_ANME = "cleanup_player_task_lock"


def setApp(_app):
    global app
    app = _app


def clearOverTimeConsistStatistic():
    logging.info('dbAction clearOverTimeConsistStatistic')
    redisImp.clearOverTimeConsistStatistic()


def clearOverTimeBattle(remain_days=CLEAR_DAYS, remain_hours=0):
    if not const.DO_CLEAR_JOB:
        return
    logging.info(f'dbAction clearOverTimeBattleC1 {remain_days=} {remain_hours=}')
    with app.app_context():
        lock = redisImp.getRedisLock(BATTLE_LOCK_NAME)
        if lock.acquire():
            logging.info("Lock acquired by process. Executing cleanup...")
            try:
                new_start_time = datetime.utcnow() + timedelta(hours=8) - timedelta(days=remain_days, hours=remain_hours)
                # 确保能找到有Room信息的战场
                filterCondition = [
                    C1_Battle.start_time < new_start_time,
                    C1_Battle.multi_status == False,  # 这里有坑，不能用is False  # noqa
                    C1_Battle.sync_status == True,  # noqa
                    C1_Battle.type == 'NORMAL_PVE',
                ]  # noqa
                target_battle = db.session.query(C1_Battle).filter(and_(*filterCondition)).order_by(C1_Battle.id.desc()).first()
                if target_battle:
                    battle_target_id = target_battle.id
                    # 删除 id 小于等于 target_id 的记录
                    db.session.query(C1_Battle).filter(C1_Battle.id <= battle_target_id).delete()
                    db.session.commit()
                    logging.info(f"clearOverTimeBattle Cleared battle records with id <= {battle_target_id}, "
                                 f"with battle_id: {target_battle.game_id}")

                    # 继续删除Room信息
                    target_room = db.session.query(C1_Room).filter(C1_Room.game_id == target_battle.game_id).first()
                    if target_room:
                        room_target_id = target_room.id
                        # 删除 id 小于等于 target_id 的记录
                        db.session.query(C1_Room).filter(C1_Room.id <= room_target_id).delete()
                        db.session.commit()
                        logging.info(f"clearOverTimeBattle Cleared room records with id <= {room_target_id}, "
                                     f"with battle_id: {target_battle.game_id}")
                    else:
                        logging.info("clearOverTimeBattle No room records found to delete.")
                else:
                    logging.info("clearOverTimeBattle No battle records found to delete.")
            finally:
                # lock.release() 不用release，等待expire30自动释放
                logging.info("clearOverTimeBattle finally end")
        else:
            logging.info("clearOverTimeBattle Lock not acquired. Another process is executing the cleanup.")


def clearOverTimePlayer(remain_days=CLEAR_DAYS, remain_hours=0):
    if not const.DO_CLEAR_JOB:
        return
    logging.info(f'dbAction clearOverTimePlayerC1 {remain_days=} {remain_hours=}')
    with app.app_context():
        lock = redisImp.getRedisLock(PLAYER_LOCK_ANME)
        if lock.acquire():
            logging.info("clearOverTimePlayer Lock acquired by process. Executing cleanup...")
            try:
                new_start_time = datetime.utcnow() + timedelta(hours=8) - timedelta(days=remain_days, hours=remain_hours)
                target_player = db.session.query(C1_Player).filter(C1_Player.start_time < new_start_time,).\
                    order_by(C1_Player.id.desc()).first()
                if target_player:
                    db.session.query(C1_Player).filter(C1_Player.id < target_player.id).delete()
                    db.session.commit()
                    logging.info(f"clearOverTimePlayer Cleared player records with id < {target_player.id}, "
                                 f"with player_id: {target_player.player_id}")
                else:
                    logging.info("clearOverTimePlayer No player records found to delete.")
            finally:
                # lock.release() 不用release，等待expire30自动释放
                logging.info("clearOverTimePlayer finally end")
        else:
            logging.info("clearOverTimePlayer Lock not acquired. Another process is executing the cleanup.")


def clearOverTimeRecord(remain_days, remain_hours=0):
    clearOverTimeBattle(remain_days, remain_hours)
    clearOverTimePlayer(remain_days, remain_hours)


def clearConsistStatistic():
    redisImp.clearConsistStatistic()


def clearClientStatistic():
    redisImp.deleteMemoryData()
    redisImp.deleteTrafficData()


def clearC1():
    logging.info('dbAction clearC1')
    with app.app_context():
        db.session.query(C1_Battle).delete()
        db.session.query(C1_Room).delete()
        db.session.query(C1_Player).delete()
        db.session.commit()
    clearConsistStatistic()
    clearClientStatistic()


def testCronTask():
    logging.info('dbAction testCronTask 5 minutes')


@cron('daily 02:00')
def clearOverTimeHotfix(expire_days=60):
    """
    清理过期的hotfix记录
    
    Args:
        expire_days: 过期天数，默认60天
    """
    if not const.DO_CLEAR_JOB:
        return
    logging.info(f'dbAction clearOverTimeHotfix {expire_days=}')
    try:
        hotfix_mongo = get_hotfix_mongo()
        deleted_count = hotfix_mongo.delete_expired_hotfix_records(expire_days)
        logging.info(f"clearOverTimeHotfix completed, deleted {deleted_count} records")
    except Exception as e:
        logging.error(f"clearOverTimeHotfix failed: {e}")


serverCronList = [
    # ({
    #      'type': 'interval',
    #      'minute': 60,
    #  }, clearOverTimeConsistStatistic),
]
