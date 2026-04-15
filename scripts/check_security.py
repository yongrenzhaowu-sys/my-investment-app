#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""


API
"""
import os
import sys
from pathlib import Path

# Windows cp932
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')


def check_env_file():
    """
    .env
    """
    print("=" * 60)
    print("[SECURITY] .env")
    print("=" * 60)

    env_file = Path(".env")
    issues = []
    warnings = []

    # .env
    if not env_file.exists():
        print(" .envWindows")
        return True

    # Git
    gitignore = Path(".gitignore")
    if gitignore.exists():
        with open(gitignore, 'r') as f:
            if '.env' not in f.read():
                issues.append(".env.gitignore")
    else:
        issues.append(".gitignore")

    # Unix
    if hasattr(os, 'stat'):
        stat_info = os.stat(env_file)
        mode = oct(stat_info.st_mode)[-3:]
        if mode != '600':
            warnings.append(f".env{mode}: 600")

    # 
    with open(env_file, 'r') as f:
        content = f.read()
        if 'your-actual-api-key-here' in content or 'your_actual_api_key_here' in content:
            warnings.append(".env")
        if 'JQUANTS_API_KEY=' in content:
            # 
            for line in content.split('\n'):
                if line.startswith('JQUANTS_API_KEY='):
                    key_value = line.split('=', 1)[1].strip()
                    if len(key_value) < 20:
                        warnings.append(f"API{len(key_value)}")

    # 
    if issues:
        print("\n :")
        for issue in issues:
            print(f"  - {issue}")

    if warnings:
        print("\n  :")
        for warning in warnings:
            print(f"  - {warning}")

    if not issues and not warnings:
        print("\n .env")

    return len(issues) == 0


def check_environment_variable():
    """
    
    """
    print("\n" + "=" * 60)
    print(" ")
    print("=" * 60)

    api_key = os.environ.get("JQUANTS_API_KEY")

    if not api_key:
        print("  JQUANTS_API_KEY")
        print("   : Windows")
        return False

    # 
    if len(api_key) <= 8:
        masked = "****"
    else:
        masked = f"{api_key[:4]}...{api_key[-4:]}"

    print(f" JQUANTS_API_KEY: {masked} ({len(api_key)})")

    # 
    if len(api_key) < 20:
        print(f"  API{len(api_key)} < 20")
        return False

    if ' ' in api_key or '\t' in api_key or '\n' in api_key:
        print("  API")
        return False

    print(" API")
    return True


def check_git_status():
    """
    Git.env
    """
    print("\n" + "=" * 60)
    print(" Git")
    print("=" * 60)

    if not Path(".git").exists():
        print("  Git")
        return True

    # git status  .env 
    import subprocess
    try:
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            capture_output=True,
            text=True,
            check=True
        )

        if '.env' in result.stdout:
            print(" .envGit")
            print("   :")
            print("   1. git rm --cached .env")
            print("   2. .gitignore.env")
            return False

        print(" .envGit")
        return True

    except (subprocess.CalledProcessError, FileNotFoundError):
        print("  Git")
        return True


def check_docker_compose():
    """
    docker-compose.yml
    """
    print("\n" + "=" * 60)
    print(" docker-compose.yml")
    print("=" * 60)

    compose_file = Path("docker-compose.yml")
    if not compose_file.exists():
        print("  docker-compose.yml")
        return True

    with open(compose_file, 'r') as f:
        content = f.read()

    issues = []

    # API
    if 'JQUANTS_API_KEY=dummy-key-for-local-data-only' in content:
        print("  OK")
    elif 'JQUANTS_API_KEY=' in content:
        # 
        for line in content.split('\n'):
            if 'JQUANTS_API_KEY=' in line and 'dummy' not in line.lower():
                issues.append("APIdocker-compose.yml")

    # env_file 
    if 'env_file:' in content and '.env' in content:
        print(" .env")

    if issues:
        print("\n :")
        for issue in issues:
            print(f"  - {issue}")
        return False

    print(" docker-compose.yml")
    return True


def main():
    """
    
    """
    print("\n" + "=" * 60)
    print(" J-Quants ")
    print("=" * 60)

    # 
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    os.chdir(project_root)
    print(f" : {project_root}")

    # 
    results = {
        "": check_environment_variable(),
        ".env": check_env_file(),
        "Git": check_git_status(),
        "docker-compose": check_docker_compose(),
    }

    # 
    print("\n" + "=" * 60)
    print(" ")
    print("=" * 60)

    all_passed = all(results.values())

    for check_name, passed in results.items():
        status = "" if passed else ""
        print(f"{status} {check_name}")

    print("=" * 60)

    if all_passed:
        print("\n ")
        return 0
    else:
        print("\n  ")
        print("\n: docs/knowledges/20260304_1600_secure_api_key_management.md")
        return 1


if __name__ == "__main__":
    sys.exit(main())
