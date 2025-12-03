const modal = document.getElementById('modal');
const openButtons = [document.getElementById('open-create'), document.getElementById('empty-create')];
const closeButtons = [document.getElementById('close-modal'), document.getElementById('cancel')];
const form = document.getElementById('record-form');
const recordIdInput = document.getElementById('record-id');
const dateInput = document.getElementById('date');
const siteInput = document.getElementById('site');
const mixInput = document.getElementById('mix');
const volumeInput = document.getElementById('volume');
const statusInput = document.getElementById('status');
const notesInput = document.getElementById('notes');
const modalTitle = document.getElementById('modal-title');
const modalSubtitle = document.getElementById('modal-subtitle');
const modalLabel = document.getElementById('modal-label');
const submitBtn = document.getElementById('submit-btn');
const tableBody = document.getElementById('records-body');
const totalVolumeEl = document.getElementById('total-volume');
const totalCountEl = document.getElementById('total-count');
const emptyState = document.getElementById('empty-state');

function openModal(editing = false, record = null) {
  modal.classList.remove('hidden');
  modal.classList.add('flex');
  if (editing && record) {
    modalTitle.textContent = 'Edit entry';
    modalSubtitle.textContent = 'Update the pour details and save changes.';
    modalLabel.textContent = 'Update';
    submitBtn.textContent = 'Save changes';
    recordIdInput.value = record.id;
    dateInput.value = record.date;
    siteInput.value = record.site;
    mixInput.value = record.mix;
    volumeInput.value = record.volume;
    statusInput.value = record.status;
    notesInput.value = record.notes || '';
  } else {
    modalTitle.textContent = 'Add pour';
    modalSubtitle.textContent = 'Enter date, destination, and mix.';
    modalLabel.textContent = 'New entry';
    submitBtn.textContent = 'Save entry';
    recordIdInput.value = '';
    form.reset();
    statusInput.value = 'Scheduled';
  }
}

function closeModal() {
  modal.classList.add('hidden');
  modal.classList.remove('flex');
}

openButtons.forEach((btn) => btn?.addEventListener('click', () => openModal(false)));
closeButtons.forEach((btn) => btn?.addEventListener('click', closeModal));
modal.addEventListener('click', (event) => {
  if (event.target === modal) {
    closeModal();
  }
});

aSyncSafe(loadRecords);

function aSyncSafe(fn) {
  document.addEventListener('DOMContentLoaded', fn);
}

async function loadRecords() {
  const response = await fetch('/api/records');
  const data = await response.json();
  const items = data.items || [];
  tableBody.innerHTML = '';
  if (!items.length) {
    emptyState.classList.remove('hidden');
  } else {
    emptyState.classList.add('hidden');
  }

  let totalVolume = 0;
  items.forEach((record) => {
    totalVolume += Number(record.volume || 0);
    const row = document.createElement('tr');
    row.innerHTML = `
      <td class="px-4 py-3 font-semibold text-slate-900" data-label="Date">${record.date}</td>
      <td class="px-4 py-3 text-slate-700" data-label="Site">${record.site}</td>
      <td class="px-4 py-3 text-slate-700" data-label="Mix">${record.mix}</td>
      <td class="px-4 py-3 text-slate-700" data-label="Volume">${Number(record.volume).toFixed(1)} m³</td>
      <td class="px-4 py-3" data-label="Status">${renderStatus(record.status)}</td>
      <td class="px-4 py-3 text-slate-600" data-label="Notes">${record.notes || ''}</td>
      <td class="px-4 py-3 text-right flex items-center gap-2 justify-end" data-label="Actions">
        <button class="table-action table-action-edit" data-action="edit" data-id="${record.id}">Edit</button>
        <button class="table-action table-action-delete" data-action="delete" data-id="${record.id}">Delete</button>
      </td>
    `;
    tableBody.appendChild(row);
  });

  totalVolumeEl.textContent = totalVolume.toFixed(1);
  totalCountEl.textContent = items.length;
}

function renderStatus(status) {
  const normalized = (status || '').toLowerCase();
  const badgeClass = {
    scheduled: 'badge badge-scheduled',
    completed: 'badge badge-completed',
    delayed: 'badge badge-delayed',
    cancelled: 'badge badge-cancelled',
  }[normalized] || 'badge badge-scheduled';
  return `<span class="${badgeClass}">
    <span class="h-2 w-2 rounded-full" style="background:${dotColor(normalized)}"></span>
    ${status || 'Scheduled'}
  </span>`;
}

function dotColor(status) {
  switch (status) {
    case 'completed':
      return '#10b981';
    case 'delayed':
      return '#f59e0b';
    case 'cancelled':
      return '#f43f5e';
    default:
      return '#3b82f6';
  }
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const payload = {
    date: dateInput.value,
    site: siteInput.value,
    mix: mixInput.value,
    volume: volumeInput.value,
    status: statusInput.value,
    notes: notesInput.value,
  };

  const recordId = recordIdInput.value;
  if (recordId) {
    await fetch(`/api/records/${recordId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  } else {
    await fetch('/api/records', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  }

  closeModal();
  await loadRecords();
});

tableBody.addEventListener('click', async (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;
  const action = target.dataset.action;
  const id = target.dataset.id;
  if (!action || !id) return;

  if (action === 'edit') {
    const record = await fetchRecord(id);
    if (record) {
      openModal(true, record);
    }
  }

  if (action === 'delete') {
    const confirmed = window.confirm('Delete this entry?');
    if (!confirmed) return;
    await fetch(`/api/records/${id}`, { method: 'DELETE' });
    await loadRecords();
  }
});

async function fetchRecord(id) {
  const response = await fetch('/api/records');
  const data = await response.json();
  const items = data.items || [];
  return items.find((item) => String(item.id) === String(id));
}
