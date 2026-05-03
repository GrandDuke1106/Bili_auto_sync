import os
from utils.config_manager import load_config

def main():
    # 1. 启动时自动检查并生成配置
    print("正在检查项目环境...")
    config = load_config()
    
    # 检查用户是否已经填入了 API Key
    if config['deepseek']['api_key'] == "YOUR_DEEPSEEK_API_KEY_HERE":
        print("[!] 警告: 检测到 API Key 未配置！")
        print("请打开 configs/config.yaml 文件，填入你的 DeepSeek API Key 后重新运行程序。")
        return

    print("环境就绪，开始执行自动化搬运流程...")
    
    # ==========================================
    # 在这里，你之后会逐步引入 downloader, translator, publisher
    # ==========================================

if __name__ == "__main__":
    main()
