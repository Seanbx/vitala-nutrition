"""
账户与个人数据中心
SQLite 存储真实用户：注册 / 登录 / 会话 / 头像 / 主题 / 个性化资料
每个用户的数据彼此隔离，且所有字段可随时修改。
"""

import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = Path(os.environ.get("VITALA_DB", str(PROJECT_ROOT / "data" / "app.db")))

_ITERATIONS = 120_000
_SESSION_DAYS = 30
_db_lock = threading.Lock()

DEFAULT_PROFILE = {
    "basic_info": {
        "gender": "",
        "age": None,
        "height_cm": None,
        "weight_kg": None,
        "body_fat_pct": None,
        "activity_level": "",
        "goal": "",
    },
    "dietary_preferences": {
        "goal": "",
        "dietary_type": "",
        "meal_frequency": "",
        "meal_times": {"breakfast": "07:30", "lunch": "12:00", "dinner": "18:30"},
        "disliked_foods": [],
        "cuisines": [],
        "spicy_level": "",
    },
    "allergies": [],
    "health_conditions": [],
    "lifestyle": {
        "exercise_frequency": "",
        "exercise_types": [],
        "exercise_time": "",
        "sleep_hours": None,
        "water_goal_ml": 2000,
        "eat_out_freq": "",
        "smoking": False,
        "alcohol": False,
    },
    "nutrition_targets": {},
    "onboarding": {"done": False, "skipped": [], "completed_at": None},
    "tracking": {"date": "", "water_logs": [], "meals": [], "workouts": []},
}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _db_lock, _connect() as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                email TEXT COLLATE NOCASE UNIQUE,
                phone TEXT UNIQUE,
                display_name TEXT,
                password_hash TEXT NOT NULL,
                avatar TEXT NOT NULL DEFAULT '{"type":"initials"}',
                language TEXT NOT NULL DEFAULT 'auto',
                theme TEXT NOT NULL DEFAULT 'light',
                onboarding_done INTEGER NOT NULL DEFAULT 0,
                profile TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        conn.commit()


# --------------------------------------------------------------------------
# 密码学工具
# --------------------------------------------------------------------------

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), _ITERATIONS)
    return f"pbkdf2${_ITERATIONS}${salt}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iters, salt, expected = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), int(iters))
        return hmac.compare_digest(dk.hex(), expected)
    except Exception:
        return False


def _new_token() -> str:
    return secrets.token_urlsafe(32)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# 数据库访问
# --------------------------------------------------------------------------

