// Wait until the page HTML is loaded before looking up modal elements.
document.addEventListener('DOMContentLoaded', () => {
    // This script is shared by the directory page; stop if that page's modal is absent.
    const modal = document.getElementById('printshop-details-modal');
    if (!modal) return;

    // Short helper for finding an element inside this modal by its ID.
    const get = (id) => modal.querySelector(`#${id}`);
    const requestButton = get('printshop-request-button');
    const requestNote = get('printshop-request-note');

    // The request feature is not built yet, so the button displays a clear placeholder message.
    requestButton.addEventListener('click', () => {
        const shopName = get('printshop-modal-name').textContent;
        requestNote.textContent = `The request form and customization options for ${shopName} are coming soon.`;
        requestNote.classList.remove('d-none');
    });

    // Show a phone or email contact row only when that shop has a value for it.
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

    // Bootstrap sends this event when a customer opens a printshop's details modal.
    modal.addEventListener('show.bs.modal', (event) => {
        // Clear the placeholder message each time a different shop is opened.
        requestNote.textContent = '';
        requestNote.classList.add('d-none');

        // The clicked directory card supplies this shop's details in data-* attributes.
        const card = event.relatedTarget;
        if (!card) return;

        // Fill the modal's heading and basic information, with a fallback for missing values.
        const name = card.dataset.shopName || 'Printshop';
        get('printshop-modal-name').textContent = name;
        get('printshop-modal-location').textContent = card.dataset.location || 'Location not added yet';
        get('printshop-modal-description').textContent =
            card.dataset.description || 'This printshop has not added a description yet.';

        const logo = get('printshop-modal-logo');
        const initial = get('printshop-modal-initial');
        // Show the logo when one exists; otherwise use the first letter of the shop name.
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

        // Turn the JSON service list from the card into visible list items in the modal.
        const serviceList = get('printshop-modal-services');
        serviceList.replaceChildren();
        let services = [];
        try {
            services = JSON.parse(card.dataset.services || '[]');
        } catch (error) {
            // If the card data is missing or malformed, display the empty-state message.
            services = [];
        }

        // Build each item with textContent so database text is displayed as text, not HTML.
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

        // Add clickable telephone and email links when those contact details are available.
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
        // Parse the website safely and allow only normal web links (HTTP or HTTPS).
        if (rawWebsite) {
            try {
                websiteUrl = new URL(/^https?:\/\//i.test(rawWebsite) ? rawWebsite : `https://${rawWebsite}`);
                if (!['http:', 'https:'].includes(websiteUrl.protocol)) websiteUrl = null;
            } catch (error) {
                websiteUrl = null;
            }
        }
        if (websiteUrl) {
            // Use a short visible label for Facebook links while keeping the destination clickable.
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

        // Show opening hours and hide the no-contact message if any contact detail exists.
        const hours = card.dataset.businessHours || '';
        get('printshop-modal-hours').textContent = hours;
        get('printshop-hours-row').classList.toggle('d-none', !hours);
        get('printshop-modal-no-contact').classList.toggle(
            'd-none', hasPhone || hasEmail || Boolean(websiteUrl) || Boolean(hours)
        );
    });
});
