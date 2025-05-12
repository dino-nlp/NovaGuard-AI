from pydantic import BaseModel, EmailStr, Field
from typing import Optional # Sẽ dùng khi có các trường tùy chọn
from datetime import datetime

# --- User Schemas ---

# Thuộc tính cơ bản của User, dùng chung
class UserBase(BaseModel):
    email: EmailStr # Pydantic sẽ validate định dạng email

# Schema cho việc tạo User mới (input từ API)
class UserCreate(UserBase):
    password: str = Field(..., min_length=8, description="User password, at least 8 characters")

# Schema cho việc đọc thông tin User (output cho API)
# Sẽ không bao gồm password_hash
class UserPublic(UserBase):
    id: int
    # github_user_id: Optional[str] = None # Bỏ comment khi tích hợp GitHub OAuth
    created_at: datetime
    updated_at: datetime

    class Config:
        # Trước đây là orm_mode = True, giờ là from_attributes = True trong Pydantic V2
        # Giúp Pydantic model đọc dữ liệu từ các SQLAlchemy model (hoặc các đối tượng có attribute tương tự)
        from_attributes = True


# --- Token Schemas ---

class Token(BaseModel):
    access_token: str
    token_type: str # Thường là "bearer"

class TokenPayload(BaseModel):
    sub: Optional[str] = None # 'sub' (subject) thường là user ID hoặc email
    exp: Optional[datetime] = None # Thời gian hết hạn của token

# Schema cho form đăng nhập (sử dụng OAuth2PasswordRequestForm của FastAPI sẽ tiện hơn)
# Tuy nhiên, định nghĩa một schema tường minh cũng tốt cho việc hiểu rõ
class UserLogin(BaseModel):
    username: EmailStr # FastAPI OAuth2PasswordRequestForm dùng 'username', chúng ta sẽ map email vào đây
    password: str