# GitHub Actions: deploy lên server qua Harbor

- Ngày: 2026-09-24
- Trạng thái: đã duyệt thiết kế, chờ lập kế hoạch
- Thuộc: vận hành / CI-CD

## 1. Vấn đề

Repo chưa có GitHub Actions. Server đã có sẵn tree deploy tại `/home/devops/cineai` (gồm `docker-compose.prod.yml` và `deploy/.env.prod`). Image app trỏ Harbor:

- `registry-harbor.ubos.vn/cineai/printfilm-api:latest`
- `registry-harbor.ubos.vn/cineai/printfilm-web:latest`
- `registry-harbor.ubos.vn/cineai/printfilm-admin-web:latest`

Cần một nút trên GitHub Actions để: build 3 image → push Harbor → SSH lên server pull & recreate chỉ các service app.

## 2. Phạm vi

**Làm:**

- Một workflow `.github/workflows/deploy.yml`
- Trigger chỉ `workflow_dispatch` (không auto khi push `main`)
- Job matrix build/push song song 3 image `:latest`
- Job deploy SSH: `docker login` → `pull` → `up -d` chỉ `api web admin-web`

**Không làm:**

- Auto-deploy khi push nhánh
- Tag theo commit SHA / version semver
- Sync / sửa file trên server (`compose`, `.env`, `git pull`)
- `docker compose down` hoặc `--force-recreate`
- Restart `postgres` / `redis`
- Health-check HTTP sau deploy
- Multi-environment / staging riêng

## 3. Quyết định đã chốt

| Hạng mục | Quyết định |
|---|---|
| Trigger | Chỉ `workflow_dispatch` — một nút làm hết |
| Architecture | Matrix build song song + job deploy (`needs`) |
| Tag image | Chỉ `:latest` |
| Đường dẫn server | Hard-code `/home/devops/cineai` |
| File trên server | Không đụng — chỉ pull image & up container |
| Services restart | Chỉ `api`, `web`, `admin-web` |
| Recreate | `pull` rồi `up -d` (không `down`, không `--force-recreate`) |
| SSH user | Secret `REMOTE_USER` |

## 4. Secrets (GitHub repo)

| Secret | Dùng cho |
|---|---|
| `REGISTRY_USERNAME` | Login Harbor (CI + remote pull) |
| `REGISTRY_PASSWORD` | Login Harbor |
| `REMOTE_HOST` | Host SSH |
| `REMOTE_USER` | User SSH |
| `REMOTE_PORT` | Port SSH |
| `SSH_PRIVATE_KEY` | Private key SSH |

Hard-code trong workflow (không phải secret): registry host `registry-harbor.ubos.vn`, project path `cineai/printfilm-*`, deploy dir, tên compose/env file.

## 5. Kiến trúc workflow

```
workflow_dispatch
        │
        ▼
┌───────────────────────────────────┐
│ Job: build-push                   │
│ strategy.matrix: api|web|admin-web│
│ (song song)                       │
│ checkout → buildx → login → push  │
└─────────────────┬─────────────────┘
                  │ needs: success (cả 3)
                  ▼
┌───────────────────────────────────┐
│ Job: deploy                       │
│ SSH → /home/devops/cineai         │
│ login → pull → up -d (3 app)      │
└───────────────────────────────────┘
```

Nếu bất kỳ matrix nào fail → `deploy` không chạy.

## 6. Job `build-push`

- Runner: `ubuntu-latest`
- Matrix:

| key | build context | dockerfile | image |
|---|---|---|---|
| `api` | `./backend` | `Dockerfile` | `registry-harbor.ubos.vn/cineai/printfilm-api:latest` |
| `web` | `./frontend` | `Dockerfile` | `registry-harbor.ubos.vn/cineai/printfilm-web:latest` |
| `admin-web` | `./admin` | `Dockerfile` | `registry-harbor.ubos.vn/cineai/printfilm-admin-web:latest` |

Các bước mỗi matrix:

1. `actions/checkout@v4`
2. `docker/setup-buildx-action@v3`
3. `docker/login-action@v3` — `registry: registry-harbor.ubos.vn`, credentials từ secrets
4. `docker/build-push-action@v6` — `push: true`, tag `:latest`, cache `type=gha`

Khớp với `build.context` / `image` trong `docker-compose.prod.yml` hiện có.

## 7. Job `deploy`

- Runner: `ubuntu-latest`
- `needs: [build-push]`

Các bước:

1. Ghi `SSH_PRIVATE_KEY` ra file tạm (`chmod 600`)
2. SSH tới `${REMOTE_USER}@${REMOTE_HOST}` `-p ${REMOTE_PORT}` với `StrictHostKeyChecking=accept-new`
3. Trên remote, `cd /home/devops/cineai`, chạy:

```bash
echo "$REGISTRY_PASSWORD" | docker login registry-harbor.ubos.vn \
  -u "$REGISTRY_USERNAME" --password-stdin
docker compose --env-file deploy/.env.prod -f docker-compose.prod.yml \
  pull api web admin-web
docker compose --env-file deploy/.env.prod -f docker-compose.prod.yml \
  up -d api web admin-web
docker compose --env-file deploy/.env.prod -f docker-compose.prod.yml ps
```

- Credential registry truyền qua env của phiên SSH (không ghi file trên server).
- Không sửa `deploy/.env.prod` / `docker-compose.prod.yml`.
- Lệnh remote exit ≠ 0 → job fail.

Compose v2 sau `pull` sẽ recreate container khi image digest đổi; không cần `down` trước.

## 8. Xử lý lỗi & rollback

- Build fail → dừng, server không đổi.
- Deploy fail giữa chừng → container nào đã `up` thành công giữ bản mới; cái chưa lên giữ bản cũ. Không auto-rollback.
- Rollback thủ công: checkout commit cũ trên GitHub → Run workflow lại (ghi đè `:latest`) rồi deploy.

## 9. Kiểm thử khi implement

- YAML hợp lệ; matrix trỏ đúng 3 `Dockerfile` đã có trong repo.
- (Tuỳ vận hành) lần chạy thật đầu tiên sau khi cấu hình đủ 6 secrets.

## 10. File tạo mới

| Path | Mô tả |
|---|---|
| `.github/workflows/deploy.yml` | Workflow duy nhất của thiết kế này |

Không đổi `docker-compose.prod.yml` hay code app.
