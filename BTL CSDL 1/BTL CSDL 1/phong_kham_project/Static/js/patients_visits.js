// MÀN HÌNH 2: BỆNH NHÂN & TRA CỨU (CHỨC NĂNG LÕI C)
async function loadPatients() {
  const q = document.getElementById("ptSearch").value;
  const status = document.getElementById("ptFilterStatus").value;
  const res = await fetch(
    `/api/patients?q=${encodeURIComponent(q)}&status=${status}`,
  );
  globalPatients = await res.json();

  const role = document.getElementById("roleSelector").value;
  const canEdit = role === "ADMIN" || role === "Y_TA";

  document.getElementById("ptTableBody").innerHTML = globalPatients
    .map(
      (p) => `
        <tr>
            <td class="fw-bold text-teal">${p.ma_benh_nhan}</td>
            <td>
                <div class="fw-semibold">${p.ho_ten}</div>
                <small class="text-muted">CMT: ${p.cmt} • ${p.gioi_tinh}</small>
            </td>
            <td>
                ${
                  p.so_dot_dang_mo > 0
                    ? `<span class="badge bg-warning text-dark">${p.so_dot_dang_mo} đợt đang ĐT</span>`
                    : `<span class="badge badge-teal">Đã khỏi / Bình thường</span>`
                }
            </td>
            <td>
                <button class="btn btn-sm btn-teal py-0 px-2" onclick="viewPatientDetail(${p.ma_nguoi})">Hồ sơ</button>
                ${canEdit ? `<button class="btn btn-sm btn-outline-secondary py-0 px-1" onclick='editPatient(${JSON.stringify(p)})'><i class="bi bi-pencil"></i></button>` : ""}
                ${role === "ADMIN" ? `<button class="btn btn-sm btn-outline-danger py-0 px-1" onclick="deletePatient(${p.ma_nguoi})"><i class="bi bi-trash"></i></button>` : ""}
            </td>
        </tr>
    `,
    )
    .join("");

  if (globalPatients.length > 0) {
    viewPatientDetail(globalPatients[0].ma_nguoi);
  }
}

async function viewPatientDetail(ma_nguoi) {
  const res = await fetch(`/api/patients/${ma_nguoi}/detail`);
  const data = await res.json();
  const info = data.info;

  document.getElementById("ptDetailTitle").innerText =
    `${info.ma_benh_nhan} — ${info.ho_ten}`;
  document.getElementById("ptDetailSub").innerText =
    `CMT/CCCD: ${info.cmt} | Ngày sinh: ${info.ngay_sinh} | Giới tính: ${info.gioi_tinh} | SĐT: ${info.so_dien_thoai || "N/A"} | Địa chỉ: ${info.dia_chi || "Hà Nội"}`;

  // Tab 3B: Episode đang mở
  document.getElementById("pt3BBody").innerHTML = data.open_episodes_3b.length
    ? data.open_episodes_3b
        .map(
          (r) => `
        <tr>
            <td class="fw-bold">#${r.ma_dot}</td>
            <td class="fw-semibold text-danger">${r.ten_benh}</td>
            <td>${r.so_lan_kham} lượt</td>
            <td>${r.lan_kham_gan_nhat}</td>
            <td><button class="btn btn-sm btn-outline-teal py-0" onclick="jumpToRecord('screen-4', 'ep-row', ${r.ma_dot})">Mở Episode #${r.ma_dot}</button></td>
        </tr>
    `,
        )
        .join("")
    : `<tr><td colspan="5" class="text-center text-muted py-3">Bệnh nhân hiện không có đợt điều trị nào đang mở</td></tr>`;

  // Tab 3A: Lịch sử khám (Có nút mở trực tiếp lượt khám)
  document.getElementById("pt3ABody").innerHTML = data.history_3a
    .map(
      (r) => `
        <tr>
            <td><a href="javascript:void(0)" class="fw-bold text-teal" onclick="jumpToRecord('screen-3', 'vs-row', ${r.ma_lan_kham})">Lượt #${r.ma_lan_kham} <i class="bi bi-box-arrow-up-right"></i></a></td>
            <td>${r.thoi_diem_vao}</td>
            <td>${r.ten_benh} <span class="badge bg-secondary">#${r.ma_dot} (${r.tinh_trang_dot})</span></td>
            <td class="text-center fw-bold">Lần ${r.lan_thu_trong_dot}</td>
            <td>${r.ten_bac_si} (${r.ma_bac_si})</td>
            <td>${fmtMoney(r.phi_kham_chua)}</td>
            <td>${r.ket_luan || ""}</td>
        </tr>
    `,
    )
    .join("");

  // Tab 3D: Thuốc đã kê (Có nút mở trực tiếp đơn thuốc)
  document.getElementById("pt3DBody").innerHTML = data.prescriptions_3d.length
    ? data.prescriptions_3d
        .map(
          (r) => `
        <tr>
            <td><a href="javascript:void(0)" class="fw-bold text-teal" onclick="jumpToRecord('screen-5', 'pr-row', ${r.ma_don})">Đơn #${r.ma_don} <i class="bi bi-box-arrow-up-right"></i></a></td>
            <td>#${r.ma_lan_kham}</td>
            <td>${r.ngay_ke}</td>
            <td class="fw-semibold">${r.ten_thuoc}</td>
            <td>${r.so_luong} × ${fmtMoney(r.don_gia_tai_thoi_diem)}</td>
            <td class="fw-bold text-danger">${fmtMoney(r.thanh_tien)}</td>
        </tr>
    `,
        )
        .join("")
    : `<tr><td colspan="6" class="text-center text-muted">Chưa có đơn thuốc</td></tr>`;

  // Tab 3C: Y tá hỗ trợ
  document.getElementById("pt3CBody").innerHTML = data.nurse_events_3c
    .map(
      (r) => `
        <tr><td>#${r.ma_lan_kham}</td><td class="fw-semibold">${r.ten_y_ta}</td><td>${r.vai_tro}</td><td>${r.thoi_diem}</td><td>${r.ghi_chu || ""}</td></tr>
    `,
    )
    .join("");
}

