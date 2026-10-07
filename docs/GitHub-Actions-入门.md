# GitHub Actions 入门（本仓库的 CI 是怎么跑的）

> 写给"刚接触 CI"的人。全部内容围绕本仓库的 `.github/workflows/tests.yml` 展开，
> 每一条都能在你自己仓库的 Actions 页面里对着看。
>
> 读完你会知道：CI 是什么、这份配置每一行在干什么、怎么读日志、怎么改它，
> 以及 **tag 和 CI 到底需不需要在 commit 的时候就动**（答案在最后一节）。

---

## 一、先回答你的问题：用的是 GitHub Actions 吗？

**是。** 你仓库里跑的那套 CI 就是 **GitHub Actions** —— GitHub 自带的持续集成服务。

判定依据：配置文件在 `.github/workflows/` 目录下、语法是 GitHub 的 YAML、
运行日志出现在仓库页面的 **Actions** 标签里、徽章地址是
`github.com/<用户>/<仓库>/actions/workflows/<文件名>/badge.svg`。这四条都是 GitHub Actions 独有的。

> 顺带一提，市面上还有 Travis CI、CircleCI、GitLab CI、Jenkins 等同类工具，
> 做的事情一样（拉代码 → 装环境 → 跑命令 → 按退出码报红绿）。
> GitHub Actions 对公开仓库**完全免费**，这也是它成为默认选择的原因。

---

## 二、CI 是什么（一句话版）

**一台每次都是全新的云端电脑，加上一份"要执行的清单"。**

```
你 push 代码
   ↓ ① 触发（on:）
GitHub 开一台干净的 Ubuntu 机器
   ↓ ② 装环境（setup-python）
python 3.10 / 3.12
   ↓ ③ 按顺序跑命令（steps）
pip install -r requirements-dev.txt
python src/core.py
python -m pytest -q
   ↓ ④ 报告结果
全绿 = 打勾；任何一步非零退出 = 打叉并邮件通知你
```

**唯一的判定依据是退出码（exit code）**：0 = 成功，非 0 = 失败。
CI 不读你打印的任何文字——所以 `print("验证通过")` 不是测试，`assert x == y` 才是。

---

## 三、这份配置逐行拆解

文件：`.github/workflows/tests.yml`

```yaml
name: tests                    # 工作流名字，显示在 Actions 页面左侧
on:                            # ① 什么时候触发
  push:                        #    任何分支 push 时（包括往 tag push）
  pull_request:                #    有人开 PR 时
  workflow_dispatch:           #    允许在 Actions 页面手动点一次（调试时很有用）

permissions:
  contents: read               # 最小权限：这份 CI 只需要读代码
                               # 不写这一行，token 默认权限可能比需要的大（安全项）

jobs:                          # 一个工作流可以含多个 job；默认并行跑
  test:
    runs-on: ubuntu-latest     # ② 用哪台机器。Linux 最便宜也最快
    strategy:
      fail-fast: false         #    矩阵里有一个失败，不要取消另一个（两个都要看结果）
      matrix:
        python-version: ['3.10', '3.12']   # 同一个 job 跑两遍，只换 Python 版本
    steps:                     # ③ 依次执行；任一步失败，后面跳过、整体判失败
      - uses: actions/checkout@v4          # 把你的仓库拉进这台机器（几乎必备第一步）
      - uses: actions/setup-python@v5      # 装指定版本的 Python
        with:
          python-version: ${{ matrix.python-version }}
          cache: pip                       #    缓存 pip 下载，第二次开始快很多
      - name: 安装测试依赖
        run: |
          python -m pip install --upgrade pip
          python -m pip install -r requirements-dev.txt
      - name: 计算核心等价性回归（零依赖入口）
        run: python src/core.py
      - name: 计算核心正确性验证（对照公开参考值）
        run: python -m pytest -q
      - name: 语法检查（含 GUI 入口）
        run: python -m py_compile main.py src/core.py src/ui/*.py legacy/sample.py
      - name: 静态检查（未定义名/未使用导入）
        run: python -m pyflakes main.py src/core.py
```

