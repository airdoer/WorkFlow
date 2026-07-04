
import sys
import os
import re

# Add the server directory to sys.path
sys.path.append(os.path.join(os.getcwd(), 'server'))

from Implement.hotfixImpl.luaImp import _generate_hotfix_data_path

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