function openPatientModal() {
  document.getElementById("ptId").value = "";
  document.getElementById("ptModalTitle").innerText =
    "Thêm Hồ sơ Bệnh nhân mới";
  document.getElementById("ptCode").value = "";
  document.getElementById("ptCmt").value = "";
  document.getElementById("ptName").value = "";
  new bootstrap.Modal(document.getElementById("patientModal")).show();
}

function editPatient(p) {
  document.getElementById("ptId").value = p.ma_nguoi;
  document.getElementById("ptModalTitle").innerText =
    "Cập nhật Hồ sơ Bệnh nhân";
  document.getElementById("ptCode").value = p.ma_benh_nhan;
  document.getElementById("ptCmt").value = p.cmt;
  document.getElementById("ptName").value = p.ho_ten;
  document.getElementById("ptDob").value = p.ngay_sinh;
  document.getElementById("ptGender").value = p.gioi_tinh;
  document.getElementById("ptPhone").value = p.so_dien_thoai || "";
  document.getElementById("ptAddress").value = p.dia_chi || "";
  new bootstrap.Modal(document.getElementById("patientModal")).show();
}

async function savePatient(e) {
  e.preventDefault();
  const id = document.getElementById("ptId").value;
  const cmt = document.getElementById("ptCmt").value.trim();
  const phone = document.getElementById("ptPhone").value.trim();

  // Validate CMT/CCCD: 9-12 chữ số dương
  if (!/^[0-9]{9,12}$/.test(cmt)) {
    return showAlert("Số CMT/CCCD không hợp lệ! Vui lòng nhập số dương từ 9 đến 12 chữ số.", "danger");
  }

  // Validate Số điện thoại: 10-11 chữ số, bắt đầu bằng 0
  if (phone && !/^0[0-9]{9,10}$/.test(phone)) {
    return showAlert("Số điện thoại không hợp lệ! Vui lòng nhập số điện thoại bắt đầu bằng 0, gồm 10-11 chữ số.", "danger");
  }

  const payload = {
    ma_benh_nhan: document.getElementById("ptCode").value.trim(),
    cmt: cmt,
    ho_ten: document.getElementById("ptName").value.trim(),
    ngay_sinh: document.getElementById("ptDob").value,
    gioi_tinh: document.getElementById("ptGender").value,
    so_dien_thoai: phone,
    dia_chi: document.getElementById("ptAddress").value.trim(),
  };
  const res = await fetch(id ? `/api/patients/${id}` : "/api/patients", {
    method: id ? "PUT" : "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (!res.ok) return showAlert(data.message || data.error, "danger");
  bootstrap.Modal.getInstance(document.getElementById("patientModal")).hide();
  showAlert(data.message);
  loadPatients();
}

async function deletePatient(id) {
  if (!confirm("Xác nhận xóa bệnh nhân này?")) return;
  const res = await fetch(`/api/patients/${id}`, { method: "DELETE" });
  const data = await res.json();
  if (!res.ok) return showAlert(data.error, "danger");
  showAlert(data.message);
  loadPatients();
}

// MÀN HÌNH 3: LƯỢT KHÁM & TIẾP NHẬN
async function loadDropdowns() {
  const [resPt, resCat, resSt] = await Promise.all([
    fetch("/api/patients"),
    fetch("/api/catalog"),
    fetch("/api/staff"),
  ]);
  globalPatients = await resPt.json();
  globalCatalog = await resCat.json();
  globalStaff = await resSt.json();

  document.getElementById("vsPatient").innerHTML = globalPatients
    .map(
      (p) =>
        `<option value="${p.ma_nguoi}">${p.ma_benh_nhan} — ${p.ho_ten}</option>`,
    )
    .join("");
  document.getElementById("vsDisease").innerHTML = globalCatalog.diseases
    .map((d) => `<option value="${d.ma_benh}">${d.ten_benh}</option>`)
    .join("");
  document.getElementById("vsDoctor").innerHTML = globalStaff.doctors
    .map(
      (d) =>
        `<option value="${d.ma_bac_si}">${d.ma_bac_si} — ${d.ho_ten}</option>`,
    )
    .join("");
  document.getElementById("nsNurse").innerHTML = globalStaff.nurses
    .map(
      (n) =>
        `<option value="${n.ma_nguoi}">${n.ma_nhan_vien} — ${n.ho_ten}</option>`,
    )
    .join("");
}

async function loadVisits() {
  const q = document.getElementById("vsSearch").value;
  const res = await fetch(`/api/visits?q=${encodeURIComponent(q)}`);
  const visits = await res.json();
  const role = document.getElementById("roleSelector").value;

  document.getElementById("vsTableBody").innerHTML = visits
    .map(
      (v) => `
        <tr id="vs-row-${v.ma_lan_kham}">
            <td class="fw-bold text-teal">#${v.ma_lan_kham}</td>
            <td><b>${v.ma_bn_code}</b> — ${v.ten_benh_nhan}<br><small class="text-muted">${v.ghi_chu || ""}</small></td>
            <td>
                <div>Vào: ${v.thoi_diem_vao}</div>
                <div>Ra: ${v.thoi_diem_ra ? `<span class="text-success fw-semibold">${v.thoi_diem_ra}</span>` : `<span class="badge bg-warning text-dark">Đang khám</span>`}</div>
            </td>
            <td>
                ${v.chan_doan
                  .map(
                    (cd) => `
                    <div class="mb-1 p-1 border rounded bg-light">
                        <b>${cd.ten_benh}</b> • <a href="javascript:void(0)" onclick="jumpToRecord('screen-4', 'ep-row', ${cd.ma_dot})">Đợt #${cd.ma_dot}</a>
                        <span class="badge ${cd.trang_thai === "KHOI" ? "bg-success" : "bg-warning text-dark"}">${cd.trang_thai}</span>
                        <br><small>BS: ${cd.ten_bac_si} (${cd.ma_bac_si}) | Phí: <b>${fmtMoney(cd.phi_kham_chua)}</b> | KL: ${cd.ket_luan || ""}</small>
                    </div>
                `,
                  )
                  .join("")}
            </td>
            <td>
                ${v.ho_tro.map((h) => `<div class="small">• <b>${h.ten_y_ta}</b>: ${h.vai_tro} (${h.thoi_diem.slice(11, 16)})</div>`).join("")}
            </td>
            <td>
                ${role === "ADMIN" || role === "Y_TA" ? `<button class="btn btn-sm btn-teal py-0 px-2 mb-1" onclick="openNurseModal(${v.ma_lan_kham})">+ Y tá hỗ trợ</button>` : ""}
                <button class="btn btn-sm btn-outline-secondary py-0 px-2" onclick="quickCheckout(${v.ma_lan_kham}, '${v.thoi_diem_vao}')">Cập nhật ra viện</button>
            </td>
        </tr>
    `,
    )
    .join("");

  const prVisit = document.getElementById("prVisit");
  if (prVisit) {
    prVisit.innerHTML = visits
      .map(
        (v) =>
          `<option value="${v.ma_lan_kham}">Lượt #${v.ma_lan_kham} — ${v.ma_bn_code} ${v.ten_benh_nhan} (${v.thoi_diem_vao})</option>`,
      )
      .join("");
  }
}

async function submitVisit(e) {
  e.preventDefault();
  const role = document.getElementById("roleSelector").value;
  const payload = {
    ma_benh_nhan: document.getElementById("vsPatient").value,
    thoi_diem_vao: document.getElementById("vsTimeIn").value,
    thoi_diem_ra: document.getElementById("vsTimeOut").value,
    ghi_chu: document.getElementById("vsNote").value,
  };
  if (role !== "Y_TA") {
    payload.ma_benh = document.getElementById("vsDisease").value;
    payload.episode_mode = document.getElementById("vsEpisodeMode").value;
    payload.ma_bac_si = document.getElementById("vsDoctor").value;
    payload.phi_kham_chua = document.getElementById("vsFee").value;
    payload.ket_luan =
      document.getElementById("vsNote").value || "Khám và điều trị";
  }
  const res = await fetch("/api/visits", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (!res.ok) return showAlert(data.error, "danger");
  showAlert(data.message);
  loadVisits();
}

async function quickCheckout(ma_lan_kham, vao) {
  const defTime = vao.slice(0, 10) + " 10:30:00";
  const ra = prompt(
    "Nhập thời điểm ra viện (YYYY-MM-DD HH:MM:SS) — R2: Phải >= thời điểm vào:",
    defTime,
  );
  if (!ra) return;
  const res = await fetch(`/api/visits/${ma_lan_kham}/checkout`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ thoi_diem_ra: ra }),
  });
  const data = await res.json();
  if (!res.ok) return showAlert(data.error, "danger");
  showAlert(data.message);
  loadVisits();
}

