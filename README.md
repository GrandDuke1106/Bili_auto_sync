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

#### 🅱️ Bilibili 上传设置
| 字段 | 说明 | 默认值 |
|------|------|--------|
| `enable_upload` | 是否上传到 B 站（`false` 仅本地压片） | `false` |
| `delete_temp_files` | 完成后删除原视频、字幕等临时材料 | `true` |
| `delete_final_video` | 上传后删除成品硬字幕视频（省空间） | `false` |
| `tid` | B 站分区 ID（122=野生动植物，详见 B 站文档） | `122` |
| `tags` | 基础标签列表（会与 AI 生成的标签合并） | `[翻译, YouTube]` |

##### 🎨 频道翻译风格 (`channel_styles`)
通过频道 ID 为不同频道指定专属的翻译风格。可选风格：

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

#### 🖋️ 字幕字体
| 字段 | 说明 | 默认值 |
|------|------|--------|
| `fonts_dir` | 字体文件目录 | `configs/fonts` |
| `zh_font_name` | 中文字体名称 | `Noto Sans SC` |
| `en_font_name` | 英文字体名称 | `Fira Code` |

---

## 🚀 如何使用

### 处理管线概览

本工具的处理流程分为 **4 个阶段**：

```
阶段1: 下载 → 阶段2: AI翻译 → 阶段3: 压制字幕 → 阶段4: 上传B站
```

| 阶段 | 说明 | 输出 |
|------|------|------|
| `download` | yt-dlp 下载 YouTube 视频+字幕+封面+简介 | `.mp4`、`.srt`、`.description`、封面图 |
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

### 方式二：分阶段运行 / 断点续传

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
  * `downloader.py`：YouTube 视频下载（yt-dlp 封装）。
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

## ⚖️ 许可证

本项目基于[MIT](LICENSE)开源，不提供担保。

本项目仅供学习和技术研究使用。请勿将本软件用于任何商业用途或侵犯第三方版权的行为。使用本软件产生的任何法律后果由使用者自行承担。
