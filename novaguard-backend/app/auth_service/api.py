from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm # Form chuẩn cho login
from sqlalchemy.orm import Session
from datetime import timedelta

from app.core.db import get_db
from app.auth_service import schemas, crud_user
from app.core.security import create_access_token, verify_password
from app.core.config import settings
from app.common.message_queue.kafka_producer import send_pr_analysis_task

router = APIRouter()

@router.post("/register", response_model=schemas.UserPublic, status_code=status.HTTP_201_CREATED)
async def register_new_user(
    user_in: schemas.UserCreate, 
    db: Session = Depends(get_db)
):
    """
    Đăng ký một người dùng mới.
    - Kiểm tra xem email đã tồn tại chưa.
    - Tạo user mới nếu chưa tồn tại.
    """
    db_user = crud_user.get_user_by_email(db, email=user_in.email)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    created_user = crud_user.create_user(db=db, user=user_in)
    return created_user

@router.post("/login", response_model=schemas.Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), # Sử dụng form chuẩn của FastAPI
    db: Session = Depends(get_db)
):
    """
    Đăng nhập người dùng và trả về access token.
    - Xác thực user bằng email (form_data.username) và password.
    - Tạo và trả về JWT nếu xác thực thành công.
    """
    user = crud_user.get_user_by_email(db, email=form_data.username) # form_data.username là email
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"}, # Chuẩn cho lỗi 401
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user.email, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# Có thể thêm endpoint để test token (yêu cầu xác thực) sau này
# Ví dụ:
# from app.auth_service.auth_bearer import JWTBearer # Sẽ tạo sau nếu cần
# @router.get("/users/me", response_model=schemas.UserPublic)
# async def read_users_me(current_user: schemas.UserPublic = Depends(JWTBearer())): # Sẽ lỗi nếu JWTBearer chưa có
# return current_user
@router.post("/test-send-kafka-message", status_code=status.HTTP_202_ACCEPTED)
async def test_send_kafka(data: dict):
    """Endpoint tạm thời để test gửi message tới Kafka."""
    success = await send_pr_analysis_task(data)
    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to send message to Kafka")
    return {"message": "Message sending task accepted", "data_sent": data}