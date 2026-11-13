// ==============================================================================
// MÀN HÌNH 10: THỐNG KÊ BỆNH THEO THÁNG (Truy vấn 1 của đề)
// Liệt kê các loại bệnh bệnh nhân mắc phải trong một tháng cho trước,
// sắp xếp theo số bệnh nhân giảm dần (thứ tự do backend trả về).
// ==============================================================================
let dsData = { month: "", diseases: [], evidence: [] };

function dsEscape(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[ch]);
}

function dsMonthLabel(month) {
  const [y, m] = month.split("-");
  return `tháng ${Number(m)}/${y}`;
}

async function loadDiseaseStats() {
  const month = document.getElementById("dsMonth").value;
  if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(month)) {
    showAlert("Vui lòng chọn tháng/năm hợp lệ.", "warning");
    return;
  }
  document.getElementById("btnDsExport").href =
    `/api/export/diseases?month=${month}&token=${encodeURIComponent(currentUser?.token || "")}`;

  try {
    const res = await fetch(`/api/reports/diseases?month=${month}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.message || "Không tải được thống kê bệnh.");
    dsData = { month, diseases: data.diseases || [], evidence: data.evidence || [] };
  } catch (err) {
    dsData = { month, diseases: [], evidence: [] };
    showAlert(err.message || "Lỗi kết nối máy chủ.", "danger");
  }
  renderDiseaseStats();
}

// Hạng theo số bệnh nhân (bằng nhau thì cùng hạng)
function dsRank(row) {
  return 1 + dsData.diseases.filter((r) => r.so_benh_nhan > row.so_benh_nhan).length;
}

function renderDiseaseStats() {
  const kw = (document.getElementById("dsSearch").value || "").trim().toLowerCase();
  const rows = dsData.diseases.filter((r) => String(r.ten_benh).toLowerCase().includes(kw));
  const patientCount = new Set(dsData.evidence.map((e) => e.ma_nguoi)).size;
  const label = dsData.month ? dsMonthLabel(dsData.month) : "";

  document.getElementById("dsSummary").innerText = dsData.diseases.length
    ? `${label}: ${dsData.diseases.length} loại bệnh, ${patientCount} bệnh nhân đến khám` +
      (kw ? ` • đang lọc: ${rows.length} bệnh khớp "${kw}"` : "")
    : "";

  const body = document.getElementById("dsBody");
  if (!rows.length) {
    const msg = dsData.diseases.length
      ? "Không có bệnh nào khớp từ khóa."
      : dsData.month
        ? `Không có bệnh nhân nào đến khám trong ${label}.`
        : "";
    body.innerHTML = `<tr><td colspan="6" class="text-center text-muted py-3">${dsEscape(msg)}</td></tr>`;
    return;
  }
  body.innerHTML = rows
    .map(
      (r) => `
        <tr>
          <td class="fw-bold">#${dsRank(r)}</td>
          <td>${dsEscape(r.ma_benh)}</td>
          <td class="fw-bold text-teal">${dsEscape(r.ten_benh)}</td>
          <td><span class="badge bg-success fs-6">${r.so_benh_nhan} bệnh nhân</span></td>
          <td class="fw-semibold">${r.so_dot_mac} đợt</td>
          <td>
            <button class="btn btn-sm btn-outline-teal py-0" onclick="openDiseaseEvidence(${Number(r.ma_benh)})">
              <i class="bi bi-people me-1"></i>Xem danh sách
            </button>
          </td>
        </tr>`,
    )
    .join("");
}

function openDiseaseEvidence(maBenh) {
  const disease = dsData.diseases.find((r) => Number(r.ma_benh) === maBenh);
  const list = dsData.evidence.filter((e) => Number(e.ma_benh) === maBenh);
  document.getElementById("dsModalTitle").innerText =
    `Bệnh nhân mắc "${disease ? disease.ten_benh : ""}" trong ${dsMonthLabel(dsData.month)}`;
  document.getElementById("dsModalBody").innerHTML = list
    .map(
      (e) => `
        <tr>
          <td class="fw-bold text-teal">${dsEscape(e.ma_benh_nhan)}</td>
          <td class="fw-semibold">${dsEscape(e.ho_ten)}</td>
          <td>Đợt #${e.ma_dot}</td>
          <td>${dsEscape(e.ngay_bat_dau)}</td>
          <td class="text-center">${e.so_luot_trong_thang} lượt</td>
          <td><span class="badge ${e.trang_thai === "KHOI" ? "bg-success" : "bg-warning text-dark"}">${e.trang_thai === "KHOI" ? "Đã khỏi" : "Đang điều trị"}</span></td>
          <td>
            <button class="btn btn-sm btn-teal py-0" onclick="bootstrap.Modal.getInstance(document.getElementById('dsEvidenceModal')).hide(); switchScreenById('screen-2'); setTimeout(() => viewPatientDetail(${Number(e.ma_nguoi)}), 250);">
              Xem hồ sơ
            </button>
          </td>
        </tr>`,
    )
    .join("");
  new bootstrap.Modal(document.getElementById("dsEvidenceModal")).show();
}
