from fastapi import Request, Depends
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from sqlalchemy.orm import Session

from app.config import SECRET_KEY, COOKIE_NAME, COOKIE_MAX_AGE
from app.database import get_db
from app.models import User

serializer = URLSafeTimedSerializer(SECRET_KEY)


def create_session_token(user_id: int) -> str:
    return serializer.dumps({"user_id": user_id})


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    try:
        data = serializer.loads(token, max_age=COOKIE_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    return db.query(User).filter(User.id == data["user_id"]).first()
