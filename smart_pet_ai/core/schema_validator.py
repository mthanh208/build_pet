# -*- coding: utf-8 -*-
try:
    from pydantic import BaseModel, Field, ValidationError
    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False
    BaseModel = object

if HAS_PYDANTIC:
    class UserInput(BaseModel):
        text: str = Field(..., min_length=1)
        emotion: str = Field(default="bình yên")
        confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    class PetResponse(BaseModel):
        answer: str = Field(..., min_length=1)
        think_block: str = Field(default="")
        emotion: str = Field(default="bình yên")
        confidence: float = Field(default=0.5, ge=0.0, le=1.0)
        sources: list = Field(default_factory=list)

    class DocumentRecord(BaseModel):
        id: int
        text: str = Field(..., min_length=1)
        source: str = Field(default="unknown")
        weight: float = Field(default=1.0, ge=0.0, le=10.0)

    class MemoryRecord(BaseModel):
        role: str = Field(..., pattern="^(user|pet|system)$")
        text: str = Field(..., min_length=1)
        time: float = Field(default=0.0)
        importance: float = Field(default=0.5, ge=0.0, le=1.0)
else:
    UserInput = None
    PetResponse = None
    DocumentRecord = None
    MemoryRecord = None

class SchemaValidator:
    def __init__(self):
        self.available = HAS_PYDANTIC

    def validate_input(self, text, emotion="bình yên", confidence=1.0):
        if not self.available:
            return True, {"text": text, "emotion": emotion, "confidence": confidence}
        try:
            inp = UserInput(text=text, emotion=emotion, confidence=confidence)
            return True, inp.model_dump()
        except ValidationError as e:
            return False, str(e)
        except:
            return True, {"text": text, "emotion": emotion, "confidence": confidence}

    def validate_response(self, answer, think_block="", emotion="bình yên", confidence=0.5, sources=None):
        if not self.available:
            return True, {"answer": answer, "think_block": think_block, "emotion": emotion, "confidence": confidence, "sources": sources or []}
        try:
            resp = PetResponse(answer=answer, think_block=think_block, emotion=emotion, confidence=confidence, sources=sources or [])
            return True, resp.model_dump()
        except ValidationError as e:
            return False, str(e)
        except:
            return True, {"answer": answer, "think_block": think_block, "emotion": emotion, "confidence": confidence, "sources": sources or []}

    def stats(self):
        return {"available": self.available}
