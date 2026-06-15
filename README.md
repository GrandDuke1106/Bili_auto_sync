# Bilibili Auto Sync (B站全自动搬运与翻译烤肉机)

这是一个全自动的 YouTube 到 Bilibili 视频搬运与本地化工具。它能够自动监听 YouTube 频道或播放列表，下载最新视频，提取并翻译英文字幕，自动生成双语字幕并硬压制，最后由 DeepSeek 包装适合 B 站风格的标题与简介，全自动发布至 B 站指定分区与合集。

---

## 🛠️ 环境准备

### 方式 A：传统 Python 环境（适用于 Linux / Windows WSL）

请确保你的系统已安装：

1. **Python 3.8 或以上版本**
2. **FFmpeg**
   * *Ubuntu/Debian:* `sudo apt install ffmpeg`
   * *CentOS:* `sudo yum install ffmpeg`

### 方式 B：Docker 部署（跨平台，实验性）

如果你不想手动配置 Python 环境，或希望在 Windows/macOS 上直接运行，可使用 Docker。

> ⚠️ **实验性声明**：Docker 部署方案为示例性质，**未经充分测试**，可能存在未知问题。如遇到 Bug 请在 GitHub Issues 中反馈。

```bash
# 1. 构建镜像（约 400MB，不含 WhisperX）
docker compose build

# 2. 登录 B 站（交互式，按提示扫码）
docker compose run --rm bili-sync-login

# 3. 运行管线
docker compose run --rm bili-sync

# 4. (可选) 安装 WhisperX 以获得词级时间戳字幕
docker compose run --rm --entrypoint pip bili-sync install whisperx
```

