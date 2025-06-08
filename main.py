import os
import uuid
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
import gc
import aiofiles
import magic
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse

from config import settings

settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="Robust Image Host",
    description="Một dịch vụ lưu trữ ảnh tạm thời với mã nguồn ổn định và bảo mật."
)

def _make_filename(orig_name: str, expire_at: int) -> str:
    """Tạo tên file duy nhất kết hợp UUID và thời gian hết hạn."""
    ext = Path(orig_name).suffix.lower()
    return f"{uuid.uuid4().hex}__{expire_at}{ext}"

def _parse_expire_from_name(name: str) -> int | None:
    """Trích xuất timestamp hết hạn từ tên file."""
    try:
        return int(name.split("__")[1].split(".")[0])
    except (IndexError, ValueError):
        return None

@app.get("/ping", tags=["Health Check"])
async def ping():
    """
    Endpoint kiểm tra tình trạng hoạt động của server.
    Trả về "pong" nếu server đang chạy.
    """
    gc.collect()
    return {"ping": "pong"}

@app.post("/upload", tags=["Image Operations"])
async def upload_image(
    file: UploadFile = File(...),
    expires_in: int = Form(..., description=f"Thời gian tồn tại (giây), tối đa {settings.TTL_LIMIT}")
):
    """
    Tải ảnh lên, xác thực loại file, và lưu trữ một cách hiệu quả và ổn định.
    """
    if not (0 < expires_in <= settings.TTL_LIMIT):
        raise HTTPException(400, f"expires_in phải nằm trong khoảng 1–{settings.TTL_LIMIT}")

    file_header = await file.read(2048)
    await file.seek(0)

    file_type = magic.from_buffer(file_header, mime=True)
    if not file_type.startswith("image/"):
        raise HTTPException(400, f"Chỉ cho phép file ảnh. File của bạn là loại: {file_type}")

    expire_at = int((datetime.utcnow() + timedelta(seconds=expires_in)).timestamp())
    filename = _make_filename(file.filename, expire_at)
    dest_path = settings.UPLOAD_DIR / filename

    try:
        async with aiofiles.open(dest_path, "wb") as out_file:
            while chunk := await file.read(1 << 20):
                await out_file.write(chunk)
    except Exception as e:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Không thể lưu file: {e}")
    finally:
        await file.close()

    return {"url": f"/images/{filename}", "expires_in": expires_in}

@app.get("/images/{file_name}", tags=["Image Operations"])
async def serve_image(file_name: str):
    """Phục vụ file ảnh nếu nó tồn tại và chưa hết hạn."""
    path = settings.UPLOAD_DIR / file_name
    if not path.is_file():
        raise HTTPException(404, "Ảnh không tồn tại hoặc đã hết hạn.")

    expire_at = _parse_expire_from_name(file_name)
    if expire_at and expire_at < int(datetime.utcnow().timestamp()):
        path.unlink(missing_ok=True)
        raise HTTPException(404, "Ảnh không tồn tại hoặc đã hết hạn.")

    return FileResponse(path)

async def sweep():
    """Quét và xóa các file đã hết hạn."""
    now = int(datetime.utcnow().timestamp())
    for f in settings.UPLOAD_DIR.iterdir():
        if f.is_file():
            exp = _parse_expire_from_name(f.name)
            if exp and exp < now:
                f.unlink(missing_ok=True)

async def sweep_periodically():
    """Chạy tác vụ dọn dẹp theo chu kỳ."""
    while True:
        await sweep()
        await asyncio.sleep(settings.SWEEP_INTERVAL)

@app.on_event("startup")
async def on_startup():
    """Khởi chạy tác vụ nền khi ứng dụng bắt đầu."""
    print("Ứng dụng đã khởi động. Bắt đầu tác vụ dọn dẹp nền...")
    asyncio.create_task(sweep_periodically())