import requests
import logging

logger = logging.getLogger(__name__)

FLOW_HOOK_KEY = '52f4beef-afac-48ce-b4ee-4e3b9e132acf'
FLOW_SEND_PATH = f'https://kim-robot.kwaitalk.com/api/robot/send?key={FLOW_HOOK_KEY}'
# FLOW_SEND_PATH = f'https://kim-robot.internal/api/robot/send?key={FLOW_HOOK_KEY}'

class KimRobot:
    @staticmethod
    def remind_pass(admin_usernames, mail_id):
        admin_list = sorted({str(item).strip() for item in (admin_usernames or []) if str(item).strip()})
        if not admin_list:
            return False, 'no admin usernames'
        
        # 测试用，之后去掉
        msg = f'有新的邮件(ID为{mail_id})待审批！点击 [申请列表](http://172.28.195.113:8008/mail/apply) 进入'
        people_str = " ".join(f"<@=username({p})=>" for p in admin_list)
        send_json = {
            "msgtype": "markdown",
            "markdown": {
                "content": f"{people_str}，{msg}"
            },
            # 之后去掉
            # "receiverUsernames": admin_list 
        }
        logger.info(f"kimRobot send to ".join(f"username({p})" for p in admin_list))
        try:
            response = requests.post(FLOW_SEND_PATH, json=send_json, timeout=5)
            if response.ok:
                return True, ''
            logger.error(f"kimRobot send error, status={response.status_code}, body={response.text[:200]}")
            return False, f'kim flow notify failed: status={response.status_code}, body={response.text[:200]}'
        except requests.RequestException as err:
            logger.error(f"kimRobot send error {err}")
            return False, f'kim flow notify exception: {err}'
        
    @staticmethod
    def remind_passed(mail_id, approved_by=None):
        approver_text = f'，审批人：{approved_by}' if approved_by else ''
        msg = f'邮件(ID为{mail_id})已审批通过{approver_text}！点击 [邮件列表](http://172.28.195.113:8008/mail/list) 查看详情'
        send_json = {
            "msgtype": "markdown",
            "markdown": {
                "content": f"{msg}"
            },
        }
        logger.info(f"[remind_passed] kimRobot send success")
        try:
            response = requests.post(FLOW_SEND_PATH, json=send_json, timeout=5)
            if response.ok:
                return True, ''
            logger.error(f"[remind_passed] kimRobot send error, status={response.status_code}, body={response.text[:200]}")
            return False, f'kim flow notify failed: status={response.status_code}, body={response.text[:200]}'
        except requests.RequestException as err:
            logger.error(f"[remind_passed] kimRobot send error {err}")
            return False, f'kim flow notify exception: {err}'
