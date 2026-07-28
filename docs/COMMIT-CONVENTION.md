# Quy ước commit & push — LexFlow

Áp dụng cho mọi commit trong repo (người và AI agent). Chuẩn nền: [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/).

## Cấu trúc message

```
<type>(<scope>): <mô tả ngắn>

- chi tiết 1 (thân commit — tùy chọn, dùng khi thay đổi nhiều điểm)
- chi tiết 2
```

- **Mô tả ngắn ≤ 72 ký tự**, thể mệnh lệnh ("them", "sua", không phải "da them").
- **Tiếng Việt KHÔNG DẤU** trong toàn bộ message — tránh lỗi encoding giữa PowerShell/git trên Windows.
- Một commit = một việc trọn vẹn. Không gộp feature với reorganize/format không liên quan.

## Type

| Type | Dùng khi |
|---|---|
| `feat` | tính năng mới cho người dùng hoặc API |
| `fix` | sửa bug |
| `refactor` | đổi cấu trúc code, không đổi hành vi |
| `docs` | chỉ tài liệu (`docs/`, README, comment) |
| `test` | chỉ thêm/sửa test |
| `chore` | việc lặt vặt: dependency, script phụ trợ, dọn dẹp |
| `perf` | cải thiện hiệu năng |
| `ci` | GitHub Actions, cấu hình build/deploy |
| `style` | format, không đổi logic (hiếm dùng — đã có linter) |
| `revert` | hoàn tác commit trước |

## Scope (danh sách đóng)

`web` (Next.js) · `api` (FastAPI: `app/api`, `app/core`, `app/reasoning`) · `ingest` (`app/ingestion`) · `kg` (Neo4j / `app/knowledge`) · `eval` (benchmark) · `design` (handoff trong `design/`) · `docs` · `scripts` · `data` (corpus) · `ci`

- Chạm nhiều scope → chọn scope chính; nếu không có scope chính rõ ràng thì bỏ scope (`feat: ...`) — cân nhắc tách commit.
- Cần scope mới → thêm vào bảng này trong cùng commit.

## Breaking change

Thêm `!` sau type/scope và dòng `BREAKING CHANGE:` trong thân:

```
feat(api)!: doi schema ChatRequest

BREAKING CHANGE: bo truong `filters`, client phai chuyen sang `doc_ids`
```

## Ví dụ thật từ repo

```
feat(web): tich hop mascot Lexi (handoff v2) - avatar chat, review, favicon, 404
fix(web): tinh heading Chuong/Muc bang ham thuan - qua eslint react-hooks/immutability
chore(scripts): script dong bo anchors vao corpus canonical tren Storage
docs: cap nhat DESIGN-GAP muc Lexi
```

## Quy tắc push

1. **Push thẳng lên `main`** (solo dev). Có teammate thì chuyển sang branch + PR — cập nhật file này khi đó.
2. Trước khi push, phải xanh local: `uv run pytest -q` + `uv run ruff check .` (backend) và `npm run lint` + `npm run build` trong `web/` (nếu chạm web).
3. Sau push, CI GitHub Actions phải xanh; đỏ thì sửa ngay bằng commit mới (ưu tiên hơn việc khác).
4. **Cấm**: `push --force` lên `main` · amend/rebase commit đã push · `--no-verify` bỏ qua hook.
5. Không commit secrets — credentials chỉ nằm trong `.env` (đã gitignore).
