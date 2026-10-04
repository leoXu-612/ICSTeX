from __future__ import annotations

from html import escape
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QLabel, QMessageBox, QPushButton, QTabWidget, QTextBrowser, QVBoxLayout, QWidget

from app.gui.assets import asset_path
from app.gui.responsive.helpers import ButtonFlowLayout
from app.gui.theme import PRIMARY_BUTTON_STATE_STYLE


GUIDE_PAGES = (
    ("先试一遍", "edit-title.png", "练习副本中的标题。只替换选中的文字，保留两边的大括号。", r"""
<h2>跟着窗口上方的提示，做出第一份 PDF</h2>
<p>第一次点上面的“开始练习”，回来时点“继续上次练习”。练习使用单独的示例窗口，不改你的原稿。</p>
<ol><li><b>改标题：</b>点“选中标题”，输入自己的标题。</li>
<li><b>编译：</b>点“正式编译”，把文字排成 PDF。</li>
<li><b>看结果：</b>在 PDF 中找到新标题，再点“我看到了新标题”。</li>
<li><b>导出：</b>选好保存位置，等文件真正导出后，练习才会显示完成。</li></ol>
<!-- illustration -->
<h3>想停一下？</h3>
<p>点“收起导引”即可继续写作。从“帮助 → 新手导引”可以接着练；关闭过练习窗口时，
先重新编译，确认 PDF 是当前内容。“另建一个练习副本”不会覆盖上次的练习。</p>
<p>缺少 LaTeX 时，按提示点“检查环境”。可以先写内容，配置好环境后再编译。</p>
"""),
    ("认识界面", "write-preview.png", "当前工作台：左侧文件与章节大纲上下排列，中间写源码，右侧看 PDF。", r"""
<h2>左边找文件，中间写，右边看</h2>
<p>“项目导航”里，上方是项目文件，下方是当前文件的章节大纲；双击章节可跳转。
中间的 <code>.tex</code> 是你写的内容，右侧 PDF 是排版结果。</p>
<!-- illustration -->
<h3>什么时候需要点编译？</h3>
<p>第一次主动点“正式编译”。以后开启“自动快速预览”，停笔并自动保存后就会更新预览。
检查原图质量或准备导出时，用“正式编译”。</p>
<p><b>文档已保存</b>只表示文字写进了文件；<b>PDF 已是最新 / 快速预览 · 当前版本</b>
才表示当前内容已编译。看到<b>旧预览</b>时，不要把右边当成最新结果。</p>
<h3>常用入口在哪里？</h3>
<p><b>结构／源码：</b>编辑区右上角切换同一份文稿。结构视图可添加和拖动内容块，
拖入章节就是归入该章节；双击编辑内容，点“编辑代码”回到对应原文。两边共用保存和撤销。<br>
<b>当前块／整篇：</b>右侧独立切换阅读范围。“当前块”在最新整篇 PDF 中定位放大，
不是单独编译或只导出这一块；“搜索 PDF”查 PDF 关键词，左侧“项目搜索”查项目文本。</p>
<p><b>找位置：</b>源码里点“定位 PDF”；双击最新 PDF 的文字可回到源码。窄窗口用“源码 / PDF”切换。<br>
<b>插公式、图片、表格：</b>左侧“插入”页。图片优先放在项目内，使用相对路径。<br>
<b>加引用：</b>左侧“引用”页。先准备 BibTeX 条目，再插入引用键；检查不会替你编造文献。<br>
<b>看错误、日志和字数：</b>顶部或底栏的“控制台”。</p>
<p>文件/大纲、源码/PDF和控制台都可拖动分隔线调整空间，正常退出后会记住。
开始自己的文稿时，点“新建项目”，选语言、模板和保存位置；高级设置保留“自动选择（推荐）”即可。</p>
"""),
    ("报错怎么办", "check-error.png", "先选一条错误，看“说明与下一步”；可以定位，也可以展开原始日志。", r"""
<h2>先处理第一条错误</h2>
<p>打开“控制台 → 检查”，选第一条提示，点“定位问题”回到相关位置。
看“说明与下一步”；需要细节时再展开“原始日志”。“错误”页则可以双击一行定位。</p>
<!-- illustration -->
<p>有“查看修复…”按钮时，先看准备修改的代码。只有点“应用修改”才会写入文稿，之后可以撤销。</p>
<h3>几个常见情况</h3>
<p><b>找不到 LaTeX</b>：点“检查环境”，按提示配置工具，重启 ICSTeX 后继续练习。软件不会自动安装 MacTeX、TeX Live 或 MiKTeX。<br>
<b>中文或字体报错</b>：中文模板使用 XeLaTeX。已有文稿可以从“编译”菜单选择 XeLaTeX 再试。<br>
<b>找不到图片</b>：检查文件名和相对路径；图片移走或改名后，引用也要相应修改。<br>
<b>命令不认识</b>：先检查拼写，再确认是否缺少相应宏包。</p>
<p>编译失败时，旧 PDF 可能还在，但它不是本次结果。修正后重新编译，看到最新状态再导出。</p>
"""),
    ("导出与分享", "export-pdf.png", "真实导出完成后的状态条：“已同步”表示本次导出成功，点“打开位置”找到文件。", r"""
<h2>把 PDF 存到你选的位置</h2>
<ol><li>点顶部<b>“导出 PDF”</b>。</li>
<li>选位置和文件名，点<b>“更新并导出”</b>，等待完成。</li></ol>
<p>PDF 下方显示<b>“已同步”</b>后，点<b>“打开位置”</b>找文件。取消选址或导出失败都不算完成。</p>
<!-- illustration -->
<h3>以后还要反复导出吗？</h3>
<p>成功导出一次后，<b>每次正式编译成功</b>会自动更新这个文件；快速预览和失败编译不会更新。
已有与当前内容一致的正式 PDF 时，不重复编译；只有快速预览时，导出会先生成正式 PDF。</p>
<p>想换地方保存，点“换位置…”；想把这一份留作固定版本，点“停止更新”，
或“文件 → 停止自动更新导出 PDF”。目标文件被其他软件改过时，程序会暂停更新，不静默覆盖。</p>
<p>“待正式编译确认”表示还没核对本次打开的内容；“更新失败”表示要先处理提示。
不要只看是否记住了保存位置。</p>
<h3>发 PDF，还是换电脑继续写？</h3>
<p><b>只发排版结果：</b>发送刚导出的 PDF。<br>
<b>换设备继续改稿：</b>用“文件 → 导出为工程文件…”按提示打包；另一台电脑仍需 ICSTeX 和 LaTeX 环境。<br>
<b>要检查报告或固定交付记录：</b>再用高级“文件 → 准备提交”；Block 项目也走这里。</p>
<p>文件都留在本机，软件不会替你上传或发送。</p>
"""),
)


