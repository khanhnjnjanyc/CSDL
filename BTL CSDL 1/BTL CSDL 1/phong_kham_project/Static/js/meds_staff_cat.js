// MÀN HÌNH 5: ĐƠN THUỐC
function addPrescriptionRow() {
  const tbody = document.getElementById("prLinesBody");
  const opts = globalCatalog.medicines
    .map(
      (m) =>
        `<option value="${m.ma_thuoc}" data-price="${m.don_gia_hien_tai}">${m.ten_thuoc} (${m.don_vi}) — Tồn: ${m.ton_kho} — Giá: ${m.don_gia_hien_tai}đ</option>`,
    )
    .join("");
  const firstPrice = globalCatalog.medicines.length
    ? globalCatalog.medicines[0].don_gia_hien_tai
    : 5000;
  const tr = document.createElement("tr");
  tr.innerHTML = `
        <td><select class="form-select form-select-sm pr-med" onchange="onMedChange(this)">${opts}</select></td>
        <td><input type="number" class="form-control form-control-sm pr-qty" value="10" min="1" oninput="calcPrTotal()"></td>
        <td><input type="number" class="form-control form-control-sm pr-price" value="${firstPrice}" min="0" oninput="calcPrTotal()"></td>
        <td><input type="text" class="form-control form-control-sm pr-guide" value="Uống sau ăn"></td>
        <td><button type="button" class="btn btn-sm btn-outline-danger" onclick="this.closest('tr').remove(); calcPrTotal();"><i class="bi bi-x"></i></button></td>
    `;
  tbody.appendChild(tr);
  calcPrTotal();
}

function onMedChange(sel) {
  const price = sel.options[sel.selectedIndex].getAttribute("data-price");
  sel.closest("tr").querySelector(".pr-price").value = price;
  calcPrTotal();
}

function calcPrTotal() {
  let total = 0;
  document.querySelectorAll("#prLinesBody tr").forEach((tr) => {
    const q = Number(tr.querySelector(".pr-qty").value || 0);
    const p = Number(tr.querySelector(".pr-price").value || 0);
    total += q * p;
  });
  document.getElementById("prTempTotal").innerText =
    total.toLocaleString("vi-VN");
}

async function loadPrescriptions() {
  await loadVisits();
  if (document.querySelectorAll("#prLinesBody tr").length === 0)
    addPrescriptionRow();
  const res = await fetch("/api/prescriptions");
  const dons = await res.json();
  document.getElementById("prTableBody").innerHTML = dons
    .map(
      (d) => `
        <tr id="pr-row-${d.ma_don}">
            <td class="fw-bold text-teal">#${d.ma_don}</td>
            <td><a href="javascript:void(0)" onclick="jumpToRecord('screen-3', 'vs-row', ${d.ma_lan_kham})">Lượt #${d.ma_lan_kham}</a><br><b>${d.ma_benh_nhan}</b> — ${d.ten_benh_nhan}</td>
            <td>${d.ngay_ke}</td>
            <td>
                <span class="badge ${d.trang_thai === "DA_CAP" ? "bg-success" : d.trang_thai === "HUY" ? "bg-danger" : "bg-secondary"}">${d.trang_thai}</span>
                ${d.thoi_diem_cap ? `<div class="small text-muted">${d.thoi_diem_cap}</div>` : ""}
            </td>
            <td>
                ${d.chi_tiet.map((ct) => `<div class="small">• <b>${ct.ten_thuoc}</b>: ${ct.so_luong} ${ct.don_vi} × ${fmtMoney(ct.don_gia_tai_thoi_diem)} = <b>${fmtMoney(ct.thanh_tien)}</b> (${ct.huong_dan_dung})</div>`).join("")}
            </td>
            <td class="fw-bold text-danger">${fmtMoney(d.tong_tien)}</td>
            <td>
                ${d.trang_thai !== "DA_CAP" ? `<button class="btn btn-sm btn-teal py-0" onclick="changePrStatus(${d.ma_don}, 'DA_CAP')">Xác nhận cấp thuốc</button>` : '<span class="small text-muted">Đã chốt</span>'}
            </td>
        </tr>
    `,
    )
    .join("");
}

