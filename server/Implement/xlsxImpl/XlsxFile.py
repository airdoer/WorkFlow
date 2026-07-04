# -*- coding: utf-8 -*-
import os


def read_xlsx_directory(root_dir):
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            # xlsx打开的临时文件是以~$开头的，需要过滤
            if not file.endswith('.xlsx') or file.startswith("~$"):
                continue
            file_path = os.path.join(root, file)
            yield file_path
