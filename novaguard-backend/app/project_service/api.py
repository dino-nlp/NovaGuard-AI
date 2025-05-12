from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List

from app.core.db import get_db
from app.project_service import schemas, crud_project
from app.auth_service.auth_bearer import get_current_active_user # Dependency xác thực
from app.auth_service.schemas import UserPublic # Để lấy user_id

router = APIRouter()

@router.post("/", response_model=schemas.ProjectPublic, status_code=status.HTTP_201_CREATED)
async def create_new_project(
    project_in: schemas.ProjectCreate,
    db: Session = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_user) # Yêu cầu xác thực
):
    """
    Tạo một project mới cho người dùng hiện tại.
    """
    created_project = crud_project.create_project(db=db, project_in=project_in, user_id=current_user.id)
    if not created_project:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, # Conflict nếu project đã tồn tại cho user này
            detail="Project with this GitHub Repo ID already exists for this user.",
        )
    return created_project

@router.get("/", response_model=schemas.ProjectList) # Sử dụng ProjectList để bao gồm total
async def read_user_projects(
    db: Session = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_user),
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(10, ge=1, le=100, description="Number of items to return per page")
):
    """
    Lấy danh sách các project của người dùng hiện tại.
    """
    projects_db = crud_project.get_projects_by_user(db=db, user_id=current_user.id, skip=skip, limit=limit)
    # Trong tương lai có thể cần query tổng số project riêng để phân trang chính xác hơn
    # total_projects = db.query(func.count(Project.id)).filter(Project.user_id == current_user.id).scalar()
    # Hiện tại, total có thể là số lượng project trả về trong batch này
    return {"projects": projects_db, "total": len(projects_db)} # Hoặc total_projects nếu có

@router.get("/{project_id}", response_model=schemas.ProjectPublic)
async def read_project_details(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_user)
):
    """
    Lấy chi tiết một project cụ thể của người dùng hiện tại.
    """
    db_project = crud_project.get_project_by_id(db=db, project_id=project_id, user_id=current_user.id)
    if db_project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found or not owned by user")
    return db_project

@router.put("/{project_id}", response_model=schemas.ProjectPublic)
async def update_existing_project(
    project_id: int,
    project_in: schemas.ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_user)
):
    """
    Cập nhật thông tin một project của người dùng hiện tại.
    """
    updated_project = crud_project.update_project(
        db=db, project_id=project_id, project_in=project_in, user_id=current_user.id
    )
    if updated_project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found or not owned by user")
    return updated_project

@router.delete("/{project_id}", response_model=schemas.ProjectPublic) # Hoặc chỉ trả về status 204 No Content
async def delete_existing_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_user)
):
    """
    Xóa một project của người dùng hiện tại.
    """
    deleted_project = crud_project.delete_project(db=db, project_id=project_id, user_id=current_user.id)
    if deleted_project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found or not owned by user")
    return deleted_project # Trả về thông tin project đã xóa