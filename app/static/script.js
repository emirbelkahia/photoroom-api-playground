const imageInput = document.getElementById("imageInput");
const fileLabel = document.getElementById("fileLabel");
const processBtn = document.getElementById("processBtn");
const downloadBtn = document.getElementById("downloadBtn");
const statusLine = document.getElementById("statusLine");
const compareStage = document.getElementById("compareStage");
const beforeLayer = document.getElementById("beforeLayer");
const compareLine = document.getElementById("compareLine");
const compareSlider = document.getElementById("compareSlider");
const beforeImage = document.getElementById("beforeImage");
const afterImage = document.getElementById("afterImage");

const modeTabRemove = document.getElementById("modeTabRemove");
const modeTabAdvanced = document.getElementById("modeTabAdvanced");
const removeBgView = document.getElementById("removeBgView");
const advancedView = document.getElementById("advancedView");

const advancedImageInput = document.getElementById("advancedImageInput");
const advancedFileLabel = document.getElementById("advancedFileLabel");
const advancedBackgroundPalette = document.getElementById("advancedBackgroundPalette");
const advancedBackgroundSwatches = Array.from(document.querySelectorAll(".swatch-chip"));
const advancedBackgroundColorValue = document.getElementById("advancedBackgroundColorValue");
const advancedProcessBtn = document.getElementById("advancedProcessBtn");
const advancedDownloadBtn = document.getElementById("advancedDownloadBtn");
const advancedStatusLine = document.getElementById("advancedStatusLine");
const advancedResultsStage = document.getElementById("advancedResultsStage");
const advancedGeneratingPlaceholder = document.getElementById("advancedGeneratingPlaceholder");
const advancedBeforeImage = document.getElementById("advancedBeforeImage");
const advancedOutputImage = document.getElementById("advancedOutputImage");
const advancedOutputPrevBtn = document.getElementById("advancedOutputPrevBtn");
const advancedOutputNextBtn = document.getElementById("advancedOutputNextBtn");
const advancedOutputLabel = document.getElementById("advancedOutputLabel");

const sidePanelRemove = document.getElementById("sidePanelRemove");
const sidePanelAdvanced = document.getElementById("sidePanelAdvanced");

const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
const REMOVE_FILE_HINT = "PNG, JPG, WEBP, HEIC/HEIF up to 10 MB";
const ADVANCED_FILE_HINT = "PNG, JPG, WEBP up to 10 MB (HEIC/HEIF only in Remove mode)";

let selectedFile = null;
let originalPreviewUrl = null;
let processedPreviewUrl = null;

let advancedSelectedFile = null;
let advancedOriginalPreviewUrl = null;
let advancedOutputVariants = [];
let advancedOutputIndex = 0;
let selectedAdvancedBackgroundColor = "FFFFFF";

function isSupportedImageFile(file) {
  const type = (file.type || "").toLowerCase();
  if (type.startsWith("image/")) {
    return true;
  }
  const name = (file.name || "").toLowerCase();
  return name.endsWith(".heic") || name.endsWith(".heif");
}

function isHeicFile(file) {
  const type = (file.type || "").toLowerCase();
  if (type === "image/heic" || type === "image/heif" || type === "image/heic-sequence" || type === "image/heif-sequence") {
    return true;
  }
  const name = (file.name || "").toLowerCase();
  return name.endsWith(".heic") || name.endsWith(".heif");
}

function setStatus(type, message) {
  statusLine.textContent = message;
  statusLine.className = `status status-${type}`;
}

function setAdvancedStatus(type, message) {
  advancedStatusLine.textContent = message;
  advancedStatusLine.className = `status status-${type}`;
}

function resetDownloadState() {
  downloadBtn.classList.add("is-disabled");
  downloadBtn.removeAttribute("href");
}

function resetAdvancedDownloadState() {
  advancedDownloadBtn.classList.add("is-disabled");
  advancedDownloadBtn.removeAttribute("href");
}

function releasePreviewUrls() {
  if (originalPreviewUrl) {
    URL.revokeObjectURL(originalPreviewUrl);
    originalPreviewUrl = null;
  }
  if (processedPreviewUrl) {
    URL.revokeObjectURL(processedPreviewUrl);
    processedPreviewUrl = null;
  }
}

