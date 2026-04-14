// ── Toast ─────────────────────────────────────────────────────────────────
function showToast(message, type = 'success') {
  const toast = document.getElementById('toast');
  toast.textContent = message;
  toast.className = `toast ${type}`;
  setTimeout(() => toast.classList.add('show'), 10);
  setTimeout(() => toast.classList.remove('show'), 3200);
}

// ── Modal helpers ──────────────────────────────────────────────────────────
function openModal(id) {
  document.getElementById(id).classList.add('open');
}
function closeModal(id) {
  document.getElementById(id).classList.remove('open');
  const form = document.getElementById('expense-form');
  if (form) form.reset();
  const editId = document.getElementById('editing-id');
  if (editId) editId.value = '';
  const modalTitle = document.getElementById('modal-title');
  if (modalTitle) modalTitle.textContent = 'Add Expense';
}

// Close on overlay click
document.querySelectorAll('.modal-overlay').forEach(overlay => {
  overlay.addEventListener('click', e => {
    if (e.target === overlay) closeModal(overlay.id);
  });
});

// ── Add expense ────────────────────────────────────────────────────────────
const addBtn = document.getElementById('add-expense-btn');
if (addBtn) {
  addBtn.addEventListener('click', () => {
    document.getElementById('modal-title').textContent = 'Add Expense';
    document.getElementById('editing-id').value = '';
    document.getElementById('expense-date').value = new Date().toISOString().split('T')[0];
    openModal('expense-modal');
  });
}

// ── Edit expense ───────────────────────────────────────────────────────────
document.querySelectorAll('.edit-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.getElementById('editing-id').value            = btn.dataset.id;
    document.getElementById('modal-title').textContent     = 'Edit Expense';
    document.getElementById('expense-amount').value        = btn.dataset.amount;
    document.getElementById('expense-date').value          = btn.dataset.date;
    document.getElementById('expense-category').value      = btn.dataset.category;
    document.getElementById('expense-description').value   = btn.dataset.description;
    openModal('expense-modal');
  });
});

// ── Save (add or edit) ─────────────────────────────────────────────────────
const saveBtn = document.getElementById('save-expense-btn');
if (saveBtn) {
  saveBtn.addEventListener('click', async () => {
    const id      = document.getElementById('editing-id').value;
    const payload = {
      amount:      document.getElementById('expense-amount').value,
      date:        document.getElementById('expense-date').value,
      category:    document.getElementById('expense-category').value,
      description: document.getElementById('expense-description').value,
    };
    const url    = id ? `/api/expense/${id}` : '/api/expense';
    const method = id ? 'PUT' : 'POST';
    try {
      const res  = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (data.success) {
        showToast(id ? 'Expense updated.' : 'Expense added.', 'success');
        closeModal('expense-modal');
        setTimeout(() => location.reload(), 600);
      } else {
        showToast(data.message || 'Something went wrong.', 'error');
      }
    } catch {
      showToast('Network error. Please try again.', 'error');
    }
  });
}

// ── Delete expense ─────────────────────────────────────────────────────────
let pendingDeleteId = null;

document.querySelectorAll('.delete-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    pendingDeleteId = btn.dataset.id;
    openModal('confirm-modal');
  });
});

const confirmDeleteBtn = document.getElementById('confirm-delete-btn');
if (confirmDeleteBtn) {
  confirmDeleteBtn.addEventListener('click', async () => {
    if (!pendingDeleteId) return;
    try {
      const res  = await fetch(`/api/expense/${pendingDeleteId}`, { method: 'DELETE' });
      const data = await res.json();
      if (data.success) {
        showToast('Expense deleted.', 'success');
        closeModal('confirm-modal');
        pendingDeleteId = null;
        setTimeout(() => location.reload(), 600);
      } else {
        showToast(data.message || 'Could not delete.', 'error');
      }
    } catch {
      showToast('Network error.', 'error');
    }
  });
}
