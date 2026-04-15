#!/usr/bin/env bash
# ============================================================================
# セキュアなコンテナ起動スクリプト
# ============================================================================
# 使用方法:
#   ./scripts/run_secure.sh secure      # ネットワーク無効 (デフォルト)
#   ./scripts/run_secure.sh network     # ネットワーク有効 (API呼び出し用)
#   ./scripts/run_secure.sh build       # イメージをビルド
#   ./scripts/run_secure.sh verify      # セキュリティ設定を検証
# ============================================================================

set -euo pipefail

# ============================================================================
# 設定
# ============================================================================
IMAGE_NAME="jquants-analysis:secure"
CONTAINER_NAME="jquants-analysis"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# 色付き出力
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ============================================================================
# 関数
# ============================================================================

# ログ出力
log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

# Docker/Podman の検出
detect_runtime() {
    if command -v podman &> /dev/null; then
        echo "podman"
    elif command -v docker &> /dev/null; then
        echo "docker"
    else
        log_error "Docker or Podman not found"
        exit 1
    fi
}

# イメージのビルド
build_image() {
    local runtime="$1"
    log_info "Building image with ${runtime}..."

    cd "$PROJECT_ROOT"
    $runtime build \
        --tag "$IMAGE_NAME" \
        --file Dockerfile \
        .

    log_info "Image built successfully: $IMAGE_NAME"
}

# セキュア実行 (ネットワーク無効)
run_secure() {
    local runtime="$1"
    log_info "Starting container (network disabled)..."

    # 出力ディレクトリを作成
    mkdir -p "$PROJECT_ROOT/out"

    $runtime run \
        --rm \
        --interactive \
        --tty \
        --name "$CONTAINER_NAME" \
        --read-only \
        --network none \
        --security-opt no-new-privileges:true \
        --cap-drop ALL \
        --mount type=bind,source="$PROJECT_ROOT",target=/workspace,readonly \
        --mount type=bind,source="$PROJECT_ROOT/out",target=/out \
        --mount type=tmpfs,target=/tmp,tmpfs-size=512M,tmpfs-mode=1777 \
        --mount type=tmpfs,target=/home/analyst/.cache,tmpfs-size=256M,tmpfs-mode=0700 \
        --env PYTHONUNBUFFERED=1 \
        --env TZ=Asia/Tokyo \
        --memory 4g \
        --cpus 4.0 \
        "$IMAGE_NAME" \
        /bin/bash
}

# ネットワーク有効実行
run_network() {
    local runtime="$1"
    log_warn "Starting container with network enabled..."
    log_warn "This mode allows internet access for API calls"

    # .env ファイルの存在確認
    if [[ ! -f "$PROJECT_ROOT/.env" ]]; then
        log_error ".env file not found"
        log_error "Create .env file with J-Quants API credentials"
        exit 1
    fi

    # 出力ディレクトリを作成
    mkdir -p "$PROJECT_ROOT/out"

    $runtime run \
        --rm \
        --interactive \
        --tty \
        --name "$CONTAINER_NAME" \
        --read-only \
        --network bridge \
        --security-opt no-new-privileges:true \
        --cap-drop ALL \
        --mount type=bind,source="$PROJECT_ROOT",target=/workspace,readonly \
        --mount type=bind,source="$PROJECT_ROOT/out",target=/out \
        --mount type=tmpfs,target=/tmp,tmpfs-size=512M,tmpfs-mode=1777 \
        --mount type=tmpfs,target=/home/analyst/.cache,tmpfs-size=256M,tmpfs-mode=0700 \
        --env-file "$PROJECT_ROOT/.env" \
        --env PYTHONUNBUFFERED=1 \
        --env TZ=Asia/Tokyo \
        --dns 1.1.1.1 \
        --dns 8.8.8.8 \
        --memory 4g \
        --cpus 4.0 \
        "$IMAGE_NAME" \
        /bin/bash
}

# セキュリティ設定の検証
verify_security() {
    local runtime="$1"
    log_info "Verifying security settings..."

    # イメージの存在確認
    if ! $runtime image inspect "$IMAGE_NAME" &> /dev/null; then
        log_error "Image not found: $IMAGE_NAME"
        log_error "Run: $0 build"
        exit 1
    fi

    log_info "Checking image configuration..."

    # ユーザー確認
    local user=$($runtime image inspect "$IMAGE_NAME" | grep -o '"User":"[^"]*"' | cut -d'"' -f4)
    if [[ "$user" == "analyst" ]] || [[ "$user" == "1000" ]]; then
        log_info "✓ Non-root user: $user"
    else
        log_warn "✗ User is not 'analyst': $user"
    fi

    # テストコンテナを起動して検証
    log_info "Running security checks in container..."

    $runtime run --rm "$IMAGE_NAME" /bin/bash -c '
        echo "=== Security Checks ==="
        echo "User: $(whoami) (UID=$(id -u))"
        echo "Groups: $(groups)"
        echo "Writable directories:"
        find / -type d -writable 2>/dev/null | head -10
        echo "Capabilities:"
        if command -v capsh &> /dev/null; then
            capsh --print
        else
            echo "capsh not available (expected in minimal image)"
        fi
    '

    log_info "Security verification complete"
}

# ============================================================================
# メイン処理
# ============================================================================

# コンテナランタイムの検出
RUNTIME=$(detect_runtime)
log_info "Using container runtime: $RUNTIME"

# コマンド引数の処理
MODE="${1:-secure}"

case "$MODE" in
    build)
        build_image "$RUNTIME"
        ;;
    secure)
        run_secure "$RUNTIME"
        ;;
    network)
        run_network "$RUNTIME"
        ;;
    verify)
        verify_security "$RUNTIME"
        ;;
    *)
        log_error "Unknown mode: $MODE"
        echo "Usage: $0 {build|secure|network|verify}"
        exit 1
        ;;
esac
