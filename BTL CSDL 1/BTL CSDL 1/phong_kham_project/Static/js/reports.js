// MÀN HÌNH 1: TỔNG QUAN
async function loadOverview() {
  const month = document.getElementById("ovMonth").value || "2026-10";
  const res = await fetch(`/api/overview?month=${month}`);
  const data = await res.json();

  document.getElementById("ovVisitsMonth").innerText = data.visits_month;
  document.getElementById("ovVisitsToday").innerText = data.visits_today;
  document.getElementById("ovActivePatients").innerText = data.active_patients;
  document.getElementById("ovOpenEpisodes").innerText = data.open_episodes;
  document.getElementById("ovRevExam").innerText = fmtMoney(
    data.revenue.doanh_thu_kham_chua,
  );
  document.getElementById("ovRevMed").innerText = fmtMoney(
    data.revenue.doanh_thu_thuoc,
  );
  document.getElementById("ovRevTotal").innerText = fmtMoney(
    data.revenue.tong_doanh_thu,
  );

  document.getElementById("ovTableCounts").innerHTML = data.table_counts
    .map(
      (c) => `
        <div class="col-md-3 col-6">
            <div class="p-2 border rounded bg-light d-flex justify-content-between align-items-center small">
                <div>
                  <span class="fw-semibold text-secondary">${c.ten_nghiep_vu || c.ten_bang}</span>
                  ${c.ten_nghiep_vu && c.ten_nghiep_vu !== c.ten_bang ? `<div class="text-muted" style="font-size:0.72rem"><code>${c.ten_bang}</code></div>` : ""}
                </div>
                <span class="badge badge-teal">${c.so_ban_ghi}</span>
            </div>
        </div>
    `,
    )
    .join("");
}

// MÀN HÌNH 7: 4 CHỨC NĂNG LÕI (A, B, D)
async function loadReports() {
  const month = document.getElementById("rpMonth").value || "2026-10";
  document.getElementById("btnExportDiseases").href =
    `/api/export/diseases?month=${month}`;
  document.getElementById("btnExportPayroll").href =
    `/api/export/payroll?month=${month}`;
  document.getElementById("btnExportRevenue").href =
    `/api/export/revenue?month=${month}`;

  const res = await fetch(`/api/reports?month=${month}`);
  const data = await res.json();
  globalQ1Evidence = data.q1_evidence || [];

  // A. Thống kê bệnh theo tháng (Đếm bệnh nhân duy nhất + Nút mở danh sách BN làm căn cứ)
  document.getElementById("rpQ1Body").innerHTML = data.q1_diseases
    .map(
      (r, idx) => `
        <tr>
            <td class="fw-bold">#${idx + 1}</td>
            <td>${r.ma_benh}</td>
            <td class="fw-bold text-teal">${r.ten_benh}</td>
            <td><span class="badge bg-success fs-6">${r.so_benh_nhan} bệnh nhân duy nhất</span></td>
            <td class="fw-semibold">${r.so_dot_mac} đợt điều trị</td>
            <td>
                <button class="btn btn-sm btn-outline-teal py-0" onclick="openQ1Evidence(${r.ma_benh}, '${r.ten_benh}')">
                    <i class="bi bi-people me-1"></i>Xem danh sách BN căn cứ
                </button>
            </td>
        </tr>
    `,
    )
    .join("");

  // B. Tính lương nhân viên (Lọc theo vai trò: Admin xem toàn bộ, Bác sĩ/Y tá chỉ xem của bản thân)
  let payrollList = data.q2_payroll || [];
  let bsEvidence = data.q2_bs_evidence || [];
  let ytEvidence = data.q2_yt_evidence || [];

  if (currentUser) {
    if (currentUser.role === "BAC_SI") {
      payrollList = payrollList.filter(
        (r) =>
          r.ma_nhan_vien === currentUser.ma_nhan_vien ||
          r.ma_chuyen_biet === currentUser.ma_bac_si ||
          (r.ho_ten && r.ho_ten.toLowerCase().includes("lan"))
      );
      bsEvidence = bsEvidence.filter(
        (e) => e.ma_bac_si === currentUser.ma_bac_si || (e.ten_bac_si && e.ten_bac_si.toLowerCase().includes("lan"))
      );
      ytEvidence = [];
    } else if (currentUser.role === "Y_TA") {
      payrollList = payrollList.filter(
        (r) =>
          r.ma_nhan_vien === currentUser.ma_nhan_vien ||
          (r.ho_ten && r.ho_ten.toLowerCase().includes("hoa"))
      );
      bsEvidence = [];
      ytEvidence = ytEvidence.filter(
        (e) => e.ma_y_ta === currentUser.ma_nhan_vien || (e.ten_y_ta && e.ten_y_ta.toLowerCase().includes("hoa"))
      );
    }
  }

  document.getElementById("rpQ2Body").innerHTML = payrollList
    .map((r) => {
      const unitBonus = r.loai === "BAC_SI" ? "1.000.000đ" : "200.000đ";
      const formulaText = `${fmtMoney(r.luong_co_ban)} + (${r.so_su_kien} × ${unitBonus})`;
      return `
        <tr>
            <td><span class="badge ${r.loai === "BAC_SI" ? "badge-teal" : "bg-info text-dark"}">${r.loai}</span></td>
            <td>${r.ma_nhan_vien}</td>
            <td>${r.ma_chuyen_biet || ""}</td>
            <td class="fw-semibold">${r.ho_ten}</td>
            <td>${fmtMoney(r.luong_co_ban)}</td>
            <td class="fw-bold text-center">${r.so_su_kien}</td>
            <td class="text-success fw-semibold">+ ${fmtMoney(r.tien_thuong)}</td>
            <td class="text-muted small"><code>${formulaText}</code></td>
            <td class="fw-bold text-danger">${fmtMoney(r.tong_luong)}</td>
        </tr>`;
    })
    .join("");

  document.getElementById("rpQ2BsEvidence").innerHTML = bsEvidence.length
    ? bsEvidence
        .map(
          (e) => `
        <tr><td>#${e.ma_dot}</td><td>${e.ten_benh_nhan}</td><td>${e.ten_benh}</td><td>${e.ngay_ket_thuc}</td><td>#${e.ma_lan_kham_ket_thuc}</td><td class="fw-bold text-teal">${e.ma_bac_si} — ${e.ten_bac_si}</td></tr>
    `,
        )
        .join("")
    : '<tr><td colspan="6" class="text-center text-muted small py-2">Không có dữ liệu căn cứ bác sĩ</td></tr>';

  document.getElementById("rpQ2YtEvidence").innerHTML = ytEvidence.length
    ? ytEvidence
        .map(
          (e) => `
        <tr><td>#${e.ma_ho_tro}</td><td>#${e.ma_lan_kham}</td><td class="fw-bold text-success">${e.ten_y_ta} (#${e.ma_y_ta})</td><td>${e.vai_tro}</td><td>${e.thoi_diem}</td></tr>
    `,
        )
        .join("")
    : '<tr><td colspan="5" class="text-center text-muted small py-2">Không có dữ liệu căn cứ y tá</td></tr>';

  // D. Báo cáo doanh thu
  document.getElementById("rpQ4Exam").innerText = fmtMoney(
    data.q4_summary.doanh_thu_kham_chua,
  );
  document.getElementById("rpQ4Med").innerText = fmtMoney(
    data.q4_summary.doanh_thu_thuoc,
  );
  document.getElementById("rpQ4Total").innerText = fmtMoney(
    data.q4_summary.tong_doanh_thu,
  );

  document.getElementById("rpQ4ExamLines").innerHTML = data.q4_exam_lines
    .map(
      (l) => `
        <tr><td>#${l.ma_lan_kham}</td><td>${l.thoi_diem_vao}</td><td>${l.ten_benh_nhan}</td><td>${l.ten_benh} (#${l.ma_dot})</td><td class="fw-bold">${fmtMoney(l.phi_kham_chua)}</td></tr>
    `,
    )
    .join("");

  document.getElementById("rpQ4MedLines").innerHTML = data.q4_med_lines
    .map(
      (l) => `
        <tr><td>#${l.ma_don}</td><td>${l.thoi_diem_cap}</td><td>${l.ten_thuoc}</td><td>${l.so_luong} × ${fmtMoney(l.don_gia_tai_thoi_diem)}</td><td class="fw-bold">${fmtMoney(l.thanh_tien)}</td></tr>
    `,
    )
    .join("");
}

