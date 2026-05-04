# Bilibili Auto Sync (B站全自动搬运与翻译烤肉机)

这是一个全自动的 YouTube 到 Bilibili 视频搬运与本地化工具。它能够自动监听 YouTube 频道或播放列表，下载最新视频，提取并翻译英文字幕，自动生成双语字幕并硬压制，最后由 DeepSeek 包装适合 B 站风格的标题与简介，全自动发布至 B 站指定分区与合集。

---

## 🛠️ 环境准备

在开始之前，请确保你的系统（Windows WSL 或 Linux 服务器）已安装以下基础环境：

1. **Python 3.8 或以上版本**
2. **FFmpeg**
   * *Ubuntu/Debian:* `sudo apt install ffmpeg`
   * *CentOS:* `sudo yum install ffmpeg`

---

## 📦 安装与初始化

**1. 克隆或下载本项目到本地**

**2. 安装 Python 依赖包**
在项目根目录下打开终端，运行：
```bash
pip install -r requirements.txt
```

**3. 字体准备**
本项目包含了一份中文字体和一份英文字体`configs/fonts`，您也可以手动加入您想要的自定义字体，并在配置文件中自行修改字体名称。

**4. 首次运行以生成配置文件**
执行以下命令：
```bash
python main.py
```
首次运行会提示“未配置 API Key”并自动退出，同时在 `configs/` 目录下生成 `config.yaml` 和空的 `cookies.json`。

---

## ⚙️ 配置指引

### 1. 登录 Bilibili 获取凭证
本工具使用 `biliup` 进行视频上传。你需要在终端中运行以下命令并扫码登录 B站：
```bash
biliup login
```
登录成功后，会在当前目录生成一个 `cookies.json`。**请确保将这个 `cookies.json` 移动或覆盖到本项目的 `configs/cookies.json` 路径下**。

### 2. 修改 `configs/config.yaml`
打开 `configs/config.yaml` 文件，根据你的需求进行修改：

* **DeepSeek API**: 填入你的 `api_key`。
* **YouTube 目标**:
  * `target_urls`: 单个视频链接。
  * `channels`: 频道链接。
  * `proxy`: 如果在国内服务器运行，请务必填写本地代理（如 `[http://127.0.0.1:7890](http://127.0.0.1:7890)`）。
* **空间清理策略 (bilibili节点下)**:
  * `delete_temp_files`: 设为 `true` 则在任务完成后自动删除原视频、原字幕等废弃材料。
  * `delete_final_video`: 设为 `true` 则在上传 B 站后，把压制好的硬字幕 MP4 也删除（适合云服务器省空间）。
* **上传设置**:
  * `enable_upload`: 设为 `true` 才会真正上传 B 站，设为 `false` 仅在本地生成带中文字幕的视频。

---

## 🚀 如何使用

### 方式一：手动单次运行
在完成上述配置后，直接在终端中运行：
```bash
python main.py
```
程序会自动读取配置，下载视频，压制字幕，并输出详细的运行日志。

### 方式二：无人值守自动化运行 (推荐)
你可以将此工具部署在服务器上，利用系统定时任务实现完全脱手的自动搬运。

**对于 Linux 云服务器 (Crontab):**
1. 运行 `crontab -e`
2. 添加一行，例如每 6 小时执行一次（请将路径替换为你的实际项目路径和 Python 环境）：
   ```bash
   0 */6 * * * cd /path/to/Bili_auto_sync && /path/to/venv/bin/python main.py >> /dev/null 2>&1

**对于 Windows 系统 (任务计划程序):**

*注意：只能用于linux系统，请使用wsl。*

1. 创建一个 `run.bat` 脚本，内容包含激活你的虚拟环境并运行 `main.py` 的命令。
2. 打开 Windows “任务计划程序”，创建一个新任务。
3. 触发器设置为“每天”并设定重复间隔。
4. 操作设置为启动该 `.bat` 脚本，并勾选“不管用户是否登录都要运行”。

## 📂 目录结构说明

* `configs/`：存放所有配置文件、Cookies 凭证和字体文件。
* `core/`：核心功能模块（下载、翻译、压制、发布）。
* `data/`：
  * `temp_workspace/`：运行时的临时工作台（视频下载和压制的暂存区）。
  * `completed_videos/`：未开启彻底删除时，压制完成的成品视频归档处。
  * `archive.txt`：已下载视频的 ID 记忆库，防止重复搬运。
* `logs/`：按天自动轮转的运行日志记录。
* `utils/`：日志管理与配置管理工具类。

## ⚖️ 许可证

本项目基于[MIT](LICENSE)开源，不提供担保。

本项目仅供学习和技术研究使用。请勿将本软件用于任何商业用途或侵犯第三方版权的行为。使用本软件产生的任何法律后果由使用者自行承担。
