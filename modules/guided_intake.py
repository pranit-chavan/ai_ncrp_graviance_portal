"""Grounded, English-only citizen workflow. No inferred identity or clock defaults."""
from typing import Any
from pydantic import BaseModel, Field
from modules.conversational_agent import conduct_counselor_turn
from modules.classifier_service import classify_complaint_text
from modules.legal_mapping import map_sections, get_main_category


class GuidedTurn(BaseModel):
    message: str = Field(min_length=1, max_length=12000)
    history: list[dict[str, str]] = Field(default_factory=list, max_length=24)
    docket: dict[str, Any] = Field(default_factory=dict)


class GuidedReview(BaseModel):
    narrative: str = Field(min_length=10, max_length=20000)
    fields: dict[str, Any] = Field(default_factory=dict)
    age: int | None = Field(default=None, ge=1, le=120)
    category: str | None = None


def guided_turn(req: GuidedTurn):
    result = conduct_counselor_turn(req.message, req.history, req.docket, language="en")
    return {"ok": True, "reply": result["spoken_response"].replace("You can upload its screenshot below and I’ll read it for you.", "If you have a screenshot, you can add it in the Describe step."), "docket": result}


def guided_review(req: GuidedReview):
    # User-reviewed fields remain separate from the original account.
    facts = "\n".join(f"{key.replace('_', ' ')}: {value}" for key, value in req.fields.items()
                      if value is not None and str(value).strip())
    result = classify_complaint_text(req.narrative + "\n" + facts)
    from modules.legal_mapping import CATEGORIES
    category = req.category if req.category in CATEGORIES else result["predicted_category"]
    return {"ok": True, "classification": result, "category": category,
            "main_category": get_main_category(category),
            "legal": map_sections(category, complainant_age=req.age)}
