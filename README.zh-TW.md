<p align="center"><img src="assets/brand/logo.png" width="104" height="104" alt="OdenMap app icon"></p>
<h1 align="center">Oden ARC</h1>
<p align="center"><strong>把散落的資料，整理成清晰、可追溯的心智圖。</strong></p>
<p align="center">為 OdenMap 配套的開源 AI 技能與本機工具</p>
<p align="center"><a href="README.md">English</a> · <a href="README.zh-CN.md">简体中文</a> · 繁體中文</p>

Oden ARC 協助 AI 助手將文件、圖片、表格等資料整理成 **OdenMap** 原生心智圖，在精煉結論旁保留可編輯公式、資源卡片、備註與證據。

它結合 **Agent Skill、命令列工具與可恢復的本機證據記憶**。AI 宿主負責理解資料，ARC 負責保存進度、驗證參照、建立新的 `.odenmap` 檔案。它不內建模型，也不要求另外設定模型 API 帳號。

**[OdenMap 官網與 Mac 測試版](https://baojiachen0214.github.io/oden-website/)** · [開源倉庫](https://github.com/baojiachen0214/oden-arc)

**OdenMap 是獨立的閉源 Swift 原生應用程式。** 本倉庫只開放配套技能、Python 工具、文件及合成範例，不開放軟體本體。

## 為什麼使用 ARC？

- **圍繞問題組織。** 依讀者需要理解、決定或執行的事情構圖，而非複製檔案目錄。
- **不只有文字。** 圖表、局部摘錄、文件、表格與原生 LaTeX 可以共同構成心智圖。
- **證據緊隨結論。** 保留關鍵限制、相反證據及未決問題。
- **中斷後繼續。** 本機工作區保存批次、租約、來源指紋及交接狀態。
- **有目的地使用上下文。** 只擷取相關證據組；確認宿主仍保留內容時，才省略重複正文。
- **不覆寫原件。** 在新目錄建立交付物，驗證後再由 OdenMap 開啟。

## 快速開始

需要 **Python 3.10 或更新版本**。核心編譯與記憶引擎只使用標準函式庫。在下載或複製的專案目錄執行：

```sh
python3 scripts/arc.py capabilities
python3 scripts/arc.py preflight examples/quickstart/plan.json
python3 scripts/arc.py compile examples/quickstart/plan.json \
  --out ./my-first-map --strict-review
python3 scripts/arc.py validate-delivery ./my-first-map
```

在 OdenMap 開啟 `my-first-map/map.odenmap`，並保留整個交付目錄中的計畫、來源副本及驗證資訊。每次輸出都必須使用**尚不存在的目錄**。

快速範例採用合成資料，不需要網路、模型或選用依賴。更多說明見 [入門指南](docs/getting-started.md)。

## 交給 AI 使用

提供完整專案，請助手先讀取 [`SKILL.md`](SKILL.md)：

> 使用 Oden ARC，圍繞我的目標整理這些資料。先讀 SKILL.md，按需載入其他規範。保留關鍵條件與來源。大量資料使用持久工作區，每批完成後提交。最後交付新的 OdenMap 原生檔案、來源及驗證結果。

支援 Agent Skills 的宿主應載入**完整 `oden-arc/` 目錄**，不是只複製一個 Markdown 檔案。安裝與技能探索方式由宿主決定，本專案不會自行安裝到全域技能目錄。

小任務可直接編寫 MapPlan；長任務見 [持久記憶](references/memory-protocol.md) 與 [Context Atlas](references/context-atlas.md)。技能規範以英文維護，輸出語言則遵循使用者要求。

## 能力與邊界

ARC 提供提示詞流程、原生檔案編譯、靜態驗證、可恢復記憶，以及選用的圖片/PDF 裁切工具。模型理解、OCR、語音轉錄、Office 解析、Mermaid 渲染和原生應用操作由宿主或其他工具提供。

**本專案是 Skill 與 CLI 工具，不是已部署的 MCP 服務。** 它也是 **OdenMap 的獨立配套工具，不是應用原始碼**。格式適配器只公開必要的資料互通結構，不包含應用的渲染器、互動畫布、專有排版引擎或效能最佳化程式碼；導出位置估算是獨立的通用回退實作。見 [架構](docs/architecture.md)。

Python 工具不會主動連網或呼叫模型，但 **AI 宿主可能將你提供的資料傳送給模型服務商**。工作區及備份包含未加密的原件快照，應置於專案之外，也不要附在公開 Issue。見 [安全說明](SECURITY.md)。

靜態驗證不能證明事實正確或保證原生應用的顯示效果。使用前應在 OdenMap 實際檢查；本專案不宣稱相容所有宿主或達到榜單最優。

## 文件與貢獻

[文件導覽](docs/README.md) · [範例](examples/README.md) · [貢獻指南](CONTRIBUTING.md) · [測試](docs/testing.md) · [更新紀錄](CHANGELOG.md)

```sh
python3 scripts/run_tests.py
python3 scripts/audit_public.py
```

缺少選用媒體依賴時，相關測試會明確略過。公開審查工具有明確檢查範圍，不能保證未來任意貢獻均無洩漏風險。

## 授權

ARC 自有程式碼、提示詞、文件及合成範例採用 [MIT 授權](LICENSE)，**不授權 OdenMap 應用或第三方依賴**。

選用 PDF 後端 **PyMuPDF** 採用 AGPL/商業雙授權；使用、散布或整合前請閱讀 [第三方依賴說明](THIRD_PARTY.md)。無依賴核心及僅圖片安裝不需要此後端。

`assets/brand/` 中的 OdenMap 圖示為產品品牌素材，不在 ARC 的 MIT 授權範圍內，見[品牌素材說明](assets/brand/README.md)。