几个关键点：

| 写法 | 含义 |
|---|---|
| `uses:` | 用现成的"动作"（别人写好的可复用步骤），如 `actions/checkout@v4` |
| `run:` | 直接跑一条 shell 命令（这里是 bash，因为机器是 Linux） |
| `@v4` | 锁主版本号。**不要写 `@main`**——上游某天改坏或被篡改你就会一起中招 |
| `matrix:` | 一份配置跑多个组合（这里 = 两个 Python 版本） |
| `${{ ... }}` | 表达式，取矩阵值、secrets、上下文等 |
| `|` | YAML 多行字符串，shell 会逐行执行 |

### 为什么这份 CI 不装 PySide2

`requirements.txt`（运行依赖）和 `requirements-dev.txt`（测试依赖）是**刻意分开**的：

- `PySide2==5.15.2.1` 只提供到 **Python 3.10** 的轮子，3.11+ 上 pip 装不上；
- 而计算核心 `src/core.py` **零第三方依赖**，测试也只需要 `pytest`。

如果 CI 里装 `requirements.txt`，那么 3.12 这个矩阵任务会因为**与代码质量无关的原因**变红，
久而久之你就开始无视红灯了——这是 CI 最常见的死法。

---

## 四、日常怎么用

### 1. 推代码，看结果

```powershell
git push origin master
```

然后打开 `https://github.com/x1shang/Wetbulb-Calculator/actions`。
最近一次运行会出现在最上面，绿色勾 = 通过，红色叉 = 失败。

命令行等价操作：

```powershell
gh run list   -R x1shang/Wetbulb-Calculator --workflow tests.yml --limit 5
gh run watch  -R x1shang/Wetbulb-Calculator --exit-status      # 盯着跑到结束
gh run view   <run-id> -R x1shang/Wetbulb-Calculator           # 看每个 job 每步的结果
gh run view   <run-id> -R x1shang/Wetbulb-Calculator --log-failed   # 只看失败那步的日志
```

`gh` 是 GitHub 官方命令行工具，本机已登录（`gh auth status` 可查看）。

### 2. 失败了怎么看

按这个顺序：

1. **看是哪一步红的**（`gh run view <id>` 会列出每一步的 ✓/✗）；
2. **看那一步的退出码和最后 20 行**（`--log-failed`）；
3. **在本机复现**——这是最重要的一步。CI 上跑的就是那几条命令，本机跑一遍几乎必然同样失败：

   ```powershell
   pwsh -File run_tests.ps1
   ```
4. 修好、提交、推上去，看它变绿。

**不要**靠"再推一次试试"来修 CI。CI 不稳几乎总是配置或代码的问题。

### 3. 手动触发（调试很有用）

因为配置里有 `workflow_dispatch:`，你可以在 Actions 页面点进 `tests`，右上角有
**Run workflow** 按钮，选分支点一下就跑，不必为了测试 CI 而推一个假提交。

命令行：`gh workflow run tests.yml -R x1shang/Wetbulb-Calculator`

### 4. 重跑某一次

Actions 页面打开那次运行，右上角 **Re-run all jobs**。
命令行：`gh run rerun <run-id> -R x1shang/Wetbulb-Calculator`

---

## 五、徽章（README 顶部那个绿勾）

```markdown
![tests](https://github.com/x1shang/Wetbulb-Calculator/actions/workflows/tests.yml/badge.svg)
```

注意 URL 里的 `workflows/tests.yml` 必须与**文件名**一致（不是 `name:` 里的名字）。
打开这个 URL 会得到一个 SVG，内容是 `tests - passing` 或 `tests - failing`。

它的意义：**别人打开你的仓库，不用读代码、不用问你，就知道"这台机器能自动验证它"。**

---

## 六、怎么改这份 CI

### 加一条检查

在 `steps:` 最后追加，例如加一个"禁止提交超过 5 MB 的文件"：

