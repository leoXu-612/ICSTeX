"use strict";

(function () {
  const config = window.ICSTEX_SITE_CONFIG;
  const releasePath = "release.json";

  function setText(selector, value) {
    document.querySelectorAll(selector).forEach((node) => { node.textContent = value; });
  }

  function setLink(selector, href) {
    document.querySelectorAll(selector).forEach((node) => { node.href = href; });
  }

  function disableDownloadLinks() {
    document.querySelectorAll("[data-release-download]").forEach((node) => {
      node.classList.add("is-disabled");
      node.setAttribute("aria-disabled", "true");
      node.removeAttribute("href");
    });
  }

  function bindDocuments(release) {
    document.querySelectorAll("[data-release-document]").forEach((node) => {
      const name = node.dataset.releaseDocument;
      node.href = `${config.githubBaseUrl}/${release.repository}/blob/${release.tag}/release/${encodeURIComponent(name)}`;
    });
  }

  function bindRelease(release) {
    setText("[data-release='version']", release.version);
    setText("[data-release='tag']", release.tag);
    setText("[data-release='channel']", release.channel);
    setLink("[data-release-link='repository']", `${config.githubBaseUrl}/${release.repository}`);
    setLink("[data-release-link='releases']", release.releases_url);
    setLink("[data-release-link='limitations']", `${config.githubBaseUrl}/${release.repository}/blob/${release.tag}/release/KNOWN_LIMITATIONS.md`);
    setLink("[data-release-link='architecture']", `${config.githubBaseUrl}/${release.repository}/blob/${release.tag}/docs/DECISION_LOG.md`);
    bindDocuments(release);

    const limitationList = document.querySelector("[data-release-limitations]");
    if (limitationList) {
      limitationList.replaceChildren(...release.limitations.map((item) => {
        const element = document.createElement("li");
        element.textContent = item;
        return element;
      }));
    }

    const availability = document.querySelector("[data-release-availability]");
    const macosPrimary = release.assets.find((asset) => (
      asset.primary_download && asset.platform === "macOS" && asset.kind === "DMG"
    ));
    if (!release.github_release_published) {
      disableDownloadLinks();
      if (availability) availability.textContent = "Release 尚未在 GitHub 发布；下载链接会在校验后的发布完成后启用。";
      return;
    }

    document.querySelectorAll("[data-release-download]").forEach((node) => {
      if (node.dataset.releaseDownload !== "macos-primary" || !macosPrimary) return;
      node.href = macosPrimary.download_url;
      node.classList.remove("is-disabled");
      node.removeAttribute("aria-disabled");
    });
    if (availability) availability.textContent = "Release 资产由 GitHub Releases 托管；下载前请核对 SHA-256。";
  }

  fetch(releasePath, { cache: "no-store" })
    .then((response) => {
      if (!response.ok) throw new Error(`Unable to load ${releasePath}`);
      return response.json();
    })
    .then(bindRelease)
    .catch(() => {
      disableDownloadLinks();
      const availability = document.querySelector("[data-release-availability]");
      if (availability) availability.textContent = "Release 元数据暂不可用；请前往 GitHub Releases 核对当前状态。";
    });
})();
