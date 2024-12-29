#!/bin/bash

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查 poetry 是否安装
check_poetry() {
    if ! command -v poetry &> /dev/null; then
        echo -e "${RED}Poetry is not installed. Please install it first:${NC}"
        echo "curl -sSL https://install.python-poetry.org | python3 -"
        exit 1
    fi
}

# 检查并创建必要的目录
setup_directories() {
    echo -e "${YELLOW}Setting up directories...${NC}"
    mkdir -p cache/pypi cache/ubuntu logs
}

# 安装依赖
install_dependencies() {
    local env="${1:-all}"
    echo -e "${YELLOW}Installing dependencies for environment: $env${NC}"
    
    case "$env" in
        "prod"|"production")
            poetry install --only main
            ;;
        "dev"|"development")
            poetry install --with dev
            ;;
        "test")
            poetry install --with test
            ;;
        "all")
            poetry install --with dev,test
            ;;
        *)
            echo -e "${RED}Unknown environment: $env${NC}"
            exit 1
            ;;
    esac
}

# 启动服务
start_service() {
    local host="${DEPHOST_HOST:-127.0.0.1}"
    local port="${DEPHOST_PORT:-8000}"
    local env="${DEPHOST_ENV:-development}"
    
    echo -e "${GREEN}Starting DepHost service...${NC}"
    echo "Environment: $env"
    echo "Host: $host"
    echo "Port: $port"
    
    if [ "$env" = "production" ]; then
        poetry run uvicorn app.main:app --host $host --port $port
    else
        poetry run uvicorn app.main:app --host $host --port $port --reload
    fi
}

# 清理缓存
clean() {
    echo -e "${YELLOW}Cleaning cache...${NC}"
    rm -rf cache/*
    mkdir -p cache/pypi cache/ubuntu
    echo -e "${GREEN}Cache cleaned${NC}"
}

# 显示帮助信息
show_help() {
    echo "Usage: ./run.sh [command] [options]"
    echo
    echo "Commands:"
    echo "  start       Start the service (default)"
    echo "  clean       Clean the cache"
    echo "  install     Install dependencies"
    echo "  test        Run tests"
    echo "  help        Show this help message"
    echo
    echo "Install options:"
    echo "  ./run.sh install all          Install all dependencies (default)"
    echo "  ./run.sh install prod         Install production dependencies only"
    echo "  ./run.sh install dev          Install development dependencies"
    echo "  ./run.sh install test         Install test dependencies"
    echo
    echo "Environment variables:"
    echo "  DEPHOST_HOST        Host to bind (default: 127.0.0.1)"
    echo "  DEPHOST_PORT        Port to bind (default: 8000)"
    echo "  DEPHOST_ENV         Environment (development/production)"
    echo
}

# 主函数
main() {
    check_poetry
    
    case "$1" in
        "clean")
            clean
            ;;
        "install")
            install_dependencies "${2:-all}"
            ;;
        "help")
            show_help
            ;;
        "test")
            echo -e "${YELLOW}Running service tests...${NC}"
            install_dependencies "test"
            poetry run pytest tests/integration
            poetry run python tests/scripts/test_service.py
            ;;
        "start"|"")
            setup_directories
            install_dependencies "${DEPHOST_ENV:-development}"
            start_service
            ;;
        *)
            echo -e "${RED}Unknown command: $1${NC}"
            show_help
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@" 