# 🎉 Discord Stage Quiz Pro (Stage Quiz Battle)

Discordの「ステージチャンネル」と「挙手機能」を早押しボタンとして活用する、プロフェッショナル仕様のリアルタイムクイズ大会システムです。
FastAPIによる高速なバックエンド、Discord.pyによるBot制御、そしてWebSocketを利用したサイバーパンク風の配信画面（Audience View）が完全に同期して動作します。

## ✨ 主な機能 (Key Features)

- **Discord連携の超高速「早押し」判定**: 参加者がステージチャンネルで「挙手」をした瞬間をBotが検知。最も早かった1名を自動的にスピーカーへ引き上げ、効果音と共に解答権を与えます。
- **排他制御による大規模対応**: 200名規模の同時アクセス（一斉挙手）が発生しても、ロック制御により確実に「最初の1人」だけを判定します。
- **サイバーパンク風のリアルタイム配信画面**: OBS等で画面共有・配信するための「Audience画面」を搭載。問題文のタイピング表示、4択のポップアップ、正誤判定のアニメーションがWebSocketで遅延なく同期します。
- **高機能な管理者ダッシュボード**: 
  - 問題の進行コントロール（開始、一時停止、正誤判定、次の問題へ）
  - スコアの手動編集、ファクトリーリセット
  - CSVファイルによる問題の一括インポート（記述式・4択問題対応）
- **司会者保護機能**: 正誤判定時に参加者を一斉にオーディエンスへ降格させますが、司会者や運営スタッフを保護（ホワイトリスト化）するDiscordコマンド（`/protect`）を搭載しています。

---

## 🛠 システム要件 (Prerequisites)

本システムを自前環境（VPSやローカルサーバー）で動かすための要件です。

- **OS**: Ubuntu 20.04 / 22.04 等のLinux環境（Windows/macOSでも動作可）
- **Python**: 3.9以上
- **FFmpeg**: Botが正解音などのオーディオを再生するために必須です。
- **Discord Bot Token**: Discord Developer Portalから取得したBotトークン。

### ⚠️ Discord Botの必須設定
Discord Developer Portalにて、以下の設定を必ず行ってください。
1. **Privileged Gateway Intents**を全てONにする（`PRESENCE INTENT`, `SERVER MEMBERS INTENT`, `MESSAGE CONTENT INTENT`）。
2. サーバー招待時の権限（Permissions）にて、**「メンバーをミュート (Mute Members)」** を必ず付与してください（ユーザーをスピーカーから降ろすために必須です）。

---

## 🚀 構築・セットアップ手順 (Installation)

### 1. 依存関係のインストール
サーバーにFFmpegとPythonの仮想環境ツールをインストールします。
```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv ffmpeg
```

### 2. リポジトリのクローンと環境構築
```bash
git clone <このリポジトリのURL> discord_stage_quiz_pro
cd discord_stage_quiz_pro

# 仮想環境の作成と有効化
python3 -m venv venv
source venv/bin/activate

# パッケージのインストール
pip install -r requirements.txt
```

### 3. 環境変数の設定
`.env.example` をコピーして `.env` ファイルを作成し、DiscordのBotトークンを設定します。
```bash
cp .env.example .env
nano .env
# DISCORD_BOT_TOKEN=あなたのボットトークン を記述して保存
```

### 4. 起動テスト
以下のコマンドで、FastAPIのWebサーバーとDiscord Botが同時に起動します。
```bash
python run.py
```
`========== BOT READY (COG LOADED) ==========` とコンソールに表示されれば起動成功です。

※ 本番環境でバックグラウンドのデーモンとして常時稼働させる手順については、同梱の `deploy_instructions.md` を参照してください。

---

## 🎮 使い方 (Usage Flow)

### 1. 画面へのアクセス
ブラウザを開き、以下のURLにアクセスします。
- **管理者ダッシュボード**: `http://<サーバーのIP>:8000/admin`
- **問題管理画面**: `http://<サーバーのIP>:8000/admin/questions`
- **配信・プロジェクター用画面 (Audience)**: `http://<サーバーのIP>:8000/audience`

### 2. 問題の準備
問題管理画面から、手動で問題を追加するか、CSVで一括インポートします。
CSVのフォーマット（ヘッダー行）は以下の通りです。
`question_type, question_text, point_value, sort_order, media_url, choice_1, choice_2, choice_3, choice_4, correct_choice`
*(※ 記述式の場合は `choice_1` 以降は空欄にします)*

### 3. Discordステージの準備
1. Discordサーバーでステージチャンネルを開始します。
2. チャット欄で `/join` コマンドを実行し、Botをステージに登壇させます。
3. 司会者など、ステージから降ろしたくない運営メンバーに対して `/protect @ユーザー名` を実行します。

### 4. クイズ大会の進行
- 管理者ダッシュボードから問題を選択し **「Start (表示開始)」** を押すと、Audience画面に問題がタイピング表示されます。
- 参加者がDiscordで「スピーカーになる（挙手）」を押すと、最も早かった1名が自動的にスピーカーになり、画面に大きく名前が表示されます。
- 司会者が解答を聞き、ダッシュボードの **「⭕ Correct」** または **「❌ Incorrect」** を押して判定します。
- 判定後、**「⏭ 次の問題へ」** を押すと、現在の回答者がオーディエンスに戻り、スムーズに次の問題へ移行します。

---

## 📁 フォルダ構成 (Project Structure)
- `src/` : アプリケーションのコアロジック（FastAPIルーター、DBモデル、Discord Bot）
- `templates/` : HTMLテンプレート（Jinja2）
- `static/js/` : フロントエンドのJavaScriptおよびWebSocket処理
- `audio/` : クイズ用の効果音（mp3）
- `quiz.db` : SQLiteデータベース（初回起動時に自動生成されます）
- `run.py` : アプリケーションの起動エントリーポイント

## 📄 License
This project is open-source and available under the MIT License.