def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_user(row: sqlite3.Row) -> Dict[str, Any]:
    try:
        avatar = json.loads(row["avatar"])
    except Exception:
        avatar = {"type": "initials"}
    try:
        profile = json.loads(row["profile"])
    except Exception:
        profile = {}
    return {
        "id": row["id"],
        "username": row["username"],
        "email": row["email"],
        "phone": row["phone"],
        "display_name": row["display_name"] or row["username"],
        "avatar": avatar,
        "language": row["language"],
        "theme": row["theme"],
        "onboarding_done": bool(row["onboarding_done"]),
        "profile": _merge_profile(profile),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def public_user(user: Dict[str, Any]) -> Dict[str, Any]:
    """去掉内部字段，只返回可展示信息"""
    return {k: v for k, v in user.items() if k != "profile"}


# --------------------------------------------------------------------------
# 校验
# --------------------------------------------------------------------------

def _validate_username(username: str) -> str:
    username = (username or "").strip()
    if not (2 <= len(username) <= 24):
        raise ValueError("用户名长度需在 2-24 个字符之间")
    if not re.fullmatch(r"[\w\u4e00-\u9fa5.\-]+", username):
        raise ValueError("用户名只能包含字母、数字、下划线、中文字符")
    return username


def _validate_email(email: str) -> Optional[str]:
    email = (email or "").strip().lower()
    if not email:
        return None
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise ValueError("邮箱格式不正确")
    return email


def _validate_phone(phone: str) -> Optional[str]:
    phone = (phone or "").strip().replace(" ", "").replace("-", "")
    if not phone:
        return None
    if not re.fullmatch(r"\+?\d{6,20}", phone):
        raise ValueError("手机号格式不正确")
    return phone


def _validate_password(password: str) -> str:
    if len(password) < 6:
        raise ValueError("密码至少需要 6 位")
    if len(password) > 72:
        raise ValueError("密码过长")
    return password


def _merge_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    """递归把数据库里的 profile 与默认结构合并，保证前端永远拿全字段"""
    import copy
    merged = copy.deepcopy(DEFAULT_PROFILE)

    def _deep_merge(base: Dict, extra: Dict) -> None:
        for k, v in (extra or {}).items():
            if isinstance(v, dict) and isinstance(base.get(k), dict):
                _deep_merge(base[k], v)
            else:
                base[k] = v

    _deep_merge(merged, profile)
    return merged


# --------------------------------------------------------------------------
# 账户操作
# --------------------------------------------------------------------------

def register_user(
    username: str,
    password: str,
    email: str = None,
    phone: str = None,
    display_name: str = None,
    avatar: dict = None,
) -> Dict[str, Any]:
    username = _validate_username(username)
    email = _validate_email(email)
    phone = _validate_phone(phone)
    password = _validate_password(password)
    if not email and not phone:
        raise ValueError("请填写邮箱或手机号，用于登录")

    display_name = (display_name or "").strip() or username
    avatar = avatar if isinstance(avatar, dict) else {"type": "initials"}
    now = _now()
    with _db_lock, _connect() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO users (username, email, phone, display_name, password_hash, avatar, created_at, updated_at, profile) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    username,
                    email,
                    phone,
                    display_name,
                    hash_password(password),
                    json.dumps(avatar),
                    now,
                    now,
                    json.dumps({}),
                ),
            )
            conn.commit()
            uid = cur.lastrowid
        except sqlite3.IntegrityError as e:
            msg = str(e).lower()
            if "username" in msg:
                raise ValueError("该用户名已被注册")
            if "email" in msg:
                raise ValueError("该邮箱已被注册")
            if "phone" in msg:
                raise ValueError("该手机号已被注册")
            raise ValueError("注册失败，请重试")
    return get_user_by_id(uid)


def authenticate(identifier: str, password: str) -> Optional[Dict[str, Any]]:
    identifier = (identifier or "").strip()
    if not identifier:
        return None
    with _db_lock, _connect() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE lower(username)=lower(?) OR lower(email)=lower(?) OR phone=?",
            (identifier, identifier, identifier),
        ).fetchone()
    if row is None:
        return None
    if not verify_password(password, row["password_hash"]):
        return None
    return get_user_by_id(row["id"])


def create_session(user_id: int) -> str:
    token = _new_token()
    expires = (datetime.now() + timedelta(days=_SESSION_DAYS)).isoformat(timespec="seconds")
    with _db_lock, _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO sessions (token_hash, user_id, expires_at, created_at) VALUES (?,?,?,?)",
            (_hash_token(token), user_id, expires, _now()),
        )
        conn.commit()
    return token


def get_user_by_token(token: str) -> Optional[Dict[str, Any]]:
    if not token:
        return None
    try:
        with _db_lock, _connect() as conn:
            row = conn.execute(
                "SELECT s.user_id, s.expires_at FROM sessions s WHERE s.token_hash=?",
                (_hash_token(token),),
            ).fetchone()
        if row is None:
            return None
        expires = datetime.fromisoformat(row["expires_at"])
        if datetime.now() > expires:
            delete_session(token)
            return None
        return get_user_by_id(row["user_id"])
    except Exception:
        return None


def delete_session(token: str) -> None:
    if not token:
        return
    with _db_lock, _connect() as conn:
        conn.execute("DELETE FROM sessions WHERE token_hash=?", (_hash_token(token),))
        conn.commit()


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    with _db_lock, _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if row is None:
        return None
    return _row_to_user(row)


