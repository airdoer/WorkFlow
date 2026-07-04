import json
import os
import argparse
import ast

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PICK_IMPL_DIR = os.path.dirname(SCRIPT_DIR)
MONGOIMPORT_PATH = os.path.join(SCRIPT_DIR, "mongoImport.py")
CONF_PATH = os.path.join(PICK_IMPL_DIR, "config", "conf.json")

def change_config(src_env, dst_env, src_logic_id, dst_logic_id, sourceaccount='', dstaccount='', avatarid='', avatarname='', service='', collection=''):
    """更新配置文件中的参数"""
    try:
        with open(CONF_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 需要转为字符串的参数
        str_params = {
            'src_logic_id': src_logic_id,
            'dst_logic_id': dst_logic_id
        }
        # 需要按逗号分割的参数
        list_params = {
            'Account': sourceaccount,
            'AvatarID': avatarid,
            'AvatarName': avatarname,
            'Service': service
        }
        
        # 更新需要转字符串的参数
        for key, value in str_params.items():
            data[key] = str(value)
        
        # 更新需要分割的参数
        for key, value in list_params.items():
            if not value:
                data[key] = []
            else:
                data[key] = value.split(',')
        
        # Collection 需要转为字典
        if not collection:
            data['Collection'] = {}
        else:
            try:
                content = collection.strip('{}')
                collection_map = {}
                if content:
                    pairs = content.split(',')
                    for pair in pairs:
                        if ':' in pair:
                            key, value = pair.split(':', 1)
                            key = key.strip().strip('\'"')
                            value = value.strip().strip('\'"')
                            collection_map[key] = value
                        else:
                            raise ValueError(f"无效的键值对格式: {pair}")
                
                if not collection_map:
                    raise ValueError("Collection不能为空")
                data['Collection'] = collection_map
            except Exception as e:
                print(f"错误: 转换Collection失败 - {e}")
                data['Collection']={}
                return False
        
        data['SourceEnvironmont'] = src_env
        data['DestEnvironmont'] = dst_env
        data['DestAccount'] = dstaccount
        # 写回 JSON 文件
        with open(CONF_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        
        print(f"配置文件已更新: {CONF_PATH}")
        return True
    
    except FileNotFoundError:
        print(f"错误: 配置文件 {CONF_PATH} 不存在")
        return False
    except json.JSONDecodeError:
        print(f"错误: 配置文件 {CONF_PATH} 格式错误")
        return False
    except Exception as e:
        print(f"错误: 更新配置文件失败 - {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="从开发服务器复制账号数据到本地")
    parser.add_argument('-se', '--srcenv', help='源环境')
    parser.add_argument('-de', '--dstenv', help='目标环境')
    parser.add_argument('-ds', '--dstserver', help='目标服务器id')
    parser.add_argument('-ss', '--srcserver', help='源服务器id')
    parser.add_argument('-sa', '--sourceaccount', help='源服务器账号id（多个用逗号分隔）')
    parser.add_argument('-da', '--dstaccount', help='目标服务器账号id（多个用逗号分隔）')
    parser.add_argument('-i', '--avatarid', help='角色id（多个用逗号分隔）')
    parser.add_argument('-n', '--avatarname', help='角色名称（多个用逗号分隔）')
    parser.add_argument('-ser', '--service', help='service名称（多个用逗号分隔）')
    parser.add_argument('-col', '--collection', help='collection名称（多个用逗号分隔）')
    
    args = parser.parse_args()
    
    # if args.dstserver and not args.dstserver.isdigit():
    #     print("错误: 目标服务器id必须为数字")
    #     return 1
    # if args.srcserver and not args.srcserver.isdigit():
    #     print("错误: 源服务器id必须为数字")
    #     return 1

    # 获取目标服务器id，优先级：命令行参数 > 环境变量 > 默认值
    dst_logic_id = args.dstserver or os.getenv('SERVERID') or os.getenv('SERVERID2') or 1
    
    # 获取源服务器id，默认为 10014
    src_logic_id = args.srcserver or 10014

    # 默认都是本地测试环境
    src_env = args.srcenv or "local"
    dst_env = args.dstenv or "local"
    
    dstaccount = args.dstaccount or 'test'
    # 检查是否至少提供了一个数据源参数
    data_params = [args.sourceaccount, args.avatarid, args.avatarname, args.service, args.collection]
    if not any(data_params):
        print("错误: 请至少输入一个源服务器需要导入的数据信息")
        print("支持的参数: -sa/--sourceaccount, -i/--avatarid, -n/--avatarname, -ser/--service, -col/--collection")
        return 1
    
    # 更新配置文件
    success = change_config(
        src_env,
        dst_env,
        src_logic_id, 
        dst_logic_id, 
        args.sourceaccount, 
        dstaccount, 
        args.avatarid, 
        args.avatarname, 
        args.service, 
        args.collection
    )
    
    if success:
        print("配置更新成功")
        os.system(f"python {MONGOIMPORT_PATH}")
        return 0
    else:
        return 1


if __name__ == "__main__":
    exit(main())