import requests
import config

SERVER_KDIP_URLS = {
    'obt-a': 'http://10.206.149.17:8088/kdip/oper/extend-cmd',
    'obt-b': 'http://10.206.147.128:8088/kdip/oper/extend-cmd',
    'preonline-a': 'http://10.206.132.218:8088/kdip/oper/extend-cmd',
    'preonline-b': 'http://10.206.133.215:8088/kdip/oper/extend-cmd',
    'czx': 'http://172.28.195.228:8088/kdip/oper/extend-cmd',

}

# 禁用代理
NO_PROXY = {
    "http": None,
    "https": None
}


def _get_del_rank_url(serverName):
    return f'{SERVER_KDIP_URLS[serverName]}'


def autoDelRankToGameServer(roleId, rankIds):
    if not getattr(config, 'CUR_SERVER_NAME') or not config.CUR_SERVER_NAME:
        print("autoDelRankToGameServer have no config.CUR_SERVER_NAME")
        return
    url = _get_del_rank_url(config.CUR_SERVER_NAME)

    headers = {
        "Content-Type": "application/json"
    }

    data = {
        "task_title": "task_from_frame_sync",
        "cmd_key": "delete_ranklist_for_review",
        "cmd_param": {
            "useLP": "1",
            "ranklistIds": rankIds,
            "roleIds": [str(roleId)]
        }
    }

    response = requests.post(url, headers=headers, json=data, timeout=5, proxies=NO_PROXY)

    print("状态码:", response.status_code)
    print("响应内容:", response.json() if response.headers.get('Content-Type') == 'application/json' else response.text)
