// Open a customer's request row in a modal without hiding the row actions.
document.addEventListener('DOMContentLoaded', () => {
    const dataElement = document.getElementById('customer-request-data');
    const modalElement = document.getElementById('customer-request-modal');
    const rows = document.querySelectorAll('.customer-request-row');
    if (!dataElement || !modalElement || !rows.length) return;

    let requests = [];
    try {
        requests = JSON.parse(dataElement.textContent || '[]');
    } catch (error) {
        requests = [];
    }

    const byId = (id) => document.getElementById(id);
    const modal = bootstrap.Modal.getOrCreateInstance(modalElement);

    function openRequestDetails(row) {
        const selectedRequest = requests.find(
            (item) => String(item.id) === row.dataset.requestId
        );
        if (!selectedRequest) return;

        byId('customer-request-modal-title').textContent = selectedRequest.service;
        byId('customer-request-modal-shop').textContent = selectedRequest.shop;
        byId('customer-modal-request-id').textContent = `#${selectedRequest.id}`;
        byId('customer-modal-submitted').textContent = selectedRequest.submitted;
        byId('customer-modal-quantity').textContent = String(selectedRequest.quantity);
        byId('customer-modal-file-count').textContent = String(selectedRequest.files.length);

        const optionList = byId('customer-modal-options');
        optionList.replaceChildren();
        const optionEntries = Object.entries(selectedRequest.options || {}).filter(
            ([, value]) => value !== null && value !== undefined && value !== ''
        );

        if (!optionEntries.length) {
            const noOptions = document.createElement('p');
            noOptions.className = 'text-secondary mb-0';
            noOptions.textContent = 'No specifications were added.';
            optionList.append(noOptions);
        } else {
            optionEntries.forEach(([key, value]) => {
                const item = document.createElement('div');
                const label = document.createElement('dt');
                const detail = document.createElement('dd');
                label.textContent = key.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
                detail.textContent = String(value);
                item.append(label, detail);
                optionList.append(item);
            });
        }

        const notesSection = byId('customer-modal-notes-section');
        notesSection.hidden = !selectedRequest.notes;
        byId('customer-modal-notes').textContent = selectedRequest.notes || '';

        const fileList = byId('customer-modal-files');
        fileList.replaceChildren();
        if (!selectedRequest.files.length) {
            const noFiles = document.createElement('p');
            noFiles.className = 'text-secondary mb-0';
            noFiles.textContent = 'No files were uploaded.';
            fileList.append(noFiles);
        } else {
            selectedRequest.files.forEach((file) => {
                const link = document.createElement('a');
                link.className = 'customer-modal-file-link';
                link.href = file.url;
                link.target = '_blank';
                link.rel = 'noopener';
                link.textContent = file.name;
                fileList.append(link);
            });
        }

        modal.show();
    }

    rows.forEach((row) => {
        row.addEventListener('click', (event) => {
            if (event.target.closest('a, button, form, input')) return;
            openRequestDetails(row);
        });

        row.addEventListener('keydown', (event) => {
            if (event.key !== 'Enter' && event.key !== ' ') return;
            if (event.target.closest('a, button, form, input')) return;
            event.preventDefault();
            openRequestDetails(row);
        });
    });
});