function releaseAdvancedPreviewUrls() {
  if (advancedOriginalPreviewUrl) {
    URL.revokeObjectURL(advancedOriginalPreviewUrl);
    advancedOriginalPreviewUrl = null;
  }
  for (const variant of advancedOutputVariants) {
    URL.revokeObjectURL(variant.url);
  }
  advancedOutputVariants = [];
  advancedOutputIndex = 0;
}

function updateSliderPosition(value) {
  const rightClip = 100 - Number(value);
  const clipValue = `inset(0 ${rightClip}% 0 0)`;
  beforeLayer.style.clipPath = clipValue;
  beforeLayer.style.webkitClipPath = clipValue;
  compareLine.style.left = `${value}%`;
}

function showComparison(beforeSrc, afterSrc) {
  beforeImage.src = beforeSrc;
  afterImage.src = afterSrc;
  compareStage.hidden = false;
  compareSlider.value = "50";
  updateSliderPosition(50);
}

function setAdvancedGeneratingState(isGenerating) {
  advancedGeneratingPlaceholder.hidden = !isGenerating;
  if (isGenerating) {
    advancedOutputImage.removeAttribute("src");
  }
}

function renderAdvancedOutputCarousel() {
  if (!advancedOutputVariants.length) {
    advancedOutputImage.removeAttribute("src");
    advancedOutputLabel.textContent = "No output yet";
    advancedOutputPrevBtn.disabled = true;
    advancedOutputNextBtn.disabled = true;
    resetAdvancedDownloadState();
    return;
  }

  const current = advancedOutputVariants[advancedOutputIndex];
  advancedOutputImage.src = current.url;
  advancedOutputLabel.textContent = `${current.label} (${advancedOutputIndex + 1}/${advancedOutputVariants.length})`;
  advancedOutputPrevBtn.disabled = advancedOutputVariants.length < 2;
  advancedOutputNextBtn.disabled = advancedOutputVariants.length < 2;
  advancedDownloadBtn.href = current.url;
  advancedDownloadBtn.download = current.downloadName;
  advancedDownloadBtn.classList.remove("is-disabled");
}

function showAdvancedInputOnly(beforeSrc) {
  advancedBeforeImage.src = beforeSrc;
  advancedResultsStage.hidden = false;
  renderAdvancedOutputCarousel();
}

function setMode(mode) {
  const isRemoveMode = mode === "remove";
  const isAdvancedMode = mode === "advanced";

  modeTabRemove.classList.toggle("is-active", isRemoveMode);
  modeTabAdvanced.classList.toggle("is-active", isAdvancedMode);
  modeTabRemove.setAttribute("aria-selected", String(isRemoveMode));
  modeTabAdvanced.setAttribute("aria-selected", String(isAdvancedMode));

  removeBgView.hidden = !isRemoveMode;
  advancedView.hidden = !isAdvancedMode;
  sidePanelRemove.hidden = !isRemoveMode;
  sidePanelAdvanced.hidden = !isAdvancedMode;
}

async function parseErrorResponse(response) {
  let message = `Request failed with status ${response.status}.`;
  try {
    const errorPayload = await response.json();
    if (errorPayload.message) {
      message = errorPayload.message;
    }
    if (errorPayload.detail) {
      const detail = String(errorPayload.detail).replace(/\s+/g, " ").trim();
      if (detail) {
        message = `${message} Detail: ${detail}`;
      }
    }
  } catch (_error) {
    // Keep default message.
  }
  return message;
}

