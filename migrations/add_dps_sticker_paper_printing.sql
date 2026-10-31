-- Add the DPS sticker paper service if it is not already present.
INSERT INTO printshops_services (printshop_id, name, category, description, is_active) SELECT shop.id, 'Sticker paper printing', 'service', 'A4 sticker paper printing. No finish.', 1 FROM printshops AS shop WHERE shop.name = 'Dan''s Printing Services' AND NOT EXISTS (SELECT 1 FROM printshops_services AS existing WHERE existing.printshop_id = shop.id AND LOWER(existing.name) = 'sticker paper printing');
-- Keep the description current if the service already existed.
UPDATE printshops_services AS service JOIN printshops AS shop ON shop.id = service.printshop_id SET service.description = 'A4 sticker paper printing. No finish.' WHERE shop.name = 'Dan''s Printing Services' AND LOWER(service.name) = 'sticker paper printing';
