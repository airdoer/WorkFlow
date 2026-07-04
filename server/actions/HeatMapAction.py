# -*- coding : utf-8 -*
import os


def get_image_size(image_path):
    from PIL import Image
    image = Image.open(image_path)
    return image.size

# def deal_data_file(file_path):
#     data_list = []
#     with open(file_path, "r") as f:
#         for line in f:
#             data = dict()
#             pairs = line.split(";")
#             for pair in pairs:
#                 if pair:
#                     if pair.count(":") == 1:
#                         key, value = pair.split(":")
#                         if value.count(",") == 0:
#                             data[key] = float(value)
#                         else:
#                             data[key] = value
#                     elif pair.count(":") > 1:
#                         key = pair[:pair.find(":")]
#                         values = pair[pair.find(":")+1:]
#                         print(values)
#                         value = {key_: float(value_) for key_, value_ in (item.split(":") for item in values.split(","))}
#                         data[key] = value
#                     else:
#                         if not pair.isspace():
#                             data[str(pair)] = 0.0
#             data_list.append(data)
#     return data_list


def deal_data_json(file_path):
    import json
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        data_list = json.load(f)
        return data_list


def transformation_conver(data_x, data_y, width_min, width_max, height_min, height_max, image_size):
    image_width, image_height = image_size
    x_scale = image_width / (width_max - width_min)
    y_scale = image_height / (height_max - height_min)
    image_x = float((data_x - width_min) * x_scale)
    image_y = float((data_y - height_min) * y_scale)
    return image_x, image_y


def get_data_max(data_liat, key):
    max_value = 0
    for i, data in enumerate(data_liat):
        if max_value < data[key]:
            max_value = data[key]
    return max_value


def deal_image_data(data_name, image_name, width_min, width_max, height_min, height_max, y_transposition_z=False):
    path = os.path.join(os.getcwd(), "static", "HeatMap")
    data_path = os.path.join(path, "data", data_name)
    image_path = os.path.join(path, "image", image_name)
    image_size = get_image_size(image_path)
    data_list = deal_data_json(data_path)
    image_data_path = os.path.join(path, "image_data", data_name)
    try:
        import json
        for i, data in enumerate(data_list):
            x, y, z = float(data["x"]), float(data["y"]), float(data["z"])
            if y_transposition_z:
                x, y, z = x, z, y
            image_x, image_y = transformation_conver(x, y, float(width_min), float(width_max), float(height_min),
                                                     float(height_max), image_size)
            data_list[i]["image_x"], data_list[i]["image_y"] = float("{:.1f}".format(float(image_x))), \
                float("{:.1f}".format(float(image_y)))
            data_list[i]["x"], data_list[i]["z"], data_list[i]["y"] = x, z, y

        with open(image_data_path, 'w', encoding='utf-8') as file:
            json.dump(data_list, file, indent=2)
    except Exception as e:
        return False, e
    return True, ""


def get_image_data_by_key(data_path, key):
    path = os.path.join(os.getcwd(), "static", "HeatMap")
    image_data_path = os.path.join(path, "image_data", data_path)
    keys = ["x", "y", "z", "image_x", "image_y"]
    keys.append(key)
    data_list = []
    import json
    with open(image_data_path, "r", encoding='utf-8') as f:
        for line in f:
            data = {}
            datas = json.loads(line)
            for key in keys:
                data[key] = datas.get(key, None)
            data_list.append(data)
    return data_list


def get_image_data(data_path):
    import json
    path = os.path.join(os.getcwd(), "static", "HeatMap")
    image_data_path = os.path.join(path, "image_data", data_path)
    with open(image_data_path, 'r', encoding='utf-8') as f:
        data_list = json.load(f)
    return data_list