async function runBackgroundRemoval() {
  if (!selectedFile) {
    setStatus("error", "Select an image first.");
    return;
  }

  const payload = new FormData();
  payload.append("image_file", selectedFile, selectedFile.name);

  processBtn.disabled = true;
  setStatus("loading", "Processing image with Photoroom API...");

  try {
    const response = await fetch("/api/remove-bg", {
      method: "POST",
      body: payload,
    });

    if (!response.ok) {
      throw new Error(await parseErrorResponse(response));
    }

    const processedBlob = await response.blob();
    if (processedPreviewUrl) {
      URL.revokeObjectURL(processedPreviewUrl);
    }
    processedPreviewUrl = URL.createObjectURL(processedBlob);

    showComparison(originalPreviewUrl, processedPreviewUrl);
    downloadBtn.href = processedPreviewUrl;
    downloadBtn.classList.remove("is-disabled");
    setStatus("success", "Done. Drag the slider to compare before vs after.");
  } catch (error) {
    setStatus("error", error.message || "Unexpected error while processing the image.");
  } finally {
    processBtn.disabled = false;
  }
}

async function runAdvancedVariant(outputVariant) {
  const payload = new FormData();
  payload.append("image_file", advancedSelectedFile, advancedSelectedFile.name);
  payload.append("output_variant", outputVariant);
  if (outputVariant === "ghost_mannequin") {
    payload.append("background_color", selectedAdvancedBackgroundColor);
  }

  const response = await fetch("/api/advanced-edit", {
    method: "POST",
    body: payload,
  });

  if (!response.ok) {
    throw new Error(await parseErrorResponse(response));
  }

  return await response.blob();
}

async function runAdvancedEdit() {
  if (!advancedSelectedFile) {
    setAdvancedStatus("error", "Select an image first.");
    return;
  }

  advancedProcessBtn.disabled = true;
  setAdvancedGeneratingState(true);
  setAdvancedStatus("loading", "Generating output 1/2: Ghost Mannequin...");

  try {
    releaseAdvancedOutputVariants();

    const ghostBlob = await runAdvancedVariant("ghost_mannequin");
    const ghostUrl = URL.createObjectURL(ghostBlob);

    setAdvancedStatus("loading", "Generating output 2/2: Lifestyle staging...");
    const lifestyleBlob = await runAdvancedVariant("lifestyle_staging");
    const lifestyleUrl = URL.createObjectURL(lifestyleBlob);

    advancedOutputVariants = [
      {
        label: "Ghost mannequin",
        url: ghostUrl,
        downloadName: "image-ghost-mannequin.png",
      },
      {
        label: "Lifestyle staging",
        url: lifestyleUrl,
        downloadName: "image-lifestyle-staging.png",
      },
    ];

    advancedOutputIndex = 0;
    renderAdvancedOutputCarousel();
    setAdvancedStatus("success", "Done. Use the output carousel to compare both generated visuals.");
  } catch (error) {
    setAdvancedStatus("error", error.message || "Unexpected error while running advanced generation.");
  } finally {
    setAdvancedGeneratingState(false);
    advancedProcessBtn.disabled = false;
  }
}

function releaseAdvancedOutputVariants() {
  for (const variant of advancedOutputVariants) {
    URL.revokeObjectURL(variant.url);
  }
  advancedOutputVariants = [];
  advancedOutputIndex = 0;
}

imageInput.addEventListener("change", () => {
  const file = imageInput.files && imageInput.files[0];
  if (!file) {
    selectedFile = null;
    fileLabel.textContent = REMOVE_FILE_HINT;
    processBtn.disabled = true;
    setStatus("neutral", "Upload an image to start.");
    return;
  }

  if (!isSupportedImageFile(file)) {
    selectedFile = null;
    processBtn.disabled = true;
    setStatus("error", "Only image files are supported (including HEIC/HEIF).");
    return;
  }

  if (file.size > MAX_UPLOAD_BYTES) {
    selectedFile = null;
    processBtn.disabled = true;
    setStatus("error", "Image is too large. Maximum is 10 MB.");
    return;
  }

  selectedFile = file;
  fileLabel.textContent = `${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)`;
  processBtn.disabled = false;
  resetDownloadState();

  if (originalPreviewUrl) {
    URL.revokeObjectURL(originalPreviewUrl);
  }
  if (processedPreviewUrl) {
    URL.revokeObjectURL(processedPreviewUrl);
    processedPreviewUrl = null;
  }

  originalPreviewUrl = URL.createObjectURL(file);
  showComparison(originalPreviewUrl, originalPreviewUrl);
  setStatus("neutral", "Image ready. Click Remove background.");
});

