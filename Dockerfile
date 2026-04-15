# ============================================================================
# セキュアな分析コンテナ - J-Quants Sector Momentum Strategy
# ============================================================================
# 設計原則:
#   - 非rootユーザーで実行
#   - ルートFS read-only (tmpfs/volume以外)
#   - 最小権限 (cap-drop=ALL)
#   - ネットワーク原則無効 (必要時のみ有効化)
#   - 依存関係は固定バージョン (pip freeze → requirements.lock)
# ============================================================================

# ============================================================================
# Stage 1: Builder (依存関係のインストール)
# ============================================================================
FROM python:3.11-slim-bookworm AS builder

# セキュリティ: 一時的にrootで必要最小限のパッケージをインストール
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        && \
    rm -rf /var/lib/apt/lists/*

# 依存関係を固定バージョンでインストール
WORKDIR /build

# メインプロジェクトの依存関係
COPY requirements.txt /build/requirements.txt

# jquants-sector-momo の依存関係
COPY jquants-sector-momo/requirements.txt /build/jquants-requirements.txt

# 仮想環境を作成 (本番イメージに持ち込む)
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 依存関係をインストール (固定バージョンで再現性確保)
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r jquants-requirements.txt

# インストール済みパッケージの固定バージョンを生成 (後で検証用)
RUN pip freeze > /opt/venv/requirements.lock

# ============================================================================
# Stage 2: Runtime (最小限の実行環境)
# ============================================================================
FROM python:3.11-slim-bookworm AS runtime

# メタデータ
LABEL maintainer="claude-code"
LABEL description="Secure analysis container for J-Quants strategy"
LABEL security.read-only-root="true"
LABEL security.user="analyst"
LABEL security.network="none-by-default"

# セキュリティ強化: 非rootユーザーを作成
RUN groupadd -r analyst --gid=1000 && \
    useradd -r -g analyst --uid=1000 --home-dir=/home/analyst --create-home analyst

# 仮想環境をbuilderからコピー
COPY --from=builder /opt/venv /opt/venv

# 環境変数: 仮想環境を有効化
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 作業ディレクトリの準備
# /workspace: リポジトリ全体 (read-only bindマウント)
# /out: 成果物出力先 (read-write bindマウント)
# /tmp: 一時ファイル (tmpfs)
# /home/analyst/.cache: キャッシュ用 (tmpfs)
RUN mkdir -p /workspace /out && \
    chown -R analyst:analyst /workspace /out /home/analyst

# 非rootユーザーに切り替え
USER analyst:analyst

WORKDIR /workspace

# ヘルスチェック用スクリプト (オプション)
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=1 \
    CMD python -c "import sys; sys.exit(0)"

# デフォルトコマンド: インタラクティブシェル
CMD ["/bin/bash"]
