"""
用户认证模块
实现独立账号体系、登录注册、JWT 认证
"""

import os
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from pathlib import Path
import json
from loguru import logger

try:
    from passlib.context import CryptContext
    from jose import JWTError, jwt
    AUTH_AVAILABLE = True
except ImportError:
    AUTH_AVAILABLE = False
    CryptContext = None
    jwt = None
    JWTError = Exception
    logger.warning("认证库未安装，账号系统将不可用")


# 密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto") if AUTH_AVAILABLE else None

# JWT 配置
SECRET_KEY = os.getenv("WEB_SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 天


class UserDatabase:
    """用户数据库管理"""
    
    def __init__(self, db_path: str = "data/users.json"):
        """
        初始化用户数据库
        
        Args:
            db_path: 用户数据文件路径
        """
        self.db_path = db_path
        self._ensure_directory()
        self._init_db()
        logger.info(f"用户数据库已初始化：{db_path}")
    
    def _ensure_directory(self):
        """确保数据库目录存在"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
            logger.info(f"创建用户数据库目录：{db_dir}")
    
    def _init_db(self):
        """初始化数据库"""
        if not os.path.exists(self.db_path):
            self._save_db({"users": [], "created_at": datetime.now().isoformat()})
            logger.info("用户数据库已创建")
    
    def _load_db(self) -> Dict:
        """加载数据库"""
        try:
            with open(self.db_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载用户数据库失败：{e}")
            return {"users": []}
    
    def _save_db(self, data: Dict):
        """保存数据库"""
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    
    def create_user(
        self,
        username: str,
        password: str,
        email: Optional[str] = None,
        role: str = "user"
    ) -> Optional[Dict]:
        """
        创建用户
        
        Args:
            username: 用户名
            password: 密码
            email: 邮箱
            role: 角色 (admin/user)
        
        Returns:
            用户信息，创建失败返回 None
        """
        if not AUTH_AVAILABLE:
            logger.error("认证库不可用")
            return None
        
        db = self._load_db()
        
        # 检查用户名是否存在
        for user in db["users"]:
            if user["username"] == username:
                logger.warning(f"用户名已存在：{username}")
                return None
        
        # 创建用户
        hashed_password = pwd_context.hash(password)
        user = {
            "id": secrets.token_urlsafe(16),
            "username": username,
            "password_hash": hashed_password,
            "email": email,
            "role": role,
            "created_at": datetime.now().isoformat(),
            "last_login": None,
            "is_active": True
        }
        
        db["users"].append(user)
        self._save_db(db)
        
        logger.info(f"用户已创建：{username} (角色：{role})")
        return {"id": user["id"], "username": user["username"], "role": user["role"]}
    
    def get_user(self, username: str) -> Optional[Dict]:
        """获取用户信息"""
        db = self._load_db()
        for user in db["users"]:
            if user["username"] == username:
                return user
        return None
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """验证密码"""
        if not AUTH_AVAILABLE:
            return False
        return pwd_context.verify(plain_password, hashed_password)
    
    def authenticate_user(self, username: str, password: str) -> Optional[Dict]:
        """
        认证用户
        
        Args:
            username: 用户名
            password: 密码
        
        Returns:
            用户信息，认证失败返回 None
        """
        user = self.get_user(username)
        if not user:
            return None
        
        if not self.verify_password(password, user["password_hash"]):
            return None
        
        if not user["is_active"]:
            return None
        
        return user
    
    def update_last_login(self, username: str):
        """更新最后登录时间"""
        db = self._load_db()
        for user in db["users"]:
            if user["username"] == username:
                user["last_login"] = datetime.now().isoformat()
                break
        self._save_db(db)
    
    def get_all_users(self) -> list:
        """获取所有用户（不含密码）"""
        db = self._load_db()
        return [
            {
                "id": u["id"],
                "username": u["username"],
                "email": u.get("email"),
                "role": u["role"],
                "created_at": u["created_at"],
                "last_login": u.get("last_login")
            }
            for u in db["users"]
        ]
    
    def delete_user(self, username: str) -> bool:
        """删除用户"""
        db = self._load_db()
        for i, user in enumerate(db["users"]):
            if user["username"] == username:
                db["users"].pop(i)
                self._save_db(db)
                logger.info(f"用户已删除：{username}")
                return True
        return False
    
    def set_password(self, username: str, new_password: str) -> bool:
        db = self._load_db()
        for i, user in enumerate(db["users"]):
            if user["username"] == username:
                db["users"][i]["password_hash"] = pwd_context.hash(new_password)
                self._save_db(db)
                logger.info(f"用户密码已更新：{username}")
                return True
        return False
    
    def set_username(self, old_username: str, new_username: str) -> bool:
        if not new_username or new_username == old_username:
            return False
        db = self._load_db()
        for u in db["users"]:
            if u["username"] == new_username:
                logger.warning(f"用户名已存在：{new_username}")
                return False
        for i, user in enumerate(db["users"]):
            if user["username"] == old_username:
                db["users"][i]["username"] = new_username
                self._save_db(db)
                logger.info(f"用户名已更新：{old_username} -> {new_username}")
                return True
        return False
    
    def create_default_admin(self) -> Dict:
        """创建默认管理员账号"""
        admin = self.create_user(
            username="admin",
            password="password",
            role="admin"
        )
        if admin:
            logger.warning("默认管理员账号已创建：admin / password")
        return admin or {}


def create_access_token(data: Dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建访问令牌"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    return encoded_jwt


def verify_access_token(token: str) -> Optional[Dict]:
    """验证访问令牌"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


# 全局用户数据库实例
user_db: Optional[UserDatabase] = None


def get_user_database() -> UserDatabase:
    """获取用户数据库实例"""
    global user_db
    if user_db is None:
        db_path = os.getenv("USER_DB_PATH")
        if db_path:
            db_path = Path(db_path)
        else:
            project_root = Path(__file__).parent.parent
            db_path = project_root / "data" / "users.json"
        user_db = UserDatabase(str(db_path))
        
        # 创建默认管理员
        if not user_db.get_user("admin"):
            user_db.create_default_admin()
    
    return user_db
