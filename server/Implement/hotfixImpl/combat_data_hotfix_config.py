class CombatDataHotfixCfgModule:
    # 可以按data行进行hotfix的表路径  走的是HotfixCppCombatDataByIdList/HotfixCppCombatRowData函数
    DataPathName2CppRowLoadfuncName = {
        "Data/Excel/AttackTypeSettingData": "load_attack_type_setting_data",
        "Data/Excel/AuraData": "load_aura_data",
        "Data/Excel/BuffControlConflictData": "load_buff_control_conflict_data",
        "Data/Excel/BuffControlDefineData": "load_buff_control_data",
        "Data/Excel/BuffDataNew": "load_buff_data",
        "Data/Excel/CombatParameterData": "load_combat_parameter_data",
        "Data/Excel/EffectBlockingRulesData": "load_effect_block_rules_data",
        "Data/Excel/ExtraHurtMultiData": "load_extra_hurt_multi_data",
        "Data/Excel/FashionMountData": "load_fashion_mount_data",
        "Data/Excel/FightActionCppData": "load_fight_action_type_data",
        "Data/Excel/FightBalanceSkillDamageAndCDData": "load_fight_balance_skill_damage_and_cd_data",
        "Data/Excel/FightPropCppData": "load_fight_prop_data",
        "Data/Excel/FightPropModeSetCppData": "load_fight_prop_set_data",
        "Data/Excel/HitActionDefineData": "load_hit_action_define_data",
        "Data/Excel/HitControlConflictData": "load_hit_control_conflict_data",
        "Data/Excel/HitFallBackData": "load_hit_fallback_data",
        "Data/Excel/HitParamIDData": "load_hit_paramid_data",
        "Data/Excel/MonsterData": "load_monster_data",
        "Data/Excel/MonsterWeakParaData": "load_monster_weak_para_data",
        "Data/Excel/NewBulletData": "load_bullet_data",
        "Data/Excel/PVPPassiveBalanceRuleData": "load_pvp_passive_balance_rule_data",
        "Data/Excel/PassiveSkillData": "load_passive_skill_data",
        "Data/Excel/ProfessionSkillData": "load_profession_prop_data",
        "Data/Excel/ReviseDamageData": "load_revise_damage_data",
        "Data/Excel/RoleSkillUnlockData": "load_role_skill_data",
        "Data/Excel/SkillDataNew": "load_skill_data",
        "Data/Excel/SkillWheelData": "load_skill_wheel_data",
        "Data/Excel/SpellAgentData": "load_spell_agent_data",
        "Data/Excel/SpellFieldData": "load_spell_field_data",
        "Data/Excel/StatisticsBuffAndSkillFilterData": "load_combat_stat_filter_data",
        "Data/Excel/SummonData": "load_summmon_data",
        "Data/Excel/TalentBattleEffectData": "load_talent_battle_effect_data",
        "Data/Excel/TargetSelectionRuleData": "load_target_select_data",
        "Data/Excel/TrapData": "load_trap_data",
    }

    # 可以整个表进行hotfix的表路径  走的是HotfixCppCombatTableData函数
    DataPathName2CppTableLoadfuncName = {
        "Data/Excel/BuffBalanceWhiteListData": "LoadCppBuffBalanceWhiteListData",
        "Data/Excel/HitConstantData": "LoadCppHitConstantData",
        "Data/Excel/PlayerPropTransData": "LoadCppPlayerPropTransData",
        "Data/Excel/RaceDeltaData": "LoadCppRaceDeltaData",
        "Data/Excel/RoleMechanismConstV2Data": "LoadCppRoleMechanismConstData",
        "Data/Excel/SkillModifierComboRuleIndex": "LoadCppSkillModifierComboRuleIndex",
    }

    # 不走通用接口的
    ManualHotFixDataPathName = {
        "Data/SkillData/AbilityDataAll": "load_ability_data",  # 这个是按照row进行hotfix的，但是这个由于不能走exceldata的生成流程，所以单独开一个 hotfix工具那边得直接按技能的粒度call过来
        "Enum/ERoleMechanismConstData": "LoadCppERoleMechanismConstData",
        "Enum/EPlayerInitialConst": "LoadCppEPlayerInitialConst",
    }