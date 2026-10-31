ALTER TABLE print_requests ADD COLUMN file_paths JSON NULL AFTER selected_options;
UPDATE print_requests SET file_paths = JSON_ARRAY(file_path) WHERE file_path IS NOT NULL AND file_path <> '';
UPDATE print_requests SET file_paths = JSON_ARRAY() WHERE file_paths IS NULL;
ALTER TABLE print_requests MODIFY file_paths JSON NOT NULL;
