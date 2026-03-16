from pydantic import BaseModel


class StreamStatusResponse(BaseModel):
    mode: str
    status: str
