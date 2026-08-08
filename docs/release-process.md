# ICSTeX Release Process

本流程把“可复现的本地候选”与“公开发布”分成两个边界。前者可由开发者在
本地完成；后者始终需要维护者明确确认。

## 1. Prepare the candidate

1. 确认 `app/__init__.py`、`pyproject.toml`、Release 文档与制品版本一致。
2. 更新 `release/release-manifest.json`，然后运行：

   ```bash
   python3 tools/update_release_site.py
   python3 tools/release_prepare.py --check
   python3 -m unittest tests.test_release_site
   bash packaging/preflight.sh
   ```

3. 检查 `git diff --check`；提交 source、Release metadata、网页和验证报告。
4. 只有全部门禁通过后，才能把 `v<version>` 轻量标签指向当前 Release commit。

## 2. Prepare the static website

网站源码仅在 `website/` 中，使用 HTML、CSS、原生 JavaScript 与仓库内已核验
截图。`website/release.json` 由 `tools/update_release_site.py` 生成；不要手改。

本地预览：

```bash
python3 -m http.server 8765 --directory website
```

Pages worktree 预演不会推送：

```bash
bash tools/deploy_release_site.sh --prepare
```

## 3. Publish only after explicit approval

维护者明确批准后，按顺序完成：

1. `git push origin release/2.1` 与 `git push origin v<version>`；
2. 用校验过的 assets 创建 GitHub **Draft prerelease**，核对名称、SHA-256、安装
   说明和限制；
3. 发布 GitHub Release 后，将 manifest 的 `github_release_published` 设为 `true`，
   重新生成 `website/release.json` 并提交；
4. 执行受环境变量保护的 `--push`，再在 GitHub Pages 中选择 `gh-pages` / root；
5. 以无缓存浏览器检查首页、下载链接、移动端和 SHA-256。

在没有明确批准时，禁止 `git push`、`git push --tags`、`gh release create`、
`gh release publish`、`git push origin gh-pages` 或任何替代性的线上部署。
