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
    use_rewrite: bool = Field(default=False, description="是否启用查询重写（默认关闭以提速）")


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
# 智能餐食分析
# --------------------------------------------------------------------------

class AnalyzeMealRequest(BaseModel):
    description: str = Field(..., description="食物描述，如 '一碗米饭加红烧肉和清炒西兰花'")

ANALYZE_PROMPT = """你是一位专业的营养师。请根据用户描述的一餐食物，估算这餐饭的营养成分。

食物描述：{description}

请严格按以下 JSON 格式返回（不要加其他文字）：
{{
  "calories": 数字,
  "protein": 数字,
  "fat": 数字,
  "carbs": 数字,
  "fiber": 数字,
  "vitamins": ["维生素A", "维生素C", ...],
  "minerals": ["钙", "铁", ...],
  "health_score": 1到10的评分,
  "suggestion": "一句话健康建议"
}}

注意：
- 热量单位 kcal，其他单位 g
- health_score：1=非常不健康，10=非常健康
- 只输出 JSON，不要加 markdown 代码块"""


@app.post("/api/analyze-meal")
async def analyze_meal(req: AnalyzeMealRequest):
    if rag_service is None:
        raise HTTPException(status_code=503, detail="服务尚未就绪")
    try:
        from langchain_core.prompts import ChatPromptTemplate
        prompt = ChatPromptTemplate.from_template(ANALYZE_PROMPT)
        chain = prompt | rag_service.generator.llm | (lambda x: x.content)
        result = await chain.ainvoke({"description": req.description})
        import json, re
        result = result.strip()
        if result.startswith("```"):
            result = re.sub(r"^```(?:json)?\s*", "", result)
            result = re.sub(r"\s*```$", "", result)
        data = json.loads(result)
        return data
    except json.JSONDecodeError:
        return {
            "calories": 0, "protein": 0, "fat": 0, "carbs": 0, "fiber": 0,
            "vitamins": [], "minerals": [], "health_score": 5,
            "suggestion": "无法精确分析，请咨询营养师"
        }
    except Exception as e:
        logger.error(f"餐食分析失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# --------------------------------------------------------------------------
# 发现页内容目录
# --------------------------------------------------------------------------

_recipe_cache = {"sig": None, "items": None}

RECIPE_CATEGORY_DIRS = ["减脂餐", "增肌餐", "维持餐"]


def _recipe_signature():
    sig = []
    for cat in RECIPE_CATEGORY_DIRS:
        d = data_dir / "recipes" / cat
        if not d.exists():
            continue
        for fp in sorted(d.glob("*.md")):
            st = fp.stat()
            sig.append(f"{fp.stem}|{st.st_size}|{int(st.st_mtime)}")
    return "|".join(sig)


def _guess_meal_type(title: str, desc: str) -> str:
    text = title + desc
    breakfast_kw = ["早餐", "燕麦", "吐司", "三明治", "奶昔", "煎饼", "粥", "卷饼", "酸奶"]
    if any(k in text for k in breakfast_kw):
        return "breakfast"
    soup_kw = ["汤", "羹"]
    if any(k in text for k in soup_kw):
        return "dinner"
    return ""


def _parse_nutrition(lines):
    out = {}
    mapping = {"热量": "calories", "蛋白质": "protein", "脂肪": "fat",
               "碳水化合物": "carbs", "碳水": "carbs", "膳食纤维": "fiber"}
    for ln in lines:
        raw = ln.strip().lstrip("-*").strip()
        for cn, en in mapping.items():
            if raw.startswith(cn) and "：" in raw:
                val = raw.split("：", 1)[1]
                num = ""
                for ch in val:
                    if ch.isdigit() or ch == ".":
                        num += ch
                    elif num:
                        break
                try:
                    out[en] = float(num)
                except Exception:
                    pass
                break
    return out


def _parse_recipe_md(fp: Path) -> dict:
    text = fp.read_text(encoding="utf-8")
    title = fp.stem
    for ln in text.splitlines():
        if ln.startswith("# "):
            title = ln[2:].strip()
            break
    desc = ""
    nutrition = {}
    ingredients = []
    steps = []
    suitable = ""
    tips = ""
    current = None
    for raw in text.splitlines():
        ln = raw.strip()
        if not ln:
            continue
        if ln.startswith("## "):
            current = ln[3:].strip()
            continue
        if ln.startswith("# "):
            continue
        if current == "食材" and (ln.startswith("-") or ln.startswith("*")):
            item = ln.lstrip("-* ").strip()
            m = __import__("re").match(r"(.+?)\s+([\d.]+)\s*([a-zA-Z克毫升gml个片瓣勺块根]*)", item)
            if m:
                ingredients.append({"name": m.group(1).strip(), "amount": float(m.group(2)), "unit": m.group(3)})
            else:
                ingredients.append({"name": item, "amount": 0, "unit": ""})
        elif current == "烹饪步骤" and ln[:1].isdigit():
            steps.append(ln.split(".", 1)[-1].strip())
        elif current == "营养成分":
            for _k, _v in _parse_nutrition([ln]).items():
                nutrition[_k] = _v
        elif current == "适合人群":
            suitable = ln
        elif current == "小贴士":
            tips = ln
        elif desc == "" and current is None and not ln.startswith("##"):
            desc = ln
    if not steps and not ingredients:
        # 部分文件用纯文本段落
        pass
    tags = []
    tag_map = [
        ("高蛋白", "高蛋白"), ("低脂", "低脂"), ("低卡", "低卡"), ("高纤", "高纤"),
        ("低碳", "低碳"), ("控糖", "控糖"), ("补铁", "补铁"), ("补钙", "补钙"),
        ("快手", "快手菜"), ("汤", "汤品"), ("凉拌", "凉拌"), ("素食", "素食"),
        ("早餐", "早餐"), ("增肌", "增肌餐"), ("减脂", "减脂餐"),
    ]
    hay = (title + desc + suitable).lower()
    for kw, label in tag_map:
        if kw.lower() in hay and label not in tags:
            tags.append(label)
    category = fp.parent.name
    meal_type = _guess_meal_type(title, desc)
    return {
        "recipe_id": fp.stem,
        "name": title,
        "category": category,
        "meal_type": meal_type,
        "calories": int(nutrition.get("calories") or 0),
        "protein": round(nutrition.get("protein") or 0, 1),
        "fat": round(nutrition.get("fat") or 0, 1),
        "carbs": round(nutrition.get("carbs") or 0, 1),
        "fiber": round(nutrition.get("fiber") or 0, 1),
        "description": desc,
        "ingredients": ingredients,
        "steps": steps,
        "tags": tags,
        "suitable_for": suitable,
        "tips": tips,
    }


def _read_recipes():
    sig = _recipe_signature()
    if _recipe_cache["sig"] == sig and _recipe_cache["items"] is not None:
        return _recipe_cache["items"]
    items = []
    for cat in RECIPE_CATEGORY_DIRS:
        d = data_dir / "recipes" / cat
        if not d.exists():
            continue
        for fp in sorted(d.glob("*.md")):
            try:
                items.append(_parse_recipe_md(fp))
            except Exception as exc:
                logger.warning(f"解析菜谱失败 {fp.name}: {exc}")
    _recipe_cache["sig"] = sig
    _recipe_cache["items"] = items
    return items


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
            "fiber": r.get("fiber", 0),
            "difficulty": "",
            "cook_time": 0,
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