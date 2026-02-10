#!/bin/bash

# Check if the first argument is 'proxyon' or 'proxyoff'
if [ "$1" == "proxyon" ]; then
    # 开启代理
    export http_proxy=http://127.0.0.1:7890
    export https_proxy=http://127.0.0.1:7890
    echo "Proxy is now ON."
elif [ "$1" == "proxyoff" ]; then
    # 关闭代理
    unset http_proxy
    unset https_proxy
    echo "Proxy is now OFF."
else
    echo "Usage: $0 {proxyon|proxyoff}"
    echo ""
    echo "若出现 ProxyError(127.0.0.1:7890 Connection refused)，说明环境里开了代理但本机无代理进程。"
    echo "在运行 Python/uvicorn 的终端执行: source proxy.sh proxyoff  或  unset http_proxy https_proxy"
fi