async function submitPrescription() {
  const items = [];
  document.querySelectorAll("#prLinesBody tr").forEach((tr) => {
    items.push({
      ma_thuoc: tr.querySelector(".pr-med").value,
      so_luong: tr.querySelector(".pr-qty").value,
      don_gia_tai_thoi_diem: tr.querySelector(".pr-price").value,
      huong_dan_dung: tr.querySelector(".pr-guide").value,
    });
  });
  const res = await fetch("/api/prescriptions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ma_lan_kham: document.getElementById("prVisit").value,
      ngay_ke: document.getElementById("prDate").value,
      trang_thai: document.getElementById("prStatus").value,
      items,
    }),
  });
  const data = await res.json();
  if (!res.ok) return showAlert(data.error, "danger");
  showAlert(data.message);
  document.getElementById("prLinesBody").innerHTML = "";
  loadPrescriptions();
}

async function changePrStatus(ma_don, trang_thai) {
  const res = await fetch(`/api/prescriptions/${ma_don}/status`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      trang_thai,
      thoi_diem_cap: document.getElementById("prDate").value,
    }),
  });
  const data = await res.json();
  if (!res.ok) return showAlert(data.error, "danger");
  showAlert(data.message);
  loadPrescriptions();
}

// MÀN HÌNH 6: NHÂN VIÊN
function toggleStaffFields() {
  const role = document.getElementById("stRole").value;
  document.getElementById("stDocCodeWrap").style.display =
    role === "BAC_SI" ? "block" : "none";
}

async function loadStaff() {
  const res = await fetch("/api/staff");
  const data = await res.json();
  document.getElementById("stDoctorsBody").innerHTML = data.doctors
    .map(
      (d) => `
        <tr><td class="fw-bold text-teal">${d.ma_bac_si}</td><td>${d.ma_nhan_vien}</td><td class="fw-semibold">${d.ho_ten}</td><td>${d.bac_nghe} (${d.trinh_do_dao_tao})</td><td>${d.chuyen_mon || "Đa khoa"}</td><td>${d.tham_nien} năm</td></tr>
    `,
    )
    .join("");
  document.getElementById("stNursesBody").innerHTML = data.nurses
    .map(
      (n) => `
        <tr><td class="fw-bold text-success">#${n.ma_nguoi}</td><td>${n.ma_nhan_vien}</td><td class="fw-semibold">${n.ho_ten}</td><td>${n.trinh_do}</td><td>${n.tham_nien} năm</td></tr>
    `,
    )
    .join("");
}

