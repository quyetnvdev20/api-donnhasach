# Migrations
# Khi thay đổi bất cứ trường nào (thêm, sửa, xóa) trong models, cần tạo migration mới theo thứ tự các bước sau

## Tạo migration mới

```bash
alembic revision --autogenerate -m "migration name"
```

## Áp dụng migration

```bash
alembic upgrade head
```

## Quay lại migration trước đó

```bash
alembic downgrade
```

## Xem lại tất cả migrations

```bash
alembic history
```

## Xem lại tất cả migrations

```bash
alembic history
```
