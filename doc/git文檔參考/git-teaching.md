# git 教學指南

## 確認git版本

```zsh
git --version
```

## 設定使用者名稱與信箱

**📚 參考資料:**

- [1.6 Getting Started - First-Time Git Setup](https://git-scm.com/book/en/v2/Getting-Started-First-Time-Git-Setup)

在第一次使用 Git 時,需要設置你的名字和信箱。這些資訊會記錄在每次的 commit 中。

> **注意**：名稱必須使用引號包覆（因為可能包含空格），信箱的引號則可省略。

- **名稱**：建議使用開發者的英文名字
- **信箱**：建議使用 GitHub 或 GitLab 的註冊信箱

### 設置

```zsh
git config --global user.name "Your Name"
git config --global user.email your.email@example.com
```

### 確認

```zsh
git config --global user.name
git config --global user.email
```

### 查看全域設定

`git config --global --list`

**提示**：使用 `--global` 參數會將設定套用到所有專案。如需針對特定專案設定，請在該專案目錄下執行指令並移除 `--global` 參數。

---

## 修改預設編輯器

正常來說預設編輯器會是使用 vim,但特別難用。

**📚 參考資料:**

- [A3.1 Appendix C: Git Commands - Setup and Config](https://git-scm.com/book/en/v2/Appendix-C:-Git-Commands-Setup-and-Config)

### TextEdit

```zsh
git config --global core.editor "open --wait-apps --new -e"
```

### Visual Studio Code

```zsh
git config --global core.editor "code --wait"
```

---

## 忽略檔案

**📚 參考資料:**

- [Ignoring files](https://docs.github.com/en/get-started/git-basics/ignoring-files)
- [Git - gitignore](https://git-scm.com/docs/gitignore/zh_HANS-CN)

### 創建 .gitignore 文件

```zsh
touch .gitignore
```

### 範例

```gitignore
.DS_Store 
node_modules/

# 忽略任何檔案with .log 副檔名（或 .log 結尾的檔案）
*.log 

# 只忽略根目錄的 node_modules（不影響子專案）
/node_modules/

# 忽略所有 build 目錄，但不忽略 build.txt 檔案
build/

# 忽略根目錄的 dist 資料夾
/dist/
```

### 使用[gitignore.io](https://www.toptal.com/developers/gitignore)創建範本

- [etc. python](https://www.toptal.com/developers/gitignore/api/python)

### 注意

#### 結尾有斜線 `/` → 表示「只忽略目錄」

```zsh
captures/
```

- ✅ 忽略所有名為 `captures` 的目錄（任何層級）
- ❌ 不會忽略名為 `captures` 的檔案

```zsh
/local/
```

- ✅ 只忽略根目錄下的 `local` 目錄
- ❌ 不會忽略根目錄下名為 `local` 的檔案
- ❌ 不會忽略其他位置的 `local` 目錄（如 `src/local/`）

---
