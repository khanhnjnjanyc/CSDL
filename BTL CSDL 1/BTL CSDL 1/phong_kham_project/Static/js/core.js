let globalCatalog = { diseases: [], medicines: [], specialties: [] };
let globalStaff = { doctors: [], nurses: [] };
let globalPatients = [];
let globalQ1Evidence = [];

function fmtMoney(val) {
  return Number(val || 0).toLocaleString("vi-VN") + " đ";
}

function showAlert(msg, type = "success") {
  const box = document.getElementById("alertBox");
  const txt = document.getElementById("alertText");
  box.className = `alert alert-${type} alert-dismissible fade show shadow-sm`;
  txt.innerText = msg;
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function switchScreen(screenId, navEl) {
  document
    .querySelectorAll(".screen-section")
    .forEach((s) => s.classList.remove("active"));
  const target = document.getElementById(screenId);
  if (target) target.classList.add("active");

  document
    .querySelectorAll("#sidebarNav .nav-link")
    .forEach((l) => l.classList.remove("active"));
  if (navEl) {
    navEl.classList.add("active");
  } else {
    const autoNav = document.querySelector(
      `#sidebarNav .nav-link[data-screen="${screenId}"]`,
    );
    if (autoNav) autoNav.classList.add("active");
  }

  if (screenId === "screen-1") loadOverview();
  if (screenId === "screen-2") loadPatients();
  if (screenId === "screen-3") {
    loadDropdowns();
    loadVisits();
  }
  if (screenId === "screen-4") loadEpisodes();
  if (screenId === "screen-5") {
    loadDropdowns();
    loadPrescriptions();
  }
  if (screenId === "screen-6") loadStaff();
  if (screenId === "screen-7") loadReports();
  if (screenId === "screen-8") loadCatalog();
}

function switchScreenById(screenId) {
  switchScreen(screenId, null);
}

// Liên kết điều hướng từ Lịch sử Bệnh nhân (3A, 3B, 3D) sang thẳng Lượt khám, Episode hoặc Đơn thuốc
async function jumpToRecord(screenId, rowPrefix, idVal) {
  switchScreenById(screenId);
  setTimeout(() => {
    const row = document.getElementById(`${rowPrefix}-${idVal}`);
    if (row) {
      row.scrollIntoView({ behavior: "smooth", block: "center" });
      row.classList.add("row-highlight");
      setTimeout(() => row.classList.remove("row-highlight"), 2500);
    }
  }, 350);
}

// PHÂN QUYỀN 3 VAI TRÒ: ADMIN / BAC_SI / Y_TA
function applyRolePermissions() {
  const role = document.getElementById("roleSelector").value;
  const hint = document.getElementById("rolePermissionHint");

  if (role === "ADMIN") {
    hint.innerText =
      "Toàn quyền quản trị: Nhân viên, Danh mục, Bệnh nhân, Lượt khám, Episode và 4 Báo cáo tháng.";
  } else if (role === "BAC_SI") {
    hint.innerText =
      "Quyền Bác sĩ chuyên môn: Khám & chẩn đoán, Kê đơn thuốc, Theo dõi & Kết thúc khỏi Episode.";
  } else {
    hint.innerText =
      "Quyền Y tá hỗ trợ: Tiếp nhận bệnh nhân, Cập nhật giờ ra viện, Ghi nhận sự kiện hỗ trợ theo lượt khám.";
  }

  document.querySelectorAll(".role-admin-only").forEach((el) => {
    el.style.display = role === "ADMIN" ? "" : "none";
  });
  document.querySelectorAll(".role-admin-doc").forEach((el) => {
    el.style.display = role === "ADMIN" || role === "BAC_SI" ? "" : "none";
  });
  document.querySelectorAll(".role-admin-nurse").forEach((el) => {
    el.style.display = role === "ADMIN" || role === "Y_TA" ? "" : "none";
  });

  // Nếu đang đứng ở màn hình bị ẩn đối với Role đó thì chuyển về Tổng quan
  const activeScreen = document.querySelector(".screen-section.active");
  if (
    activeScreen &&
    (activeScreen.id === "screen-6" || activeScreen.id === "screen-7") &&
    role !== "ADMIN"
  ) {
    switchScreenById("screen-1");
  }
}

window.onload = () => {
  applyRolePermissions();
  loadOverview();
};
