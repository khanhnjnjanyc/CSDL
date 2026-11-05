let globalCatalog = { diseases: [], medicines: [], specialties: [] };
let globalStaff = { doctors: [], nurses: [] };
let globalPatients = [];
let globalQ1Evidence = [];
let currentUser = null;

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

// ==============================================================================
// XÁC THỰC NGƯỜI DÙNG & ĐĂNG NHẬP (BẢNG TAI_KHOAN)
// ==============================================================================
function initAuth() {
  const saved = localStorage.getItem("medcare_user");
  if (saved) {
    try {
      currentUser = JSON.parse(saved);
    } catch (e) {
      currentUser = null;
    }
  }

  // Mặc định tài khoản Quản trị viên nếu chưa đăng nhập
  if (!currentUser) {
    currentUser = {
      cmt: "001000000010",
      role: "ADMIN",
      title: "Quản trị viên",
      ho_ten: "Bac si Minh",
      ma_nhan_vien: "NV010",
      ma_bac_si: "BS010",
    };
    localStorage.setItem("medcare_user", JSON.stringify(currentUser));
  }
}

function openLoginModal() {
  const alertEl = document.getElementById("loginAlert");
  if (alertEl) alertEl.classList.add("d-none");
  const modalEl = document.getElementById("loginModal");
  if (modalEl) {
    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();
  }
}

async function handleLoginSubmit(e) {
  e.preventDefault();
  const cmt = document.getElementById("loginCmt").value.trim();
  const password = document.getElementById("loginPassword").value.trim();
  const alertEl = document.getElementById("loginAlert");

  try {
    const res = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cmt, password }),
    });
    const data = await res.json();

    if (!res.ok) {
      if (alertEl) {
        alertEl.innerText = data.message || data.error || "Đăng nhập thất bại!";
        alertEl.classList.remove("d-none");
      }
      return;
    }

    currentUser = data.user;
    localStorage.setItem("medcare_user", JSON.stringify(currentUser));

    const modalEl = document.getElementById("loginModal");
    const modal = bootstrap.Modal.getInstance(modalEl);
    if (modal) modal.hide();

    applyRolePermissions();
    showAlert(data.message, "success");

    // Tải lại màn hình hiện tại
    const activeScreen = document.querySelector(".screen-section.active");
    if (activeScreen) {
      switchScreenById(activeScreen.id);
    } else {
      switchScreenById("screen-1");
    }
  } catch (err) {
    if (alertEl) {
      alertEl.innerText = "Lỗi kết nối máy chủ!";
      alertEl.classList.remove("d-none");
    }
  }
}

async function quickLogin(role) {
  let cmt = "001000000010";
  if (role === "BAC_SI") cmt = "001000000011";
  if (role === "Y_TA") cmt = "001000000020";

  document.getElementById("loginCmt").value = cmt;
  document.getElementById("loginPassword").value = "demo123";

  try {
    const res = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cmt, password: "demo123" }),
    });
    const data = await res.json();

    if (!res.ok) {
      showAlert(data.message || data.error, "danger");
      return;
    }

    currentUser = data.user;
    localStorage.setItem("medcare_user", JSON.stringify(currentUser));

    const modalEl = document.getElementById("loginModal");
    const modal = bootstrap.Modal.getInstance(modalEl);
    if (modal) modal.hide();

    applyRolePermissions();
    showAlert(`Đã chuyển sang vai trò: ${currentUser.title} (${currentUser.ho_ten})`, "success");

    // Tải lại dữ liệu
    const activeScreen = document.querySelector(".screen-section.active");
    if (activeScreen) {
      switchScreenById(activeScreen.id);
    } else {
      switchScreenById("screen-1");
    }
  } catch (err) {
    showAlert("Lỗi đăng nhập nhanh!", "danger");
  }
}

