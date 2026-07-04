# utils.py

def get_arg(request, param, default=None):
    """
    从请求参数中获取值，处理 null 和 undefined 情况。

    :param request: Flask 的请求对象
    :param param: 参数名
    :param default: 默认值
    :return: 参数值或默认值
    """
    value = request.args.get(param, default)
    if value in ('null', 'undefined', None):
        return default
    return value


def get_arg_as_int(request, param, default=0):
    """
    获取整型参数，处理异常情况。

    :param request: Flask 的请求对象
    :param param: 参数名
    :param default: 默认值
    :return: 参数值（整型）或默认值
    """
    value = get_arg(request, param, default=str(default))
    try:
        return int(value)
    except ValueError:
        return default
