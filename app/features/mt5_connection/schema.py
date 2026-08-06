from pydantic import BaseModel


class MT5ConnectionStatus(BaseModel):
    connected: bool
    login: int | None = None
    server: str | None = None
    balance: float | None = None
    equity: float | None = None
