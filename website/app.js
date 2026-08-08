"use strict";

(function () {
  const config = window.ICSTEX_SITE_CONFIG;
  const releasePath = "release.json";

  function setText(selector, value) {
    document.querySelectorAll(selector).forEach((node) => { node.textContent = value; });
  }

  function setLink(selector, href) {
    document.querySelectorAll(selector).forEach((node) => {
      node.href = href;
      node.classList.remove("is-disabled");
      node.removeAttribute("aria-disabled");
      node.removeAttribute("title");
    });
  }

  function disableLinks(selector, reason) {
    document.querySelectorAll(selector).forEach((node) => {
      node.classList.add("is-disabled");
      node.setAttribute("aria-disabled", "true");
      node.removeAttribute("href");
      node.title = reason;
    });
  }

  function assetForKey(release, key) {
    const matches = {
      "macos-primary": (asset) => asset.primary_download && asset.platform === "macOS" && asset.kind === "DMG",
      "macos-dmg": (asset) => asset.platform === "macOS" && asset.kind === "DMG",
      "macos-zip": (asset) => asset.platform === "macOS" && asset.kind === "ZIP",
      "windows-arm64": (asset) => asset.platform === "Windows" && asset.architecture.includes("ARM64")
    };
    return release.assets.find(matches[key] || (() => false));
  }

  function bindAssets(release, downloadsAvailable, unavailableReason) {
    document.querySelectorAll("[data-release-sha]").forEach((node) => {
      const asset = assetForKey(release, node.dataset.releaseSha);
      node.textContent = asset ? `SHA-256 ${asset.sha256}` : "SHA-256 unavailable";
    });
    document.querySelectorAll("[data-release-download]").forEach((node) => {
      const asset = assetForKey(release, node.dataset.releaseDownload);
      if (!downloadsAvailable || !asset) return;
      setLink(`[data-release-download="${node.dataset.releaseDownload}"]`, asset.download_url);
    });
    if (!downloadsAvailable) disableLinks("[data-release-download]", unavailableReason);
  }

  function bindDocuments(release, ref) {
    document.querySelectorAll("[data-release-document]").forEach((node) => {
      const name = node.dataset.releaseDocument;
      setLink(`[data-release-document="${name}"]`, `${config.githubBaseUrl}/${release.repository}/blob/${ref}/release/${encodeURIComponent(name)}`);
    });
  }

  function setupPlatformPicker() {
    const tabs = Array.from(document.querySelectorAll("[data-platform-tab]"));
    const panels = Array.from(document.querySelectorAll("[data-platform-panel]"));
    if (!tabs.length || !panels.length) return;

    function activate(platform, updateHash) {
      tabs.forEach((tab) => {
        const selected = tab.dataset.platformTab === platform;
        tab.setAttribute("aria-selected", String(selected));
        tab.tabIndex = selected ? 0 : -1;
      });
      panels.forEach((panel) => { panel.hidden = panel.dataset.platformPanel !== platform; });
      if (updateHash) history.replaceState(null, "", `#panel-${platform}`);
    }

    tabs.forEach((tab, index) => {
      tab.addEventListener("click", () => activate(tab.dataset.platformTab, true));
      tab.addEventListener("keydown", (event) => {
        const keys = { ArrowLeft: -1, ArrowRight: 1, Home: -index, End: tabs.length - 1 - index };
        if (!(event.key in keys)) return;
        event.preventDefault();
        const next = tabs[(index + keys[event.key] + tabs.length) % tabs.length];
        activate(next.dataset.platformTab, true);
        next.focus();
      });
    });
    const requested = location.hash === "#panel-windows" ? "windows" : "macos";
    activate(requested, false);
    window.addEventListener("hashchange", () => {
      if (location.hash === "#panel-windows") activate("windows", false);
      else if (location.hash === "#panel-macos") activate("macos", false);
    });
  }

  function bindRelease(release) {
    setText("[data-release='version']", release.version);
    setText("[data-release='tag']", release.tag);
    setText("[data-release='channel']", release.channel);
    setText("[data-release='name']", release.release_name);
    const repositoryPublic = release.github_repository_public === true;
    const releasePublished = release.github_release_published === true;
    const downloadsAvailable = repositoryPublic && releasePublished;
    const documentRef = releasePublished ? release.tag : config.repositoryDefaultBranch;
    const privateReason = "GitHub 仓库当前为 Private，公开链接尚未开放";

    if (repositoryPublic) {
      setLink("[data-release-link='repository']", `${config.githubBaseUrl}/${release.repository}`);
      setLink("[data-release-link='releases']", release.releases_url);
      setLink("[data-release-link='limitations']", `${config.githubBaseUrl}/${release.repository}/blob/${documentRef}/release/KNOWN_LIMITATIONS.md`);
      setLink("[data-release-link='architecture']", `${config.githubBaseUrl}/${release.repository}/blob/${documentRef}/docs/DECISION_LOG.md`);
      bindDocuments(release, documentRef);
    } else {
      disableLinks("[data-release-link], [data-release-document]", privateReason);
    }

    const limitationList = document.querySelector("[data-release-limitations]");
    if (limitationList) {
      limitationList.replaceChildren(...release.limitations.map((item) => {
        const element = document.createElement("li");
        element.textContent = item;
        return element;
      }));
    }

    const availability = document.querySelector("[data-release-availability]");
    const unavailableReason = repositoryPublic
      ? "GitHub Release 尚未发布，下载链接尚未开放"
      : "GitHub 仓库当前为 Private，公开下载尚未开放";
    bindAssets(release, downloadsAvailable, unavailableReason);
    if (availability && !repositoryPublic) availability.textContent = "GitHub 仓库当前为 Private；为避免 404，下载入口在公开 Release 完成前保持关闭。";
    else if (availability && !releasePublished) availability.textContent = "Release 尚未在 GitHub 发布；下载链接会在校验后的发布完成后启用。";
    else if (availability) availability.textContent = "Release 资产由 GitHub Releases 托管；下载前请核对 SHA-256。";
  }

  setupPlatformPicker();
  fetch(releasePath, { cache: "no-store" })
    .then((response) => {
      if (!response.ok) throw new Error(`Unable to load ${releasePath}`);
      return response.json();
    })
    .then(bindRelease)
    .catch(() => {
      disableLinks("[data-release-download]", "Release 元数据暂不可用");
      const availability = document.querySelector("[data-release-availability]");
      if (availability) availability.textContent = "Release 元数据暂不可用；请前往 GitHub Releases 核对当前状态。";
    });
})();
