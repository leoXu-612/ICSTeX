# FORCODEX.md

本轮交付已结束（2026-10-02）：先完成文件/大纲上下分区和顶部留白收紧，再完成
局部按钮高光、边框和即时状态反馈。源码88ac73f、f24ceb4已推送草稿PR#10，
分支codex/workbench-structure-polish；不自动合并或发布。

最终app1cc875a9，夹具修正后app+tests91f73d20。全量1912项执行后唯一旧展示
夹具时序问题已受控复现并仅修测试，8项补验通过；原全量退出1保留，不宣称全量
命令退出0。原生示例编译/PDF与最后导航补验分别保留源码身份；细节见PROJECT_STATE。

已备份并替换/Applications/ICSTeX.app，运行程序bba9a751…39c4a07与候选一致，
当前停在欢迎页。旧版位于~/Applications/ICSTeX Backups/
ICSTeX-2.1.0-beta.4-before-structure-polish-20261002.app。
本地版本标签仍Beta4/210004，官网、feed、公钥、Actions和依赖未变。

后续等待用户验收，不自动追加UI、性能或无障碍重构；macOS27.0/Qt6.11.1的
selectedChildren缓解仍不等于完整无障碍验收。学生文稿不改，运行版不强退。
主树codex/pdf-export-status的未提交源码/索引保持原样，不从主树旧源码打包。
所有当前事实和收据以本工作树docs/PROJECT_STATE.md及PROJECT_LOG.md为准。
