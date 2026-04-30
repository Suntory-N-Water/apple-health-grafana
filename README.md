# apple-health-grafana

iPhone のヘルスケアデータを Grafana でローカル可視化するツール。

Docker と Python 3 があれば動きます。

## できること

- 睡眠ステージ(Deep / REM / コア)の日別積み上げグラフ
- 総睡眠時間・Deep+REM 割合のトレンド
- 日別歩数・週別運動時間
- ワークアウト記録(種別・時間・距離・消費カロリー)
- 安静時心拍数・HRV・VO2 Max のトレンド

## 必要なもの

- Docker
- Python 3.8 以上
- iPhone のヘルスケアデータ(エクスポート ZIP)

## セットアップ

### 1. ヘルスケアデータをエクスポート

iPhone の「ヘルスケア」アプリ → 右上のアイコン → **「すべてのヘルスデータをエクスポート」**

ZIP ファイルが書き出されるので Mac に AirDrop する。

### 2. ZIP を data/ に展開

※場合によっては`書き出したデータ.zip`のようなファイル名になっているかもしれないので、その場合は適宜修正してください。

```bash
unzip ~/Downloads/apple_health_export.zip -d data/
# → data/apple_health_export/export.xml が生成される
```

### 3. XML を SQLite に変換

```bash
python3 parse_health.py data/apple_health_export/export.xml
```

`data/health.db` に書き出される。データ量によっては数分かかる。

### 4. Grafana を起動

```bash
docker compose up -d
```

### 5. ブラウザで開く

http://localhost:3000/dashboards

「iPhone Health Data」ダッシュボードを選択し、ダッシュボードを確認。

### 終了

```bash
docker compose down
```

## ディレクトリ構成

```
health-viz/
├── parse_health.py                        # XML → SQLite 変換スクリプト
├── docker-compose.yml                     # Grafana 起動設定
├── data/                                  # DB 置き場(.gitignore 済み)
│   └── health.db                          # parse_health.py が生成
└── grafana/
    ├── provisioning/
    │   ├── datasources/sqlite.yml         # SQLite データソース設定
    │   └── dashboards/default.yml         # ダッシュボード読み込み設定
    └── dashboards/health.json             # ダッシュボード定義
```

## 取り込まれるデータ

| テーブル | 内容 |
|---|---|
| `steps` | 歩数 |
| `heart_rate` | 心拍数 |
| `resting_heart_rate` | 安静時心拍数 |
| `hrv` | 心拍変動(SDNN) |
| `active_energy` | 消費カロリー(アクティブ) |
| `exercise_time` | 運動時間 |
| `distance` | 歩行・ランニング距離 |
| `vo2max` | VO2 Max |
| `respiratory_rate` | 呼吸数 |
| `oxygen_saturation` | 血中酸素濃度 |
| `sleep` | 睡眠ステージ(Apple Watch のデータのみ) |
| `workouts` | ワークアウト記録(種別・時間・距離・消費kcal) |

## 注意

- 睡眠データは Apple Watch のソースのみを使用(AutoSleep 等との二重計上を防ぐため)
- `data/` ディレクトリは `.gitignore` 済みのため個人データはコミットされない
- ヘルスケアデータは個人情報のため取り扱いに注意
