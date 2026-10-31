-- Update the two DPS service descriptions.
UPDATE printshops_services AS service JOIN printshops AS shop ON shop.id = service.printshop_id SET service.description = 'Regular print on regular bondpaper.' WHERE shop.name = 'Dan''s Printing Services' AND service.name = 'Document printing';
UPDATE printshops_services AS service JOIN printshops AS shop ON shop.id = service.printshop_id SET service.description = 'Prints on photo paper.' WHERE shop.name = 'Dan''s Printing Services' AND service.name = 'Photo printing';
-- Add ID picture only if DPS does not already have it.
INSERT INTO printshops_services (printshop_id, name, category, description, is_active) SELECT shop.id, 'ID picture', 'service', 'Prints on photo paper.', 1 FROM printshops AS shop WHERE shop.name = 'Dan''s Printing Services' AND NOT EXISTS (SELECT 1 FROM printshops_services AS existing WHERE existing.printshop_id = shop.id AND LOWER(existing.name) = 'id picture');
