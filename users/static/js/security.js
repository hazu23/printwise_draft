// Shared confirmation behavior keeps JavaScript out of HTML attributes.
document.addEventListener('DOMContentLoaded', () => {
    const opening = document.querySelector('input[name="opening_time"]');
    const closing = document.querySelector('input[name="closing_time"]');
    const validateHours = () => {
        if (!opening || !closing) return;
        const message = Boolean(opening.value) === Boolean(closing.value)
            ? '' : 'Enter both the opening and closing time.';
        opening.setCustomValidity(message);
        closing.setCustomValidity(message);
    };
    opening?.addEventListener('input', validateHours);
    closing?.addEventListener('input', validateHours);
    validateHours();

    document.querySelectorAll('form[data-confirm]').forEach((form) => {
        form.addEventListener('submit', (event) => {
            if (!window.confirm(form.dataset.confirm || 'Continue?')) event.preventDefault();
        });
    });
    document.querySelectorAll('button[data-confirm]').forEach((button) => {
        button.addEventListener('click', (event) => {
            if (!window.confirm(button.dataset.confirm || 'Continue?')) event.preventDefault();
        });
    });
});