def update_account(user_id: int, fields: Dict[str, Any]) -> Dict[str, Any]:
    """更新账号级字段（头像 / 昵称 / 语言 / 主题 / 是否完成引导）"""
    allowed = {
        "display_name": lambda v: (str(v).strip() or None),
        "avatar": lambda v: json.dumps(v) if isinstance(v, dict) else str(v),
        "language": lambda v: str(v),
        "theme": lambda v: str(v),
        "onboarding_done": lambda v: 1 if v else 0,
    }
    sets, vals = [], []
    for k, fn in allowed.items():
        if k in fields and fields[k] is not None:
            sets.append(f"{k}=?")
            vals.append(fn(fields[k]))
    if not sets:
        return get_user_by_id(user_id)
    vals.append(_now())
    vals.append(user_id)
    sets.append("updated_at=?")
    with _db_lock, _connect() as conn:
        conn.execute(f"UPDATE users SET {', '.join(sets)} WHERE id=?", vals)
        conn.commit()
    return get_user_by_id(user_id)


def change_password(user_id: int, old_password: str, new_password: str) -> bool:
    new_password = _validate_password(new_password)
    with _db_lock, _connect() as conn:
        row = conn.execute("SELECT password_hash FROM users WHERE id=?", (user_id,)).fetchone()
    if row is None:
        return False
    if not verify_password(old_password, row["password_hash"]):
        return False
    with _db_lock, _connect() as conn:
        conn.execute(
            "UPDATE users SET password_hash=?, updated_at=? WHERE id=?",
            (hash_password(new_password), _now(), user_id),
        )
        conn.commit()
    return True


def change_contact(user_id: int, field: str, value: Optional[str]) -> Dict[str, Any]:
    """修改邮箱或手机号"""
    if field not in ("email", "phone"):
        raise ValueError("不支持的字段")
    if field == "email":
        value = _validate_email(value)
    else:
        value = _validate_phone(value)
    with _db_lock, _connect() as conn:
        try:
            conn.execute(
                f"UPDATE users SET {field}=?, updated_at=? WHERE id=?",
                (value, _now(), user_id),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            raise ValueError("该联系方式已被其他账号使用")
    return get_user_by_id(user_id)


def update_profile(user_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
    """深度合并更新个性化资料"""
    user = get_user_by_id(user_id)
    merged = _merge_profile(user["profile"])
    _deep_update(merged, updates or {})
    with _db_lock, _connect() as conn:
        conn.execute(
            "UPDATE users SET profile=?, updated_at=? WHERE id=?",
            (json.dumps(merged, ensure_ascii=False), _now(), user_id),
        )
        conn.commit()
    return get_user_by_id(user_id)


def _deep_update(base: Dict[str, Any], updates: Dict[str, Any]) -> None:
    for k, v in (updates or {}).items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_update(base[k], v)
        else:
            base[k] = v


# --------------------------------------------------------------------------
# 每日记录（喝水 / 加餐 / 运动）
# --------------------------------------------------------------------------

def add_tracking_entry(user_id: int, entry: Dict[str, Any]) -> Dict[str, Any]:
    """在“今天”的记录里追加一条。entry: {type: water|meal|workout, ...}"""
    user = get_user_by_id(user_id)
    profile = user["profile"]
    tr = profile.setdefault("tracking", {})
    if tr.get("date") != _today():
        tr["date"] = _today()
        tr["water_logs"] = []
        tr["meals"] = []
        tr["workouts"] = []
    etype = entry.get("type")
    item = dict(entry)
    item["t"] = datetime.now().strftime("%H:%M")
    if etype == "water":
        tr.setdefault("water_logs", []).append(item)
    elif etype == "meal":
        tr.setdefault("meals", []).append(item)
    elif etype == "workout":
        tr.setdefault("workouts", []).append(item)
    else:
        raise ValueError("unknown tracking type")
    return update_profile(user_id, {"tracking": tr})


def undo_tracking(user_id: int, etype: str) -> Dict[str, Any]:
    user = get_user_by_id(user_id)
    profile = user["profile"]
    tr = profile.get("tracking", {})
    if tr.get("date") != _today():
        return update_profile(user_id, {"tracking": {"date": _today(), "water_logs": [], "meals": [], "workouts": []}})
    key = {"water": "water_logs", "meal": "meals", "workout": "workouts"}.get(etype)
    if key and tr.get(key):
        tr[key].pop()
    return update_profile(user_id, {"tracking": tr})


