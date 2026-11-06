// Wait for the request form to exist before connecting its service picker.
document.addEventListener('DOMContentLoaded', () => {
    const serviceSelect = document.getElementById('request-service');
    const description = document.getElementById('request-service-description');
    const optionsContainer = document.getElementById('request-custom-options');
    const optionsData = document.getElementById('request-service-options');
    const previousOptionsData = document.getElementById('request-selected-options');
    const filesInput = document.getElementById('request-files');
    const quantityLabel = document.querySelector('label[for="request-quantity"]');

    if (!serviceSelect || !description || !optionsContainer || !optionsData) return;

    // Browsers replace an input's FileList when another selection is made.
    // Keep a combined list so each file-picker selection adds to the previous ones.
    if (filesInput) {
        let accumulatedFiles = Array.from(filesInput.files);
        const fileList = document.getElementById('request-file-list');
        let previewUrls = [];

        function updateFileInput() {
            const combinedFiles = new DataTransfer();
            accumulatedFiles.forEach((file) => combinedFiles.items.add(file));
            filesInput.files = combinedFiles.files;
        }

        function formatFileSize(bytes) {
            if (bytes < 1024) {
                return `${bytes} B`;
            }
            if (bytes < 1024 * 1024) {
                return `${Math.max(1, Math.round(bytes / 1024))} KB`;
            }
            return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
        }

        function renderFileList() {
            if (!fileList) return;

            previewUrls.forEach((url) => URL.revokeObjectURL(url));
            previewUrls = [];
            fileList.replaceChildren();

            if (accumulatedFiles.length === 0) {
                fileList.textContent = 'No files selected yet.';
                fileList.classList.add('is-empty');
                return;
            }

            fileList.classList.remove('is-empty');
            const heading = document.createElement('p');
            heading.className = 'request-file-list-heading';
            heading.textContent = `${accumulatedFiles.length} file${accumulatedFiles.length === 1 ? '' : 's'} selected`;
            fileList.append(heading);

            const list = document.createElement('ul');
            list.className = 'request-file-items';

            accumulatedFiles.forEach((file, index) => {
                const item = document.createElement('li');
                item.className = 'request-file-item';

                const details = document.createElement('div');
                details.className = 'request-file-details';

                const fileInfo = document.createElement('div');
                fileInfo.className = 'request-file-info';

                const name = document.createElement('span');
                name.className = 'request-file-name';
                name.textContent = file.name;

                const size = document.createElement('span');
                size.className = 'request-file-size';
                size.textContent = formatFileSize(file.size);
                fileInfo.append(name, size);

                const previewUrl = URL.createObjectURL(file);
                previewUrls.push(previewUrl);

                const viewLink = document.createElement('a');
                viewLink.className = 'request-file-view';
                viewLink.href = previewUrl;
                viewLink.target = '_blank';
                viewLink.rel = 'noopener';
                viewLink.textContent = 'View';
                viewLink.setAttribute('aria-label', `View ${file.name} in a new tab`);

                const removeButton = document.createElement('button');
                removeButton.className = 'request-file-remove';
                removeButton.type = 'button';
                removeButton.textContent = 'Remove';
                removeButton.setAttribute('aria-label', `Remove ${file.name}`);
                removeButton.addEventListener('click', () => {
                    accumulatedFiles = accumulatedFiles.filter((selectedFile, fileIndex) => fileIndex !== index);
                    updateFileInput();
                    renderFileList();
                });

                details.append(fileInfo, viewLink, removeButton);

                if (file.type.startsWith('image/')) {
                    const imagePreview = document.createElement('img');
                    imagePreview.className = 'request-file-preview';
                    imagePreview.src = previewUrl;
                    imagePreview.alt = `Preview of ${file.name}`;
                    item.append(imagePreview);
                }

                item.append(details);
                list.append(item);
            });

            fileList.append(list);
        }

        filesInput.addEventListener('change', () => {
            const knownFiles = new Set(
                accumulatedFiles.map((file) => `${file.name}:${file.size}:${file.lastModified}`)
            );

            Array.from(filesInput.files).forEach((file) => {
                const fileKey = `${file.name}:${file.size}:${file.lastModified}`;
                if (!knownFiles.has(fileKey)) {
                    accumulatedFiles.push(file);
                    knownFiles.add(fileKey);
                }
            });

            updateFileInput();
            renderFileList();
        });

        renderFileList();
    }

    // These JSON objects come from the printshop's service records.
    let serviceOptions = {};
    let previousOptions = {};
    try {
        serviceOptions = JSON.parse(optionsData.textContent || '{}');
        previousOptions = JSON.parse(previousOptionsData?.textContent || '{}');
    } catch (error) {
        serviceOptions = {};
        previousOptions = {};
    }

    function renderServiceOptions() {
        const config = serviceOptions[serviceSelect.value] || {};
        const fields = Array.isArray(config.fields) ? config.fields : [];

        description.textContent = config.description || '';
        if (quantityLabel) quantityLabel.textContent = config.quantity_label || 'Quantity';
        optionsContainer.replaceChildren();

        // Create only the customization controls configured for the chosen service.
        fields.forEach((field, index) => {
            if (!field || typeof field.key !== 'string' || !field.key.replaceAll('_', '').match(/^[a-zA-Z0-9]+$/)) {
                return;
            }

            const wrapper = document.createElement('div');
            wrapper.className = 'request-form-field';

            const label = document.createElement('label');
            const inputId = `request-option-${index}`;
            label.htmlFor = inputId;
            label.textContent = field.label || 'Additional option';

            const optional = !field.required;
            if (optional) {
                const note = document.createElement('span');
                note.className = 'request-optional';
                note.textContent = ' (Optional)';
                label.append(note);
            }

            let input;
            if (field.type === 'select') {
                input = document.createElement('select');
                input.className = 'form-select';

                const placeholder = document.createElement('option');
                placeholder.value = '';
                placeholder.textContent = 'Choose an option';
                input.append(placeholder);

                (Array.isArray(field.choices) ? field.choices : []).forEach((choice) => {
                    const option = document.createElement('option');
                    if (typeof choice === 'string') {
                        option.value = choice;
                        option.textContent = choice;
                    } else if (choice && typeof choice === 'object') {
                        option.value = choice.value || '';
                        option.textContent = choice.label || choice.value || '';
                    }
                    input.append(option);
                });
            } else {
                input = document.createElement('input');
                input.className = 'form-control';
                input.type = ['number', 'text'].includes(field.type) ? field.type : 'text';
                if (input.type === 'number' && field.min !== undefined) {
                    input.min = String(field.min);
                }
                if (input.type === 'number' && field.max !== undefined) {
                    input.max = String(field.max);
                }
                if (field.placeholder) {
                    input.placeholder = field.placeholder;
                }
            }

            input.id = inputId;
            input.name = `option_${field.key}`;
            input.required = Boolean(field.required);
            input.value = previousOptions[field.key] || '';
            wrapper.append(label, input);

            if (field.help) {
                const help = document.createElement('small');
                help.className = 'request-field-help';
                help.textContent = field.help;
                wrapper.append(help);
            }

            optionsContainer.append(wrapper);
        });
    }

    serviceSelect.addEventListener('change', () => {
        // Old values belong to the previously selected service; don't carry them over.
        previousOptions = {};
        renderServiceOptions();
    });

    renderServiceOptions();
});
