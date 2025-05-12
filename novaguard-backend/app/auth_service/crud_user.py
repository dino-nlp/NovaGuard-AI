from sqlalchemy.orm import Session

from app.models.user_model import User # Model SQLAlchemy
from app.auth_service.schemas import UserCreate # Schema Pydantic
from app.core.security import get_password_hash # Hàm hash password (sẽ tạo ở file security.py)

def get_user_by_email(db: Session, email: str) -> User | None:
    """
    Lấy một user từ DB bằng địa chỉ email.
    """
    return db.query(User).filter(User.email == email).first()

def get_user_by_id(db: Session, user_id: int) -> User | None:
    """
    Lấy một user từ DB bằng ID.
    """
    return db.query(User).filter(User.id == user_id).first()

def create_user(db: Session, user: UserCreate) -> User:
    """
    Tạo một user mới trong DB.
    """
    hashed_password = get_password_hash(user.password)
    db_user = User(
        email=user.email,
        password_hash=hashed_password
        # Các trường khác như github_user_id sẽ được cập nhật sau
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user) # Lấy lại thông tin user từ DB (ví dụ: để có ID, created_at)
    return db_user

# Các hàm CRUD khác có thể được thêm vào đây nếu cần (ví dụ: update_user, delete_user)
# Nhưng cho MVP1 của auth_service, get và create là đủ.