```yaml
      - name: 大文件守门
        run: |
          big=$(git ls-files -z | xargs -0 -I{} du -k "{}" | awk '$1 > 5120 {print $2}')
          test -z "$big" || { echo "以下文件超过 5 MB：$big"; exit 1; }
```

### 只在特定分支跑

```yaml
on:
  push:
    branches: [master]
```

### 让 CI 也看看代码风格

```yaml
      - run: python -m pip install ruff
      - run: ruff check src main.py
```

### 定时跑（适合"每天体检"类检查）

```yaml
on:
  schedule:
    - cron: '0 20 * * *'   # UTC 20:00 = 北京时间次日 04:00
```

> 注意：**私有仓库的 Actions 会消耗免费额度**（公开仓库不计费），
> 所以私有库存量检查要用 `schedule` 而不是每次 push。

### 改完怎么验证

改 `.yml` 属于改代码：提交 → 推送 → 看 Actions 是否按预期跑。
如果 YAML 写错了，GitHub 会在 Actions 页面顶部直接提示 "Invalid workflow file" 并指出行号。

---

## 七、⭐ 你最关心的：tag 和 CI 需要"在 commit 的时候"就动吗？

**不需要。** 这三件事是**三件独立的事**，发生在不同的时刻：

| 动作 | 什么时候做 | 对应命令 |
|---|---|---|
| **提交（commit）** | 你改完代码、本地检查通过 | `git add` + `git commit` |
| **CI 自动跑** | **每次 push 时自动发生**，你不用做任何事 | CI 配置不需要跟着改 |
| **打 tag** | 你决定"这一版可以发布了"的**那一刻之后** | `git tag` + `git push origin <tag>` |

### 关键理解：CI 配置是"规则"，不是"记录"

`.github/workflows/tests.yml` 里写的是**规则**："只要有人 push 或开 PR，就跑这些检查"。
规则一旦写好就长期有效，**不需要每次提交都去改它**。

只有在你想**改变检查内容**时（比如加一条 lint）才需要改这个文件——而那时它也是一次普通提交。

### 那 tag 呢？

tag 是**给某个已经存在的提交贴的永久书签**。顺序永远是：

```
① 改代码
② git commit                    ← 提交诞生了（此时还没有 tag）
③ git push                      ← CI 自动跑起来
④ 等 CI 变绿                    ← 只有绿了才值得发布
⑤ git tag v1.3.2                ← 给"刚才那个被验证过的提交"贴书签
⑥ git push origin v1.3.2        ← 把 tag 推上去
⑦ gh release create v1.3.2 ...  ← 建发布页 + 挂 exe 附件
```

要点：

- **tag 指向的是一个提交**，所以必须"先有提交，后有 tag"。
- **先等 CI 绿再打 tag**。tag 的全部意义是"这个提交被验证过"。
  如果 CI 还没跑完就打了 tag，那这个 tag 什么也没证明。
- **tag 一旦推上去就永不移动**。要修 bug 就打 `v1.3.3`。
  （你仓库的 Aippt 项目曾经用脚本 `git tag -d v2.2.1` 之后重建同名 tag，
  结果所有声称"我用的是 v2.2.1"的人都无法确定自己在用什么。别这么做。）
- **`v1.3.1` 这个版本号还写在代码里**（`src/core.py` 的 `tag`、`src/ui/about.py` 的关于框文本）。
  那不是"commit 时要改"，而是"**决定发新版时**要改"——改完提交，提交信息里写清版本号，
  这个提交再去打 tag。顺序是：改版本号 → 提交 → push → CI 绿 → 打 tag。

### 一个常见疑问：往 tag 上 push 会不会触发 CI？

会。`on: push` 对**分支**和**tag**都生效。

所以本仓库现在的行为是：推 `master` 跑一次，推 `v1.3.1` 又跑一次——
第二次的价值是"确认被贴上 tag 的那个提交确实是绿的"。

如果你**不想**让 tag 触发（比如觉得重复），可以显式排除：