function openQ1Evidence(ma_benh, ten_benh) {
  const list = globalQ1Evidence.filter((x) => x.ma_benh === ma_benh);
  document.getElementById("q1ModalTitle").innerText =
    `Danh sách Bệnh nhân căn cứ — Bệnh: ${ten_benh}`;
  document.getElementById("q1ModalBody").innerHTML = list
    .map(
      (item) => `
        <tr>
            <td class="fw-bold text-teal">${item.ma_benh_nhan}</td>
            <td class="fw-semibold">${item.ho_ten}</td>
            <td>Đợt #${item.ma_dot}</td>
            <td>${item.ngay_bat_dau}</td>
            <td class="text-center">${item.so_luot_trong_thang} lượt</td>
            <td><span class="badge ${item.trang_thai === "KHOI" ? "bg-success" : "bg-warning text-dark"}">${item.trang_thai}</span></td>
            <td>
                <button class="btn btn-sm btn-teal py-0" onclick="bootstrap.Modal.getInstance(document.getElementById('q1EvidenceModal')).hide(); switchScreenById('screen-2'); setTimeout(()=>viewPatientDetail(${item.ma_nguoi}), 250);">
                    Xem hồ sơ BN
                </button>
            </td>
        </tr>
    `,
    )
    .join("");
  new bootstrap.Modal(document.getElementById("q1EvidenceModal")).show();
}

async function resetSqliteData() {
  if (!confirm("Khôi phục toàn bộ dữ liệu mẫu gốc tháng 10/2026 trên SQLite?"))
    return;
  const res = await fetch("/api/reset-sqlite", { method: "POST" });
  const data = await res.json();
  if (!res.ok) return showAlert(data.error, "danger");
  showAlert(data.message);
  loadOverview();
}
