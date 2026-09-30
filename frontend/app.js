// Onion Quality AI - Mandi & Procurement Frontend Controller (SIH Edition)

let selectedFile = null;
let currentAnalysisData = null;
let originalImageUrl = null;
let annotatedImageUrl = null;

// DOM Elements - Intake
const fileInput = document.getElementById("fileInput");
const dropZone = document.getElementById("dropZone");
const dropPrompt = document.getElementById("dropPrompt");
const fileChosenInfo = document.getElementById("fileChosenInfo");
const chosenFileName = document.getElementById("chosenFileName");
const btnRemoveFile = document.getElementById("btnRemoveFile");
const thumbCard = document.getElementById("thumbCard");
const thumbImg = document.getElementById("thumbImg");

const standardSelect = document.getElementById("standardSelect");
const standardDesc = document.getElementById("standardDesc");
const btnAnalyze = document.getElementById("btnAnalyze");

// Results Dashboard Elements
const resultsDashboard = document.getElementById("resultsDashboard");
const inspectedStandardName = document.getElementById("inspectedStandardName");

// Top Summary Cards (SIH Quality Summary)
const cardTotalOnions = document.getElementById("cardTotalOnions");
const cardGradeA = document.getElementById("cardGradeA");
const cardGradeASub = document.getElementById("cardGradeASub");
const cardURS = document.getElementById("cardURS");
const cardURSSub = document.getElementById("cardURSSub");
const cardDefective = document.getElementById("cardDefective");
const cardDefectiveSub = document.getElementById("cardDefectiveSub");

// Unconfigured Criteria Alert Box
const unconfiguredCriteriaNotice = document.getElementById("unconfiguredCriteriaNotice");
const unconfiguredCriteriaReason = document.getElementById("unconfiguredCriteriaReason");
const missingRequirementsList = document.getElementById("missingRequirementsList");
const noOnionsAlert = document.getElementById("noOnionsAlert");

// Visible Quality Indicators (Rotten, Sprouted, Damaged, Undersized)
const countRotten = document.getElementById("countRotten");
const rateRotten = document.getElementById("rateRotten");
const countSprout = document.getElementById("countSprout");
const rateSprout = document.getElementById("rateSprout");
const countSplit = document.getElementById("countSplit");
const rateSplit = document.getElementById("rateSplit");
const countUndersized = document.getElementById("countUndersized");
const rateUndersized = document.getElementById("rateUndersized");

// Visual Inspection View
const mainDisplayImg = document.getElementById("mainDisplayImg");
const tabAnnotated = document.getElementById("tabAnnotated");
const tabOriginal = document.getElementById("tabOriginal");
const btnEnlargeImage = document.getElementById("btnEnlargeImage");

// Grading Basis Section
const gradingBasisSection = document.getElementById("gradingBasisSection");
const gradingBasisGrid = document.getElementById("gradingBasisGrid");

// Assessment Basis
const assessmentBasisText = document.getElementById("assessmentBasisText");

// Size Assessment Cards
const countLarge = document.getElementById("countLarge");
const barLarge = document.getElementById("barLarge");
const countMedium = document.getElementById("countMedium");
const barMedium = document.getElementById("barMedium");
const countSmall = document.getElementById("countSmall");
const barSmall = document.getElementById("barSmall");

// Standards Assessment Elements
const stdCardSubtitle = document.getElementById("stdCardSubtitle");
const stdNameVal = document.getElementById("stdNameVal");
const stdStatusVal = document.getElementById("stdStatusVal");
const stdReasonVal = document.getElementById("stdReasonVal");
const criteriaTableBody = document.getElementById("criteriaTableBody");

// Report Modal Elements
const btnOpenReport = document.getElementById("btnOpenReport");
const reportModal = document.getElementById("reportModal");
const btnCloseReport = document.getElementById("btnCloseReport");
const repDateTime = document.getElementById("repDateTime");
const repStandard = document.getElementById("repStandard");
const repTotalAssessed = document.getElementById("repTotalAssessed");
const repImg = document.getElementById("repImg");
const repGradingSection = document.getElementById("repGradingSection");
const repGradingTableBody = document.getElementById("repGradingTableBody");
const repDefectsTableBody = document.getElementById("repDefectsTableBody");
const repReasonText = document.getElementById("repReasonText");
const btnPrintReport = document.getElementById("btnPrintReport");
const btnDownloadJson = document.getElementById("btnDownloadJson");

