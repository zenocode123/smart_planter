from tortoise import Tortoise, run_async
from app.models import User

async def clean_db():
    # 初始化資料庫連線
    await Tortoise.init(
        db_url="sqlite://app/database.db",
        modules={"models": ["app.models"]}
    )
    
    # 刪除 username 不是 'admin' 的所有使用者
    deleted_count = await User.filter(username__not="admin").delete()
    
    print(f"清理完成！共刪除了 {deleted_count} 個測試帳號，僅保留 admin。")
    
    # 關閉連線
    await Tortoise.close_connections()

if __name__ == "__main__":
    run_async(clean_db())