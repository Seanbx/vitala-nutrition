"""
FastAPI 服务层 —— Vitala 营养助手
提供：账户注册/登录/会话、个人资料、每日记录、RAG 对话、内容目录
"""

import os
import sys
import logging
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional, Any, Dict

from fastapi import FastAPI, HTTPException, Request, Header, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

rag_service = None
NO_RAG = os.getenv("NUTRI_NO_RAG") == "1"

PROJECT_ROOT = Path(__file__).parent.parent
static_dir = PROJECT_ROOT / "static"
data_dir = PROJECT_ROOT / "data"


@asynccontextmanager
async def lifespan(app: FastAPI):
    global rag_service
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
    from src import accounts
    accounts.init_db()
    if not NO_RAG:
        try:
            from src.rag_service import NutriRAGService
            rag_service = NutriRAGService()
            logger.info("RAG 服务就绪")
        except Exception as e:
            logger.error(f"RAG 初始化失败: {e}，对话功能暂不可用")
    yield
    logger.info("服务关闭")


app = FastAPI(
    title="Vitala — AI Nutrition Companion API",
    description="个性化营养助手：真实账户 + 个性化画像 + RAG 智能问答",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# --------------------------------------------------------------------------
# 工具
# --------------------------------------------------------------------------

def _bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def _opt_user(authorization: Optional[str]):
    from src import accounts
    token = _bearer_token(authorization)
    if not token:
        return None
    return accounts.get_user_by_token(token)


def _require_user(authorization: Optional[str]):
    user = _opt_user(authorization)
    if user is None:
        raise HTTPException(status_code=401, detail="请先登录")
    return user


# --------------------------------------------------------------------------
# 请求模型
# --------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    phone: Optional[str] = None
    display_name: Optional[str] = None
    avatar: Optional[dict] = None


class LoginRequest(BaseModel):
    identifier: str
    password: str


class PasswordRequest(BaseModel):
    old_password: str
    new_password: str


class ContactRequest(BaseModel):
    field: str
    value: Optional[str] = None


class MeUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    avatar: Optional[dict] = None
    language: Optional[str] = None
    theme: Optional[str] = None
    profile: Optional[dict] = None


class OnboardingRequest(BaseModel):
    profile: Optional[dict] = None
    skipped: Optional[List[str]] = None


class TrackingRequest(BaseModel):
    type: str
    name: Optional[str] = None
    calories: Optional[float] = None
    protein_g: Optional[float] = None
    fat_g: Optional[float] = None
    carbs_g: Optional[float] = None
    minutes: Optional[int] = None
    ml: Optional[int] = None


class ChatRequest(BaseModel):
    query: str = Field(..., description="用户问题")
    user_id: str = Field(default="default", description="用户ID（兼容旧版）")
    chat_history: Optional[List[dict]] = Field(default=None, description="历史对话")
    use_rewrite: bool = Field(default=True, description="是否启用查询重写")


# --------------------------------------------------------------------------
# 页面
# --------------------------------------------------------------------------

@app.get("/")
async def root():
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "Vitala API", "docs": "/docs"}


@app.get("/manifest.webmanifest")
async def manifest():
    f = static_dir / "manifest.webmanifest"
    if f.exists():
        return FileResponse(str(f), media_type="application/manifest+json")
    raise HTTPException(404)


# --------------------------------------------------------------------------
# 账户：注册 / 登录 / 登出 / 个人信息
# --------------------------------------------------------------------------

