# DepHost

DepHost 是一个高效的依赖包缓存和代理服务，支持 Python 包和 Ubuntu 系统包的本地缓存和镜像服务。

## 功能特点

- 📦 多源支持
  - 支持 PyPI 包源
  - 支持 Ubuntu 软件源
  - 可配置多个远程源，自动选择最快源
  
- 🚀 智能缓存
  - 本地缓存依赖包
  - 自动清理过期缓存
  - 可配置缓存大小限制
  
- 🔄 代理功能
  - 为每个远程源配置独立代理
  - 支持 HTTP/HTTPS 代理
  - 支持 SOCKS5 代理
  
- 🛠 易于使用
  - RESTful API 接口
  - 简单的配置方式
  - 详细的使用文档

## 快速开始

### 安装

确保你的系统已安装 Python 3.8+ 和 Poetry。

```bash
克隆仓库
git clone https://github.com/yourusername/dephost.git
cd dephost
安装依赖
poetry install
```


### 配置

创建配置文件 `config.yaml`：

```yaml
cache:
    dir: "./cache"
    max_size: "10GB"
    retention_days: 30
sources:
    pypi:
        url: "https://pypi.org/simple"
    proxy: "http://proxy.example.com:8080"
        url: "https://mirrors.aliyun.com/pypi/simple"
    ubuntu:
        url: "http://archive.ubuntu.com/ubuntu"
        url: "https://mirrors.aliyun.com/ubuntu"
```

### 运行

```bash
#启动服务
poetry run python -m app.main
# 服务默认在 http://localhost:8000 启动
```

## API 使用

### PyPI 包

```bash
# 获取 Python 包
curl http://localhost:8000/pypi/requests/2.28.1
# 查看包信息
curl http://localhost:8000/pypi/requests/info
```

### Ubuntu 包

```bash
# 获取 Ubuntu 包
curl http://localhost:8000/ubuntu/nginx/1.18.0
# 查看包信息
curl http://localhost:8000/ubuntu/nginx/info
```


## 配置为本地镜像源

## 开发指南

### 开发环境设置

```bash
# 安装开发依赖
poetry install --with dev
# 运行测试
poetry run pytest
# 格式化代码
poetry run ruff format .
# 检查代码并自动修复简单问题
poetry run ruff check . --fix
# 运行类型检查
poetry run mypy app
```