详见下方 [🐳 Docker 部署详解](#-docker-部署详解) 章节。

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
打开 `configs/config.yaml` 文件，根据你的需求进行修改。以下是完整的配置项说明：

#### 📡 DeepSeek API（必填）
| 字段 | 说明 | 示例 |
|------|------|------|
| `api_key` | DeepSeek API 密钥 | `sk-xxxx` |
| `base_url` | API 地址（支持任意 OpenAI 兼容接口） | `https://api.deepseek.com` |
| `model` | 使用的模型名称 | `deepseek-v4-flash` |

#### 📺 YouTube 下载设置
| 字段 | 说明 | 示例 |
|------|------|------|
| `target_urls` | 单个视频链接列表 | `- https://www.youtube.com/watch?v=xxx` |
| `channels` | 频道/播放列表链接列表 | `- https://www.youtube.com/@Example/videos` |
| `format` | yt-dlp 下载格式 | `bestvideo[ext=mp4]+bestaudio[ext=m4a]/best` |
| `max_downloads_per_run` | 每次运行最多下载几个新视频 | `3` |
| `proxy` | 代理地址（国内服务器必填） | `http://127.0.0.1:7890` |

#### 🔧 管道控制 (`pipeline`)
| 字段 | 说明 | 可选值 | 默认值 |
|------|------|--------|--------|
| `start_from` | 默认起始阶段 | `download` / `translate` / `compose` | `download` |

> **注意：** 此处的`target_urls`和`channels`所填写的链接传递到`yt-dlp`没有语义上的区分，此处配置分开只是为了便于整理。

> 并且可以填写任意含有视频的链接（如`https://www.youtube.com/watch?v=dQw4w9WgXcQ`），频道视频（如`https://www.youtube.com/channel/UCuAXFkgsw1L7xaCfnd5JJOw/videos`），播放列表（如`https://www.youtube.com/playlist?list=PLlaN88a7y2_oBUxLd3j23dkAFNtM-P24e`），短视频（如`https://www.youtube.com/channel/UCuAXFkgsw1L7xaCfnd5JJOw//shorts`）等，也就是相当于网页爬虫，能够下载当前标签内所有页码的所有视频。

> 详细说明请参考[yt-dlp文档](https://github.com/yt-dlp/yt-dlp/blob/master/README.md)。

#### 🅱️ Bilibili 上传设置
| 字段 | 说明 | 默认值 |
|------|------|--------|
| `enable_upload` | 是否上传到 B 站（`false` 仅本地压片） | `false` |
| `delete_temp_files` | 完成后删除原视频、字幕等临时材料 | `true` |
| `delete_final_video` | 上传后删除成品硬字幕视频（省空间） | `false` |
| `tid` | B 站分区 ID（122=知识-野技能协会） | `122` |
| `tags` | 基础标签列表（会与 AI 生成的标签合并） | `[翻译, YouTube]` |

##### 🎨 频道翻译风格 (`channel_styles`)
通过频道 ID 为不同频道指定专属的翻译风格。示例风格：

| 风格名称 | 适用场景 |
|----------|----------|
| `default` | 通用字幕翻译 |
| `pure_math` | 纯数学内容 |
| `popular_science` | 硬核科普 |
| `tea_culture` | 茶文化与慢生活 |
| `literature_art` | 文学艺术 |
| `tech_hardware` | 硬件与技术折腾 |
| `mechanical_engineering` | 机械工程 |
| `aviation_sim` | 航空与模拟飞行 |
| `ACG_3d` | 3D 建模 / ACG 技术 |

```yaml
bilibili:
  channel_styles:
    UCAILTiWNai7Y2zsO8ECFxcA: aviation_sim   # 为某频道指定航空风格
    UCexample123: pure_math                    # 为另一频道指定数学风格
```

用户可以自行添加各种风格提示词。

##### 📁 合集管理 (`collections`)
上传视频后自动加入指定合集（需先在 B 站创作中心手动创建该合集）。

```yaml
bilibili:
  collections:
    UCAILTiWNai7Y2zsO8ECFxcA: "我的合集名称"   # 频道ID → 合集名称
```

#### 🧠 翻译专有名词保留 (`translation`)
某些术语、品牌名、缩写不应被翻译，可在此配置：

```yaml
translation:
  # 全局保留（对所有频道生效）
  preserve_proper_nouns:
    - ChatGPT
    - OpenAI
  # 按频道保留（仅对特定频道生效）
  channel_preserve_nouns:
    UCAILTiWNai7Y2zsO8ECFxcA:
      - FMC
      - VNAV
      - ILS
      - ATC
      - IFR
```

#### 🎙️ WhisperX 词级时间戳转录（可选）
WhisperX 可以生成**词级毫秒精度**的时间戳，彻底解决 YouTube 自动字幕时间轴与语音不同步的问题。启用后，字幕中的每一句话都会精确对齐到说话人的发音时刻。

> ⚠️ **硬件要求**：WhisperX 需要 **NVIDIA GPU + CUDA**，显存建议 ≥8GB（`large-v3` 模型约需 6GB）。CPU 模式极慢，不推荐用于长视频。

> 📦 **安装**：`pip install whisperx`（建议先手动安装对应 CUDA 版本的 PyTorch）

| 字段 | 说明 | 默认值 |
|------|------|--------|
| `enabled` | 是否启用 WhisperX 转录 | `false` |
| `model` | Whisper 模型大小（`large-v3` / `medium` / `small`） | `large-v3` |
| `device` | 推理设备（`cuda` 或 `cpu`） | `cuda` |
| `compute_type` | 计算精度（`float16` / `float32` / `int8`） | `float16` |
| `language` | 音频语言代码 | `en` |
| `batch_size` | 批处理大小（减少可降低显存占用） | `16` |
| `hf_endpoint` | HuggingFace 镜像站（国内推荐 `https://hf-mirror.com`） | `""` |
| `hf_proxy` | HuggingFace 下载代理（如 `http://127.0.0.1:7897`） | `""` |
| `hf_offline` | 离线模式，仅使用已缓存的模型（不联网） | `false` |

```yaml
whisperx:
  enabled: true           # 启用 WhisperX
  model: large-v3         # 最佳精度（需 ~6GB 显存）
  device: cuda            # GPU 推理
  compute_type: float16   # 半精度（节省显存）
  language: en
  batch_size: 16
  hf_endpoint: https://hf-mirror.com   # 国内用户必填（否则模型无法下载）
  # hf_proxy: http://127.0.0.1:7897    # 或使用代理替代镜像
  # hf_offline: true                    # 已有缓存模型后可开启
```

> 💡 **工作流程**：启用后，yt-dlp 下载的 YouTube 自动字幕会被 WhisperX 生成的词级对齐字幕**完全替换**。后续的 AI 翻译和压制流程不受影响。如果 WhisperX 转录失败（如显存不足），程序会自动回退到 yt-dlp 自带字幕。

> 📦 **模型缓存**：WhisperX 模型（约 4.2GB）首次下载后缓存于 `~/.cache/huggingface/hub/`，后续运行直接加载，无需重复下载。若已通过代理/镜像成功下载过一次，后续可设置 `hf_offline: true` 跳过网络检查。

#### 🖋️ 字幕字体
| 字段 | 说明 | 默认值 |
|------|------|--------|
| `fonts_dir` | 字体文件目录 | `configs/fonts` |
| `zh_font_name` | 中文字体名称 | `Noto Sans SC` |
| `en_font_name` | 英文字体名称 | `Fira Code` |

用户可以在此目录下加入其他字体文件，并指定中文或英文字体的名称。

#### 🎬 FFmpeg 视频编码器设置

硬字幕压制阶段使用 FFmpeg。`video_args` 为**原始 FFmpeg 参数列表**，原样传递给 `ffmpeg` 命令（放在 `-vf` 滤镜之后、`-c:a` 之前）。你可以直接查阅 FFmpeg 官方文档后将参数粘贴进来。

| 字段 | 说明 | 默认值 |
|------|------|--------|
| `video_args` | FFmpeg 视频编码原始参数列表 | `["-c:v", "libx264", "-preset", "medium", "-crf", "23"]` |
| `audio_encoder` | 音频编码器 | `copy` |

**常用平台配置（直接复制粘贴即可）：**

```yaml
# CPU 软编码（默认，最通用）
ffmpeg:
  video_args: ["-c:v", "libx264", "-preset", "medium", "-crf", "23"]
  audio_encoder: copy

# NVIDIA GPU 硬编码（NVENC）
ffmpeg:
  video_args: ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "18", "-b:v", "0"]
  audio_encoder: copy

# AMD GPU 硬编码（AMF）
ffmpeg:
  video_args: ["-c:v", "h264_amf", "-quality", "balanced", "-qp_i", "18", "-qp_p", "18"]
  audio_encoder: copy

# Intel GPU 硬编码（QSV）
ffmpeg:
  video_args: ["-c:v", "h264_qsv", "-preset", "medium", "-global_quality", "23"]
  audio_encoder: copy
```

> ⚠️ **注意**：硬件编码器需要对应的显卡驱动和 FFmpeg 编译支持。如果指定的编码器不可用，FFmpeg 会直接报错退出。建议先用默认的 CPU 软编码确认流程正常，再切换到硬件编码器。

---

## 🐳 Docker 部署详解

> ⚠️ **实验性声明**：以下 Docker 部署方案为示例性质，**未经充分测试**。如遇到构建失败、权限异常、网络不通等问题，可以在 GitHub Issues 中提出。

### 镜像设计理念

| 内容 | 位置 | 原因 |
|------|------|------|
| Python + pip 依赖 (~200MB) | 镜像内 | 运行必需 |
| FFmpeg (~50MB) | 镜像内 | 字幕压制 + 音频提取必需 |
| 字体文件 (~30MB) | 镜像内 | 静态资源，体积可控 |
| NLTK 分词数据 (~10MB) | 镜像内 | 避免运行时网络依赖 |
| **WhisperX + PyTorch (~3GB)** | **运行时按需安装** | 体积过大，多数用户不需要 |
| **WhisperX 模型 (~4.2GB)** | **运行时自动下载 → 命名卷持久化** | 首次使用才下载，后续直接复用 |
| 配置文件 + Cookies | 宿主机目录挂载 (`./configs`) | 敏感信息不入镜像 |
| 下载视频 + 成品 | 宿主机目录挂载 (`./data`) | 方便查看和使用 |

最终镜像体积约 **400MB**，不含 WhisperX 时为同等功能完整镜像的 1/10。

### 构建与运行

```bash
# 1. 克隆项目并进入目录
git clone <repo-url> && cd Bili_auto_sync

# 2. 准备配置文件（首次使用会自动生成模板）
mkdir -p configs data logs
# 编辑 configs/config.yaml，至少填入 DeepSeek API Key

# 3. 构建镜像
docker compose build

# 4. 登录 B 站
docker compose run --rm bili-sync-login

# 5. 运行完整管线
docker compose run --rm bili-sync

# 6. 或指定起始阶段运行
docker compose run --rm bili-sync --start-from translate
```

### 卷挂载说明

| 宿主机路径 | 容器内路径 | 权限 | 用途 |
|-----------|-----------|------|------|
| `./configs/` | `/app/configs/` | 只读 | 配置文件 + cookies |
| `./data/` | `/app/data/` | 读写 | 下载视频 + 成品输出 |
| `./logs/` | `/app/logs/` | 读写 | 运行日志 |
| `whisperx_cache` (命名卷) | `/root/.cache/huggingface/` | 读写 | WhisperX 模型缓存 |
| `nltk_data` (命名卷) | `/root/nltk_data/` | 读写 | NLTK 分词数据 |

### 安装 WhisperX（可选）

```bash
# 在容器内安装 WhisperX（约 3GB 下载量）
docker compose run --rm --entrypoint pip bili-sync install whisperx

# 安装后正常运行即可，模型将在首次转录时自动下载（约 4.2GB）
docker compose run --rm bili-sync
```

### 定时运行

```bash
# 使用 crontab 定时执行（每 6 小时）
crontab -e
# 添加: 0 */6 * * * cd /path/to/Bili_auto_sync && docker compose run --rm bili-sync >> logs/cron.log 2>&1
```

### Windows 用户特别说明

Docker Desktop for Windows 可直接运行上述命令。如果容器内需要访问宿主机的代理（如 Clash），将 `docker-compose.yml` 中的代理环境变量取消注释，并将 `host.docker.internal` 保留即可（Docker Desktop 会自动解析此域名到宿主机）。

---

## 🚀 如何使用

### 处理管线概览

本工具的处理流程分为 **4 个阶段**：

```
阶段1: 下载 → 阶段2: AI翻译 → 阶段3: 压制字幕 → 阶段4: 上传B站
```

| 阶段 | 说明 | 输出 |
|------|------|------|
| `download` | yt-dlp 下载 YouTube 视频+字幕+封面+简介（可选：WhisperX 词级对齐转录） | `.mp4`、`.srt`、`.description`、封面图 |
| `translate` | DeepSeek AI 翻译字幕 + 生成 B 站标题/简介/Tag | 中文译文、B 站元数据 |
| `compose` | 生成双语 ASS 字幕 + FFmpeg 硬字幕压制 | `_zh_sub.mp4` |
| `upload` | 通过 biliup 上传至 B 站（可选，需开启 `enable_upload`） | B 站稿件 |

---

### 方式一：全自动单次运行（默认）

完成配置后，直接运行即可走完完整流程：

```bash
python main.py
```

执行过程：下载新视频 → AI 翻译字幕 → 生成标题简介 → FFmpeg 压制硬字幕 → 上传 B 站（若启用）。

---

### 方式二：分阶段运行

如果某个阶段失败（如翻译 API 超时、压制出错），可以从指定阶段重新开始，而无需重新下载视频。

使用 `--start-from` 参数：

```bash
# 跳过下载，直接从 AI 翻译开始（使用已下载好的视频和字幕）
python main.py --start-from translate

# 跳过下载和翻译，直接从压制字幕开始（使用已保存的翻译结果）
python main.py --start-from compose
```

**原理**：翻译阶段结束后，翻译结果会自动保存为 `*_pipeline_state.json` 文件。后续 `--start-from compose` 会加载这个文件，直接跳过翻译步骤进行压制。

> 💡 **提示**：你也可以在 `config.yaml` 中设置 `pipeline.start_from` 来固定默认起始阶段。命令行参数 `--start-from` 的优先级高于配置文件。

---

### 方式三：多频道多风格运行

本工具支持同时监控多个 YouTube 频道，并为每个频道指定不同的翻译风格：

**配置示例**（`config.yaml`）：

```yaml
youtube:
  channels:
    - https://www.youtube.com/@MathChannel/videos
    - https://www.youtube.com/@FlightSimChannel/videos
    - https://www.youtube.com/@TeaArtChannel/videos

bilibili:
  channel_styles:
    UCmath123: pure_math          # 数学频道 → 严谨学术翻译
    UCflight456: aviation_sim      # 飞行频道 → 航空术语翻译
    UCtea789: tea_culture          # 茶道频道 → 古朴诗意翻译

  collections:
    UCmath123: "数学合集"
    UCflight456: "模拟飞行合集"
    UCtea789: "茶文化合集"
```

每个频道的视频将自动使用对应的 AI 提示词进行翻译，上传后自动归入对应合集。

---

### 方式四：无人值守定时运行

将工具部署在服务器上，通过系统定时任务实现全自动搬运。

#### Linux 云服务器 (Crontab)

1. 编辑 crontab：
   ```bash
   crontab -e
   ```
2. 添加定时任务（每 6 小时执行一次）：
   ```bash
   0 */6 * * * cd /path/to/Bili_auto_sync && /path/to/venv/bin/python main.py >> logs/cron.log 2>&1
   ```
3. 查看日志：
   ```bash
   tail -f /path/to/Bili_auto_sync/logs/cron.log
   ```

#### Windows 系统 (WSL)

本工具仅支持 Linux 环境。Windows 用户请在 WSL 中运行，然后使用 Windows 任务计划程序触发 WSL 命令：

1. 打开 Windows "任务计划程序"，创建新任务。
2. 触发器：每天，按需设置重复间隔。
3. 操作 → 启动程序：
   - **程序**: `wsl.exe`
   - **参数**: `cd /path/to/Bili_auto_sync && python main.py`

---

### 🔧 常见使用场景

#### 场景 A：仅本地压片，不上传
```yaml
bilibili:
  enable_upload: false
```
运行后成品视频保存在 `data/completed_videos/`。

#### 场景 B：上传后清理所有文件（节省磁盘空间）
```yaml
bilibili:
  enable_upload: true
  delete_temp_files: true
  delete_final_video: true
```

#### 场景 C：保留临时材料用于调试
```yaml
bilibili:
  delete_temp_files: false
```
临时文件保留在 `data/temp_workspace/`，可手动检查字幕、翻译结果等。

#### 场景 D：手动微调翻译后用 AI 重新压制
1. 先运行 `python main.py --start-from translate` 完成翻译。
2. 手动修改 `data/temp_workspace/*_pipeline_state.json` 中的翻译内容。
3. 运行 `python main.py --start-from compose` 用修改后的翻译重新压制。

#### 场景 E：已下载视频，更换翻译风格重新压制
1. 修改 `config.yaml` 中的 `channel_styles`。
2. 运行 `python main.py --start-from translate` 用新风格重新翻译。
3. 程序会自动接续压制步骤。

## 📂 目录结构说明

* `configs/`：存放所有配置文件（`config.yaml`、`cookies.json`）、字体文件。
* `core/`：核心功能模块。
  * `downloader.py`：YouTube 视频下载（yt-dlp 封装）+ WhisperX 词级时间戳转录（可选）。
  * `translator.py`：字幕优化 + DeepSeek AI 翻译 + B 站元数据生成。
  * `composer.py`：双语 ASS 字幕生成 + FFmpeg 硬字幕压制。
  * `publisher.py`：B 站上传（biliup 封装）+ 自动合集归类。
  * `collection.py`：B 站合集管理 API 封装。
* `data/`：
  * `temp_workspace/`：运行时临时工作台。包含下载的视频、字幕、封面、简介描述，以及翻译阶段生成的 `*_pipeline_state.json`（断点续传的关键文件）。
  * `completed_videos/`：未开启彻底删除时，压制完成的双语硬字幕成品视频归档处。
  * `archive.txt`：已下载视频的 YouTube ID 记忆库，防止重复搬运。
* `logs/`：按天自动轮转的运行日志记录。
* `utils/`：日志管理（`logger.py`）与配置管理（`config_manager.py`）工具类。

## ⚖️ 许可证与免责声明

### 本项目代码

本项目 Python 代码基于 [MIT](LICENSE) 许可证开源，不提供任何形式的明示或暗示担保。

### FFmpeg 许可证说明

本项目的 Docker 镜像和运行流程中使用了 FFmpeg。Debian/Ubuntu 官方源中的 FFmpeg 通常以 GPL 许可证编译（包含 `libx264` 等 GPL 编码器）。请注意：

- FFmpeg 自身的许可证适用于 FFmpeg 二进制本身
- 本项目通过 `subprocess` 方式调用 FFmpeg 命令行工具，属于"独立进程间通信"（mere aggregation），**本项目的 Python 代码不因此受 GPL 传染**
- 如果你分发包含 FFmpeg 的 Docker 镜像，你**需要遵守 FFmpeg 的 GPL 条款**（主要是提供 FFmpeg 源码的获取方式）
- 如果你对此有顾虑，可自行替换为 LGPL 编译的 FFmpeg 版本（如 [BtbN/FFmpeg-Builds](https://github.com/BtbN/FFmpeg-Builds) 提供的 LGPL 静态构建），或从 Dockerfile 中移除 FFmpeg 改为运行时挂载

### Docker 部署免责声明

- Docker 部署方案（`Dockerfile`、`docker-compose.yml`、`scripts/docker-entrypoint.sh`）为**示例性质**，未经充分测试，可能存在未知问题
- 使用 Docker 部署前请确保理解基本的 Docker 操作（卷挂载、网络配置、GPU 直通等）
- 如遇到构建失败、权限异常、网络不通等问题，请在 GitHub Issues 中提出，附上完整的错误日志

### 使用免责声明

本项目仅供学习和技术研究使用。请勿将本软件用于任何商业用途或侵犯第三方版权的行为。使用本软件产生的任何法律后果由使用者自行承担。
