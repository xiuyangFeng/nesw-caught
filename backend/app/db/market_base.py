from sqlalchemy.orm import DeclarativeBase


class MarketBase(DeclarativeBase):
    """独立行情库 metadata，不得与主库 Base 混用。"""