async function submitStaff(e) {
  e.preventDefault();
  const role = document.getElementById("stRole").value;
  const payload = {
    loai: role,
    ma_nhan_vien: document.getElementById("stEmpCode").value,
    ma_bac_si: document.getElementById("stDocCode").value,
    ho_ten: document.getElementById("stName").value,
    cmt: document.getElementById("stCmt").value,
    ngay_sinh: document.getElementById("stDob").value,
    gioi_tinh: document.getElementById("stGender").value,
    ngay_vao_lam: document.getElementById("stHireDate").value,
    bac_nghe: "Bác sĩ",
    trinh_do_dao_tao: document.getElementById("stLevel").value,
    trinh_do: document.getElementById("stLevel").value,
    tham_nien: document.getElementById("stExp").value,
  };
  const res = await fetch("/api/staff", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (!res.ok) return showAlert(data.error, "danger");
  showAlert(data.message);
  loadStaff();
}

// MÀN HÌNH 8: DANH MỤC
async function loadCatalog() {
  const res = await fetch("/api/catalog");
  globalCatalog = await res.json();
  const isAdmin = document.getElementById("roleSelector").value === "ADMIN";

  document.getElementById("catDiseasesBody").innerHTML = globalCatalog.diseases
    .map(
      (d) => `
        <tr>
            <td>${d.ma_benh}</td>
            <td class="fw-semibold">${d.ten_benh}</td>
            <td>${d.mo_ta || ""}</td>
            ${isAdmin ? `<td><button class="btn btn-sm btn-outline-danger py-0" onclick="deleteDisease(${d.ma_benh})"><i class="bi bi-trash"></i></button></td>` : ""}
        </tr>
    `,
    )
    .join("");

  document.getElementById("catMedicinesBody").innerHTML =
    globalCatalog.medicines
      .map(
        (m) => `
        <tr>
            <td>${m.ma_thuoc}</td>
            <td><input type="text" class="form-control form-control-sm" id="med-name-${m.ma_thuoc}" value="${m.ten_thuoc}" ${!isAdmin ? "disabled" : ""}></td>
            <td><input type="text" class="form-control form-control-sm" id="med-unit-${m.ma_thuoc}" value="${m.don_vi}" ${!isAdmin ? "disabled" : ""}></td>
            <td><input type="number" class="form-control form-control-sm" id="med-price-${m.ma_thuoc}" value="${m.don_gia_hien_tai}" ${!isAdmin ? "disabled" : ""}></td>
            <td><input type="number" class="form-control form-control-sm" id="med-stock-${m.ma_thuoc}" value="${m.ton_kho}" ${!isAdmin ? "disabled" : ""}></td>
            ${
              isAdmin
                ? `
            <td>
                <button class="btn btn-sm btn-teal py-0" onclick="updateMedicine(${m.ma_thuoc})">Lưu</button>
                <button class="btn btn-sm btn-outline-danger py-0" onclick="deleteMedicine(${m.ma_thuoc})"><i class="bi bi-trash"></i></button>
            </td>`
                : ""
            }
        </tr>
    `,
      )
      .join("");
}

async function submitDisease(e) {
  e.preventDefault();
  const res = await fetch("/api/diseases", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ten_benh: document.getElementById("catDiseaseName").value,
      mo_ta: document.getElementById("catDiseaseDesc").value,
    }),
  });
  const data = await res.json();
  showAlert(data.message);
  document.getElementById("catDiseaseName").value = "";
  document.getElementById("catDiseaseDesc").value = "";
  loadCatalog();
}

async function deleteDisease(id) {
  const res = await fetch(`/api/diseases/${id}`, { method: "DELETE" });
  const data = await res.json();
  if (!res.ok) return showAlert(data.error, "danger");
  showAlert(data.message);
  loadCatalog();
}

async function submitMedicine(e) {
  e.preventDefault();
  const res = await fetch("/api/medicines", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ten_thuoc: document.getElementById("catMedName").value,
      don_vi: document.getElementById("catMedUnit").value,
      don_gia_hien_tai: document.getElementById("catMedPrice").value,
      ton_kho: document.getElementById("catMedStock").value,
    }),
  });
  const data = await res.json();
  if (!res.ok) return showAlert(data.error, "danger");
  showAlert(data.message);
  loadCatalog();
}

async function updateMedicine(id) {
  const res = await fetch(`/api/medicines/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ten_thuoc: document.getElementById(`med-name-${id}`).value,
      don_vi: document.getElementById(`med-unit-${id}`).value,
      don_gia_hien_tai: document.getElementById(`med-price-${id}`).value,
      ton_kho: document.getElementById(`med-stock-${id}`).value,
    }),
  });
  const data = await res.json();
  if (!res.ok) return showAlert(data.error, "danger");
  showAlert(data.message);
  loadCatalog();
}

async function deleteMedicine(id) {
  const res = await fetch(`/api/medicines/${id}`, { method: "DELETE" });
  const data = await res.json();
  if (!res.ok) return showAlert(data.error, "danger");
  showAlert(data.message);
  loadCatalog();
}
