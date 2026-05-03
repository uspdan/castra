from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class InstanceResponse(BaseModel):
    id: int
    user_id: int
    challenge_id: int
    container_id: Optional[str] = None
    container_name: Optional[str] = None
    status: str
    assigned_ip: Optional[str] = None
    assigned_port: Optional[int] = None
    started_at: datetime
    expires_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    challenge_slug: Optional[str] = None

    model_config = {"from_attributes": True}


class InstanceLaunchResponse(BaseModel):
    instance_id: int
    container_id: str
    ip: Optional[str] = None
    port: int
    expires_at: datetime