```yaml
on:
  push:
    tags-ignore: ['**']    # 只对分支 push 生效
```

反过来，只想在 tag 上跑（比如"只做发布构建"），写成：

```yaml
on:
  push:
    tags: ['v*']
```

### 一张速查表

| 你做了什么 | CI 会跑吗 | 需要改 CI 配置吗 | 需要动版本号吗 |
|---|---|---|---|
| 改代码后 `git commit`（还没 push） | ❌ 不会 | 否 | 否 |
| `git push origin master` | ✅ 会 | 否 | 否 |
| 开一个 PR | ✅ 会 | 否 | 否 |
| `git tag v1.3.2` + `git push origin v1.3.2` | ✅ 会（因为 `on: push` 含 tag） | 否 | 打 tag **前**要先把代码里的版本号改成 v1.3.2 |
| 想加一条新检查 | — | **是**，改完是一次普通提交 | 否 |
| 想在 Actions 页面手动跑一次 | ✅ 会（`workflow_dispatch`） | 否 | 否 |

---

## 八、排查用命令速查

```powershell
# 看当前仓库的登录状态与权限
gh auth status

# 最近几次运行
gh run list -R x1shang/Wetbulb-Calculator --workflow tests.yml --limit 5

# 盯着某次运行到结束（退出码 0 = 全绿）
gh run watch <run-id> -R x1shang/Wetbulb-Calculator --exit-status

# 只看失败步骤的日志
gh run view <run-id> -R x1shang/Wetbulb-Calculator --log-failed

# 某个 job 里每一步的结果
gh api repos/x1shang/Wetbulb-Calculator/actions/runs/<run-id>/jobs `
  --jq '.jobs[] | "── \(.name)", (.steps[] | "   \(.conclusion)\t\(.name)")'

# 手动触发
gh workflow run tests.yml -R x1shang/Wetbulb-Calculator

# 重跑
gh run rerun <run-id> -R x1shang/Wetbulb-Calculator
```

---

## 九、六个最容易踩的坑

| 坑 | 说明 | 怎么办 |
|---|---|---|
| **只打印，不看退出码** | CI 靠退出码判成败 | 脚本末尾 `sys.exit(1)` / `process.exit(1)`；Python 用 `assert` 或 pytest |
| **环境没写在仓库里** | 空白机器上装不上依赖 | `requirements*.txt` 锁版本；CI 里显式 `pip install` |
| **把 GUI 依赖塞进测试环境** | 装不上 → 整条流水线无关地变红 | 运行依赖与测试依赖分开（本仓库就是这么做的） |
| **第三方 action 不锁版本** | `@main` 某天变坏或被篡改 | 用 `@v4` 这种主版本标签 |
| **权限过大** | 默认 token 权限可能超出需要 | workflow 顶层加 `permissions: contents: read` |
| **CI 红了就去点"重跑"** | 不稳定几乎总是真问题 | 在本机跑同样的命令复现（`pwsh -File run_tests.ps1`） |

---

## 十、想再深入一点

1. **GitHub 官方**：[GitHub Skills](https://skills.github.com/) 有"用 Actions 建 CI"的实操课（免费、带练习仓库）。
2. **语法参考**：[Workflow syntax for GitHub Actions](https://docs.github.com/en/actions/reference/workflow-syntax-for-github-actions)。
3. **本仓库的实践**：把 `.github/workflows/tests.yml` 和 `run_tests.ps1` 对着看一遍——
   前者是"云端怎么跑"，后者是"本机怎么跑"，两者跑的是同一批命令。
   这个对应关系就是 CI 的核心：**把"我说通过"变成"机器说通过"**。
4. **下一步可以加的**：
   - `matrix` 扩到更多 Python 版本；
   - `actions/cache` 缓存依赖（本仓库已用 `setup-python` 的 `cache: pip`）；
   - 发布自动化：CI 跑绿后自动打 tag、建 Release、上传 exe（把第 ⑤⑥⑦ 步交给机器）。
