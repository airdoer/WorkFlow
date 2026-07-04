
import re

def _generate_hotfix_data_path(path):
    pathStr = ""
    for _path_part in path:
        if isinstance(_path_part, int):
            pathStr += f"[{_path_part}]"
        elif isinstance(_path_part, str):
            # 检查是否为合法的 Lua 标识符：字母或下划线开头，仅包含字母数字下划线
            if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', _path_part):
                pathStr += f".{_path_part}"
            else:
                # 包含中文、数字开头、特殊字符等，使用中括号形式
                escaped_part = _path_part.replace("'", "\\'")
                pathStr += f"['{escaped_part}']"
        else:
            pathStr += f".{_path_part}"
    return pathStr

def test_hotfix_path_generation():
    test_cases = [
        (['table', 'key1'], '.table.key1'),
        (['table', '123'], ".table['123']"),  # String '123'
        (['table', 123], ".table[123]"),      # Integer 123
        (['data', '中文Key'], ".data['中文Key']"),
        (['config', 'key-with-dash'], ".config['key-with-dash']"),
        (['special', "It's me"], ".special['It\\'s me']"),
        (['mixed', 'valid_key', 'invalid key'], ".mixed.valid_key['invalid key']"),
    ]

    print("Running tests for _generate_hotfix_data_path...")
    for path, expected in test_cases:
        result = _generate_hotfix_data_path(path)
        if result == expected:
            print(f"PASS: {path} -> {result}")
        else:
            print(f"FAIL: {path} -> {result}, expected {expected}")

if __name__ == "__main__":
    test_hotfix_path_generation()