function openNurseModal(ma_lan_kham) {
  document.getElementById("nsVisitId").value = ma_lan_kham;
  new bootstrap.Modal(document.getElementById("nurseModal")).show();
}

async function saveNurseSupport(e) {
  e.preventDefault();
  const lk = document.getElementById("nsVisitId").value;
  const res = await fetch(`/api/visits/${lk}/nurse-support`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ma_y_ta: document.getElementById("nsNurse").value,
      vai_tro: document.getElementById("nsRole").value,
      thoi_diem: document.getElementById("nsTime").value,
      ghi_chu: document.getElementById("nsNote").value,
    }),
  });
  const data = await res.json();
  if (!res.ok) return showAlert(data.error, "danger");
  bootstrap.Modal.getInstance(document.getElementById("nurseModal")).hide();
  showAlert(data.message);
  loadVisits();
}

// MÀN HÌNH 4: EPISODE ĐIỀU TRỊ
async function loadEpisodes() {
  const status = document.getElementById("epStatusFilter").value;
  const res = await fetch(`/api/episodes?status=${status}`);
  const episodes = await res.json();
  const role = document.getElementById("roleSelector").value;
  const canCure = role === "ADMIN" || role === "BAC_SI";

  document.getElementById("epTableBody").innerHTML = episodes
    .map(
      (ep) => `
        <tr id="ep-row-${ep.ma_dot}">
            <td class="fw-bold text-teal">#${ep.ma_dot}</td>
            <td><b>${ep.ma_bn_code}</b> — ${ep.ten_benh_nhan}</td>
            <td class="fw-semibold">${ep.ten_benh}</td>
            <td>Bắt đầu: ${ep.ngay_bat_dau}${ep.ngay_ket_thuc ? `<br><span class="text-success fw-semibold">Khỏi: ${ep.ngay_ket_thuc}</span>` : ""}</td>
            <td>
                <div class="fw-bold mb-1">Đã khám: ${ep.so_luot_kham} lượt</div>
                ${ep.cac_luot.map((l) => `<div class="small text-secondary">• Lần ${l.stt_luot}: <a href="javascript:void(0)" onclick="jumpToRecord('screen-3', 'vs-row', ${l.ma_lan_kham})">Lượt #${l.ma_lan_kham}</a> (${l.thoi_diem_vao.slice(0, 10)}) — BS ${l.ma_bac_si}</div>`).join("")}
            </td>
            <td>
                <span class="badge ${ep.trang_thai === "KHOI" ? "bg-success" : "bg-warning text-dark"}">${ep.trang_thai}</span>
                ${ep.ma_lan_kham_ket_thuc ? `<div class="small text-muted">Lượt KT: #${ep.ma_lan_kham_ket_thuc}</div>` : ""}
            </td>
            <td>
                ${
                  ep.trang_thai === "DANG_DIEU_TRI" &&
                  ep.ma_lan_kham_moi_nhat &&
                  canCure
                    ? `<button class="btn btn-sm btn-teal" onclick="cureEpisode(${ep.ma_dot}, ${ep.ma_lan_kham_moi_nhat}, '${(ep.lan_kham_moi_nhat || "2026-10-25").slice(0, 10)}')"><i class="bi bi-check2-all me-1"></i>Kết thúc Khỏi</button>`
                    : `<span class="text-muted small">${ep.trang_thai === "KHOI" ? "Đã đóng đợt" : "Chỉ BS/Admin kết thúc"}</span>`
                }
            </td>
        </tr>
    `,
    )
    .join("");
}

async function cureEpisode(ma_dot, ma_lan_kham_ket_thuc, defaultDate) {
  const ngay = prompt(
    `Xác nhận kết thúc KHỎI cho Episode #${ma_dot} tại lượt khám #${ma_lan_kham_ket_thuc}.\nNhập ngày kết thúc (YYYY-MM-DD):`,
    defaultDate,
  );
  if (!ngay) return;
  const res = await fetch(`/api/episodes/${ma_dot}/cure`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ngay_ket_thuc: ngay, ma_lan_kham_ket_thuc }),
  });
  const data = await res.json();
  if (!res.ok) return showAlert(data.error, "danger");
  showAlert(data.message);
  loadEpisodes();
}
