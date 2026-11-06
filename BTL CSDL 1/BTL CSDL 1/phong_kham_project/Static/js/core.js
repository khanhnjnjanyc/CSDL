let globalCatalog = { diseases: [], medicines: [], specialties: [] };
let globalStaff = { doctors: [], nurses: [] };
let globalPatients = [];
let globalQ1Evidence = [];
let currentUser = null;

// Tự gắn token vào mọi lời gọi /api/ và xử lý tập trung 401 (hết phiên) / 403 (không đủ quyền).
const _nativeFetch = window.fetch.bind(window);
window.fetch = async (input, init = {}) => {
  const url = typeof input === "string" ? input : input.url;
  const isApi = url.startsWith("/api/");
  if (isApi && currentUser && currentUser.token) {
    init = {
      ...init,
      headers: { ...(init.headers || {}), Authorization: `Bearer ${currentUser.token}` },
    };
  }
  const res = await _nativeFetch(input, init);
  if (isApi && !url.startsWith("/api/login")) {
    if (res.status === 401) {
      localStorage.removeItem("medcare_user");
      currentUser = null;
      requireLogin();
      showAlert("Phiên đăng nhập đã hết hạn, vui lòng đăng nhập lại.", "warning");
    } else if (res.status === 403) {
      showAlert("Bạn không có quyền thực hiện thao tác này.", "danger");
    }
  }
  return res;
};

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
  currentUser = null;
  const saved = localStorage.getItem("medcare_user");
  if (saved) {
    try {
      currentUser = JSON.parse(saved);
    } catch (e) {
      currentUser = null;
    }
  }
  // Không còn tự động đăng nhập Admin: chưa có tài khoản hợp lệ thì bắt buộc đăng nhập.
  if (currentUser && !["ADMIN", "BAC_SI", "Y_TA"].includes(currentUser.role)) {
    currentUser = null;
  }
  return !!currentUser;
}

