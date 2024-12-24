#!/bin/bash

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 默认配置
HOST=${DEPHOST_HOST:-127.0.0.1}
PORT=${DEPHOST_PORT:-8000}
TIMEOUT=5

# 检查服务是否运行
check_service() {
    echo -e "${YELLOW}Checking service health...${NC}"
    
    # 检查根端点
    if curl -s -f "http://$HOST:$PORT/" > /dev/null; then
        echo -e "${GREEN}✓ Root endpoint is accessible${NC}"
    else
        echo -e "${RED}✗ Root endpoint is not accessible${NC}"
        return 1
    fi
    
    # 检查健康检查端点
    if curl -s -f "http://$HOST:$PORT/health" > /dev/null; then
        echo -e "${GREEN}✓ Health check endpoint is accessible${NC}"
    else
        echo -e "${RED}✗ Health check endpoint is not accessible${NC}"
        return 1
    fi
    
    # 检查 PyPI 服务
    if curl -s -f "http://$HOST:$PORT/pypi/simple" > /dev/null; then
        echo -e "${GREEN}✓ PyPI service is accessible${NC}"
    else
        echo -e "${RED}✗ PyPI service is not accessible${NC}"
        return 1
    fi
    
    return 0
}

# 等待服务启动
wait_for_service() {
    echo -e "${YELLOW}Waiting for service to start...${NC}"
    local count=0
    
    while [ $count -lt $TIMEOUT ]; do
        if check_service > /dev/null 2>&1; then
            echo -e "${GREEN}Service is ready!${NC}"
            return 0
        fi
        
        count=$((count + 1))
        sleep 1
    done
    
    echo -e "${RED}Service failed to start within $TIMEOUT seconds${NC}"
    return 1
}

# 主函数
main() {
    if [ "$1" = "--wait" ]; then
        wait_for_service
    else
        check_service
    fi
}

# 执行主函数
main "$@" 