@app.post("/api/auth/register")
async def register(req: RegisterRequest, authorization: Optional[str] = Header(None)):
    from src import accounts
    try:
        user = accounts.register_user(
            username=req.username,
            password=req.password,
            email=req.email,
            phone=req.phone,
            display_name=req.display_name,
            avatar=req.avatar,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    token = accounts.create_session(user["id"])
    return {"token": token, "user": accounts.public_user(user)}


@app.post("/api/auth/login")
async def login(req: LoginRequest, authorization: Optional[str] = Header(None)):
    from src import accounts
    user = accounts.authenticate(req.identifier, req.password)
    if user is None:
        raise HTTPException(status_code=401, detail="账号或密码错误")
    token = accounts.create_session(user["id"])
    return {"token": token, "user": accounts.public_user(user)}


@app.post("/api/auth/logout")
async def logout(authorization: Optional[str] = Header(None)):
    from src import accounts
    token = _bearer_token(authorization)
    if token:
        accounts.delete_session(token)
    return {"ok": True}


@app.get("/api/auth/me")
async def me(authorization: Optional[str] = Header(None)):
    user = _require_user(authorization)
    return _full_me(user)


@app.put("/api/auth/me")
async def update_me(req: MeUpdateRequest, authorization: Optional[str] = Header(None)):
    from src import accounts
    user = _require_user(authorization)
    acct_fields = {}
    if req.display_name is not None:
        acct_fields["display_name"] = req.display_name
    if req.avatar is not None:
        acct_fields["avatar"] = req.avatar
    if req.language is not None:
        acct_fields["language"] = req.language
    if req.theme is not None:
        acct_fields["theme"] = req.theme
    if acct_fields:
        user = accounts.update_account(user["id"], acct_fields)
    if req.profile is not None:
        user = accounts.update_profile(user["id"], req.profile)
    return _full_me(user)


@app.put("/api/auth/password")
async def change_password(req: PasswordRequest, authorization: Optional[str] = Header(None)):
    from src import accounts
    user = _require_user(authorization)
    if not accounts.change_password(user["id"], req.old_password, req.new_password):
        raise HTTPException(status_code=400, detail="当前密码不正确")
    return {"ok": True}


@app.put("/api/auth/contact")
async def change_contact(req: ContactRequest, authorization: Optional[str] = Header(None)):
    from src import accounts
    user = _require_user(authorization)
    try:
        user = accounts.change_contact(user["id"], req.field, req.value)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _full_me(user)


# --------------------------------------------------------------------------
# 个人资料 / 引导
# --------------------------------------------------------------------------

def _full_me(user: dict) -> dict:
    from src.user_profile import calculate_targets_from_profile
    profile = user["profile"]
    targets = calculate_targets_from_profile(profile)
    return {
        "user": {k: v for k, v in user.items() if k != "profile"},
        "profile": profile,
        "targets": targets,
    }


@app.get("/api/me")
async def get_me(authorization: Optional[str] = Header(None)):
    user = _require_user(authorization)
    return _full_me(user)


@app.put("/api/me")
async def put_me(req: MeUpdateRequest, authorization: Optional[str] = Header(None)):
    from src import accounts
    user = _require_user(authorization)
    acct_fields = {}
    for f in ("display_name", "avatar", "language", "theme"):
        v = getattr(req, f, None)
        if v is not None:
            acct_fields[f] = v
    if acct_fields:
        user = accounts.update_account(user["id"], acct_fields)
    if req.profile is not None:
        user = accounts.update_profile(user["id"], req.profile)
    return _full_me(user)


@app.post("/api/me/onboarding")
async def finish_onboarding(req: OnboardingRequest, authorization: Optional[str] = Header(None)):
    from src import accounts
    from datetime import datetime
    user = _require_user(authorization)
    if req.profile is not None:
        user = accounts.update_profile(user["id"], req.profile)
    profile = user["profile"]
    profile.setdefault("onboarding", {})
    profile["onboarding"]["done"] = True
    profile["onboarding"]["skipped"] = req.skipped or profile["onboarding"].get("skipped", [])
    profile["onboarding"]["completed_at"] = datetime.now().isoformat(timespec="seconds")
    user = accounts.update_profile(user["id"], {"onboarding": profile["onboarding"]})
    user = accounts.update_account(user["id"], {"onboarding_done": True})
    return _full_me(user)


@app.get("/api/me/targets")
async def get_targets(authorization: Optional[str] = Header(None)):
    user = _require_user(authorization)
    return _full_me(user)["targets"]


# --------------------------------------------------------------------------
# 每日记录
# --------------------------------------------------------------------------

@app.post("/api/me/tracking")
async def add_tracking(req: TrackingRequest, authorization: Optional[str] = Header(None)):
    from src import accounts
    user = _require_user(authorization)
    try:
        user = accounts.add_tracking_entry(
            user["id"],
            {k: v for k, v in req.model_dump().items() if v is not None},
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _full_me(user)


@app.delete("/api/me/tracking")
async def undo_tracking(type: str, authorization: Optional[str] = Header(None)):
    from src import accounts
    user = _require_user(authorization)
    user = accounts.undo_tracking(user["id"], type)
    return _full_me(user)


# --------------------------------------------------------------------------
# RAG 对话
# --------------------------------------------------------------------------

def _chat_profile(user: Optional[dict]) -> dict:
    if user:
        return user.get("profile", {})
    return {}


@app.post("/api/chat", response_model=None)
async def chat(req: ChatRequest, authorization: Optional[str] = Header(None)):
    if rag_service is None:
        raise HTTPException(status_code=503, detail="智能服务尚未就绪")
    user = _opt_user(authorization)
    try:
        result = rag_service.chat(
            query=req.query,
            user_id=str(user["id"]) if user else req.user_id,
            profile=_chat_profile(user) if user else None,
            chat_history=req.chat_history,
            use_rewrite=req.use_rewrite,
        )
        return result
    except Exception as e:
        logger.error(f"对话失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest, authorization: Optional[str] = Header(None)):
    if rag_service is None:
        raise HTTPException(status_code=503, detail="智能服务尚未就绪")
    user = _opt_user(authorization)

    async def gen():
        try:
            async for piece in rag_service.stream_chat(
                query=req.query,
                user_id=str(user["id"]) if user else req.user_id,
                profile=_chat_profile(user) if user else None,
                chat_history=req.chat_history,
                use_rewrite=req.use_rewrite,
            ):
                yield piece
        except Exception as e:
            logger.error(f"流式对话失败: {e}", exc_info=True)
            yield f"\n\n[error] {e}"

    return StreamingResponse(gen(), media_type="text/plain")


@app.get("/api/search")
async def search(q: str, top_k: int = 5, category: Optional[str] = None):
    if rag_service is None:
        raise HTTPException(status_code=503, detail="服务尚未就绪")
    filters = {"category": category} if category else {}
    if filters:
        docs = rag_service.retriever.metadata_filter_search(q, filters, top_k)
    else:
        docs = rag_service.retriever.hybrid_search(q, top_k)
    return {
        "query": q,
        "results": [
            {
                "title": d.metadata.get("title", ""),
                "category": d.metadata.get("category", ""),
                "doc_type": d.metadata.get("doc_type", ""),
                "content": d.page_content[:300],
                "rrf_score": d.metadata.get("rrf_score", 0),
            }
            for d in docs
        ],
    }


@app.get("/api/safety/check")
async def safety_check(q: str):
    from src.safety import SafetyValidator
    validator = SafetyValidator()
    return validator.validate_query(q)


@app.get("/api/stats")
async def stats():
    if rag_service is None:
        return {"total_chunks": 0, "has_generator": False, "status": "rag_offline"}
    info = rag_service.get_stats()
    info["status"] = "ok"
    return info


# --------------------------------------------------------------------------
# 发现页内容目录
# --------------------------------------------------------------------------

def _read_recipes():
    f = data_dir / "raw" / "recipes.json"
    if not f.exists():
        return []
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        return data.get("recipes", []) if isinstance(data, dict) else data
    except Exception as e:
        logger.warning(f"读取菜谱失败: {e}")
        return []


def _read_knowledge():
    items = []
    kdir = data_dir / "knowledge"
    if kdir.exists():
        for fp in sorted(kdir.glob("*.md")):
            try:
                text = fp.read_text(encoding="utf-8")
                items.append({
                    "id": fp.stem,
                    "title": fp.stem,
                    "doc_type": "knowledge",
                    "content": text,
                    "summary": text[:160].strip(),
                })
            except Exception:
                continue
    return items


@app.get("/api/catalog")
async def catalog():
    recipes = []
    for r in _read_recipes():
        recipes.append({
            "id": r.get("recipe_id", ""),
            "name": r.get("name", ""),
            "category": r.get("category", ""),
            "meal_type": r.get("meal_type", ""),
            "calories": r.get("calories", 0),
            "protein": r.get("protein", 0),
            "fat": r.get("fat", 0),
            "carbs": r.get("carbs", 0),
            "difficulty": r.get("difficulty", ""),
            "cook_time": r.get("cook_time", 0),
            "tags": r.get("tags", []),
        })
    knowledge = _read_knowledge()
    return {"recipes": recipes, "knowledge": knowledge}


@app.get("/api/catalog/recipe/{recipe_id}")
async def recipe_detail(recipe_id: str):
    for r in _read_recipes():
        if r.get("recipe_id") == recipe_id:
            return r
    raise HTTPException(status_code=404, detail="菜谱不存在")


@app.get("/api/catalog/knowledge/{doc_id}")
async def knowledge_detail(doc_id: str):
    fp = data_dir / "knowledge" / f"{doc_id}.md"
    if not fp.exists():
        raise HTTPException(status_code=404, detail="内容不存在")
    return {"id": doc_id, "title": doc_id, "content": fp.read_text(encoding="utf-8")}


# --------------------------------------------------------------------------
# 旧版兼容接口（避免破坏历史脚本/测试）
# --------------------------------------------------------------------------

@app.get("/api/profile/{user_id}")
async def get_profile_legacy(user_id: str):
    if rag_service is None:
        raise HTTPException(status_code=503, detail="服务尚未就绪")
    return {"user_id": user_id, "profile": rag_service.user_manager.get_profile(user_id)}


@app.post("/api/profile")
async def update_profile_legacy(body: dict = Body(...)):
    if rag_service is None:
        raise HTTPException(status_code=503, detail="服务尚未就绪")
    user_id = body.get("user_id", "default")
    updates = body.get("updates", {})
    updated = rag_service.user_manager.update_profile(user_id, updates)
    return {"user_id": user_id, "profile": updated}


@app.get("/api/profile/{user_id}/targets")
async def get_targets_legacy(user_id: str):
    if rag_service is None:
        raise HTTPException(status_code=503, detail="服务尚未就绪")
    targets = rag_service.user_manager.calculate_nutrition_targets(user_id)
    return {"user_id": user_id, "targets": targets}