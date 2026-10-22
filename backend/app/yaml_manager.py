import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from ruamel.yaml import YAML
from ruamel.yaml.compat import StringIO

from .config import PROFILES_DIR, BACKUPS_DIR, DEFAULT_TEST_URL


def get_yaml_instance() -> YAML:
    """获取配置好的 ruamel.yaml 实例，保留注释和格式"""
    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.width = 4096
    return yaml


class YamlManager:
    """管理母本 YAML 文件的解析、备份与无损写入"""

    @staticmethod
    def get_profile_path(profile_name: str) -> Path:
        """规范化母本文件名并返回绝对路径"""
        clean_name = profile_name.strip()
        if not clean_name.endswith((".yaml", ".yml")):
            clean_name += ".yaml"
        return PROFILES_DIR / clean_name

    @classmethod
    def list_profiles(cls) -> List[Dict[str, Any]]:
        """列出所有母本文件及基础元数据"""
        profiles = []
        if not PROFILES_DIR.exists():
            return profiles

        for file_path in PROFILES_DIR.glob("*.*"):
            if file_path.suffix.lower() in [".yaml", ".yml"]:
                # 【母本模板.yaml】仅供【基于模板创建】使用，不展示在母本列表中
                if file_path.stem in ["母本模板", "template"]:
                    continue
                stat = file_path.stat()
                summary = cls.get_profile_summary(file_path.name)
                profiles.append({
                    "name": file_path.name,
                    "stem": file_path.stem,
                    "size": stat.st_size,
                    "updated_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                    "proxy_count": summary["proxy_count"],
                    "group_count": summary["group_count"],
                    "backup_count": len(cls.list_backups(file_path.name)),
                    "test_url": summary.get("test_url", DEFAULT_TEST_URL)
                })
        
        # 按修改时间倒序排列
        profiles.sort(key=lambda x: x["updated_at"], reverse=True)
        return profiles

    @classmethod
    def get_profile_summary(cls, profile_name: str) -> Dict[str, Any]:
        """快速提取母本的节点数、策略组列表以及测速与测延迟接口"""
        path = cls.get_profile_path(profile_name)
        if not path.exists():
            return {
                "proxy_count": 0,
                "group_count": 0,
                "groups": [],
                "proxy_names": [],
                "test_url": DEFAULT_TEST_URL
            }

        try:
            yaml = get_yaml_instance()
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.load(f) or {}

            proxies = data.get("proxies") or []
            proxy_groups = data.get("proxy-groups") or []

            proxy_names = []
            for p in proxies:
                if isinstance(p, dict) and "name" in p:
                    proxy_names.append(str(p["name"]))

            groups = []
            current_test_url = None

            for g in proxy_groups:
                if isinstance(g, dict) and "name" in g:
                    grp_type = str(g.get("type", "select"))
                    group_item: Dict[str, Any] = {
                        "name": str(g.get("name")),
                        "type": grp_type,
                        "proxies": [str(x) for x in (g.get("proxies") or [])]
                    }
                    if "url" in g and g["url"]:
                        group_item["url"] = str(g["url"])
                        if not current_test_url and grp_type in ["url-test", "fallback", "load-balance"]:
                            current_test_url = str(g["url"])
                    groups.append(group_item)

            # 如果未在策略组中找到 url，再检查 health-check
            if not current_test_url:
                providers = data.get("proxy-providers") or {}
                if isinstance(providers, dict):
                    for _, pvd in providers.items():
                        if isinstance(pvd, dict) and "health-check" in pvd:
                            hc = pvd["health-check"]
                            if isinstance(hc, dict) and "url" in hc:
                                current_test_url = str(hc["url"])
                                break

            return {
                "proxy_count": len(proxy_names),
                "group_count": len(groups),
                "groups": groups,
                "proxy_names": proxy_names,
                "test_url": current_test_url or DEFAULT_TEST_URL
            }
        except Exception as e:
            return {
                "proxy_count": 0,
                "group_count": 0,
                "groups": [],
                "proxy_names": [],
                "test_url": DEFAULT_TEST_URL,
                "error": str(e)
            }

    @classmethod
    def update_profile_test_urls(
        cls,
        profile_name: str,
        new_test_url: str = DEFAULT_TEST_URL
    ) -> Dict[str, Any]:
        """
        核心方法：将母本中所有 url-test、fallback、load-balance 策略组
        及 health-check 中的测速与测延迟接口统一替换为国内直连接口
        """
        path = cls.get_profile_path(profile_name)
        if not path.exists():
            raise FileNotFoundError(f"母本 {profile_name} 不存在")

        clean_url = new_test_url.strip() or DEFAULT_TEST_URL

        yaml = get_yaml_instance()
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.load(f) or {}

        updated_groups = []

        # 1. 策略组 proxy-groups
        proxy_groups = data.get("proxy-groups") or []
        for g in proxy_groups:
            if isinstance(g, dict):
                g_type = str(g.get("type", "")).lower()
                # url-test、fallback、load-balance 或者显式配置了 url 的策略组
                if g_type in ["url-test", "fallback", "load-balance"] or "url" in g:
                    g["url"] = clean_url
                    updated_groups.append(str(g.get("name", "未命名策略组")))

        # 2. 节点提供商 proxy-providers (如有)
        updated_providers = []
        providers = data.get("proxy-providers") or {}
        if isinstance(providers, dict):
            for p_name, p_data in providers.items():
                if isinstance(p_data, dict) and "health-check" in p_data:
                    hc = p_data["health-check"]
                    if isinstance(hc, dict):
                        hc["url"] = clean_url
                        updated_providers.append(str(p_name))

        # 3. 创建自动备份并保存
        backup_file = cls.create_backup(profile_name)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f)

        return {
            "success": True,
            "profile_name": path.name,
            "test_url": clean_url,
            "backup_file": backup_file,
            "updated_groups": updated_groups,
            "updated_providers": updated_providers,
            "updated_count": len(updated_groups) + len(updated_providers)
        }

    @classmethod
    def create_backup(cls, profile_name: str) -> Optional[str]:
        """创建时间戳备份"""
        path = cls.get_profile_path(profile_name)
        if not path.exists():
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{path.stem}_{timestamp}.bak"
        backup_path = BACKUPS_DIR / backup_filename

        shutil.copy2(path, backup_path)
        return backup_filename

    @classmethod
    def list_backups(cls, profile_name: str) -> List[Dict[str, Any]]:
        """获取指定母本的所有历史备份"""
        stem = Path(profile_name).stem
        backups = []
        if not BACKUPS_DIR.exists():
            return backups

        prefix = f"{stem}_"
        for f in BACKUPS_DIR.glob(f"{prefix}*.bak"):
            stat = f.stat()
            backups.append({
                "filename": f.name,
                "size": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            })

        backups.sort(key=lambda x: x["created_at"], reverse=True)
        return backups

    @classmethod
    def restore_backup(cls, profile_name: str, backup_filename: str) -> bool:
        """从备份恢复母本"""
        profile_path = cls.get_profile_path(profile_name)
        backup_path = BACKUPS_DIR / backup_filename

        if not backup_path.exists():
            raise FileNotFoundError(f"备份文件 {backup_filename} 不存在")

        # 恢复前给当前状态也做个快照保护
        if profile_path.exists():
            cls.create_backup(profile_name)

        shutil.copy2(backup_path, profile_path)
        return True

    @classmethod
    def delete_backup(cls, profile_name: str, backup_filename: str) -> bool:
        """删除指定的快照备份文件"""
        clean_name = Path(backup_filename).name
        backup_path = BACKUPS_DIR / clean_name
        if not backup_path.exists():
            raise FileNotFoundError(f"备份文件 {clean_name} 不存在")
        if not backup_path.resolve().is_relative_to(BACKUPS_DIR.resolve()):
            raise ValueError("非法路径访问")
        backup_path.unlink()
        return True

    @classmethod
    def save_raw_yaml(cls, profile_name: str, content: str) -> None:
        """直接保存 YAML 文本（带格式校验与备份）"""
        yaml = get_yaml_instance()
        # 语法测试
        yaml.load(content)

        profile_path = cls.get_profile_path(profile_name)
        if profile_path.exists():
            cls.create_backup(profile_name)

        with open(profile_path, "w", encoding="utf-8") as f:
            f.write(content)

    @classmethod
    def get_raw_yaml(cls, profile_name: str) -> str:
        """获取原始 YAML 文本内容"""
        profile_path = cls.get_profile_path(profile_name)
        if not profile_path.exists():
            raise FileNotFoundError(f"母本文件 {profile_name} 不存在")
        with open(profile_path, "r", encoding="utf-8") as f:
            return f.read()

    @classmethod
    def delete_profile(cls, profile_name: str) -> bool:
        """删除指定母本"""
        path = cls.get_profile_path(profile_name)
        if path.exists():
            path.unlink()
            return True
        return False

    @classmethod
    def inject_nodes(
        cls,
        profile_name: str,
        nodes_to_import: List[Dict[str, Any]],
        target_group_names: List[str],
        overwrite: bool = True
    ) -> Dict[str, Any]:
        """
        核心方法：向母本注入节点并加入用户选定的策略组
        """
        path = cls.get_profile_path(profile_name)
        if not path.exists():
            raise FileNotFoundError(f"母本 {profile_name} 不存在")

        yaml = get_yaml_instance()
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.load(f) or {}

        # 1. 确保 proxies 字段存在
        if "proxies" not in data or data["proxies"] is None:
            data["proxies"] = []

        existing_proxies = data["proxies"]
        # 建立现存节点名字 -> 下标映射
        existing_names_map = {}
        for idx, p in enumerate(existing_proxies):
            if isinstance(p, dict) and "name" in p:
                existing_names_map[str(p["name"])] = idx

        added_count = 0
        updated_count = 0
        skipped_count = 0
        imported_node_names = []

        # 2. 注入节点到 proxies 列表
        for node in nodes_to_import:
            if not isinstance(node, dict) or "name" not in node:
                continue

            node_name = str(node["name"])
            imported_node_names.append(node_name)

            if node_name in existing_names_map:
                if overwrite:
                    idx = existing_names_map[node_name]
                    existing_proxies[idx] = node
                    updated_count += 1
                else:
                    skipped_count += 1
            else:
                existing_proxies.append(node)
                existing_names_map[node_name] = len(existing_proxies) - 1
                added_count += 1

        # 3. 更新目标策略组 proxy-groups
        groups_updated = []
        if "proxy-groups" in data and isinstance(data["proxy-groups"], list):
            target_set = set(target_group_names)
            for group in data["proxy-groups"]:
                if isinstance(group, dict):
                    # 顺便保证测速接口为国内直连接口（如果是 gstatic 或空）
                    g_type = str(group.get("type", "")).lower()
                    if g_type in ["url-test", "fallback", "load-balance"]:
                        cur_u = str(group.get("url", ""))
                        if not cur_u or "gstatic.com" in cur_u:
                            group["url"] = DEFAULT_TEST_URL

                    if str(group.get("name")) in target_set:
                        if "proxies" not in group or group["proxies"] is None:
                            group["proxies"] = []
                        
                        group_proxies = group["proxies"]
                        existing_in_group = set(str(x) for x in group_proxies)
                        
                        # 追加选中的节点名（自动去重）
                        for n_name in imported_node_names:
                            if n_name not in existing_in_group:
                                group_proxies.append(n_name)
                                existing_in_group.add(n_name)
                        
                        groups_updated.append(str(group.get("name")))

        # 4. 执行自动备份
        backup_file = cls.create_backup(profile_name)

        # 5. 无损写回文件
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f)

        return {
            "success": True,
            "profile_name": path.name,
            "backup_file": backup_file,
            "added_count": added_count,
            "updated_count": updated_count,
            "skipped_count": skipped_count,
            "total_imported": len(imported_node_names),
            "groups_updated": groups_updated
        }

    @classmethod
    def get_profile_structure(cls, profile_name: str) -> Dict[str, Any]:
        """获取母本完整解析结构（包含所有节点配置与策略组配置详情）"""
        path = cls.get_profile_path(profile_name)
        if not path.exists():
            raise FileNotFoundError(f"母本 {profile_name} 不存在")

        yaml = get_yaml_instance()
        with open(path, "r", encoding="utf-8") as f:
            raw_content = f.read()

        data = yaml.load(raw_content) or {}
        proxies = data.get("proxies") or []
        proxy_groups = data.get("proxy-groups") or []
        rules = data.get("rules") or []

        clean_proxies = [dict(p) for p in proxies if isinstance(p, dict)]
        clean_groups = []
        for g in proxy_groups:
            if isinstance(g, dict):
                g_dict = dict(g)
                g_dict["proxies"] = list(g_dict.get("proxies") or [])
                clean_groups.append(g_dict)

        return {
            "name": path.name,
            "proxies": clean_proxies,
            "proxy_groups": clean_groups,
            "rules_count": len(rules) if isinstance(rules, list) else 0,
            "raw_yaml": raw_content
        }

    @classmethod
    def save_profile_structure(
        cls,
        profile_name: str,
        proxies: List[Dict[str, Any]],
        proxy_groups: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """可视化保存母本中的节点与策略组配置，无损保留注释及其他顶级配置"""
        path = cls.get_profile_path(profile_name)
        if not path.exists():
            raise FileNotFoundError(f"母本 {profile_name} 不存在")

        yaml = get_yaml_instance()
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.load(f) or {}

        data["proxies"] = proxies
        data["proxy-groups"] = proxy_groups

        cls.create_backup(profile_name)

        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f)

        with open(path, "r", encoding="utf-8") as f:
            updated_content = f.read()

        return {
            "success": True,
            "message": "母本配置保存成功，已生成快照备份",
            "proxy_count": len(proxies),
            "group_count": len(proxy_groups),
            "raw_yaml": updated_content
        }

    @classmethod
    def preview_profile_yaml(
        cls,
        profile_name: str,
        proxies: List[Dict[str, Any]],
        proxy_groups: List[Dict[str, Any]]
    ) -> str:
        """根据当前修改的节点和策略组生成 YAML 预览文本（不保存至磁盘）"""
        path = cls.get_profile_path(profile_name)
        yaml = get_yaml_instance()

        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.load(f) or {}
        else:
            data = {}

        data["proxies"] = proxies
        data["proxy-groups"] = proxy_groups

        buf = StringIO()
        yaml.dump(data, buf)
        return buf.getvalue()

    @classmethod
    def parse_yaml_to_structure(cls, content: str) -> Dict[str, Any]:
        """解析用户在源码编辑框中输入的 YAML 文本为结构化节点与策略组"""
        yaml = get_yaml_instance()
        data = yaml.load(content)
        if not isinstance(data, dict):
            raise ValueError("YAML 格式错误：根对象必须是一个字典映射")

        proxies = data.get("proxies") or []
        proxy_groups = data.get("proxy-groups") or []

        clean_proxies = [dict(p) for p in proxies if isinstance(p, dict)]
        clean_groups = []
        for g in proxy_groups:
            if isinstance(g, dict):
                g_dict = dict(g)
                g_dict["proxies"] = list(g_dict.get("proxies") or [])
                clean_groups.append(g_dict)

        return {
            "proxies": clean_proxies,
            "proxy_groups": clean_groups,
            "rules_count": len(data.get("rules") or [])
        }
