document.addEventListener('DOMContentLoaded', () => {
    const modal = document.getElementById('printshop-details-modal');
    if (!modal) return;

    const get = (id) => modal.querySelector(`#${id}`);
    const requestButton = get('printshop-request-button');
    const requestNote = get('printshop-request-note');

    requestButton.addEventListener('click', () => {
        const shopName = get('printshop-modal-name').textContent;
        requestNote.textContent = `The request form and customization options for ${shopName} are coming soon.`;
        requestNote.classList.remove('d-none');
    });

    function setContact(rowId, linkId, value, scheme) {
        const row = get(rowId);
        const link = get(linkId);
        if (!value) {
            row.classList.add('d-none');
            return false;
        }

        if (scheme === 'mailto') {
            link.textContent = value;
            link.setAttribute('aria-label', `Send email to ${value}`);
        } else {
            link.textContent = value;
            link.setAttribute('aria-label', `Call ${value}`);
        }
        link.href = `${scheme}:${value}`;
        row.classList.remove('d-none');
        return true;
    }

    modal.addEventListener('show.bs.modal', (event) => {
        requestNote.textContent = '';
        requestNote.classList.add('d-none');
        const card = event.relatedTarget;
        if (!card) return;

        const name = card.dataset.shopName || 'Printshop';
        get('printshop-modal-name').textContent = name;
        get('printshop-modal-location').textContent = card.dataset.location || 'Location not added yet';
        get('printshop-modal-description').textContent =
            card.dataset.description || 'This printshop has not added a description yet.';

        const logo = get('printshop-modal-logo');
        const initial = get('printshop-modal-initial');
        if (card.dataset.logoUrl) {
            logo.src = card.dataset.logoUrl;
            logo.alt = `${name} logo`;
            logo.classList.remove('d-none');
            initial.classList.add('d-none');
        } else {
            logo.removeAttribute('src');
            logo.alt = '';
            logo.classList.add('d-none');
            initial.textContent = name.trim().charAt(0).toUpperCase() || 'P';
            initial.classList.remove('d-none');
        }

        const serviceList = get('printshop-modal-services');
        serviceList.replaceChildren();
        let services = [];
        try {
            services = JSON.parse(card.dataset.services || '[]');
        } catch (error) {
            services = [];
        }

        if (services.length === 0) {
            const emptyItem = document.createElement('li');
            emptyItem.className = 'text-secondary';
            emptyItem.textContent = 'No services or products have been listed yet.';
            serviceList.append(emptyItem);
        } else {
            services.forEach((service) => {
                const item = document.createElement('li');
                const title = document.createElement('strong');
                title.textContent = service.name;
                item.append(title);

                if (service.description) {
                    const description = document.createElement('small');
                    description.textContent = service.description;
                    item.append(description);
                }
                serviceList.append(item);
            });
        }

        const hasPhone = setContact(
            'printshop-phone-row', 'printshop-modal-phone', card.dataset.contactPhone, 'tel'
        );
        const hasEmail = setContact(
            'printshop-email-row', 'printshop-modal-email', card.dataset.contactEmail, 'mailto'
        );

        const websiteRow = get('printshop-website-row');
        const websiteLink = get('printshop-modal-website');
        const rawWebsite = card.dataset.website || '';
        let websiteUrl = null;
        if (rawWebsite) {
            try {
                websiteUrl = new URL(/^https?:\/\//i.test(rawWebsite) ? rawWebsite : `https://${rawWebsite}`);
                if (!['http:', 'https:'].includes(websiteUrl.protocol)) websiteUrl = null;
            } catch (error) {
                websiteUrl = null;
            }
        }
        if (websiteUrl) {
            const isFacebook = ['facebook.com', 'www.facebook.com', 'm.facebook.com']
                .includes(websiteUrl.hostname.toLowerCase());
            websiteLink.textContent = isFacebook ? 'Facebook Profile' : 'Visit website';
            websiteLink.setAttribute('aria-label', `${websiteLink.textContent} (${websiteUrl.hostname})`);
            websiteLink.href = websiteUrl.href;
            websiteRow.classList.remove('d-none');
        } else {
            websiteLink.removeAttribute('href');
            websiteLink.removeAttribute('aria-label');
            websiteRow.classList.add('d-none');
        }

        const hours = card.dataset.businessHours || '';
        get('printshop-modal-hours').textContent = hours;
        get('printshop-hours-row').classList.toggle('d-none', !hours);
        get('printshop-modal-no-contact').classList.toggle(
            'd-none', hasPhone || hasEmail || Boolean(websiteUrl) || Boolean(hours)
        );
    });
});