advancedImageInput.addEventListener("change", () => {
  const file = advancedImageInput.files && advancedImageInput.files[0];
  if (!file) {
    advancedSelectedFile = null;
    advancedFileLabel.textContent = ADVANCED_FILE_HINT;
    advancedProcessBtn.disabled = true;
    advancedResultsStage.hidden = true;
    advancedBeforeImage.removeAttribute("src");
    advancedOutputImage.removeAttribute("src");
    setAdvancedGeneratingState(false);
    releaseAdvancedOutputVariants();
    setAdvancedStatus("neutral", "Upload a clothing image to generate both outputs.");
    return;
  }

  if (isHeicFile(file)) {
    advancedSelectedFile = null;
    advancedProcessBtn.disabled = true;
    advancedResultsStage.hidden = true;
    setAdvancedGeneratingState(false);
    releaseAdvancedOutputVariants();
    setAdvancedStatus("error", "HEIC/HEIF is supported in Remove mode but not in Advanced mode. Please use PNG, JPG or WEBP.");
    return;
  }

  if (!isSupportedImageFile(file)) {
    advancedSelectedFile = null;
    advancedProcessBtn.disabled = true;
    advancedResultsStage.hidden = true;
    setAdvancedGeneratingState(false);
    releaseAdvancedOutputVariants();
    setAdvancedStatus("error", "Only image files are supported.");
    return;
  }

  if (file.size > MAX_UPLOAD_BYTES) {
    advancedSelectedFile = null;
    advancedProcessBtn.disabled = true;
    advancedResultsStage.hidden = true;
    setAdvancedGeneratingState(false);
    releaseAdvancedOutputVariants();
    setAdvancedStatus("error", "Image is too large. Maximum is 10 MB.");
    return;
  }

  advancedSelectedFile = file;
  advancedFileLabel.textContent = `${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)`;
  advancedProcessBtn.disabled = false;
  resetAdvancedDownloadState();

  if (advancedOriginalPreviewUrl) {
    URL.revokeObjectURL(advancedOriginalPreviewUrl);
  }
  releaseAdvancedOutputVariants();

  advancedOriginalPreviewUrl = URL.createObjectURL(file);
  showAdvancedInputOnly(advancedOriginalPreviewUrl);
  setAdvancedGeneratingState(false);
  setAdvancedStatus("neutral", "Image ready. Click Generate to create two outputs.");
});

advancedBackgroundPalette.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) {
    return;
  }
  const swatch = target.closest(".swatch-chip");
  if (!swatch) {
    return;
  }

  const color = (swatch.dataset.color || "").toUpperCase();
  if (!color) {
    return;
  }

  selectedAdvancedBackgroundColor = color;
  advancedBackgroundColorValue.textContent = `#${color}`;

  for (const button of advancedBackgroundSwatches) {
    const isActive = button === swatch;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-checked", String(isActive));
  }
});

advancedOutputPrevBtn.addEventListener("click", () => {
  if (advancedOutputVariants.length < 2) {
    return;
  }
  advancedOutputIndex = (advancedOutputIndex - 1 + advancedOutputVariants.length) % advancedOutputVariants.length;
  renderAdvancedOutputCarousel();
});

advancedOutputNextBtn.addEventListener("click", () => {
  if (advancedOutputVariants.length < 2) {
    return;
  }
  advancedOutputIndex = (advancedOutputIndex + 1) % advancedOutputVariants.length;
  renderAdvancedOutputCarousel();
});

processBtn.addEventListener("click", runBackgroundRemoval);
advancedProcessBtn.addEventListener("click", runAdvancedEdit);

compareSlider.addEventListener("input", (event) => {
  updateSliderPosition(event.target.value);
});

modeTabRemove.addEventListener("click", () => {
  setMode("remove");
});

modeTabAdvanced.addEventListener("click", () => {
  setMode("advanced");
});

setMode("remove");

window.addEventListener("beforeunload", () => {
  releasePreviewUrls();
  releaseAdvancedPreviewUrls();
});
