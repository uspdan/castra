from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SolveResponse(BaseModel):
    id: int
    user_id: int
    challenge_id: int
    points_awarded: int
    hint_used: bool
    is_first_blood: bool
    time_to_solve: Optional[int] = None
    solved_at: datetime

    model_config = {"from_attributes": True}


class FlagResult(BaseModel):
    correct: bool
    points_awarded: Optional[int] = None
    is_first_blood: Optional[bool] = None
    message: Optional[str] = None
