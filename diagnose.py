#!/usr/bin/env python3
"""
诊断脚本 - 检测 Emby API 返回数据
用于排查检测慢和结果不准确的问题
"""

import sys
import json
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.config_manager import get_config_manager
from app.emby_client import EmbyClient

def main():
    print("=" * 60)
    print("Emby 缺集检测系统 - 诊断工具")
    print("=" * 60)
    
    # 加载配置
    config_mgr = get_config_manager()
    config = config_mgr.get_all_config()
    
    emby_host = config.get('emby', {}).get('host', '')
    emby_key = config.get('emby', {}).get('api_key', '')
    
    if not emby_host or not emby_key:
        print("❌ Emby 配置为空，请先在 Web 界面配置")
        return
    
    print(f"\n📺 Emby: {emby_host}")
    
    # 测试连接
    client = EmbyClient(emby_host, emby_key)
    
    print("\n1️⃣ 测试连接...")
    if client.test_connection():
        print("✅ 连接正常")
    else:
        print("❌ 连接失败")
        return
    
    # 获取系统信息
    print("\n2️⃣ 获取系统信息...")
    sys_info = client.get_system_info()
    if sys_info:
        print(f"   服务器名称：{sys_info.get('ServerName', 'Unknown')}")
        print(f"   版本：{sys_info.get('Version', 'Unknown')}")
    
    # 获取媒体库
    print("\n3️⃣ 获取媒体库...")
    libraries = client.get_media_libraries()
    print(f"   媒体库数量：{len(libraries)}")
    for lib in libraries[:5]:
        print(f"   - {lib.get('Name', 'Unknown')} ({lib.get('CollectionType', 'unknown')})")
    
    # 获取剧集
    print("\n4️⃣ 获取剧集列表...")
    tv_shows = client.get_tv_shows()
    print(f"   剧集数量：{len(tv_shows)}")
    
    # 分析前 3 个剧集
    print("\n5️⃣ 抽样分析剧集数据...")
    for i, show in enumerate(tv_shows[:3]):
        print(f"\n   剧集 {i+1}: {show.get('Name', 'Unknown')}")
        print(f"   - ID: {show.get('Id')}")
        print(f"   - 年份：{show.get('ProductionYear', 'Unknown')}")
        print(f"   - 状态：{show.get('Status', 'Unknown')}")
        
        # 获取季
        seasons = client.get_seasons(show.get('Id'))
        print(f"   - 季数量：{len(seasons)}")
        
        for season in seasons[:2]:
            season_num = season.get('IndexNumber', 0)
            if season_num == 0:
                continue
            season_id = season.get('Id')
            print(f"\n     季 {season_num}: {season.get('Name', 'Unknown')}")
            
            # 获取集
            episodes = client.get_episodes(show.get('Id'), season_id)
            print(f"     - 集数量：{len(episodes)}")
            
            if episodes:
                ep_nums = [ep.get('IndexNumber') for ep in episodes if ep.get('IndexNumber')]
                print(f"     - 集号：{sorted(ep_nums)[:10]}{'...' if len(ep_nums) > 10 else ''}")
    
    print("\n" + "=" * 60)
    print("诊断完成！")
    print("=" * 60)
    
    # 建议
    print("\n💡 建议:")
    if len(tv_shows) > 1000:
        print("   - 剧集数量较多 (>1000)，检测可能需要 2-5 分钟")
        print("   - 建议在媒体库配置中只选择需要的库")
    
    print("   - 如需准确检测结果，建议配置 TMDB API")
    print("   - 检查特别季 (Season 0) 是否应该跳过")

if __name__ == "__main__":
    main()