def illustrated_page(body: str, filename: str, caption: str) -> str:
    image = asset_path(f"user-guide/{filename}")
    if image.is_file():
        url = escape(image.as_uri(), quote=True)
        picture = f'<p><a href="{url}"><img src="{url}" width="560" alt="{escape(caption)}"></a></p>'
        picture += f"<p><small>{escape(caption)} 点击图片可放大查看。</small></p>"
    else:
        picture = "<p><small>本机未找到图示，以上文字步骤仍可使用。</small></p>"
    return body.replace("<!-- illustration -->", picture) if "<!-- illustration -->" in body else body + picture


class UserGuideDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("新手导引")
        self.resize(820, 720)
        self.setMinimumSize(660, 460)
        self.example_root: Path | None = None
        layout = QVBoxLayout(self)
        title = QLabel("做出一份可以发出去的 PDF")
        title.setObjectName("dialogTitle")
        title.setWordWrap(True)
        layout.addWidget(title)
        intro = QLabel("用独立副本走一遍，不改原稿。也可以只看下面的图文。")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        ready = parent is not None and hasattr(parent, "app_settings")
        if ready:
            from app.gui.tutorial_controller import remembered_example
            self.example_root = remembered_example(parent)
        self.start_button = QPushButton("继续上次练习" if self.example_root else "开始练习（独立副本）")
        self.start_button.setObjectName("primaryButton")
        self.start_button.setStyleSheet(PRIMARY_BUTTON_STATE_STYLE)
        self.start_button.setAutoDefault(False)
        self.start_button.setEnabled(ready)
        self.start_button.clicked.connect(self.accept)
        self.new_button = QPushButton("另建一个练习副本")
        self.new_button.setAutoDefault(False)
        self.new_button.setVisible(self.example_root is not None)
        self.new_button.clicked.connect(self._new_example)
        actions = ButtonFlowLayout()
        actions.addWidget(self.start_button)
        actions.addWidget(self.new_button)
        layout.addLayout(actions)
        self.pages = QTabWidget()
        self.pages.tabBar().setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._illustrations = {asset_path(f"user-guide/{item[1]}") for item in GUIDE_PAGES}
        scale = getattr(getattr(QApplication.instance(), "ui_scale_manager", None), "scale", 1.0)
        for name, image, caption, body in GUIDE_PAGES:
            browser = QTextBrowser()
            browser.setStyleSheet(f"font-size: {round(15 * scale)}px;")
            browser.setOpenLinks(False)
            browser.setOpenExternalLinks(False)
            browser.anchorClicked.connect(self._open_illustration)
            browser.setHtml(illustrated_page(body, image, caption))
            self.pages.addTab(browser, name)
        layout.addWidget(self.pages)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("关闭")
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _new_example(self) -> None:
        self.example_root = None
        self.accept()

    def _open_illustration(self, url: QUrl) -> None:
        if url.isLocalFile() and Path(url.toLocalFile()) in self._illustrations:
            if not QDesktopServices.openUrl(url):
                QMessageBox.information(self, "图片没有打开", "系统没有打开图片。你仍可以在教程中查看这张图。")