// Image Modal
const imageModal = document.getElementById("imageModal");
const enlargedImg = document.getElementById("enlargedImg");
const btnCloseImageModal = document.getElementById("btnCloseImageModal");

// Standard Descriptions Map
const standardDescriptions = {
  procurement_trial: "SIH demonstration profile. Configurable visual grading criteria for Grade A and URS classification based on surface defect absence and relative sizing.",
  local_market: "NHB wholesale mandi size tiers (Extra Large, Large, Medium, Small). Decay <= 5%, sprout <= 3%. (Size / visible-defect assessment)",
  nhb_nasik: "National Horticulture Board export standard. Min dia 20mm, decay <= 2%, zero sprouting. (Size / visible-defect assessment)",
  nhb_bangalore: "Export standard for Bangalore Rose specialty onion. Min dia 15mm, decay <= 2%, zero sprouting. (Size / visible-defect assessment)",
  nhb_krishnapuram: "Export standard for Krishnapuram variety. Min dia 15mm, decay <= 2%, zero sprouting. (Size / visible-defect assessment)"
};

// Initialize on DOM load
document.addEventListener("DOMContentLoaded", () => {
  setupEventListeners();
});

function setupEventListeners() {
  // File upload input
  fileInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFileSelected(e.target.files[0]);
    }
  });

  // Drag and drop
  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("dragover");
  });

  dropZone.addEventListener("dragleave", () => {
    dropZone.classList.remove("dragover");
  });

  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("dragover");
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  });

  // Remove file
  btnRemoveFile.addEventListener("click", (e) => {
    e.stopPropagation();
    clearSelectedFile();
  });

  // Sample Lot Buttons
  document.querySelectorAll(".btn-sample").forEach((btn) => {
    btn.addEventListener("click", () => {
      const sample = btn.getAttribute("data-sample");
      loadSample(sample);
    });
  });

  // Standard select description update
  standardSelect.addEventListener("change", (e) => {
    standardDesc.textContent = standardDescriptions[e.target.value] || "";
  });

  // Analyze Action Button
  btnAnalyze.addEventListener("click", runAnalysis);

  // Image tab toggles
  tabAnnotated.addEventListener("click", () => {
    tabAnnotated.classList.add("active");
    tabOriginal.classList.remove("active");
    if (annotatedImageUrl) mainDisplayImg.src = annotatedImageUrl;
  });

  tabOriginal.addEventListener("click", () => {
    tabOriginal.classList.add("active");
    tabAnnotated.classList.remove("active");
    if (originalImageUrl) mainDisplayImg.src = originalImageUrl;
  });

  // Image zoom/enlarge modal
  btnEnlargeImage.addEventListener("click", openImageModal);
  mainDisplayImg.addEventListener("click", openImageModal);
  btnCloseImageModal.addEventListener("click", closeImageModal);
  imageModal.addEventListener("click", (e) => {
    if (e.target === imageModal) closeImageModal();
  });

  // Report Modal
  btnOpenReport.addEventListener("click", openReportModal);
  btnCloseReport.addEventListener("click", closeReportModal);
  reportModal.addEventListener("click", (e) => {
    if (e.target === reportModal) closeReportModal();
  });

  // Print Report
  btnPrintReport.addEventListener("click", () => {
    window.print();
  });

  // Download JSON Data
  btnDownloadJson.addEventListener("click", () => {
    if (!currentAnalysisData) return;
    const blob = new Blob([JSON.stringify(currentAnalysisData, null, 2)], {
      type: "application/json"
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `onion_inspection_report_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  });
}

function handleFileSelected(file) {
  selectedFile = file;
  chosenFileName.textContent = `${file.name} (${(file.size / 1024).toFixed(0)} KB)`;
  dropPrompt.style.display = "none";
  fileChosenInfo.style.display = "flex";

  const reader = new FileReader();
  reader.onload = (e) => {
    originalImageUrl = e.target.result;
    thumbImg.src = originalImageUrl;
    thumbCard.style.display = "block";
  };
  reader.readAsDataURL(file);
}

function clearSelectedFile() {
  selectedFile = null;
  fileInput.value = "";
  dropPrompt.style.display = "block";
  fileChosenInfo.style.display = "none";
  originalImageUrl = null;
  annotatedImageUrl = null;
  currentAnalysisData = null;
  thumbCard.style.display = "none";
  resultsDashboard.style.display = "none";
}

async function loadSample(sampleName) {
  try {
    const res = await fetch(`/samples/${sampleName}`);
    if (!res.ok) throw new Error("Could not load sample lot image");
    const blob = await res.blob();
    const file = new File([blob], sampleName, { type: blob.type || "image/jpeg" });
    handleFileSelected(file);
  } catch (err) {
    alert("Error loading sample: " + err.message);
  }
}

// Run Analysis
async function runAnalysis() {
  if (!selectedFile) {
    alert("Please upload or select an onion lot image first.");
    return;
  }

  // Set loading state
  const btnLabel = btnAnalyze.querySelector(".btn-label");
  const spinner = btnAnalyze.querySelector(".btn-spinner");
  btnLabel.style.display = "none";
  spinner.style.display = "inline-block";
  btnAnalyze.disabled = true;

  const formData = new FormData();
  formData.append("image", selectedFile);
  formData.append("standard", standardSelect.value);
  formData.append("conf_threshold", 0.25);
  formData.append("enhance_image", false);
  formData.append("calibration_enabled", false);

  try {
    const response = await fetch("/analyze", {
      method: "POST",
      body: formData
    });

    if (!response.ok) {
      throw new Error(`Inference error: ${response.status}`);
    }

    const data = await response.json();
    currentAnalysisData = data;
    renderResults(data);
  } catch (err) {
    alert("Unable to analyze this image. Please upload a clear JPG or PNG image and try again.");
    console.error("Analysis error:", err);
  } finally {
    btnLabel.style.display = "inline-flex";
    spinner.style.display = "none";
    btnAnalyze.disabled = false;
  }
}

// Render Results into Dashboard
function renderResults(data) {
  resultsDashboard.style.display = "block";

  const stats = data.lot_statistics;
  const grading = data.grading;

  inspectedStandardName.textContent = `Standard: ${data.assessment.standard_name}`;
  cardTotalOnions.textContent = stats.total_onions;

  // 1. SIH Quality Summary: Grade A, URS, Defective / Reject
  if (stats.total_onions === 0) {
    // Empty detection case (0 onions detected)
    if (noOnionsAlert) noOnionsAlert.style.display = "block";
    unconfiguredCriteriaNotice.style.display = "none";
    gradingBasisSection.style.display = "none";

    cardGradeA.textContent = "0.0%";
    cardGradeASub.textContent = "0 sound bulbs";
    cardURS.textContent = "0.0%";
    cardURSSub.textContent = "0 bulbs";
    cardDefective.textContent = "0.0%";
    cardDefectiveSub.textContent = "0 reject bulbs";

  } else if (grading && grading.is_configured) {
    if (noOnionsAlert) noOnionsAlert.style.display = "none";
    // Criteria configured: show calculated percentages
    unconfiguredCriteriaNotice.style.display = "none";

    cardGradeA.textContent = `${grading.grade_a_percentage.toFixed(1)}%`;
    cardGradeASub.textContent = `${grading.grade_a_count} sound bulb${grading.grade_a_count === 1 ? '' : 's'}`;

    cardURS.textContent = `${grading.urs_percentage.toFixed(1)}%`;
    cardURSSub.textContent = `${grading.urs_count} bulb${grading.urs_count === 1 ? '' : 's'} (URS)`;

    cardDefective.textContent = `${grading.defective_percentage.toFixed(1)}%`;
    cardDefectiveSub.textContent = `${grading.defective_count} reject bulb${grading.defective_count === 1 ? '' : 's'}`;

    // Render Grading Basis Section
    gradingBasisSection.style.display = "block";
    gradingBasisGrid.innerHTML = "";

    const categories = [
      { name: "Grade A", badgeClass: "badge-grade-a", data: grading.categories_breakdown["Grade A"] },
      { name: "URS", badgeClass: "badge-urs", data: grading.categories_breakdown["URS"] },
      { name: "Defective / Reject", badgeClass: "badge-reject", data: grading.categories_breakdown["Defective / Reject"] },
      { name: "Undersized", badgeClass: "badge-under", data: grading.categories_breakdown["Undersized"] }
    ];

    categories.forEach(cat => {
      if (cat.data) {
        const item = document.createElement("div");
        item.className = "grading-basis-item";
        item.innerHTML = `
          <div class="grading-basis-top">
            <span class="grading-basis-badge ${cat.badgeClass}">${cat.name}</span>
            <span class="grading-basis-stat">${cat.data.count} (${cat.data.percentage.toFixed(1)}%)</span>
          </div>
          <p class="grading-basis-crit"><strong>Criteria:</strong> ${cat.data.criteria}</p>
          <span class="grading-basis-obs">Observed: ${cat.data.observed_result}</span>
        `;
        gradingBasisGrid.appendChild(item);
      }
    });

  } else {
    // Criteria not configured for this standard (e.g. standard NHB export rules)
    if (noOnionsAlert) noOnionsAlert.style.display = "none";
    cardGradeA.textContent = "N/A";
    cardGradeASub.textContent = "Criteria unconfigured";

    cardURS.textContent = "N/A";
    cardURSSub.textContent = "Criteria unconfigured";

    cardDefective.textContent = `${stats.defect_indicator_percent.toFixed(1)}%`;
    cardDefectiveSub.textContent = `${stats.defective_onions} defect bulb${stats.defective_onions === 1 ? '' : 's'}`;

    unconfiguredCriteriaNotice.style.display = "block";
    if (unconfiguredCriteriaReason) {
      unconfiguredCriteriaReason.textContent = (grading && grading.unavailability_reason) || "This grading profile does not currently contain Grade A / URS criteria.";
    }
    missingRequirementsList.innerHTML = "";

    const missingItems = (grading && grading.missing_criteria) || [
      "Official procurement tender definition of Grade A vs URS for this standard",
      "Physical diameter calibration in mm (cannot be reliably verified from uncalibrated RGB pixels)",
      "Lot weight data (NAFED/APMC procurement limits are based on weight percentages, not visual image count)"
    ];

    missingItems.forEach(itemText => {
      const li = document.createElement("li");
      li.textContent = itemText;
      missingRequirementsList.appendChild(li);
    });

    gradingBasisSection.style.display = "none";
  }

  // 2. Visible Quality Indicators (Rotten, Sprouted, Damaged, Undersized)
  countRotten.textContent = stats.rotten_count;
  rateRotten.textContent = `${stats.rotten_count} (${stats.decay_indicator_percent.toFixed(1)}%)`;

  countSprout.textContent = stats.sprout_count;
  rateSprout.textContent = `${stats.sprout_count} (${stats.sprout_indicator_percent.toFixed(1)}%)`;

  countSplit.textContent = stats.double_split_count;
  rateSplit.textContent = `${stats.double_split_count} (${stats.double_split_indicator_percent.toFixed(1)}%)`;

  countUndersized.textContent = stats.size_distribution.small;
  rateUndersized.textContent = `${stats.size_distribution.small} (${stats.size_distribution.small_percent.toFixed(1)}%)`;

  // 3. Visual Inspection Image
  if (data.annotated_image) {
    annotatedImageUrl = "data:image/jpeg;base64," + data.annotated_image;
    mainDisplayImg.src = annotatedImageUrl;
    tabAnnotated.classList.add("active");
    tabOriginal.classList.remove("active");
  }

  // 4. Assessment Basis (Transparency statement)
  if (grading && grading.assessment_basis_statement) {
    assessmentBasisText.textContent = grading.assessment_basis_statement;
  }

  // 5. Size Assessment
  const dist = stats.size_distribution;
  countLarge.textContent = `${dist.large} (${dist.large_percent.toFixed(0)}%)`;
  barLarge.style.width = `${dist.large_percent}%`;

  countMedium.textContent = `${dist.medium} (${dist.medium_percent.toFixed(0)}%)`;
  barMedium.style.width = `${dist.medium_percent}%`;

  countSmall.textContent = `${dist.small} (${dist.small_percent.toFixed(0)}%)`;
  barSmall.style.width = `${dist.small_percent}%`;

  // 6. Standards Assessment Card
  stdNameVal.textContent = data.assessment.standard_name;
  stdStatusVal.textContent = data.assessment.assessment_status;
  stdStatusVal.className = "std-status-pill";

  const assessmentStatus = data.assessment.assessment_status;
  if (assessmentStatus.toLowerCase().includes("does not meet")) {
    stdStatusVal.classList.add("pill-fail");
  } else if (assessmentStatus.toLowerCase().includes("meets evaluated")) {
    stdStatusVal.classList.add("pill-pass");
  } else {
    stdStatusVal.classList.add("pill-warn");
  }

  stdReasonVal.textContent = data.assessment.reasons.length > 0
    ? data.assessment.reasons.join(" ")
    : data.assessment.summary;

  // Criteria Table
  criteriaTableBody.innerHTML = "";
  data.assessment.evaluated_criteria.forEach((crit) => {
    const tr = document.createElement("tr");
    const tagClass = crit.status === "PASS"
      ? "tag-pass"
      : (crit.status === "FAIL" ? "tag-fail" : "tag-neutral");

    tr.innerHTML = `
      <td><strong>${crit.criterion}</strong></td>
      <td>${crit.limit}</td>
      <td>${crit.observed}</td>
      <td><span class="tag-status ${tagClass}">${crit.status}</span></td>
    `;
    criteriaTableBody.appendChild(tr);
  });

  // Smooth scroll down to results
  resultsDashboard.scrollIntoView({ behavior: "smooth", block: "start" });
}

// Fullscreen Image Modal
function openImageModal() {
  if (!mainDisplayImg.src) return;
  enlargedImg.src = mainDisplayImg.src;
  imageModal.style.display = "flex";
}

function closeImageModal() {
  imageModal.style.display = "none";
}

// Report Modal
function openReportModal() {
  if (!currentAnalysisData) return;
  const data = currentAnalysisData;
  const stats = data.lot_statistics;
  const grading = data.grading;

  repDateTime.textContent = new Date().toLocaleString();
  repStandard.textContent = data.assessment.standard_name;
  repTotalAssessed.textContent = `${stats.total_onions} bulbs`;
  repImg.src = annotatedImageUrl || originalImageUrl;

  // Report Grading Summary Table
  repGradingTableBody.innerHTML = "";
  if (grading && grading.is_configured) {
    repGradingSection.style.display = "block";
    const categories = [
      { name: "Grade A", count: grading.grade_a_count, pct: grading.grade_a_percentage, crit: "Sound single bulb (Medium or Large size)" },
      { name: "URS", count: grading.urs_count, pct: grading.urs_percentage, crit: "Double/split or Small size (free of rot/sprout)" },
      { name: "Defective / Reject", count: grading.defective_count, pct: grading.defective_percentage, crit: "Visible rot, decay, or sprouting" },
      { name: "Undersized", count: grading.undersized_count, pct: grading.undersized_percentage, crit: "Small approximate image-based size" }
    ];

    categories.forEach(c => {
      const row = document.createElement("tr");
      row.innerHTML = `
        <td><strong>${c.name}</strong></td>
        <td>${c.count}</td>
        <td>${c.pct.toFixed(1)}%</td>
        <td>${c.crit}</td>
      `;
      repGradingTableBody.appendChild(row);
    });
  } else {
    repGradingSection.style.display = "block";
    repGradingTableBody.innerHTML = `
      <tr>
        <td colspan="4" style="color: #92400e; font-style: italic;">
          Grade A / URS calculation unavailable for this standard (criteria not configured in standard specification).
        </td>
      </tr>
    `;
  }

  // Report Visible Quality Indicators Table
  repDefectsTableBody.innerHTML = `
    <tr>
      <td>Visible Rot / Decay</td>
      <td><strong>${stats.rotten_count}</strong></td>
      <td>${stats.decay_indicator_percent.toFixed(1)}%</td>
      <td><span class="tag-status ${stats.rotten_count === 0 ? 'tag-pass' : 'tag-fail'}">${stats.rotten_count === 0 ? 'CLEAN' : 'DETECTED'}</span></td>
    </tr>
    <tr>
      <td>Sprouting</td>
      <td><strong>${stats.sprout_count}</strong></td>
      <td>${stats.sprout_indicator_percent.toFixed(1)}%</td>
      <td><span class="tag-status ${stats.sprout_count === 0 ? 'tag-pass' : 'tag-fail'}">${stats.sprout_count === 0 ? 'CLEAN' : 'DETECTED'}</span></td>
    </tr>
    <tr>
      <td>Damaged (Double Split)</td>
      <td><strong>${stats.double_split_count}</strong></td>
      <td>${stats.double_split_indicator_percent.toFixed(1)}%</td>
      <td><span class="tag-status ${stats.double_split_count === 0 ? 'tag-pass' : 'tag-neutral'}">${stats.double_split_count === 0 ? 'CLEAN' : 'DETECTED'}</span></td>
    </tr>
    <tr>
      <td>Undersized Bulbs (Small)</td>
      <td><strong>${stats.size_distribution.small}</strong></td>
      <td>${stats.size_distribution.small_percent.toFixed(1)}%</td>
      <td><span class="tag-status tag-neutral">${stats.size_distribution.small_percent.toFixed(0)}% of lot</span></td>
    </tr>
  `;

  repReasonText.textContent = data.assessment.reasons.join(" ") || data.assessment.summary;

  reportModal.style.display = "flex";
}

function closeReportModal() {
  reportModal.style.display = "none";
}
