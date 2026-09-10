"""Wire every QAction/QWidget signal in MainWindow to its slot.

Same shape as ``build_actions`` / ``build_ui``: mutates the window in place.
Pulled out so the connection topology lives in one auditable file.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from app.core.compiler import BuildPurpose
from app.gui.project_profile_dialog import show_project_profile

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.gui.main_window import MainWindow


def connect_signals(window: "MainWindow") -> None:
    # File / project actions
    window.new_project_action.triggered.connect(window.new_project)
    window.project_profile_action.triggered.connect(lambda: show_project_profile(window))
    window.new_action.triggered.connect(window.new_document)
    window.open_file_action.triggered.connect(window.open_file_dialog)
    window.open_folder_action.triggered.connect(window.open_folder_dialog)
    window.save_action.triggered.connect(window.save_current)
    window.save_as_action.triggered.connect(window.save_current_as)
    window.export_pdf_action.triggered.connect(window.export_pdf)
    window.reveal_pdf_action.triggered.connect(window.reveal_pdf)
    window.new_window_action.triggered.connect(window.spawn_window)

    # Compile actions
    window.compile_action.triggered.connect(
        lambda _checked=False: window.compile_current(
            immediate=True,
            show_missing_warning=True,
            purpose=BuildPurpose.FINAL,
        )
    )
    window.stop_compile_action.triggered.connect(window.stop_compile_current)
    window.clean_build_action.triggered.connect(window.clean_build_cache)
    window.full_rebuild_action.triggered.connect(window.full_rebuild_current)
    window.health_check_action.triggered.connect(
        lambda _checked=False: window.run_project_check(switch_to_panel=True)
    )
    window.submission_check_action.triggered.connect(window.readiness.show)
    window.submission_panel.refreshRequested.connect(window.readiness.request)
    window.submission_panel.cancelRequested.connect(window.readiness.cancel)
    window.submission_panel.actionRequested.connect(window.readiness.act)
    window.signals.external_changed.connect(window.readiness.external_changed)
    window.signals.started.connect(window.readiness.build_started)
    window.signals.finished.connect(window.readiness.build_finished)
    window.editor_tabs.currentChanged.connect(window.readiness.invalidate)
    window.engine_selector.currentIndexChanged.connect(window.readiness.invalidate)
    window.environment_doctor_action.triggered.connect(window.show_environment_doctor)
    window.feedback_bundle_action.triggered.connect(window.copy_feedback_bundle)
    window.import_perf_action.triggered.connect(window.show_import_perf_dialog)
    window.block_project_action.triggered.connect(window.show_block_project_dialog)
    window.user_guide_action.triggered.connect(window.show_user_guide)
    window.word_count_action.triggered.connect(lambda: window.update_word_count(force=True))
    window.sync_pdf_action.triggered.connect(window.sync_current_source_to_pdf)
    window.engine_selector.currentIndexChanged.connect(window.on_engine_selector_changed)

    # Toolbox / auto-compile toggles
    window.toolbox_action.toggled.connect(window.set_toolbox_visible)
    window.toolbox_dock.visibilityChanged.connect(window.sync_toolbox_action)
    window.toolbox_dock.visibilityChanged.connect(window.project_panels.refresh_visible)
    window.sidebar_tabs.currentChanged.connect(window.project_panels.refresh_visible)
    window.auto_compile_action.toggled.connect(window.sync_auto_compile_toggle)
    window.auto_compile_action.toggled.connect(window._persist_preferences_from_ui)
    window.auto_compile_toggle.toggled.connect(window.sync_auto_compile_action)

    # Settings / find / replace
    window.settings_action.triggered.connect(window.show_settings_dialog)
    window.find_action.triggered.connect(window.show_find_bar)
    window.replace_action.triggered.connect(window.show_replace_bar)
    window.formula_composer_action.triggered.connect(window.open_formula_composer)

    # Editor tab life cycle
    window.editor_tabs.tabCloseRequested.connect(window.close_tab)
    window.editor_tabs.currentChanged.connect(window.on_current_tab_changed)
    window.tree.doubleClicked.connect(window.open_tree_item)
    window.tree.customContextMenuRequested.connect(window.show_file_tree_context_menu)
    window.error_table.cellDoubleClicked.connect(window.jump_to_error)

    # Compile signals + PDF
    window.signals.external_changed.connect(window.reload_external_change)
    window.signals.started.connect(window.on_compile_started)
    window.signals.finished.connect(window.on_compile_finished)
    window.pdf_panel.sourceRequested.connect(window.sync_pdf_to_source)
    window.pdf_panel.export_pdf_button.clicked.connect(window.export_pdf)
    window.pdf_panel.reveal_pdf_button.clicked.connect(window.reveal_pdf)

    # Welcome page entry points
    window.welcome_page.newProjectRequested.connect(window.new_project)
    window.welcome_page.openFileRequested.connect(window.open_file_dialog)
    window.welcome_page.openFolderRequested.connect(window.open_folder_dialog)
    window.welcome_page.guideRequested.connect(window.show_user_guide)
    window.welcome_page.recentProjectRequested.connect(
        lambda path: window.open_recent_project(Path(path))
    )

    # Diagnostics panel
    window.diagnostic_panel.refreshRequested.connect(
        lambda: window.run_project_check(switch_to_panel=True)
    )
    window.diagnostic_panel.fixRequested.connect(window.fix_diagnostic)
    window.diagnostic_panel.jumpRequested.connect(window.jump_to_diagnostic)

    # Outline / search / images / history panels
    window.outline_panel.refreshRequested.connect(window.refresh_project_panels)
    window.outline_panel.jumpRequested.connect(window.jump_to_outline)
    window.search_panel.searchRequested.connect(window.run_project_search)
    window.search_panel.jumpRequested.connect(window.jump_to_project_search_result)
    window.images_panel.refreshRequested.connect(window.refresh_project_panels)
    window.images_panel.insertRequested.connect(window.insert_existing_image)
    window.history_panel.refreshRequested.connect(window.refresh_project_panels)
    window.history_panel.restoreRequested.connect(window.restore_history_snapshot)

    # Insert + templates panels
    window.insert_panel.figureRequested.connect(window.insert_figure)
    window.insert_panel.sideBySideFigureRequested.connect(window.insert_side_by_side_figures)
    window.insert_panel.tableRequested.connect(window.insert_table)
    window.insert_panel.hyperlinkRequested.connect(window.insert_hyperlink)
    window.insert_panel.equationRequested.connect(window.open_formula_composer)
    window.insert_panel.listRequested.connect(window.insert_list)
    window.insert_panel.sectionRequested.connect(window.insert_section)
    window.insert_panel.casesRequested.connect(window.insert_cases)
    window.insert_panel.quoteRequested.connect(window.insert_quote)
    window.templates_panel.templateRequested.connect(window.new_document_from_template)
    window.templates_panel.saveCurrentRequested.connect(window.save_current_as_template)
    window.templates_panel.importRequested.connect(window.import_template_dialog)
    window.templates_panel.exportRequested.connect(window.export_template_dialog)

    # Bibliography & labels panels
    window.references_panel.addReferenceRequested.connect(window.add_reference)
    window.references_panel.importReferenceRequested.connect(window.import_reference)
    window.references_panel.refreshRequested.connect(window.refresh_project_panels)
    window.references_panel.citeRequested.connect(window.insert_citation)
    window.references_panel.checkRequested.connect(window.citations.request)
    window.references_panel.cancelCheckRequested.connect(window.citations.cancel)
    window.references_panel.locationRequested.connect(window.citations.navigate)
    window.signals.external_changed.connect(window.citations.external_changed)
    window.editor_tabs.currentChanged.connect(window.citations.invalidate)
    window.block_mode_action.toggled.connect(window.citations.invalidate)
    window.images_panel.checkRequested.connect(window.materials.request)
    window.images_panel.cancelCheckRequested.connect(window.materials.cancel)
    window.images_panel.locationRequested.connect(window.materials.navigate)
    window.images_panel.material_tabs.currentChanged.connect(window.project_panels.refresh_visible)
    window.signals.external_changed.connect(window.materials.external_changed)
    window.editor_tabs.currentChanged.connect(window.materials.invalidate)
    window.block_mode_action.toggled.connect(window.materials.invalidate)
    window.labels_panel.refreshRequested.connect(window.refresh_project_panels)
    window.labels_panel.referenceRequested.connect(window.insert_reference)

    # Editor option toggles
    for action in (
        window.auto_item_action,
        window.auto_environment_action,
        window.auto_pairs_action,
        window.snippets_action,
    ):
        action.toggled.connect(window.apply_editor_options_to_all)
        action.toggled.connect(window._persist_preferences_from_ui)