function logout() {
  localStorage.removeItem("medcare_user");
  currentUser = null;
  initAuth();
  applyRolePermissions();
  openLoginModal();
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

// ==============================================================================
// PHÂN QUYỀN 3 VAI TRÒ DỰA TRÊN TÀI KHOẢN ĐĂNG NHẬP: ADMIN / BAC_SI / Y_TA
// ==============================================================================
function applyRolePermissions() {
  if (!currentUser) initAuth();

  const role = currentUser.role;
  const roleSelector = document.getElementById("roleSelector");
  if (roleSelector) roleSelector.value = role;

  // Cập nhật thông tin trên topbar
  const nameEl = document.getElementById("topbarUserName");
  const badgeEl = document.getElementById("topbarRoleBadge");
  const codeEl = document.getElementById("topbarUserCode");
  const hintEl = document.getElementById("rolePermissionHint");

  if (nameEl) nameEl.innerText = currentUser.ho_ten || "Người dùng";

  if (badgeEl) {
    if (role === "ADMIN") {
      badgeEl.className = "badge bg-warning text-dark";
      badgeEl.innerHTML = '<i class="bi bi-crown me-1"></i>Admin (Quản trị viên)';
    } else if (role === "BAC_SI") {
      badgeEl.className = "badge bg-danger";
      badgeEl.innerHTML = '<i class="bi bi-heart-pulse me-1"></i>Bác sĩ điều trị';
    } else {
      badgeEl.className = "badge bg-info text-dark";
      badgeEl.innerHTML = '<i class="bi bi-capsule me-1"></i>Y tá phòng khám';
    }
  }

  if (codeEl) {
    const parts = [];
    if (currentUser.ma_bac_si) parts.push(currentUser.ma_bac_si);
    if (currentUser.ma_nhan_vien) parts.push(currentUser.ma_nhan_vien);
    codeEl.innerText = parts.length ? `(${parts.join(" • ")})` : `(${currentUser.cmt})`;
  }

  if (hintEl) {
    if (role === "ADMIN") {
      hintEl.innerText =
        "Toàn quyền quản trị hệ thống: Danh mục, Nhân sự, Bệnh nhân, Lượt khám, Doanh thu và Toàn bộ lương.";
    } else if (role === "BAC_SI") {
      hintEl.innerText =
        "Quyền Bác sĩ: Khám bệnh, Kê đơn, Kết thúc Khỏi đợt điều trị. (Ẩn doanh thu & danh mục hệ thống).";
    } else {
      hintEl.innerText =
        "Quyền Y tá: Tiếp đón, Cấp phát thuốc, Ghi nhận sự kiện hỗ trợ (+200.000đ thưởng/lượt). (Ẩn doanh thu).";
    }
  }

  // Ẩn / hiện phần tử theo lớp phân quyền
  document.querySelectorAll(".role-admin-only").forEach((el) => {
    el.style.display = role === "ADMIN" ? "" : "none";
  });
  document.querySelectorAll(".role-admin-doc").forEach((el) => {
    el.style.display = role === "ADMIN" || role === "BAC_SI" ? "" : "none";
  });
  document.querySelectorAll(".role-admin-nurse").forEach((el) => {
    el.style.display = role === "ADMIN" || role === "Y_TA" ? "" : "none";
  });

  // Chuyển màn hình an toàn nếu màn hình hiện tại bị ẩn với vai trò đăng nhập
  const activeScreen = document.querySelector(".screen-section.active");
  if (activeScreen) {
    if (role === "BAC_SI" && (activeScreen.id === "screen-6" || activeScreen.id === "screen-8")) {
      switchScreenById("screen-1");
    } else if (
      role === "Y_TA" &&
      (activeScreen.id === "screen-4" || activeScreen.id === "screen-6" || activeScreen.id === "screen-8")
    ) {
      switchScreenById("screen-1");
    }
  }
}

window.onload = () => {
  initAuth();
  applyRolePermissions();
  loadOverview();
};
