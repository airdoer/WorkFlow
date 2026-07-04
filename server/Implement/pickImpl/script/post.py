
COLLECTION_ACCOUNT_NAME = "Account"
COLLECTION_AVATAR_NAME = "AvatarActor"
COLLECTION_HOMELAND_NAME = "homeland_building"
COLLECTION_AVATAR_BASIC_NAME = "player_basic_info"
COLLECTION_FRIENDSHIP_NAME = "friendship_data"
COLLECTION_MAIL_NAME = "mail"
COLLECTION_OFFLINE_FRI_SYS_MSG = "offline_fri_sys_msg"
COLLECTION_QUEST_PLANE_ARCHIVE = "quest_plane_archive"
COLLECTION_OFFLINE_UNREAD_MSG = "offline_unread_msg"
COLLECTION_APPEARANCE_LOTTERY_RECORD = "appearance_lottery_record"
COLLECTION_DUNGEON_AUCTION_ORDER = "dungeon_auction_order"
COLLECTION_MAIL_FAVORITES = "mail_favorites"
COLLECTION_TEAM_3V3_BRIEF_RECORD_TABLE = "team_3v3_brief_record_table"
COLLECTION_TEAM_12V12_BRIEF_RECORD_TABLE = "team_12v12_brief_record_table"
COLLECTION_TEAM_6V6_BRIEF_RECORD_TABLE = "team_6v6_brief_record_table"
COLLECTION_PVP_CHAMPION_BRIEF_RECORD_TABLE = "pvp_champion_brief_record_table"
COLLECTION_GUILD_BID_RECORD_TABLE = "guild_bid_record_table"
COLLECTION_WORLD_BID_RECORD_TABLE = "world_bid_record_table"
COLLECTION_RED_PACKET_RECORD = "red_packet_record"
COLLECTION_UMSG = "umsg"
COLLECTION_CHAT_CUSTOM_IMG = "chat_custom_img"
COLLECTION_FELLOW_GACHA_RECORDS = "fellow_gacha_records"
COLLECTION_PAY_ORDER = "pay_order"
COLLECTION_COMMONINTERACTOR_PRIVATE_STATE = "commonInteractor_private_state"

# 需要修改的字段配置
# 格式: { "集合名": { "字段名": 新值 } }
FIELDS_TO_CHANGE = {
    COLLECTION_AVATAR_NAME: {
        "payCountRecords": {}  
    }
}

def post_process(data):
    print("开始数据后处理...")
    
    # 处理 AvatarCollections
    avatar_collections = data.get("AvatarCollections", {})
    if avatar_collections:
        process_avatar_collections(avatar_collections)
    
    print("数据后处理完成。")
    return data

def process_avatar_collections(avatar_collections):
    for collection_name, docs in avatar_collections.items():
        if not docs or not isinstance(docs, list):
            continue
        
        # 检查该集合是否需要处理
        if collection_name not in FIELDS_TO_CHANGE:
            continue
        
        field_changes = FIELDS_TO_CHANGE[collection_name]
        print(f"  处理集合 {collection_name}: {len(docs)} 个文档")
        
        # 对该集合的每个文档进行字段修改
        for doc in docs:
            if not isinstance(doc, dict):
                continue
            
            for field_name, new_value in field_changes.items():
                if field_name in doc:
                    doc[field_name] = new_value