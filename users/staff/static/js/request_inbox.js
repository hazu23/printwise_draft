// Wait until the inbox page is ready before connecting its buttons.
document.addEventListener('DOMContentLoaded', () => {
    const dataElement = document.getElementById('request-inbox-data');
    const modal = document.getElementById('request-details-modal');
    const requestList = document.getElementById('request-inbox-list');

    if (!dataElement || !modal || !requestList) return;

    // Flask sends the request details as JSON so the modal can show one request at a time.
    let requests = [];
    try {
        requests = JSON.parse(dataElement.textContent || '[]');
    } catch (error) {
        requests = [];
    }

    // Show only requests that match the selected status filter.
    const filters = document.querySelectorAll('[data-request-filter]');
    const rows = requestList.querySelectorAll('[data-request-status]');

    filters.forEach((filterButton) => {
        filterButton.addEventListener('click', () => {
            const selectedStatus = filterButton.dataset.requestFilter;

            filters.forEach((button) => {
                const isSelected = button === filterButton;
                button.classList.toggle('is-active', isSelected);
                button.setAttribute('aria-pressed', String(isSelected));
            });

            rows.forEach((row) => {
                const shouldShow = selectedStatus === 'all' || row.dataset.requestStatus === selectedStatus;
                row.hidden = !shouldShow;
            });
        });
    });

    const byId = (id) => document.getElementById(id);
    const updateForm = byId('request-update-form');
    const statusSelect = byId('request-status-select');
    const paymentSelect = byId('request-payment-select');
    const priceInput = byId('request-price-input');
    const decisionActions = byId('request-decision-actions');

    // Open the modal with the details for the row the staff member selected.
    modal.addEventListener('show.bs.modal', (event) => {
        const selectedRow = event.relatedTarget;
        if (!selectedRow) return;

        const selectedRequest = requests.find((item) => String(item.id) === selectedRow.dataset.requestId);
        if (!selectedRequest) return;

        byId('request-modal-title').textContent = selectedRequest.service;
        byId('request-modal-id').textContent = `Request #${selectedRequest.id} · ${selectedRequest.shop} · ${selectedRequest.submitted}`;
        byId('request-modal-customer-name').textContent = selectedRequest.customer_name;

        const emailLink = byId('request-modal-customer-email');
        emailLink.textContent = selectedRequest.customer_contact;
        if (selectedRequest.customer_email) {
            emailLink.href = `mailto:${selectedRequest.customer_email}`;
        } else {
            emailLink.removeAttribute('href');
        }

        const statusBadge = byId('request-modal-status');
        statusBadge.className = `request-status-badge status-${selectedRequest.status}`;
        statusBadge.textContent = selectedRequest.status_label;

        // Show the service, quantity, and selected print options as a definition list.
        const optionList = byId('request-modal-options');
        optionList.replaceChildren();
        const printDetails = {
            service: selectedRequest.service,
            quantity: selectedRequest.quantity,
            ...selectedRequest.options,
        };

        Object.entries(printDetails).forEach(([key, value]) => {
            if (value === null || value === undefined || value === '') return;

            const row = document.createElement('div');
            const label = document.createElement('dt');
            const detail = document.createElement('dd');
            label.textContent = key.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
            detail.textContent = String(value);
            row.append(label, detail);
            optionList.append(row);
        });

        const notes = byId('request-modal-notes');
        notes.textContent = selectedRequest.notes || 'No additional instructions.';
        byId('request-modal-notes-section').hidden = !selectedRequest.notes;

        // Show the current amount. One form saves price, request status, and payment status.
        byId('request-modal-price-current').textContent = selectedRequest.price_label;
        priceInput.value = selectedRequest.price;
        updateForm.action = selectedRow.dataset.updateUrl;

        // Display a submitted GCash/Maya receipt for staff verification.
        const receiptSection = byId('request-modal-receipt-section');
        receiptSection.hidden = !selectedRequest.payment_receipt_url;
        byId('request-modal-payment-method').textContent = selectedRequest.payment_method
            ? `Submitted through ${selectedRequest.payment_method}`
            : '';
        byId('request-modal-receipt-link').href = selectedRequest.payment_receipt_url || '#';

        // Only staff-created requests can open the full edit form.
        const editLink = byId('request-modal-edit');
        editLink.hidden = !selectedRequest.is_staff_created;
        editLink.href = selectedRequest.edit_url || '#';

        // Add secure download links that the server checks against this user's shop.
        const fileList = byId('request-modal-files');
        fileList.replaceChildren();
        if (!selectedRequest.files.length) {
            const noFiles = document.createElement('p');
            noFiles.className = 'text-secondary mb-0';
            noFiles.textContent = 'No files were attached.';
            fileList.append(noFiles);
        } else {
            selectedRequest.files.forEach((file) => {
                const link = document.createElement('a');
                link.className = 'request-modal-file-link';
                link.href = file.url;
                link.textContent = file.name;
                link.setAttribute('download', '');
                fileList.append(link);
            });
        }

        statusSelect.value = selectedRequest.status;
        paymentSelect.value = selectedRequest.payment_status;
        decisionActions.hidden = selectedRequest.status !== 'pending';
    });

    // The quick buttons set the matching status and submit the unified form.
    byId('request-accept-button')?.addEventListener('click', () => {
        statusSelect.value = 'accepted';
        updateForm.requestSubmit();
    });

    byId('request-decline-button')?.addEventListener('click', () => {
        statusSelect.value = 'declined';
        updateForm.requestSubmit();
    });

    // Choosing any status other than Pending means the shop has already
    // handled the request, so a separate Accept/Decline choice is unnecessary.
    statusSelect.addEventListener('change', () => {
        decisionActions.hidden = statusSelect.value !== 'pending';
    });
});
