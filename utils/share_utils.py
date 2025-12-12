# backend/utils/share_utils.py
import uuid
from datetime import datetime, timedelta

def create_share_token():
    return uuid.uuid4().hex

def make_expiry(days:int=7):
    return datetime.utcnow() + timedelta(days=days)