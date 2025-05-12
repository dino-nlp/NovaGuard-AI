from sqlalchemy import Column, Integer, String, Text, DateTime, func
from sqlalchemy.orm import relationship # Sẽ dùng sau nếu có quan hệ

from app.core.db import Base # Import Base từ db.py

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(Text, nullable=False)
    
    github_user_id = Column(String(255), unique=True, nullable=True, index=True)
    github_access_token_encrypted = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    # Định nghĩa mối quan hệ với bảng Project (one-to-many: một User có nhiều Project)
    projects = relationship("Project", back_populates="owner", cascade="all, delete-orphan")


    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}')>"

# Bạn có thể thêm các model khác vào đây hoặc tạo file riêng cho chúng
# Ví dụ: project_model.py, pr_analysis_request_model.py, ...