// Khóa giao diện và buộc người dùng đăng nhập (chưa đăng nhập thì không thấy menu, dữ liệu).
function requireLogin() {
  document.body.classList.add("auth-locked");
  const cmt = document.getElementById("loginCmt");
  const pw = document.getElementById("loginPassword");
  if (cmt) cmt.value = "";
  if (pw) pw.value = "";
  openLoginModal();
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

    currentUser = { ...data.user, token: data.token };
    localStorage.setItem("medcare_user", JSON.stringify(currentUser));
    document.body.classList.remove("auth-locked");

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

// Nút tài khoản demo chỉ ĐIỀN SẴN thông tin; người dùng vẫn phải bấm "Đăng nhập".
function quickLogin(role) {
  let cmt = "001000000010";
  if (role === "BAC_SI") cmt = "001000000011";
  if (role === "Y_TA") cmt = "001000000020";

  document.getElementById("loginCmt").value = cmt;
  const pw = document.getElementById("loginPassword");
  pw.value = "demo123";
  const alertEl = document.getElementById("loginAlert");
  if (alertEl) alertEl.classList.add("d-none");
  pw.focus();
}

function logout() {
  localStorage.removeItem("medcare_user");
  currentUser = null;
  requireLogin();
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
  if (!currentUser && !initAuth()) return requireLogin();

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

  // Mô tả quyền hạn hiển thị khi rê chuột vào thẻ người dùng (thanh trên chỉ còn slogan)
  const userCard = document.getElementById("topbarUserCard");
  if (userCard && hintEl) userCard.title = hintEl.innerText;

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

// ==============================================================================
// KIỂM TRA DỮ LIỆU NHẬP NGAY TRÊN Ô (CMT, SĐT, NGÀY VÀO LÀM)
// ==============================================================================
function fmtDateVN(iso) {
  return iso ? iso.split("-").reverse().join("/") : "";
}

// Cộng n năm vào chuỗi ngày YYYY-MM-DD (29/02 -> 28/02 nếu năm đích không nhuận)
function addYears(iso, n) {
  const [y, m, d] = iso.split("-").map(Number);
  let dt = new Date(Date.UTC(y + n, m - 1, d));
  if (dt.getUTCMonth() !== m - 1) dt = new Date(Date.UTC(y + n, m - 1, 28));
  return dt.toISOString().slice(0, 10);
}

// Hiện / xóa thông báo lỗi đỏ ngay dưới ô nhập; khóa nút Lưu khi form còn lỗi.
function setFieldError(input, msg) {
  let fb = input.nextElementSibling;
  if (!fb || !fb.classList.contains("mc-feedback")) {
    fb = document.createElement("div");
    fb.className = "invalid-feedback mc-feedback";
    input.insertAdjacentElement("afterend", fb);
  }
  fb.textContent = msg || "";
  input.classList.toggle("is-invalid", !!msg);
  input.setCustomValidity(msg || "");
  if (input.form) {
    const btn = input.form.querySelector('button[type="submit"]');
    if (btn) btn.disabled = !!input.form.querySelector(".is-invalid");
  }
}

function clearFieldErrors(root) {
  root.querySelectorAll(".is-invalid").forEach((el) => setFieldError(el, ""));
}

// Chỉ cho gõ chữ số (chặn dấu trừ, chữ cái, khoảng trắng), giới hạn độ dài, báo lỗi ngay.
function bindDigitsField(id, { min, max, label, phone }) {
  const el = document.getElementById(id);
  if (!el) return;
  const check = () => {
    const v = el.value;
    if (!v) return setFieldError(el, "");
    if (v.length < min) return setFieldError(el, `${label} phải có ít nhất ${min} chữ số.`);
    if (phone && v[0] !== "0") return setFieldError(el, `${label} phải bắt đầu bằng số 0.`);
    setFieldError(el, "");
  };
  el.addEventListener("input", () => {
    const raw = el.value;
    const digits = raw.replace(/\D/g, "");
    const cleaned = digits.slice(0, max);
    if (cleaned !== raw) {
      el.value = cleaned;
      return setFieldError(
        el,
        digits.length > max
          ? `${label} tối đa ${max} chữ số.`
          : `${label} chỉ được nhập chữ số (không nhập dấu âm, chữ cái hay khoảng trắng).`,
      );
    }
    check();
  });
  el.addEventListener("blur", check);
}

function checkHireDate() {
  const dobEl = document.getElementById("stDob");
  const hireEl = document.getElementById("stHireDate");
  if (!dobEl || !hireEl) return;
  if (!dobEl.value) {
    hireEl.removeAttribute("min");
    return setFieldError(hireEl, "");
  }
  const minHire = addYears(dobEl.value, 18);
  hireEl.min = minHire;
  if (!hireEl.value) return setFieldError(hireEl, "");
  if (hireEl.value <= dobEl.value) {
    return setFieldError(hireEl, "Ngày vào làm phải sau ngày sinh.");
  }
  if (hireEl.value < minHire) {
    return setFieldError(
      hireEl,
      `Nhân viên phải đủ 18 tuổi: ngày vào làm sớm nhất là ${fmtDateVN(minHire)}.`,
    );
  }
  setFieldError(hireEl, "");
}

function bindInputGuards() {
  bindDigitsField("ptCmt", { min: 9, max: 12, label: "Số CMT/CCCD" });
  bindDigitsField("ptPhone", { min: 10, max: 11, label: "Số điện thoại", phone: true });
  bindDigitsField("stCmt", { min: 9, max: 12, label: "Số CMT/CCCD" });
  const dob = document.getElementById("stDob");
  const hire = document.getElementById("stHireDate");
  if (dob && hire) {
    dob.addEventListener("change", checkHireDate);
    hire.addEventListener("change", checkHireDate);
    checkHireDate();
  }
  // Mở lại form bệnh nhân thì xóa lỗi cũ (tránh khóa nút Lưu oan)
  const pm = document.getElementById("patientModal");
  if (pm) pm.addEventListener("show.bs.modal", () => clearFieldErrors(pm));
}

window.onload = () => {
  bindInputGuards();
  if (!initAuth()) return requireLogin();
  applyRolePermissions();
  loadOverview();
};
